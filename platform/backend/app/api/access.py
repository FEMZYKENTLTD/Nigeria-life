"""Data & Access: collection scopes, API connectors, licensed data assets,
manual evidence capture. All sanctioned paths — the agent never bypasses a
restriction these controls create; it waits for a human decision instead."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import get_settings
from ..db import get_session
from ..engine import data_import, robots
from ..engine.api_connect import sync_connector, validate_connector
from ..engine.ids import new_id
from ..engine.knowledge import upsert_knowledge
from ..engine.page_understanding import analyze_html
from ..models import (ActivityLog, ApiConnector, CollectionScope, DataAsset,
                      Decision, Evidence, PageRecord, Project, ResearchTask,
                      Screenshot, Subtask)
from ..schemas import PageImportIn
from .research import import_page

router = APIRouter(tags=["access"])


async def _require_project(db, project_id: str) -> Project:
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if p is None:
        raise HTTPException(404, "project not found")
    return p


# ---------------------------------------------------------------- collection scope

class ScopeIn(BaseModel):
    domain: str = "*"
    allowed_methods: list[str] = Field(default_factory=lambda: ["http", "manual"])
    min_delay_s: float = 2.0
    max_pages: int = 40
    robots_mode: str = "respect"  # respect | approved_exception (the latter via decision)
    note: str = ""


def _scope_dict(r: CollectionScope) -> dict:
    return {"id": r.id, "domain": r.domain, "allowed_methods": r.allowed_methods,
            "min_delay_s": r.min_delay_s, "max_pages": r.max_pages,
            "robots_mode": r.robots_mode, "note": r.note}


@router.get("/projects/{project_id}/scope")
async def list_scope(project_id: str, db=Depends(get_session)):
    await _require_project(db, project_id)
    rows = (await db.execute(
        select(CollectionScope).where(CollectionScope.project_id == project_id)
    )).scalars().all()
    return [_scope_dict(r) for r in rows]


@router.post("/projects/{project_id}/scope", status_code=201)
async def upsert_scope(project_id: str, body: ScopeIn, db=Depends(get_session)):
    await _require_project(db, project_id)
    bad = [m for m in body.allowed_methods if m not in ("browser", "http", "manual", "api")]
    if bad:
        raise HTTPException(400, f"unknown methods: {bad}")
    if not (0 <= body.min_delay_s <= 300) or not (1 <= body.max_pages <= 500):
        raise HTTPException(400, "min_delay_s must be 0..300 and max_pages 1..500")
    if body.robots_mode not in ("respect", "approved_exception"):
        raise HTTPException(400, "robots_mode must be respect|approved_exception")

    row = (await db.execute(
        select(CollectionScope).where(
            CollectionScope.project_id == project_id,
            CollectionScope.domain == body.domain,
        )
    )).scalars().first()
    created = row is None
    if created:
        row = CollectionScope(id=new_id(), project_id=project_id, domain=body.domain)
        db.add(row)
    row.allowed_methods = body.allowed_methods
    row.min_delay_s = body.min_delay_s
    row.max_pages = body.max_pages
    row.note = body.note

    pending_exception = False
    if body.robots_mode == "approved_exception" and row.robots_mode != "approved_exception":
        # a robots exception is a permission change: human sign-off required
        row.robots_mode = "respect"
        decision = Decision(
            id=new_id(), project_id=project_id, kind="permission_change",
            question=(f"Approve a robots.txt exception for domain '{body.domain}' on project "
                      f"'{project_id[:12]}…'? This authorises automated fetches that robots.txt "
                      "disallows for that domain. Approve only if you have explicit authorisation "
                      "from the site owner."),
            context={"scope_id": row.id, "robots_exception": True, "domain": body.domain},
        )
        db.add(decision)
        pending_exception = True
    else:
        row.robots_mode = body.robots_mode

    db.add(ActivityLog(project_id=project_id, actor="user",
                       action="scope.updated", subject=body.domain,
                       detail=f"methods={body.allowed_methods} delay={body.min_delay_s}s "
                              f"max_pages={body.max_pages} robots={row.robots_mode}"))
    await db.commit()
    return {"scope": _scope_dict(row),
            "robots_exception_pending": pending_exception,
            "created": created}


# ---------------------------------------------------------------- api connectors

class EndpointIn(BaseModel):
    name: str
    path: str
    method: str = "GET"


class ConnectorIn(BaseModel):
    name: str
    base_url: str
    auth_type: str = "none"
    env_var: str = ""
    key_header: str = "X-API-Key"
    endpoints: list[EndpointIn] = Field(default_factory=list)


def _connector_dict(c: ApiConnector) -> dict:
    return {"id": c.id, "name": c.name, "base_url": c.base_url, "auth_type": c.auth_type,
            "env_var": c.env_var, "key_header": c.key_header, "endpoints": c.endpoints,
            "status": c.status, "last_sync_at": c.last_sync_at,
            "last_sync": c.last_sync, "error": c.error}


@router.get("/projects/{project_id}/connectors")
async def list_connectors(project_id: str, db=Depends(get_session)):
    await _require_project(db, project_id)
    rows = (await db.execute(
        select(ApiConnector).where(ApiConnector.project_id == project_id)
    )).scalars().all()
    return [_connector_dict(r) for r in rows]


@router.post("/projects/{project_id}/connectors", status_code=201)
async def create_connector(project_id: str, body: ConnectorIn, db=Depends(get_session)):
    await _require_project(db, project_id)
    eps = [e.model_dump() for e in body.endpoints]
    err = validate_connector(body.name, body.base_url, body.auth_type, body.env_var,
                             body.key_header, eps)
    if err:
        raise HTTPException(400, err)
    c = ApiConnector(id=new_id(), project_id=project_id, name=body.name,
                     base_url=body.base_url, auth_type=body.auth_type,
                     env_var=body.env_var, key_header=body.key_header,
                     endpoints=eps, status="pending_approval")
    db.add(c)
    await db.flush()
    d = Decision(
        id=new_id(), project_id=project_id, kind="new_source",
        question=(f"Approve new API source '{body.name}' at {body.base_url}? The agent will call "
                  f"only its documented endpoints, with your own credentials from env var "
                  f"{body.env_var or '(none — public endpoint)'}. Credentials are never stored or logged."),
        context={"connector_id": c.id, "name": body.name},
    )
    db.add(d)
    db.add(ActivityLog(project_id=project_id, actor="user", action="connector.registered",
                       subject=body.name, detail=body.base_url))
    await db.commit()
    return {"connector": _connector_dict(c), "decision_id": d.id}


@router.post("/projects/{project_id}/connectors/{connector_id}/sync")
async def connector_sync(project_id: str, connector_id: str, db=Depends(get_session)):
    await _require_project(db, project_id)
    c = (await db.execute(
        select(ApiConnector).where(
            ApiConnector.id == connector_id, ApiConnector.project_id == project_id)
    )).scalars().first()
    if c is None:
        raise HTTPException(404, "connector not found")
    result = await sync_connector(connector_id)
    if not result.get("ok"):
        raise HTTPException(502, result.get("error", "sync failed"))
    return result


# ---------------------------------------------------------------- data assets

@router.get("/projects/{project_id}/data-assets")
async def list_data_assets(project_id: str, db=Depends(get_session)):
    await _require_project(db, project_id)
    rows = (await db.execute(
        select(DataAsset).where(DataAsset.project_id == project_id)
        .order_by(DataAsset.imported_at.desc())
    )).scalars().all()
    return [{"id": r.id, "name": r.name, "filename": r.filename, "format": r.format,
             "provenance": r.provenance, "license": r.license, "rows": r.rows,
             "evidence_id": r.evidence_id, "status": r.status, "error": r.error,
             "imported_at": r.imported_at.isoformat() if r.imported_at else ""} for r in rows]


@router.post("/projects/{project_id}/data-assets/import", status_code=201)
async def import_data_asset(
    project_id: str,
    name: str = Form(""),
    provenance: str = Form(""),
    license: str = Form(""),
    evidence_class: str = Form("S"),
    confidence: float = Form(0.6),
    file: UploadFile = File(...),
    db=Depends(get_session),
):
    await _require_project(db, project_id)
    content = await file.read()
    if len(content) > data_import.MAX_FILE_BYTES:
        raise HTTPException(413, "file too large (max 25 MB)")
    result = await data_import.import_dataset(
        project_id, name, file.filename or "upload", content,
        provenance, license, evidence_class, confidence)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "import failed"))
    return result


# ---------------------------------------------------------------- manual captures

class ManualCaptureIn(BaseModel):
    url: str
    title: str = ""
    notes: str = ""
    html: str = ""
    screenshot_b64: str = ""  # data URL or raw base64 PNG


@router.post("/projects/{project_id}/manual-captures", status_code=201)
async def manual_capture(project_id: str, body: ManualCaptureIn, db=Depends(get_session)):
    """Human-captured page (from the extension side panel or a paste-in).
    Recorded as confirmed manual evidence — the human did the collection."""
    await _require_project(db, project_id)
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)")
    analysis = analyze_html(body.html, url=body.url, base_url=body.url) if body.html else None
    title = body.title or (analysis.get("title", "") if analysis else "") or body.url
    text = body.notes or (analysis.get("body_text", "")[:20000] if analysis else "")
    now = datetime.now(timezone.utc)

    existing = (await db.execute(
        select(PageRecord).where(
            PageRecord.project_id == project_id,
            PageRecord.canonical_url == body.url[:700],
        )
    )).scalars().first()
    if existing:
        existing.title = title
        existing.status = "documented"
        existing.body_text = text or existing.body_text
        existing.error = body.notes
        existing.updated_at = now
        page_id = existing.id
    else:
        page = PageRecord(
            id=new_id(), project_id=project_id, url=body.url[:700],
            canonical_url=body.url[:700], title=title[:500], status="documented",
            content_category=(analysis.get("content_category", "") if analysis else ""),
            purpose=(analysis.get("purpose", "") if analysis else body.notes),
            summary=(analysis.get("summary", "") if analysis else text[:500]),
            structure=({k: analysis[k] for k in
                        ("regions", "navigation", "forms", "controls", "interactive", "buttons",
                         "sections", "links", "images", "states", "repeated_components",
                         "element_counts")} if analysis else {}),
            body_text=text[:20000], observed_at=now, capture_method="manual_evidence",
            error="",
        )
        db.add(page)
        await db.flush()
        page_id = page.id

    ev = Evidence(
        id=new_id(), project_id=project_id, evidence_class="C",
        source_uri=body.url, source_name=title[:300],
        capture_method="manual_evidence",
        description=body.notes or f"Manual capture by researcher: {body.url}",
        captured_at=now,
    )
    db.add(ev)
    await db.flush()

    # optional screenshot (base64 from the extension side panel)
    if body.screenshot_b64:
        raw = body.screenshot_b64
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[1] if "," in raw else ""
        try:
            png = base64.b64decode(raw, validate=False)
        except Exception:
            png = b""
        if png:
            settings_dir = os.path.join(get_settings().data_dir, "screenshots", project_id)
            os.makedirs(settings_dir, exist_ok=True)
            fname = f"manual-{page_id[:12]}.png"
            fpath = os.path.join(settings_dir, fname)
            with open(fpath, "wb") as f:
                f.write(png)
            shot = Screenshot(
                id=new_id(), project_id=project_id, page_id=page_id, evidence_id=ev.id,
                url=body.url[:700], viewport={"width": 0, "height": 0},
                full_page=False, file_path=fpath,
                file_checksum="", notes="manual-evidence bridge", captured_at=now,
            )
            db.add(shot)
            ev.file_path = fpath

    page_row = (await db.execute(
        select(PageRecord).where(PageRecord.id == page_id))).scalars().first()
    if page_row and ev.id not in page_row.evidence_ids:
        page_row.evidence_ids.append(ev.id)

    db.add(ActivityLog(project_id=project_id, actor="user", action="manual.capture",
                       subject=body.url, detail=body.notes[:200]))
    await db.commit()
    await upsert_knowledge(project_id, "page", page_id, f"Page: {title}",
                           f"{body.url} {text[:6000]}")
    return {"page_id": page_id, "evidence_id": ev.id}


# ---------------------------------------------------------------- manual queue & batch

@router.post("/projects/{project_id}/pages/import-batch", status_code=201)
async def import_pages_batch(project_id: str, body: list[PageImportIn], db=Depends(get_session)):
    """Batch manual import (e.g. pages exported from the researcher's browser)."""
    await _require_project(db, project_id)
    if not body:
        raise HTTPException(400, "empty batch")
    if len(body) > 100:
        raise HTTPException(400, "max 100 pages per batch")
    results = []
    for item in body:
        r = await import_page(project_id, item, db)
        results.append({"url": item.url, "page_id": r["page_id"]})
    return {"imported": len(results), "pages": results}


@router.get("/projects/{project_id}/manual-queue")
async def manual_queue(project_id: str, db=Depends(get_session)):
    """The 'restricted sources checklist': pending manual-evidence decisions +
    fetch subtasks that failed/skipped with a reason, so the researcher can see
    exactly what still needs human collection."""
    await _require_project(db, project_id)
    decisions = (await db.execute(
        select(Decision).where(
            Decision.project_id == project_id,
            Decision.kind == "manual_evidence",
            Decision.status == "pending",
        ).order_by(Decision.created_at.desc())
    )).scalars().all()
    task_ids = (await db.execute(
        select(ResearchTask.id).where(ResearchTask.project_id == project_id)
    )).scalars().all()
    subs = []
    if task_ids:
        subs = (await db.execute(
            select(Subtask).where(
                Subtask.task_id.in_(list(task_ids)),
                Subtask.type == "fetch",
                Subtask.status.in_(["failed", "skipped", "waiting_decision"]),
            )
        )).scalars().all()
    return {
        "pending_decisions": [{
            "id": d.id, "task_id": d.task_id, "question": d.question,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        } for d in decisions],
        "blocked_fetches": [{
            "id": s.id, "task_id": s.task_id, "description": s.description,
            "status": s.status, "last_error": s.last_error,
        } for s in subs],
    }


# ---------------------------------------------------------------- robots (admin)

@router.get("/projects/{project_id}/robots-check")
async def robots_check(project_id: str, url: str, db=Depends(get_session)):
    """Read-only robots.txt posture for a URL — what the agent will do."""
    await _require_project(db, project_id)
    status, detail = await robots.robots_status(url)
    return {"url": url, "status": status, "detail": detail}
