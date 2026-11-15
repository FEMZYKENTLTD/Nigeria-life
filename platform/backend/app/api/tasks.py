"""Research tasks, decisions and the AI Agent Centre."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..config import get_settings
from ..db import get_session
from ..engine import agent_loop
from ..engine.ids import new_id
from ..models import (ActivityLog, AgentRun, Decision, Project, ResearchTask, Subtask)
from ..schemas import TaskIn
from ..security.auth import (auth_enabled, check_project_access, check_row_access,
                             get_current_user, is_admin, require_project_access)

router = APIRouter(tags=["tasks"])


def _st(m: Subtask) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns} | {
        "started_at": m.started_at.isoformat() if m.started_at else "",
        "finished_at": m.finished_at.isoformat() if m.finished_at else "",
    }


def _t(m: ResearchTask) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns} | {
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, db=Depends(get_session),
                     _p=Depends(require_project_access)):
    rows = (await db.execute(
        select(ResearchTask).where(ResearchTask.project_id == project_id)
        .order_by(ResearchTask.created_at.desc())
    )).scalars().all()
    out = []
    for t in rows:
        subs = (await db.execute(
            select(Subtask).where(Subtask.task_id == t.id).order_by(Subtask.idx)
        )).scalars().all()
        out.append({**_t(t), "subtasks": [_st(s) for s in subs],
                    "running": agent_loop.is_running(t.id)})
    return out


@router.post("/projects/{project_id}/tasks", status_code=201)
async def create_task(project_id: str, body: TaskIn, db=Depends(get_session),
                      user=Depends(get_current_user)):
    await check_project_access(db, user, project_id)
    t = ResearchTask(id=new_id(), project_id=project_id, title=body.title,
                     objective=body.objective, priority=body.priority)
    plan = {}
    if body.report_types:
        plan = {"report_types": body.report_types}
    t.plan = plan
    db.add(t)
    db.add(ActivityLog(project_id=project_id, actor="user", action="task.created", subject=t.title))
    await db.commit()
    await db.refresh(t)
    return _t(t)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    t = (await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
    if not t:
        raise HTTPException(404, "task not found")
    await check_project_access(db, user, t.project_id)
    subs = (await db.execute(
        select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.idx)
    )).scalars().all()
    runs = (await db.execute(
        select(AgentRun).where(AgentRun.task_id == task_id)
        .order_by(AgentRun.started_at.desc()).limit(10)
    )).scalars().all()
    return {**_t(t), "subtasks": [_st(s) for s in subs],
            "running": agent_loop.is_running(t.id),
            "runs": [{"id": r.id, "mode": r.mode, "status": r.status,
                      "started_at": r.started_at.isoformat() if r.started_at else "",
                      "finished_at": r.finished_at.isoformat() if r.finished_at else "",
                      "log": r.log or []} for r in runs]}


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    t = (await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
    if not t:
        raise HTTPException(404, "task not found")
    await check_project_access(db, user, t.project_id)
    if agent_loop.is_running(task_id):
        raise HTTPException(409, "task already running")
    db.add(ActivityLog(project_id=t.project_id, actor="user", action="task.run_requested", subject=t.title))
    await db.commit()
    agent_loop.start_task(task_id)
    return {"started": True, "task_id": task_id}


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    t = (await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
    if not t:
        raise HTTPException(404, "task not found")
    await check_project_access(db, user, t.project_id)
    if agent_loop.is_running(task_id):
        agent_loop.cancel(task_id)
        t.status = "paused"
        db.add(ActivityLog(project_id=t.project_id, actor="user", action="task.paused", subject=t.title))
        await db.commit()
        return {"paused": True}
    t.status = "paused"
    await db.commit()
    return {"paused": True}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db=Depends(get_session), user=Depends(get_current_user)):
    t = (await db.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
    if not t:
        raise HTTPException(404, "task not found")
    await check_project_access(db, user, t.project_id)
    if agent_loop.is_running(task_id):
        agent_loop.cancel(task_id)
    t.status = "cancelled"
    db.add(ActivityLog(project_id=t.project_id, actor="user", action="task.cancelled", subject=t.title))
    await db.commit()
    return {"cancelled": True}


# ---------------------------------------------------------------- decisions

@router.get("/projects/{project_id}/decisions")
async def list_decisions(project_id: str, status: str = "pending", db=Depends(get_session),
                         _p=Depends(require_project_access)):
    q = select(Decision).where(Decision.project_id == project_id)
    if status != "all":
        q = q.where(Decision.status == status)
    rows = (await db.execute(q.order_by(Decision.created_at.desc()))).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "decided_at": r.decided_at.isoformat() if r.decided_at else ""} for r in rows]


@router.post("/decisions/{decision_id}/{verdict}")
async def decide(decision_id: str, verdict: str, db=Depends(get_session),
                 user=Depends(get_current_user)):
    if verdict not in ("approve", "reject"):
        raise HTTPException(400, "verdict must be approve|reject")
    d = (await db.execute(select(Decision).where(Decision.id == decision_id))).scalars().first()
    if not d:
        raise HTTPException(404, "decision not found")
    await check_project_access(db, user, d.project_id)
    if d.status != "pending":
        raise HTTPException(409, f"decision already {d.status}")
    db.add(ActivityLog(project_id=d.project_id, actor="user", action=f"decision.{verdict}",
                       subject=d.question[:200]))
    await db.commit()
    await agent_loop.resume_after_decision(decision_id, approved=(verdict == "approve"))
    return {"decision_id": decision_id, "verdict": verdict}


# ---------------------------------------------------------------- agent centre

def _visible_pid_filter(user: dict):
    if not auth_enabled() or is_admin(user):
        return None
    return Project.owner_id == user["id"]


@router.get("/agent/status")
async def agent_status(db=Depends(get_session), user=Depends(get_current_user)):
    vis = _visible_pid_filter(user)
    tq = select(ResearchTask)
    if vis is not None:
        tq = tq.where(ResearchTask.project_id.in_(
            select(Project.id).where(vis)))
    tasks = (await db.execute(tq)).scalars().all()
    dq = select(Decision).where(Decision.status == "pending").order_by(Decision.created_at.desc())
    if vis is not None:
        dq = dq.where(Decision.project_id.in_(select(Project.id).where(vis)))
    decisions = (await db.execute(dq)).scalars().all()
    task_ids = [t.id for t in tasks] or [""]
    runs = (await db.execute(
        select(AgentRun).where(AgentRun.task_id.in_(task_ids))
        .order_by(AgentRun.started_at.desc()).limit(10)
    )).scalars().all()
    active = [t for t in tasks if t.status in ("running", "planned", "waiting_decision")]
    return {
        "active_tasks": [{**_t(t), "running": agent_loop.is_running(t.id)} for t in active],
        "queue": [{**_t(t)} for t in tasks if t.status == "queued"],
        "failed": [{**_t(t)} for t in tasks if t.status == "failed"],
        "complete": [{**_t(t)} for t in tasks if t.status == "complete"][:20],
        "pending_decisions": [{c.name: getattr(r, c.name) for c in r.__table__.columns} | {
            "created_at": r.created_at.isoformat() if r.created_at else ""} for r in decisions],
        "recent_runs": [{"id": r.id, "mode": r.mode, "status": r.status,
                         "started_at": r.started_at.isoformat() if r.started_at else ""} for r in runs],
        "ai_provider": get_settings().ai_provider,
    }


@router.get("/agent/logs")
async def agent_logs(limit: int = 100, db=Depends(get_session), user=Depends(get_current_user)):
    aq = select(ActivityLog).where(ActivityLog.actor.in_(["agent", "system"]))
    vis = _visible_pid_filter(user)
    if vis is not None:
        aq = aq.where(ActivityLog.project_id.in_(select(Project.id).where(vis)))
    rows = (await db.execute(aq.order_by(ActivityLog.ts.desc()).limit(limit))).scalars().all()
    return [{"id": a.id, "project_id": a.project_id, "actor": a.actor, "action": a.action,
             "subject": a.subject, "detail": a.detail[:300],
             "ts": a.ts.isoformat() if a.ts else ""} for a in rows]
