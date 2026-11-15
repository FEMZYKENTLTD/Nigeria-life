"""User administration (multi-user mode).

Who exists, what each person is scraping and what they are getting —
projects, tasks, captured pages, evidence and activity. Admin-only; in
local mode the single local operator is the admin and sees everything.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..db import get_session
from ..models import (ActivityLog, Evidence, Observation, PageRecord,
                      Profile, Project, ResearchSession, ResearchTask)
from ..security.auth import LOCAL_USER_ID, get_current_user, is_admin, require_admin

router = APIRouter(tags=["users"])


class RoleIn(BaseModel):
    role: str  # admin | member


def _iso(v) -> str:
    return v.isoformat() if v else ""


async def _pids_for(db, user_id: str) -> list[str]:
    """Project ids visible to this user — mirrors can_see_project: admins
    and the local operator see everything, members see their own."""
    if user_id == LOCAL_USER_ID:
        return list((await db.execute(select(Project.id))).scalars().all())
    return list((await db.execute(
        select(Project.id).where(Project.owner_id == user_id)
    )).scalars().all())


async def _counts(db, pids: list[str]) -> dict:
    if not pids:
        return {"projects": 0, "tasks": 0, "pages": 0, "evidence": 0,
                "observations": 0, "sessions": 0}

    async def _n(model) -> int:
        r = await db.execute(
            select(func.count()).select_from(model).where(model.project_id.in_(pids)))
        return int(r.scalar_one())

    return {
        "projects": len(pids),
        "tasks": await _n(ResearchTask),
        "pages": await _n(PageRecord),
        "evidence": await _n(Evidence),
        "observations": await _n(Observation),
        "sessions": await _n(ResearchSession),
    }


def _profile_dict(p: Profile, counts: dict | None = None) -> dict:
    d = {
        "id": p.id,
        "email": p.email or "",
        "display_name": p.display_name,
        "role": p.role,
        "created_at": _iso(p.created_at),
        "last_seen_at": _iso(p.last_seen_at),
    }
    if counts is not None:
        d["counts"] = counts
    return d


@router.get("/users")
async def list_users(db=Depends(get_session), user=Depends(get_current_user)):
    """All registered users with per-user volume counts — the admin's
    overview of who is using the tool and how much they are pulling."""
    require_admin(user)
    profiles = (await db.execute(
        select(Profile).order_by(Profile.created_at.desc()))).scalars().all()
    out = []
    for p in profiles:
        out.append(_profile_dict(p, await _counts(db, await _pids_for(db, p.id))))
    return {"users": out, "total": len(out)}


@router.get("/users/{user_id}")
async def user_detail(user_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    """One user's activity: their projects, what they scraped (pages) and
    what they got (evidence, task results), plus the recent activity log."""
    require_admin(user)
    p = (await db.execute(
        select(Profile).where(Profile.id == user_id))).scalars().first()
    if p is None:
        raise HTTPException(404, "user not found")
    pids = await _pids_for(db, user_id)

    projects = (await db.execute(
        select(Project).where(Project.id.in_(pids)).order_by(Project.created_at.desc())
    )).scalars().all() if pids else []

    tasks = (await db.execute(
        select(ResearchTask).where(ResearchTask.project_id.in_(pids))
        .order_by(ResearchTask.created_at.desc()).limit(20)
    )).scalars().all() if pids else []

    pages = (await db.execute(
        select(PageRecord).where(PageRecord.project_id.in_(pids))
        .order_by(PageRecord.created_at.desc()).limit(20)
    )).scalars().all() if pids else []

    evidence = (await db.execute(
        select(Evidence).where(Evidence.project_id.in_(pids))
        .order_by(Evidence.created_at.desc()).limit(20)
    )).scalars().all() if pids else []

    activity = (await db.execute(
        select(ActivityLog).where(ActivityLog.project_id.in_(pids))
        .order_by(ActivityLog.ts.desc()).limit(30)
    )).scalars().all() if pids else []

    return {
        "user": _profile_dict(p, await _counts(db, pids)),
        "projects": [{
            "id": x.id, "name": x.name, "status": x.status,
            "created_at": _iso(x.created_at),
        } for x in projects],
        "recent_tasks": [{
            "id": t.id, "project_id": t.project_id, "title": t.title,
            "status": t.status, "progress": t.progress,
            "result_summary": (t.result_summary or "")[:400],
            "error": (t.error or "")[:200],
            "created_at": _iso(t.created_at),
        } for t in tasks],
        "recent_pages": [{
            "id": pg.id, "project_id": pg.project_id, "url": pg.url,
            "title": pg.title, "status": pg.status,
            "capture_method": pg.capture_method, "browser_engine": pg.browser_engine,
            "error": (pg.error or "")[:200],
            "observed_at": _iso(pg.observed_at),
        } for pg in pages],
        "recent_evidence": [{
            "id": e.id, "project_id": e.project_id, "ref_code": e.ref_code,
            "evidence_class": e.evidence_class, "source_name": e.source_name,
            "capture_method": e.capture_method,
            "description": (e.description or "")[:300],
            "created_at": _iso(e.created_at),
        } for e in evidence],
        "recent_activity": [{
            "project_id": a.project_id, "actor": a.actor, "action": a.action,
            "subject": a.subject, "detail": (a.detail or "")[:200],
            "ts": _iso(a.ts),
        } for a in activity],
    }


@router.patch("/users/{user_id}/role")
async def set_user_role(user_id: str, body: RoleIn, db=Depends(get_session),
                        user=Depends(get_current_user)):
    """Promote/demote a user. Admin-only. The local operator is synthetic
    and cannot be changed; an email listed in RICE_ADMIN_EMAILS is re-promoted
    on their next request (sticky admin)."""
    require_admin(user)
    if body.role not in ("admin", "member"):
        raise HTTPException(400, "role must be 'admin' or 'member'")
    if user_id == LOCAL_USER_ID:
        raise HTTPException(400, "the local operator role is fixed")
    p = (await db.execute(
        select(Profile).where(Profile.id == user_id))).scalars().first()
    if p is None:
        raise HTTPException(404, "user not found")
    p.role = body.role
    await db.commit()
    return _profile_dict(p)
