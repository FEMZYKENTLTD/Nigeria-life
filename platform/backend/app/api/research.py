"""Research records: sources, pages, features, observations, evidence,
unresolved questions, manual imports."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select

from ..config import get_settings
from ..db import get_session
from ..engine.feature_engine import slugify
from ..engine.ids import new_id
from ..engine.knowledge import related as kb_related
from ..engine.knowledge import upsert_knowledge
from ..engine.page_understanding import analyze_html
from ..models import (ActivityLog, Evidence, Feature, Observation, PageRecord,
                      Project, Source, UnresolvedQuestion)
from ..schemas import FeatureIn, ObservationIn, PageImportIn, QuestionIn, SourceIn
from ..security.auth import (check_project_access, get_current_user,
                             require_project_access)

router = APIRouter(tags=["research"])


# ---------------------------------------------------------------- sources

@router.get("/projects/{project_id}/sources")
async def list_sources(project_id: str, db=Depends(get_session), _p=Depends(require_project_access)):
    rows = (await db.execute(
        select(Source).where(Source.project_id == project_id).order_by(Source.created_at.desc())
    )).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]


@router.post("/projects/{project_id}/sources", status_code=201)
async def add_source(project_id: str, body: SourceIn, db=Depends(get_session), _p=Depends(require_project_access)):
    from urllib.parse import urlparse
    domain = urlparse(body.url).netloc or body.url
    status = "authorised" if (body.status == "authorised" and body.auto_authorise) else body.status
    s = Source(id=new_id(), project_id=project_id, name=body.name, url=body.url,
               domain=domain, status=status, notes=body.notes, discovered_by="user")
    db.add(s)
    db.add(ActivityLog(project_id=project_id, actor="user", action="source.added",
                       subject=body.url, detail=f"status={status}"))
    await db.commit()
    return {"id": s.id, "status": status,
            "note": "" if status == "authorised" else
            "New sources start pending approval; the scheduler will not touch them until approved."}


# ---------------------------------------------------------------- pages

@router.get("/projects/{project_id}/pages")
async def list_pages(project_id: str, q: str = "", db=Depends(get_session), _p=Depends(require_project_access)):
    query = select(PageRecord).where(PageRecord.project_id == project_id)
    rows = (await db.execute(query.order_by(PageRecord.updated_at.desc()))).scalars().all()
    out = [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "observed_at": r.observed_at.isoformat() if r.observed_at else "",
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else ""} for r in rows]
    if q:
        qq = q.lower()
        out = [p for p in out if qq in (p.get("url") or "").lower()
               or qq in (p.get("title") or "").lower() or qq in (p.get("purpose") or "").lower()]
    return out


@router.post("/projects/{project_id}/pages/import", status_code=201)
async def import_page(project_id: str, body: PageImportIn, db=Depends(get_session), _p=Depends(require_project_access)):
    """Manual evidence import (the sanctioned path for restricted sources)."""
    analysis = None
    if body.html:
        analysis = analyze_html(body.html, url=body.url, base_url=body.url)
    text = body.text or (analysis.get("body_text", "") if analysis else "")
    title = body.title or (analysis.get("title", "") if analysis else "") or body.url
    existing = (await db.execute(
        select(PageRecord).where(
            PageRecord.project_id == project_id,
            PageRecord.canonical_url == body.url[:700],
        )
    )).scalars().first()
    structure = {}
    if analysis:
        structure = {k: analysis[k] for k in
                     ("regions", "navigation", "forms", "controls", "interactive", "buttons",
                      "sections", "links", "images", "states", "repeated_components", "element_counts")}
    if existing:
        existing.title = title
        existing.status = body.status
        existing.body_text = text[:20000]
        existing.structure = structure or existing.structure
        existing.error = body.notes
        existing.updated_at = datetime.now(timezone.utc)
        pid = existing.id
    else:
        page = PageRecord(
            id=new_id(), project_id=project_id, url=body.url[:700], canonical_url=body.url[:700],
            title=title[:500], status=body.status,
            content_category=(analysis.get("content_category", "") if analysis else ""),
            purpose=(analysis.get("purpose", "") if analysis else body.notes),
            summary=(analysis.get("summary", "") if analysis else text[:500]),
            structure=structure, body_text=text[:20000],
            observed_at=datetime.now(timezone.utc), capture_method="manual_import",
            error=body.notes,
        )
        db.add(page)
        await db.flush()
        pid = page.id
    # optional evidence record
    if body.evidence_source or body.evidence_class != "I":
        ev = Evidence(
            id=new_id(), project_id=project_id, evidence_class=body.evidence_class,
            source_uri=body.url, source_name=body.evidence_source or title,
            capture_method="import", description=body.notes or text[:500],
            captured_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        await db.flush()
        if existing:
            if ev.id not in existing.evidence_ids:
                existing.evidence_ids.append(ev.id)
        else:
            page.evidence_ids.append(ev.id)
    db.add(ActivityLog(project_id=project_id, actor="user", action="page.imported", subject=body.url))
    await db.commit()
    await upsert_knowledge(project_id, "page", pid, f"Page: {title}", f"{body.url} {text[:6000]}")
    return {"page_id": pid}


# ---------------------------------------------------------------- features

@router.get("/projects/{project_id}/features")
async def list_features(project_id: str, category: str = "", db=Depends(get_session), _p=Depends(require_project_access)):
    q = select(Feature).where(Feature.project_id == project_id)
    if category:
        q = q.where(Feature.category == category)
    rows = (await db.execute(q.order_by(Feature.category, Feature.name))).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "updated_at": r.updated_at.isoformat() if r.updated_at else ""} for r in rows]


@router.post("/projects/{project_id}/features", status_code=201)
async def create_feature(project_id: str, body: FeatureIn, db=Depends(get_session), _p=Depends(require_project_access)):
    existing = (await db.execute(
        select(Feature).where(Feature.project_id == project_id, Feature.slug == slugify(body.name))
    )).scalars().first()
    if existing:
        raise HTTPException(409, f"feature '{body.name}' already exists")
    f = Feature(id=new_id(), project_id=project_id, name=body.name, slug=slugify(body.name),
                **body.model_dump(exclude={"name"}))
    db.add(f)
    db.add(ActivityLog(project_id=project_id, actor="user", action="feature.created", subject=body.name))
    await db.flush()
    await db.commit()
    await upsert_knowledge(project_id, "feature", f.id, f"Feature: {f.name}",
                           f"{f.description} {f.purpose} {f.observed_behaviour} {f.limitations}")
    return {"id": f.id}


class FeaturePatch(FeatureIn):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    purpose: str | None = None
    user_type: str | None = None
    access_location: str | None = None
    inputs: str | None = None
    outputs: str | None = None
    observed_behaviour: str | None = None
    dependencies: list[str] | None = None
    related_features: list[str] | None = None
    user_journey: str | None = None
    limitations: str | None = None
    opportunities: str | None = None
    implementation_implications: str | None = None
    evidence_ids: list[str] | None = None
    confidence: float | None = None
    status: str | None = None


@router.patch("/features/{feature_id}")
async def update_feature(feature_id: str, body: FeaturePatch, db=Depends(get_session),
                         user=Depends(get_current_user)):
    f = (await db.execute(select(Feature).where(Feature.id == feature_id))).scalars().first()
    if not f:
        raise HTTPException(404, "feature not found")
    await check_project_access(db, user, f.project_id)
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "name" and v:
            f.name = v
            f.slug = slugify(v)
        else:
            setattr(f, k, v)
    f.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await upsert_knowledge(f.project_id, "feature", f.id, f"Feature: {f.name}",
                           f"{f.description} {f.purpose} {f.observed_behaviour} {f.limitations}")
    return {"updated": True}


@router.get("/features/{feature_id}/related")
async def feature_related(feature_id: str, db=Depends(get_session),
                          user=Depends(get_current_user)):
    f = (await db.execute(select(Feature).where(Feature.id == feature_id))).scalars().first()
    if not f:
        raise HTTPException(404, "feature not found")
    await check_project_access(db, user, f.project_id)
    return {"dependencies": f.dependencies or [], "related": f.related_features or [],
            "knowledge": await kb_related(f.project_id, "feature", f.id)}


# ---------------------------------------------------------------- observations

@router.get("/projects/{project_id}/observations")
async def list_observations(project_id: str, kind: str = "", status: str = "", db=Depends(get_session), _p=Depends(require_project_access)):
    q = select(Observation).where(Observation.project_id == project_id)
    if kind:
        q = q.where(Observation.kind == kind)
    if status:
        q = q.where(Observation.status == status)
    rows = (await db.execute(q.order_by(Observation.created_at.desc()).limit(500))).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]


@router.post("/projects/{project_id}/observations", status_code=201)
async def add_observation(project_id: str, body: ObservationIn, db=Depends(get_session), _p=Depends(require_project_access)):
    o = Observation(id=new_id(), project_id=project_id, **body.model_dump())
    db.add(o)
    db.add(ActivityLog(project_id=project_id, actor="user", action="observation.added",
                       subject=body.observation[:160]))
    await db.flush()
    await db.commit()
    await upsert_knowledge(project_id, "observation", o.id,
                           f"Observation ({body.kind}): {body.observation[:120]}",
                           f"{body.key} {body.value} {body.observation[:3000]}")
    return {"id": o.id}


# ---------------------------------------------------------------- evidence

@router.get("/projects/{project_id}/evidence")
async def list_evidence(project_id: str, cls: str = "", db=Depends(get_session), _p=Depends(require_project_access)):
    q = select(Evidence).where(Evidence.project_id == project_id)
    if cls:
        q = q.where(Evidence.evidence_class == cls)
    rows = (await db.execute(q.order_by(Evidence.ref_code))).scalars().all()
    out = []
    for r in rows:
        cited = (await db.execute(
            select(Observation).where(Observation.project_id == project_id)
        )).scalars().all()
        cited_by = [o.id for o in cited if r.id in (o.evidence_ids or [])]
        out.append({c.name: getattr(r, c.name) for c in r.__table__.columns} | {
            "captured_at": r.captured_at.isoformat() if r.captured_at else "",
            "cited_by": cited_by[:50]})
    return out


@router.post("/projects/{project_id}/evidence/import", status_code=201)
async def import_evidence_file(project_id: str, cls: str = "I", method: str = "import",
                               file: UploadFile | None = None, db=Depends(get_session)):
    s = get_settings()
    data = await file.read() if file else b""
    if not data:
        raise HTTPException(400, "no file provided")
    dest_dir = os.path.join(s.data_dir, "evidence", project_id)
    os.makedirs(dest_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload.bin").replace("../", "_")
    dest = os.path.join(dest_dir, f"{new_id()}-{safe_name}")
    with open(dest, "wb") as f:
        f.write(data)
    ev = Evidence(
        id=new_id(), project_id=project_id, evidence_class=cls,
        source_name=file.filename or "upload", capture_method=method,
        description=f"Imported file {file.filename} ({len(data)} bytes)",
        file_path=os.path.relpath(dest, s.data_dir),
        file_checksum=hashlib.sha256(data).hexdigest(),
        captured_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.add(ActivityLog(project_id=project_id, actor="user", action="evidence.imported",
                       subject=file.filename or ""))
    await db.flush()
    await db.commit()
    await upsert_knowledge(project_id, "evidence", ev.id,
                           f"Evidence: {file.filename or 'upload'}", ev.description)
    return {"id": ev.id, "file_path": ev.file_path, "checksum": ev.file_checksum}


# ---------------------------------------------------------------- questions

@router.get("/projects/{project_id}/questions")
async def list_questions(project_id: str, db=Depends(get_session), _p=Depends(require_project_access)):
    rows = (await db.execute(
        select(UnresolvedQuestion).where(UnresolvedQuestion.project_id == project_id)
        .order_by(UnresolvedQuestion.created_at.desc())
    )).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]


@router.post("/projects/{project_id}/questions", status_code=201)
async def add_question(project_id: str, body: QuestionIn, db=Depends(get_session), _p=Depends(require_project_access)):
    q = UnresolvedQuestion(id=new_id(), project_id=project_id, question=body.question,
                           context=body.context)
    db.add(q)
    await db.commit()
    return {"id": q.id}


@router.post("/questions/{question_id}/resolve")
async def resolve_question(question_id: str, resolution: str = "",
                           db=Depends(get_session), user=Depends(get_current_user)):
    q = (await db.execute(
        select(UnresolvedQuestion).where(UnresolvedQuestion.id == question_id)
    )).scalars().first()
    if not q:
        raise HTTPException(404, "question not found")
    await check_project_access(db, user, q.project_id)
    q.status = "resolved"
    q.resolution = resolution
    q.updated_at = datetime.now(timezone.utc)
    return {"resolved": True}
