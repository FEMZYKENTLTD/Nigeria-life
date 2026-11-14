"""Research planner. Rule-based, so it works with no language model.

It reads the current state of the project and decides what to queue next, and it can explain every task it queues.
It also decides when the objective is covered — by stated criteria, not by "a page opened".
"""
from __future__ import annotations

from . import ai
from .browser.registry import best_engine, get_adapter
from .db import Approval, Evidence, Feature, Page, Project, Question, Source, Task, log
from .features import field_completeness
from .jobs import enqueue
from .knowledge import add_question


def plan(s, project: Project) -> dict:
    created, notes = [], []

    def q(kind, title, payload, priority, key, why):
        t, new = enqueue(s, project.id, kind, title, payload, priority=priority, dedupe_key=key)
        if new:
            created.append({"task_id": t.id, "kind": kind, "title": title, "priority": priority, "why": why})

    # 1. Existing repository research comes first, so nothing already documented is investigated again.
    if project.repo_path:
        imported = s.query(Evidence).filter_by(project_id=project.id, kind="import").count()
        if not imported:
            q("import_research", "Read the repository's research index and investigation log, then import existing research", {}, 5,
              f"{project.id}:import_research", "No imported research found; the repository is the project's knowledge base and is read before new work.")
    else:
        notes.append("No repository path configured: existing research cannot be read.")

    sources = s.query(Source).filter_by(project_id=project.id).all()
    if not sources:
        notes.append("No research sources configured. Add a source and have it approved.")
    engine = best_engine()
    if not get_adapter(engine).renders_js:
        notes.append("No rendering browser engine is installed: captures use plain HTTP, so JavaScript-built pages and screenshots are not available.")

    for src in sources:
        if not src.approved:
            notes.append(f"Source '{src.name}' is waiting for human approval; nothing queued for it.")
            continue
        if src.automation != "automated":
            notes.append(f"Source '{src.name}' is manual-only; evidence must be imported by a researcher.")
            add_question(s, project.id, f"Manual evidence needed for source '{src.name}' ({src.base_url}): automated collection is not permitted.", "planner")
            continue
        done = s.query(Page).filter(Page.source_id == src.id, Page.status.in_(("captured", "analysed"))).count()
        budget = max(0, src.max_pages - done)
        seed = s.query(Page).filter_by(project_id=project.id, url=src.base_url).first()
        if (not seed or seed.status == "discovered") and budget:
            q("capture_page", f"Capture seed page {src.base_url}", {"url": src.base_url}, 20, f"{project.id}:capture:{src.base_url}", f"Seed page of approved source '{src.name}'.")
            budget -= 1
        pending = s.query(Page).filter_by(source_id=src.id, status="discovered").order_by(Page.id).all()
        for pg in pending[:budget]:
            q("capture_page", f"Capture {pg.url}", {"url": pg.url}, 40, f"{project.id}:capture:{pg.url}", f"Linked from {pg.discovered_from or 'a captured page'}; inside the approved scope.")
        if len(pending) > budget:
            notes.append(f"Source '{src.name}': {len(pending) - budget} discovered page(s) exceed the page budget of {src.max_pages} and were not queued.")

    assessment = assess(s, project)
    if created:
        log(s, "plan_created", project.id, tasks=len(created), notes=notes)
    return {"created": created, "notes": notes, "assessment": assessment}


