"""Project CRUD + the Overview dashboard aggregate."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..db import get_session
from ..engine.feature_engine import slugify
from ..engine.ids import new_id
from ..engine.knowledge import upsert_knowledge
from ..models import (ActivityLog, Evidence, Feature, Observation, PageRecord,
                      Project, ResearchSession, ResearchTask)
from ..schemas import ProjectIn, ProjectPatch

router = APIRouter(tags=["projects"])


def _p(m: Project) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns} | {
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


@router.get("/overview")
async def overview(db=Depends(get_session)):
    projects = (await db.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
    tasks = (await db.execute(select(ResearchTask))).scalars().all()
    pages = (await db.execute(select(PageRecord))).scalars().all()
    features = (await db.execute(select(Feature))).scalars().all()
    evidence = (await db.execute(select(Evidence))).scalars().all()
    observations = (await db.execute(select(Observation))).scalars().all()
    activity = (await db.execute(
        select(ActivityLog).order_by(ActivityLog.ts.desc()).limit(30)
    )).scalars().all()
    sessions = (await db.execute(
        select(func.count()).select_from(ResearchSession)
    )).scalar() or 0

    def by_project(rows, field="project_id"):
        out: dict[str, list] = {}
        for r in rows:
            out.setdefault(getattr(r, field, ""), []).append(r)
        return out

    ppages, pfeatures, pevidence = by_project(pages), by_project(features), by_project(evidence)
    pobs = by_project(observations)

    project_cards = []
    for p in projects:
        pp, pf, pe, po = ppages.get(p.id, []), pfeatures.get(p.id, []), pevidence.get(p.id, []), pobs.get(p.id, [])
        doc_pages = sum(1 for x in pp if x.status == "documented")
        verified = sum(1 for o in po if o.status == "verified")
        project_cards.append({
            **_p(p),
            "counts": {
                "tasks": sum(1 for t in tasks if t.project_id == p.id),
                "active_tasks": sum(1 for t in tasks if t.project_id == p.id and t.status in ("running", "planned", "waiting_decision", "queued", "paused")),
                "pages": len(pp), "pages_documented": doc_pages,
                "features": len(pf),
                "evidence": len(pe),
                "observations": len(po), "verified_observations": verified,
            },
        })
    return {
        "projects": project_cards,
        "totals": {
            "projects": len(projects),
            "tasks": len(tasks),
            "tasks_active": sum(1 for t in tasks if t.status in ("running", "planned", "waiting_decision", "queued", "paused")),
            "sessions": sessions,
            "pages": len(pages),
            "pages_documented": sum(1 for x in pages if x.status == "documented"),
            "features": len(features),
            "evidence": len(evidence),
            "observations": len(observations),
            "verified": sum(1 for o in observations if o.status == "verified"),
        },
        "recent_activity": [
            {"id": a.id, "project_id": a.project_id, "actor": a.actor, "action": a.action,
             "subject": a.subject, "detail": a.detail[:200],
             "ts": a.ts.isoformat() if a.ts else ""} for a in activity
        ],
    }


@router.get("/projects")
async def list_projects(db=Depends(get_session)):
    rows = (await db.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
    return [_p(p) for p in rows]


@router.post("/projects", status_code=201)
async def create_project(body: ProjectIn, db=Depends(get_session)):
    slug = slugify(body.name)
    existing = (await db.execute(select(Project).where(Project.slug == slug))).scalars().first()
    if existing:
        raise HTTPException(409, f"project with name '{body.name}' already exists")
    p = Project(id=new_id(), name=body.name, slug=slug, description=body.description,
                industry=body.industry, target_base_url=body.target_base_url,
                instructions=body.instructions, repo_url=body.repo_url,
                permissions=body.permissions)
    db.add(p)
    await db.flush()
    db.add(ActivityLog(project_id=p.id, actor="user", action="project.created", subject=p.name))
    await db.commit()
    await upsert_knowledge(p.id, "project", p.id, f"Project: {p.name}",
                           f"{p.description} target={p.target_base_url} {p.instructions[:800]}")
    return _p(p)


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db=Depends(get_session)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if not p:
        raise HTTPException(404, "project not found")
    tasks = (await db.execute(
        select(ResearchTask).where(ResearchTask.project_id == project_id)
        .order_by(ResearchTask.created_at.desc())
    )).scalars().all()
    return {**_p(p), "tasks": [_t(t) for t in tasks]}


def _t(m: ResearchTask) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns} | {
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


@router.patch("/projects/{project_id}")
async def patch_project(project_id: str, body: ProjectPatch, db=Depends(get_session)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if not p:
        raise HTTPException(404, "project not found")
    data = body.model_dump(exclude_none=True)
    if "name" in data and data["name"] != p.name:
        p.slug = slugify(data["name"])
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_at = datetime.now(timezone.utc)
    db.add(ActivityLog(project_id=p.id, actor="user", action="project.updated", subject=p.name))
    await db.commit()
    return _p(p)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, confirm: str = "", db=Depends(get_session)):
    """Destructive: requires explicit confirm=project-name (directive §16)."""
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if not p:
        raise HTTPException(404, "project not found")
    if confirm != p.name:
        raise HTTPException(400, "destructive operation: pass ?confirm=<exact project name>")
    await db.delete(p)
    return {"deleted": p.name}


# ---------------------------------------------------------------- export / import (portability)

@router.get("/projects/{project_id}/export")
async def export_project(project_id: str):
    from ..engine.export_import import dump_project
    try:
        bundle = await dump_project(project_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return bundle


@router.post("/projects/import", status_code=201)
async def import_project_bundle(bundle: dict, name: str = ""):
    from ..engine.export_import import import_project
    r = await import_project(bundle, name_override=name)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "import failed"))
    return r
