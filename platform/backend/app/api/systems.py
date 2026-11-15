"""Analytics, reports, knowledge base, browser management, sessions, GitHub
integration and the research-package import endpoint."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..config import get_settings
from ..db import get_session
from ..engine import analytics
from ..engine.browser import manager as browser_manager
from ..engine.ids import new_id
from ..engine.reports import REPORT_TYPES, render_report
from ..engine.knowledge import related as kb_related
from ..engine.knowledge import search as kb_search
from ..engine.knowledge import upsert_knowledge
from ..github_int.client import get_adapter, sanitize
from ..models import (ActivityLog, Evidence, Feature, GitHubState, Observation,
                      PageRecord, Project, Report, ResearchSession, ResearchTask,
                      Source, UnresolvedQuestion)
from ..db import session_scope
from ..schemas import CaptureIn, GitHubWriteIn, ProfileIn, ReportGenIn, SearchIn
from ..security.auth import (auth_enabled, check_project_access, get_current_user,
                             is_admin, require_admin, require_project_access)

router = APIRouter(tags=["systems"])


async def _ctx(project_id: str, db) -> dict:
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if project is None:
        raise HTTPException(404, "project not found")
    tasks = (await db.execute(
        select(ResearchTask).where(ResearchTask.project_id == project_id))).scalars().all()
    pages = (await db.execute(
        select(PageRecord).where(PageRecord.project_id == project_id))).scalars().all()
    features = (await db.execute(
        select(Feature).where(Feature.project_id == project_id))).scalars().all()
    evidence = (await db.execute(
        select(Evidence).where(Evidence.project_id == project_id))).scalars().all()
    observations = (await db.execute(
        select(Observation).where(Observation.project_id == project_id))).scalars().all()
    questions = (await db.execute(
        select(UnresolvedQuestion).where(UnresolvedQuestion.project_id == project_id))).scalars().all()
    reports = (await db.execute(
        select(Report).where(Report.project_id == project_id))).scalars().all()

    def d(m):
        return {c.name: getattr(m, c.name) for c in m.__table__.columns}

    ev = [d(e) for e in evidence]
    obs = [d(o) for o in observations]
    # attach citation lists
    for e in ev:
        e["cited_by"] = [o["id"] for o in obs if e["id"] in (o.get("evidence_ids") or [])]
    for o in obs:
        o["evidence_refs"] = o.get("evidence_ids") or []
    pg = [d(p) for p in pages]
    for p in pg:
        p["evidence_refs"] = p.get("evidence_ids") or []
    return {
        "project": d(project),
        "tasks": [d(t) for t in tasks],
        "pages": pg,
        "features": [d(f) for f in features],
        "evidence": ev,
        "observations": obs,
        "questions": [d(q) for q in questions],
        "reports": [d(r) for r in reports],
    }


# ---------------------------------------------------------------- analytics

@router.get("/projects/{project_id}/analytics")
async def project_analytics(project_id: str, db=Depends(get_session),
                            _p=Depends(require_project_access)):
    ctx = await _ctx(project_id, db)
    return analytics.full_project_analytics(
        ctx["project"], ctx["pages"], ctx["features"],
        ctx["evidence"], ctx["observations"], ctx["questions"],
    )


# ---------------------------------------------------------------- reports

@router.get("/reports/types")
async def report_types():
    return REPORT_TYPES


@router.get("/projects/{project_id}/reports")
async def list_reports(project_id: str, db=Depends(get_session),
                       _p=Depends(require_project_access)):
    rows = (await db.execute(
        select(Report).where(Report.project_id == project_id)
        .order_by(Report.generated_at.desc())
    )).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "generated_at": r.generated_at.isoformat() if r.generated_at else "",
        "chars": len(r.content or "")} for r in rows]


@router.post("/projects/{project_id}/reports/generate")
async def generate_report(project_id: str, body: ReportGenIn, db=Depends(get_session),
                          _p=Depends(require_project_access)):
    if body.type not in REPORT_TYPES:
        raise HTTPException(400, f"unknown report type; options: {', '.join(REPORT_TYPES)}")
    if body.format not in ("md", "json", "csv", "html", "pdf"):
        raise HTTPException(400, "format must be md|json|csv|html|pdf")
    ctx = await _ctx(project_id, db)
    ctx["analytics"] = analytics.full_project_analytics(
        ctx["project"], ctx["pages"], ctx["features"],
        ctx["evidence"], ctx["observations"], ctx["questions"],
    )
    content = render_report(body.type, ctx, body.format)
    s = get_settings()
    report = Report(
        id=new_id(), project_id=project_id, type=body.type,
        title=f"{REPORT_TYPES[body.type]} — {ctx['project']['name']}",
        format=body.format, content=content,
        meta={"project": ctx["project"]["name"], "generated_at": datetime.now(timezone.utc).isoformat()},
    )
    db.add(report)
    await db.flush()
    out_dir = os.path.join(s.data_dir, "reports", project_id)
    os.makedirs(out_dir, exist_ok=True)
    ext = {"md": "md", "json": "json", "csv": "csv", "html": "html", "pdf": "pdf"}[body.format]
    path = os.path.join(out_dir, f"{body.type}-{report.id}.{ext}")
    if body.format == "pdf":
        import base64

        raw = base64.b64decode(content.split(",", 1)[1])
        with open(path, "wb") as f:
            f.write(raw)
        # knowledge gets the markdown source of truth, never base64
        kb_body = render_report(body.type, ctx, "md")[:12000]
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        kb_body = content[:12000]
    report.file_path = os.path.relpath(path, s.data_dir)
    db.add(ActivityLog(project_id=project_id, actor="system", action="report.generated",
                       subject=report.title))
    await db.commit()
    await upsert_knowledge(project_id, "report", report.id, report.title, kb_body)
    return {"id": report.id, "title": report.title, "format": body.format, "chars": len(content)}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    r = (await db.execute(select(Report).where(Report.id == report_id))).scalars().first()
    if not r:
        raise HTTPException(404, "report not found")
    await check_project_access(db, user, r.project_id)
    return {c.name: getattr(r, c.name) for c in r.__table__.columns}


# ---------------------------------------------------------------- knowledge base

@router.post("/projects/{project_id}/knowledge/search")
async def knowledge_search(project_id: str, body: SearchIn, db=Depends(get_session),
                           _p=Depends(require_project_access)):
    return await kb_search(project_id, body.query, body.kinds, body.limit)


@router.get("/knowledge/related")
async def knowledge_related(kind: str, ref_id: str, project_id: str = "",
                            db=Depends(get_session), user=Depends(get_current_user)):
    if not project_id:
        # resolve project from ref id kind
        if kind == "feature":
            f = (await db.execute(select(Feature).where(Feature.id == ref_id))).scalars().first()
            project_id = f.project_id if f else ""
        if kind == "page":
            p = (await db.execute(select(PageRecord).where(PageRecord.id == ref_id))).scalars().first()
            project_id = p.project_id if p else ""
    if not project_id:
        raise HTTPException(400, "project_id required")
    await check_project_access(db, user, project_id)
    return await kb_related(project_id, kind, ref_id)


# ---------------------------------------------------------------- browser management

@router.get("/browsers/health")
async def browsers_health(refresh: bool = False, db=Depends(get_session)):
    if refresh:
        return await browser_manager.probe_engines()
    return await browser_manager.get_health()


@router.post("/browsers/profiles", status_code=201)
async def create_browser_profile(body: ProfileIn, db=Depends(get_session),
                                 user=Depends(get_current_user)):
    await check_project_access(db, user, body.project_id)
    return await browser_manager.create_profile(body.project_id, body.name, body.engine,
                                                body.viewports, body.shared)


@router.get("/browsers/profiles")
async def browser_profiles():
    return await browser_manager.list_profiles()


@router.post("/projects/{project_id}/captures")
async def run_capture(project_id: str, body: CaptureIn, db=Depends(get_session),
                      user=Depends(get_current_user)):
    await check_project_access(db, user, project_id)
    result = await browser_manager.run_capture(
        project_id=project_id, source_url=body.url, engine=body.engine,
        headless=body.headless, viewport=body.viewport,
        extra_viewports=body.extra_viewports, full_page=body.full_page,
        profile_id=body.profile_id,
    )
    async with session_scope() as s:
        s.add(ActivityLog(project_id=project_id, actor="system",
                          action="capture." + ("ok" if result.get("ok") else "failed"),
                          subject=body.url, detail=result.get("error", "")[:400]))
    return result


@router.get("/sessions")
async def sessions(project_id: str = "", limit: int = 50, db=Depends(get_session),
                   user=Depends(get_current_user)):
    if project_id:
        await check_project_access(db, user, project_id)
        return await browser_manager.list_sessions(project_id, limit)
    pids = None
    if auth_enabled() and not is_admin(user):
        pids = list((await db.execute(
            select(Project.id).where(Project.owner_id == user["id"]))).scalars().all()) or [""]
    return await browser_manager.list_sessions(None, limit, project_ids=pids)


@router.get("/sessions/{session_id}/log")
async def session_log(session_id: str, db=Depends(get_session),
                      user=Depends(get_current_user)):
    sess = (await db.execute(
        select(ResearchSession).where(ResearchSession.id == session_id))).scalars().first()
    if sess is None:
        raise HTTPException(404, "session not found")
    await check_project_access(db, user, sess.project_id)
    return await browser_manager.session_log(session_id)


# ---------------------------------------------------------------- github

@router.get("/github/status")
async def github_status(project_id: str = "", db=Depends(get_session)):
    s = get_settings()
    adapter = get_adapter(local_path=s.local_repo_path or None, remote=s.github_repo or None)
    if adapter is None:
        raise HTTPException(503, "No GitHub adapter available (neither local checkout nor remote configured).")
    info = adapter.repo_info()
    commits = adapter.recent_commits(15)
    tree = adapter.docs_tree("docs")
    state = None
    if project_id:
        state = (await db.execute(
            select(GitHubState).where(GitHubState.project_id == project_id)
        )).scalars().first()
    return {
        "connected": True,
        "info": info,
        "commits": commits,
        "branches": adapter.branches() if hasattr(adapter, "branches") else [],
        "docs_tree": tree[:200],
        "state": {c.name: getattr(state, c.name) for c in state.__table__.columns} | {
            "last_sync_at": state.last_sync_at.isoformat() if state and state.last_sync_at else ""} if state else None,
    }


@router.post("/github/sync")
async def github_sync(project_id: str = "", db=Depends(get_session),
                      user=Depends(get_current_user)):
    require_admin(user)
    s = get_settings()
    adapter = get_adapter(local_path=s.local_repo_path or None, remote=s.github_repo or None)
    if adapter is None:
        raise HTTPException(503, "No GitHub adapter available.")
    info = adapter.repo_info()
    tree = adapter.docs_tree("docs")
    now = datetime.now(timezone.utc)
    async with session_scope() as sess:
        st = None
        if project_id:
            st = (await sess.execute(
                select(GitHubState).where(GitHubState.project_id == project_id)
            )).scalars().first()
            if st is None:
                st = GitHubState(id=new_id(), project_id=project_id)
                sess.add(st)
        if st is not None:
            st.repo_full_name = info.get("remote", s.github_repo)
            st.default_branch = info.get("branch", "")
            st.current_branch = info.get("branch", "")
            st.last_commit_sha = info.get("last_commit_sha", "")
            st.last_commit_message = info.get("last_commit_message", "")
            st.docs_tree = tree
            st.last_sync_at = now
            st.sync_status = "ok"
        # read the research README + investigation log before any new
        # investigation (directive §12) — store digest in state notes.
        digest = ""
        try:
            readme = adapter.read_doc("docs/research/README.md")
            digest = "research README read: " + readme[:300].replace("\n", " ")
        except Exception:
            digest = "research README not found"
        if st is not None:
            st.notes = digest
    return {"synced": True, "info": info, "docs": len(tree), "digest": digest[:200]}


@router.post("/github/write-back")
async def github_write(body: GitHubWriteIn, decision_id: str = "", db=Depends(get_session),
                       user=Depends(get_current_user)):
    """Consequential repo change: allowed only after an approved Decision of
    kind repo_change. Pass ?decision_id=<approved decision>. Admin-only in
    multi-user mode (the central repo is shared)."""
    require_admin(user)
    from ..models import Decision
    if not decision_id:
        raise HTTPException(400, "consequential repo change requires an approved decision: pass ?decision_id=<id>")
    d = (await db.execute(select(Decision).where(Decision.id == decision_id))).scalars().first()
    if d is None:
        raise HTTPException(404, "decision not found")
    if d.kind != "repo_change":
        raise HTTPException(400, "decision is not a repo_change approval")
    if d.status != "approved":
        raise HTTPException(403, f"decision is {d.status}; repo changes require approval")
    s = get_settings()
    adapter = get_adapter(local_path=s.local_repo_path or None)
    if adapter is None:
        raise HTTPException(503, "Local checkout not available for write-back.")
    if not body.path.startswith("docs/"):
        raise HTTPException(400, "write-back is restricted to docs/** (research knowledge). Product code changes require a reviewed PR by a human.")
    content = sanitize(body.content)
    result = adapter.write_back(body.path, content, body.commit_message, body.branch)
    if body.open_pr:
        pr = adapter.create_pr(body.pr_title or body.commit_message,
                               f"Research write-back from the Intelligence Engine.\n\nFile: `{body.path}`",
                               base="main")
        result["pr"] = pr
    db.add(ActivityLog(actor="user", action="github.write_back", subject=body.path,
                       detail=str(result)[:400]))
    return result


# ---------------------------------------------------------------- import pipeline

@router.post("/projects/{project_id}/import/research-package")
async def import_package(project_id: str, docs_dir: str = "docs/research",
                         db=Depends(get_session), _p=Depends(require_project_access)):
    """Ingest a markdown research package directory into the project."""
    from ..engine.evidence_import import import_research_package
    s = get_settings()
    repo_root = s.local_repo_path or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    full = os.path.join(repo_root, docs_dir) if not os.path.isabs(docs_dir) else docs_dir
    if not os.path.isdir(full):
        raise HTTPException(404, f"docs dir not found: {full}")
    counts = await import_research_package(project_id, full)
    db.add(ActivityLog(project_id=project_id, actor="import", action="import.complete",
                       subject=docs_dir, detail=str(counts)))
    return {"imported": counts, "from": full}


# ---------------------------------------------------------------- system: backup / plugins

@router.post("/systems/backup")
async def systems_backup(user=Depends(get_current_user)):
    require_admin(user)
    from ..engine.export_import import create_backup
    r = await create_backup()
    if not r.get("ok"):
        raise HTTPException(503, r.get("error", "backup failed"))
    return r


@router.get("/systems/backups")
async def systems_backups(user=Depends(get_current_user)):
    require_admin(user)
    from ..engine.export_import import list_backups
    return list_backups()


@router.get("/plugins")
async def plugins_list():
    from ..engine.plugins import KINDS, discover, registry

    discover()
    return {kind: [{"name": p.name, "source": p.meta.get("source", "unknown"),
                    "description": p.meta.get("description", "")}
                   for p in registry.list(kind)] for kind in KINDS}