def assess(s, project: Project) -> dict:
    """Is the objective sufficiently covered? Each criterion is listed with its current state."""
    pid = project.id
    tasks = s.query(Task).filter_by(project_id=pid).all()
    by = lambda st: [t for t in tasks if t.status == st]  # noqa: E731
    discovered = s.query(Page).filter_by(project_id=pid, status="discovered").count()
    blocked_pages = s.query(Page).filter_by(project_id=pid, status="blocked").count()
    open_q = s.query(Question).filter_by(project_id=pid, status="open").count()
    feats = s.query(Feature).filter_by(project_id=pid).all()
    incomplete = sum(1 for f in feats if field_completeness(f.fields or {})[1])
    unapproved = s.query(Source).filter_by(project_id=pid, approved=False).count()
    pending_appr = s.query(Approval).filter_by(project_id=pid, status="pending").count()
    captured = s.query(Page).filter(Page.project_id == pid, Page.status.in_(("captured", "analysed"))).count()
    criteria = [
        {"criterion": "No tasks waiting or running", "met": not by("queued") and not by("running"), "detail": f"{len(by('queued'))} queued, {len(by('running'))} running"},
        {"criterion": "No failed tasks left unexplained", "met": not by("failed"), "detail": f"{len(by('failed'))} failed"},
        {"criterion": "No blocked tasks", "met": not by("blocked"), "detail": f"{len(by('blocked'))} blocked"},
        {"criterion": "Every discovered in-scope page captured", "met": discovered == 0, "detail": f"{discovered} discovered but not captured; {blocked_pages} blocked by permissions"},
        {"criterion": "At least one page captured first-hand", "met": captured > 0, "detail": f"{captured} captured"},
        {"criterion": "All sources approved or removed", "met": unapproved == 0, "detail": f"{unapproved} awaiting approval"},
        {"criterion": "No open questions", "met": open_q == 0, "detail": f"{open_q} open"},
        {"criterion": "Every feature has all 15 fields", "met": incomplete == 0 and bool(feats), "detail": f"{incomplete} of {len(feats)} features have empty fields"},
        {"criterion": "No approvals pending", "met": pending_appr == 0, "detail": f"{pending_appr} pending"},
    ]
    met = sum(c["met"] for c in criteria)
    return {"complete": met == len(criteria), "criteria_met": met, "criteria_total": len(criteria), "criteria": criteria,
            "summary": "Objective covered by all stated criteria." if met == len(criteria) else
                       f"Not complete: {len(criteria) - met} of {len(criteria)} criteria unmet."}


def agent_status(s, project: Project) -> dict:
    tasks = s.query(Task).filter_by(project_id=project.id).all()
    running = [t for t in tasks if t.status == "running"]
    counts = {st: sum(1 for t in tasks if t.status == st) for st in ("queued", "running", "done", "failed", "blocked", "cancelled")}
    recs = recommendations(s, project)
    return {"objective": project.objective, "project_status": project.status, "state": "paused" if project.status == "paused" else "working" if running or counts["queued"] else "idle",
            "current_task": running[0].title if running else None, "task_counts": counts, "ai": ai.status(),
            "pending_decisions": [a.as_dict() for a in s.query(Approval).filter_by(project_id=project.id, status="pending")],
            "recommendations": recs, "assessment": assess(s, project)}


def recommendations(s, project: Project) -> list[dict]:
    """Next-step suggestions derived from the state. Each one states the rule that produced it."""
    pid, out = project.id, []
    for t in s.query(Task).filter_by(project_id=pid, status="failed"):
        out.append({"action": f"Review failed task #{t.id}: {t.title}", "basis": (t.error or "").splitlines()[0][:200]})
    for t in s.query(Task).filter_by(project_id=pid, status="blocked"):
        out.append({"action": f"Blocked task #{t.id}: {t.title}", "basis": t.error[:200]})
    n = s.query(Source).filter_by(project_id=pid, approved=False).count()
    if n:
        out.append({"action": f"Approve or reject {n} research source(s)", "basis": "Sources are never automated before a human approves them."})
    if not get_adapter(best_engine()).renders_js:
        out.append({"action": "Install a browser engine: playwright install chromium firefox webkit", "basis": "Only the HTTP fetcher is available, so no JavaScript rendering or screenshots."})
    weak = s.query(Feature).filter(Feature.project_id == pid, Feature.confidence.in_(("secondary", "unknown", "hypothesis"))).count()
    if weak:
        out.append({"action": f"Verify {weak} feature(s) that rest on secondary or unknown evidence", "basis": "Feature confidence is the weakest class among its evidence tags."})
    oq = s.query(Question).filter_by(project_id=pid, status="open").count()
    if oq:
        out.append({"action": f"Resolve {oq} open question(s)", "basis": "Open questions imported from the investigation log or raised by the planner."})
    return out
