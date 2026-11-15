"""JWT verification + user/role/ownership primitives (see package docstring)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select

from ..config import get_settings
from ..db import get_session, session_scope
from ..models import Profile, Project

log = logging.getLogger("rice.auth")

LOCAL_USER_ID = "local"


def auth_enabled() -> bool:
    """Multi-user mode is on only when both Supabase credentials are set."""
    s = get_settings()
    return bool(s.supabase_url and s.supabase_jwt_secret)


def local_user() -> dict:
    return {"id": LOCAL_USER_ID, "email": "local@rice.local",
            "display_name": "Local operator", "role": "admin"}


def is_admin(user: dict) -> bool:
    return (user.get("role") == "admin")


def admin_emails() -> set[str]:
    s = get_settings()
    return {e.strip().lower() for e in (s.admin_emails or "").split(",") if e.strip()}


def _decode(token: str) -> dict:
    import jwt  # pyjwt

    s = get_settings()
    try:
        return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"invalid token: {str(e)[:160]}")


async def get_current_user(authorization: str | None = Header(default=None),
                           db=Depends(get_session)) -> dict:
    """Resolve the caller. Local mode → implicit admin; Supabase mode →
    verified JWT, with an idempotent profiles upsert (admin promotion is
    sticky — once admin, never silently demoted)."""
    if not auth_enabled():
        return local_user()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    claims = _decode(authorization.split(None, 1)[1].strip())
    uid = str(claims.get("sub") or "").strip()
    if not uid:
        raise HTTPException(401, "token has no subject")
    email = str(claims.get("email") or "").strip()

    async def _upsert() -> dict:
        async with session_scope() as s:
            p = (await s.execute(select(Profile).where(Profile.id == uid))).scalars().first()
            if p is None:
                p = Profile(id=uid, email=email or None,
                            display_name=(email.split("@")[0] if email else "Researcher"),
                            role="admin" if email.lower() in admin_emails() else "member")
                s.add(p)
                log.info("new profile registered: %s (%s)", p.email or uid, p.role)
            else:
                if email and p.email != email:
                    p.email = email
                if email.lower() in admin_emails() and p.role != "admin":
                    p.role = "admin"
                    log.info("profile promoted to admin: %s", email)
            p.last_seen_at = datetime.now(timezone.utc)
            await s.commit()
            return {"id": p.id, "email": p.email or "", "display_name": p.display_name,
                    "role": p.role}

    return await _upsert()


# ---------------------------------------------------------------- ownership

async def check_project_access(db, user: dict, project_id: str) -> Project:
    """Load the project and enforce ownership. 404 (not 403) for projects
    the caller may not see — no cross-user existence leaks."""
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalars().first()
    if p is None:
        raise HTTPException(404, "project not found")
    if auth_enabled() and not is_admin(user) and p.owner_id != user.get("id"):
        raise HTTPException(404, "project not found")
    return p


async def require_project_access(project_id: str,
                                 user: dict = Depends(get_current_user),
                                 db=Depends(get_session)) -> Project:
    """Drop-in dependency for any route whose path carries {project_id}."""
    return await check_project_access(db, user, project_id)


async def check_row_access(db, user: dict, model, row_id: str) -> None:
    """Ownership check for child-scoped routes (task/feature/report/... id)."""
    row = (await db.execute(select(model).where(model.id == row_id))).scalars().first()
    if row is None:
        raise HTTPException(404, "not found")
    if hasattr(row, "task_id"):  # e.g. Decision → task → project
        from ..models import ResearchTask

        task = (await db.execute(select(ResearchTask).where(ResearchTask.id == row.task_id))).scalars().first()
        if task is None:
            raise HTTPException(404, "not found")
        project_id = task.project_id
    else:
        project_id = row.project_id
    await check_project_access(db, user, project_id)


def visible_project_ids_clause(user: dict, model_project: type[Project]):
    """SQL filter for list endpoints: None = see all, else owner filter."""
    if not auth_enabled() or is_admin(user):
        return None
    return model_project.owner_id == user.get("id")


def require_admin(user: dict) -> None:
    if auth_enabled() and not is_admin(user):
        raise HTTPException(403, "admin only")
