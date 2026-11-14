"""Human approval gate. The engine proposes; a person decides; only then is the action executed."""
from __future__ import annotations

from . import github, permissions, reports
from .db import Approval, Project, Source, log, now

GATED = {"approve_source": "Start using a third-party source", "change_permissions": "Change collection permissions for a source",
         "publish_to_repo": "Commit generated documents to the repository on a new branch", "delete_project_data": "Delete research data"}


def request(s, project_id: int, action: str, summary: str, payload: dict) -> Approval:
    if action not in GATED:
        raise ValueError(f"Unknown gated action '{action}'")
    for a in s.query(Approval).filter_by(project_id=project_id, action=action, status="pending"):
        if a.payload == payload:
            return a
    a = Approval(project_id=project_id, action=action, summary=summary[:600], payload=payload)
    s.add(a)
    s.flush()
    log(s, "approval_requested", project_id, action=action, summary=summary)
    return a


def decide(s, approval_id: int, approve: bool, decided_by: str = "human") -> Approval:
    a = s.get(Approval, approval_id)
    if a is None:
        raise KeyError("No such approval")
    if a.status != "pending":
        raise ValueError(f"Already {a.status}")
    a.decided_by, a.decided_at = decided_by, now()
    if not approve:
        a.status = "rejected"
        log(s, "approval_rejected", a.project_id, actor=decided_by, action=a.action)
        return a
    try:
        a.result = _execute(s, a)
        a.status = "approved"
        log(s, "approval_executed", a.project_id, actor=decided_by, action=a.action, result=a.result)
    except Exception as e:  # the approval stays visible with the reason; it is not lost
        a.status, a.result = "approved", {"error": f"{type(e).__name__}: {e}"}
        log(s, "approval_execution_failed", a.project_id, level="error", actor=decided_by, action=a.action, error=str(e))
    return a


def _execute(s, a: Approval) -> dict:
    p = a.payload
    if a.action in ("approve_source", "change_permissions"):
        src = s.get(Source, p["source_id"])
        for k in ("automation", "max_pages", "allowed_paths", "rate_limit_seconds", "respect_robots", "capture_screenshots"):
            if k in p:
                setattr(src, k, p[k])
        src.approved = True
        permissions.clear_cache()
        return {"source": src.name, "automation": src.automation, "approved": True}
    if a.action == "publish_to_repo":
        project = s.get(Project, a.project_id)
        files = {}
        for kind in p["kinds"]:
            files[f"{p.get('folder', 'docs/engine/generated')}/{kind}.md"] = reports.to_md(reports.build(s, project, kind))
        return github.publish(project.repo_path, p["branch"], files, p.get("message", "Add generated research reports"),
                              push=p.get("push", False), open_pr=p.get("open_pr", False), pr_title=p.get("message", ""), pr_body=p.get("pr_body", ""))
    if a.action == "delete_project_data":
        raise NotImplementedError("Deletion is not implemented; nothing was removed.")
    raise ValueError(a.action)
