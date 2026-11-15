"""Autonomous research agent loop.

Executes a ResearchTask's subtask plan end-to-end:

  discover → fetch → understand → document → analyse → report

Guarantees (directive §4/§15):
* a task is never "complete" because a browser opened a page — completeness
  is measured against the documented record set;
* a failed subtask is persisted with its reason; the task stops as failed
  with an explanation of what remains incomplete;
* checkpoints let a task resume after interruption (recovery on boot);
* consequential actions (new sources, permissions, publication, repo
  changes) create a Decision and wait for human approval;
* if a source cannot be captured automatically, the agent records the
  failure and proposes the manual-evidence path instead of pretending.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..db import session_scope
from ..engine import analytics
from ..engine.feature_engine import feature_from_page_record, find_similar_existing, slugify
from ..engine.ids import new_id
from ..engine.knowledge import upsert_knowledge
from ..engine.planner import heuristic_plan, llm_plan
from ..engine.reports import REPORT_TYPES, render_report
from ..models import (AgentRun, ApiConnector, CollectionScope, Decision, Evidence,
                      Feature, Observation, PageRecord, Project, Report, ResearchTask,
                      Subtask, UnresolvedQuestion)

log = logging.getLogger("rice.agent")

_running: dict[str, asyncio.Task] = {}


def is_running(task_id: str) -> bool:
    t = _running.get(task_id)
    return bool(t and not t.done())


def cancel(task_id: str) -> bool:
    t = _running.get(task_id)
    if t and not t.done():
        t.cancel()
        return True
    return False


async def _load_project_ctx(project_id: str) -> dict:
    async with session_scope() as s:
        project = (await s.execute(select(Project).where(Project.id == project_id))).scalars().first()
        if project is None:
            raise ValueError(f"project {project_id} not found")
        tasks = (await s.execute(select(ResearchTask).where(ResearchTask.project_id == project_id))).scalars().all()
        pages = (await s.execute(select(PageRecord).where(PageRecord.project_id == project_id))).scalars().all()
        features = (await s.execute(select(Feature).where(Feature.project_id == project_id))).scalars().all()
        evidence = (await s.execute(select(Evidence).where(Evidence.project_id == project_id))).scalars().all()
        observations = (await s.execute(select(Observation).where(Observation.project_id == project_id))).scalars().all()
        questions = (await s.execute(
            select(UnresolvedQuestion).where(UnresolvedQuestion.project_id == project_id)
        )).scalars().all()
    return {
        "project": _p(project),
        "tasks": [_t(t) for t in tasks],
        "pages": [_p(p) for p in pages],
        "features": [_f(f) for f in features],
        "evidence": [_e(e) for e in evidence],
        "observations": [_o(o) for o in observations],
        "questions": [{"id": q.id, "question": q.question, "status": q.status} for q in questions],
    }


def _p(m) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns}


def _t(m) -> dict:
    d = _p(m)
    d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else ""
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else ""
    return d


def _f(m) -> dict:
    return {c.name: getattr(m, c.name) for c in m.__table__.columns}


def _e(m) -> dict:
    d = _p(m)
    cited: list[str] = []
    d["captured_at"] = d["captured_at"].isoformat() if d.get("captured_at") else ""
    d["cited_by"] = cited
    return d


def _o(m) -> dict:
    d = _p(m)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else ""
    return d


async def _set_task(task_id: str, **kw) -> None:
    async with session_scope() as s:
        t = (await s.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
        for k, v in kw.items():
            setattr(t, k, v)


async def _subtasks_of(task_id: str) -> list[Subtask]:
    async with session_scope() as s:
        return list((await s.execute(
            select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.idx)
        )).scalars().all())


async def _set_subtask(sub_id: str, **kw) -> None:
    async with session_scope() as s:
        st = (await s.execute(select(Subtask).where(Subtask.id == sub_id))).scalars().first()
        if st is None:
            return
        for k, v in kw.items():
            setattr(st, k, v)


async def _activity(project_id: str, action: str, subject: str, detail: str, actor: str = "agent") -> None:
    from ..models import ActivityLog

    async with session_scope() as s:
        s.add(ActivityLog(project_id=project_id, actor=actor, action=action,
                          subject=subject[:300], detail=detail[:1000]))


# ---------------------------------------------------------------- subtask handlers

async def _h_discover(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    project = ctx["project"]
    sources = []
    async with session_scope() as s:
        from ..models import Source
        rows = (await s.execute(
            select(Source).where(Source.project_id == task.project_id)
        )).scalars().all()
        sources = [{"id": r.id, "url": r.url, "status": r.status, "domain": r.domain} for r in rows]
    urls: list[str] = []
    for u in (task.plan or {}).get("url_queue", []):
        if u not in urls:
            urls.append(u)
    for src in sources:
        if src["status"] == "authorised" and src["url"] and src["url"] not in urls:
            urls.append(src["url"])
    if project.get("target_base_url") and project["target_base_url"] not in urls:
        urls.insert(0, project["target_base_url"])
    st.checkpoint = {"url_queue": urls[:50]}
    return {"url_queue": urls[:50], "count": len(urls[:50])}


class SubtaskSkip(Exception):
    """Handler asks the loop to mark the subtask skipped (honest, explained)."""


async def _scope_for(project_id: str, domain: str) -> dict | None:
    """Per-domain collection scope, with the project's '*' default row as
    fallback. Returns a plain dict (the ORM row is detached after the
    session closes)."""
    from ..models import CollectionScope

    async with session_scope() as s:
        rows = (await s.execute(
            select(CollectionScope).where(CollectionScope.project_id == project_id)
        )).scalars().all()
    wildcard = next((r for r in rows if r.domain == "*"), None)
    exact = next((r for r in rows if r.domain == domain), None)
    r = exact or wildcard
    if r is None:
        return None
    return {"id": r.id, "domain": r.domain, "allowed_methods": r.allowed_methods or [],
            "min_delay_s": r.min_delay_s, "max_pages": r.max_pages,
            "robots_mode": r.robots_mode, "note": r.note}


async def _h_fetch(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    """One fetch subtask. The description carries the target URL (set by the
    planner). Enforces the per-domain collection scope (allowed methods,
    politeness delay, page cap, robots.txt) and project permissions; a
    restricted URL is gated to a human decision, never bypassed. Failures are
    recorded and trigger the manual-evidence path."""
    from urllib.parse import urlparse

    from ..config import get_settings
    from . import http_fetch, robots
    from .browser.manager import run_capture

    desc = st.description
    url = st.checkpoint.get("url") or _extract_url(desc)
    if not url:
        raise RuntimeError("fetch subtask has no URL in description/checkpoint")
    project = ctx["project"]
    perms = project.get("permissions") or {}
    settings = get_settings()

    domain = urlparse(url).netloc
    scope = await _scope_for(task.project_id, domain)
    if scope is not None:
        # an explicit scope row wins; an empty method list means manual-only
        methods = scope.get("allowed_methods") or ["manual"]
    else:
        methods = perms.get("collection_methods") or ["browser"]

    # --- page cap: honest, explained skip (not a silent drop) ---
    max_pages = int((scope or {}).get("max_pages") or settings.max_pages_per_session)
    async with session_scope() as s:
        siblings = (await s.execute(
            select(Subtask).where(Subtask.task_id == task.id, Subtask.type == "fetch")
        )).scalars().all()
    done = sum(1 for sib in siblings if sib.idx < st.idx and sib.status == "complete")
    if done >= max_pages:
        raise SubtaskSkip(
            f"collection page cap reached for {domain or '(no domain)'} (scope max_pages={max_pages}); "
            "this URL was not fetched — extend the scope with an approved decision if it is required"
        )

    # --- robots.txt: respected unless a human approved an exception ---
    if scope and scope.get("robots_mode") == "approved_exception":
        pass  # sign-off recorded on the scope row
    else:
        status, detail = await robots.robots_status(url)
        if status == "disallowed":
            raise PermissionGate(
                f"robots.txt for {domain} disallows automated fetch of this URL ({detail}). "
                "Sanctioned paths: import the evidence manually, or have the researcher approve a "
                "robots exception for this domain's collection scope."
            )

    # --- politeness delay (per scope or platform default) ---
    delay = float((scope or {}).get("min_delay_s") or settings.default_delay_between_fetches_s)

    # --- method dispatch: http (polite GET + ETag cache) then browser ---
    if "http" in methods:
        res = await http_fetch.fetch_page(task.project_id, url, delay_s=delay)
        if res.get("ok"):
            st.checkpoint["page_id"] = res.get("page_id", "")
            return {**res, "method": "http"}
        if "browser" in methods:
            log.info("HTTP capture failed for %s (%s) — falling back to browser",
                     url, (res.get("error") or "")[:160])
        else:
            raise RuntimeError(f"HTTP capture failed for {url}: {res.get('error')} (browser not in scope)")
    if "browser" in methods:
        if "http" not in methods:
            await asyncio.sleep(delay)  # politeness delay applies to browser too
        result = await run_capture(
            project_id=task.project_id,
            source_url=url,
            task_id=task.id,
            max_retries=1,
        )
        if not result.get("ok"):
            err = result.get("error", "capture failed")
            low_err = err.lower()
            if "binar" in low_err or "adapter" in low_err or "playwright install" in low_err:
                # environmental: everything will fail the same way → surface as a
                # decision to switch to manual evidence instead of burning retries.
                raise PermissionGate(
                    f"Browser capture unavailable ({err}). Approve manual evidence import to "
                    "continue, or install browser binaries on the host."
                )
            raise RuntimeError(f"Capture failed for {url}: {err}")
        st.checkpoint["page_id"] = result.get("page_id", "")
        return {**result, "method": "browser"}
    raise PermissionGate(
        f"No automated collection method is allowed for {domain or url} (scope methods: "
        f"{', '.join(methods) or 'none'}). Approve manual evidence import."
    )


def _extract_url(text: str) -> str:
    import re
    m = re.search(r"(https?://[^\s,]+)", text or "")
    return m.group(1) if m else ""


class PermissionGate(Exception):
    """Raised when a step requires a human decision (approval gate)."""


async def _h_understand(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    """Re-analyse any captured HTML we have stored (from fetch or import)."""
    from ..engine.page_understanding import analyze_html

    async with session_scope() as s:
        pages = list((await s.execute(
            select(PageRecord).where(
                PageRecord.project_id == task.project_id,
                PageRecord.status.in_(["pending", "error", "documented"]),
            )
        )).scalars().all())
    updated = 0
    kb_updates: list[tuple[str, str, str, str]] = []
    async with session_scope() as s:
        rows = list((await s.execute(
            select(PageRecord).where(PageRecord.project_id == task.project_id)
        )).scalars().all())
        for pg in rows:
            if pg.structure and (pg.structure.get("sections") or pg.structure.get("forms")
                                 or pg.structure.get("controls")):
                continue  # already understood
            body = pg.body_text or ""
            if not body or pg.error:
                continue
            if not pg.structure:
                wrapper = (f"<html><head><title>{pg.title or ''}</title></head>"
                           f"<body><p>{body[:8000]}</p></body></html>")
                analysis = analyze_html(wrapper, url=pg.url)
                pg.structure = {k: analysis[k] for k in
                                ("regions", "navigation", "forms", "controls", "interactive",
                                 "buttons", "sections", "links", "images", "states",
                                 "repeated_components", "element_counts")}
                pg.title = pg.title or analysis.get("title", "")
                pg.content_category = pg.content_category or analysis.get("content_category", "")
                pg.purpose = pg.purpose or analysis.get("purpose", "")
                pg.summary = pg.summary or analysis.get("summary", "")
                pg.status = "documented"
                pg.observed_at = datetime.now(timezone.utc)
                updated += 1
                kb_updates.append((pg.id, pg.title or pg.url, pg.purpose,
                                   f"{pg.summary} {pg.body_text[:4000]}"))
    for pid_, title, purpose, body in kb_updates:
        await upsert_knowledge(task.project_id, "page", pid_, f"Page: {title}",
                               f"{purpose} {body[:4000]}")
    return {"pages_reviewed": len(rows), "pages_updated": updated}


async def _h_document(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    """Extract/upsert features from structured page records."""
    created, merged = 0, 0
    kb_updates: list[tuple[str, str, str, str, str, str]] = []
    async with session_scope() as s:
        pages = list((await s.execute(
            select(PageRecord).where(PageRecord.project_id == task.project_id,
                                     PageRecord.status == "documented")
        )).scalars().all())
        features = list((await s.execute(
            select(Feature).where(Feature.project_id == task.project_id)
        )).scalars().all())
        existing_dicts = [{"name": f.name, "id": f.id, "description": f.description or ""}
                          for f in features]
    for pg in pages:
        ev_refs = pg.evidence_ids or []
        page_dict = {
            "url": pg.url, "title": pg.title, "purpose": pg.purpose,
            "summary": pg.summary, "content_category": pg.content_category,
            "status": pg.status, "structure": pg.structure or {},
            "evidence_refs": ev_refs,
        }
        for cand in feature_from_page_record(page_dict):
            similar = find_similar_existing(cand["name"], existing_dicts)
            slug = slugify(cand["name"])
            async with session_scope() as s:
                if similar:
                    feat = (await s.execute(select(Feature).where(Feature.id == similar["id"]))).scalars().first()
                    if cand.get("access_location") and not feat.access_location:
                        feat.access_location = cand["access_location"]
                    if cand.get("description") and len(cand["description"]) > len(feat.description or ""):
                        feat.description = cand["description"][:1000]
                    if not feat.evidence_ids:
                        feat.evidence_ids = ev_refs
                    merged += 1
                    kb_updates.append((feat.id, feat.name, feat.description or "",
                                       feat.purpose or "", feat.observed_behaviour or "",
                                       feat.limitations or ""))
                else:
                    feat = Feature(
                        id=new_id(), project_id=task.project_id, name=cand["name"][:200],
                        slug=slug, category=cand["category"], description=cand["description"],
                        purpose=cand["purpose"], user_type=cand["user_type"],
                        access_location=cand["access_location"], inputs=cand["inputs"],
                        outputs=cand["outputs"], observed_behaviour=cand["observed_behaviour"],
                        dependencies=[], related_features=[], user_journey="",
                        limitations=cand["limitations"], opportunities=cand["opportunities"],
                        implementation_implications=cand["implementation_implications"],
                        evidence_ids=ev_refs, confidence=cand["confidence"], status=cand["status"],
                    )
                    s.add(feat)
                    await s.flush()
                    existing_dicts.append({"name": feat.name, "id": feat.id,
                                           "description": feat.description or ""})
                    created += 1
                    kb_updates.append((feat.id, feat.name, feat.description or "",
                                       feat.purpose or "", feat.observed_behaviour or "",
                                       feat.limitations or ""))
    for fid_, name, desc, purpose, beh, lim in kb_updates:
        await upsert_knowledge(task.project_id, "feature", fid_, f"Feature: {name}",
                               f"{desc} {purpose} {beh} {lim}")
    return {"features_created": created, "features_merged": merged, "features_total": len(existing_dicts)}


async def _h_analyse(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    ctx2 = await _load_project_ctx(task.project_id)
    a = analytics.full_project_analytics(
        ctx2["project"], ctx2["pages"], ctx2["features"],
        ctx2["evidence"], ctx2["observations"], ctx2["questions"],
    )
    # store snapshot as a note observation for the record
    async with session_scope() as s:
        s.add(Observation(
            id=new_id(), project_id=task.project_id, kind="note",
            observation=(f"Analytics snapshot: completeness={a['research_completeness']['score']}, "
                         f"features={len(ctx2['features'])}, pages={a['page_coverage']['documented']}/{a['page_coverage']['total']}, "
                         f"evidence_quality={a['evidence_quality']['score']}, open_questions={a['missing_information']['open_questions']}"),
            confidence=1.0, status="verified", created_by="agent",
        ))
    return {
        "completeness": a["research_completeness"]["score"],
        "features": len(ctx2["features"]),
        "pages": f"{a['page_coverage']['documented']}/{a['page_coverage']['total']}",
        "evidence_quality": a["evidence_quality"]["score"],
    }


async def _h_report(task: ResearchTask, st: Subtask, ctx: dict) -> dict:
    rtype = _report_type_from(st.description)
    if rtype not in REPORT_TYPES:
        raise RuntimeError(f"Unknown report type in subtask: {rtype}")
    ctx2 = await _load_project_ctx(task.project_id)
    ctx2["analytics"] = analytics.full_project_analytics(
        ctx2["project"], ctx2["pages"], ctx2["features"],
        ctx2["evidence"], ctx2["observations"], ctx2["questions"],
    )
    ctx2["reports"] = []
    content = render_report(rtype, ctx2, "md")
    report = Report(id=new_id(), project_id=task.project_id, type=rtype,
                    title=f"{REPORT_TYPES[rtype]} — {ctx2['project']['name']}",
                    format="md", content=content)
    async with session_scope() as s:
        s.add(report)
        await s.flush()
    await upsert_knowledge(task.project_id, "report", report.id, report.title, content[:12000])
    await _activity(task.project_id, "report.generated", report.title, f"type={rtype}")
    return {"report_id": report.id, "type": rtype, "chars": len(content)}


def _report_type_from(desc: str) -> str:
    import re
    m = re.search(r"report:\s*([a-z_]+)", desc or "")
    return m.group(1) if m else "completion_report"


HANDLERS = {
    "discover": _h_discover,
    "fetch": _h_fetch,
    "understand": _h_understand,
    "document": _h_document,
    "analyse": _h_analyse,
    "report": _h_report,
}


# ---------------------------------------------------------------- main loop

async def execute_task(task_id: str) -> None:
    async with session_scope() as s:
        task = (await s.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
    if task is None:
        log.error("execute_task: task %s not found", task_id)
        return

    run = AgentRun(id=new_id(), project_id=task.project_id, task_id=task.id,
                   mode="offline-heuristic", status="running")
    async with session_scope() as s:
        s.add(run)
    run_id = run.id

    def _rlog(msg: str) -> None:
        run.log.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": msg[:500]})

    try:
        await _set_task(task_id, status="planned", error="")
        _rlog(f"Task '{task.title}' started (mode=offline-heuristic)")

        # ---- planning ----
        if not (task.plan or {}).get("subtasks"):
            ctx = await _load_project_ctx(task.project_id)
            from ..ai.registry import resolve_adapter
            from ..models import Source
            async with session_scope() as s:
                src_rows = (await s.execute(
                    select(Source).where(Source.project_id == task.project_id)
                )).scalars().all()
            sources = [{"id": r.id, "url": r.url, "status": r.status} for r in src_rows]
            adapter, degraded = await resolve_adapter(complexity="complex")
            if adapter.name == "offline-heuristic":
                plan = heuristic_plan(ctx["project"], _t(task), sources)
                run.mode = "offline-heuristic"
            else:
                from ..models import Source
                async with session_scope() as s:
                    srcs = (await s.execute(
                        select(Source).where(Source.project_id == task.project_id)
                    )).scalars().all()
                sources = [{"id": r.id, "url": r.url, "status": r.status} for r in srcs]
                plan = llm_plan(ctx["project"], _t(task), sources, adapter)
                run.mode = f"provider:{adapter.name}"
                if degraded:
                    run.mode = "offline-heuristic (provider degraded)"
                    plan = heuristic_plan(ctx["project"], _t(task), sources)
            async with session_scope() as s:
                t2 = (await s.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
                t2.plan = plan
                # materialise subtasks
                for st_def in plan["subtasks"]:
                    s.add(Subtask(
                        id=st_def["id"], task_id=task.id, idx=st_def["idx"],
                        type=st_def["type"], description=st_def["description"],
                        status="queued", priority=st_def.get("priority", 3),
                        requires_approval=st_def.get("requires_approval", False),
                        max_attempts=st_def.get("max_attempts", 1),
                    ))
                t2.status = "planned"
            _rlog(f"Plan created by {plan.get('planner')}: {len(plan['subtasks'])} subtasks")
        else:
            _rlog("Resuming with existing plan (recovery)")
            run.mode = "resume"

        # materialise subtasks if the plan exists but DB rows do not (recovery)
        async with session_scope() as s:
            db_sub_count = (await s.execute(
                select(Subtask).where(Subtask.task_id == task_id)
            )).scalars().all()
            if not db_sub_count and (task.plan or {}).get("subtasks"):
                from sqlalchemy import func
                t2 = (await s.execute(select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
                for st_def in t2.plan["subtasks"]:
                    s.add(Subtask(
                        id=st_def["id"], task_id=task.id, idx=st_def["idx"],
                        type=st_def["type"], description=st_def["description"],
                        status="queued", priority=st_def.get("priority", 3),
                        requires_approval=st_def.get("requires_approval", False),
                        max_attempts=st_def.get("max_attempts", 1),
                    ))
                _rlog("Materialised subtasks from persisted plan")

        # ---- execution ----
        # Hard iteration cap: the loop must NEVER spin. If it does, the task
        # is marked failed with an explanation (honest failure).
        MAX_ITER = 250
        for _iter in range(MAX_ITER):
            subtasks = await _subtasks_of(task_id)
            pending = [st for st in subtasks if st.status in ("queued", "running")]
            if not pending:
                break
            st = min(pending, key=lambda x: (x.priority, x.idx))
            handler = HANDLERS.get(st.type)
            if handler is None:
                await _set_subtask(st.id, status="skipped", last_error=f"no handler for type {st.type}")
                _rlog(f"Subtask {st.idx} skipped (no handler for {st.type})")
                continue

            if st.requires_approval and not st.decision_id:
                # create a decision and wait for human
                kind = "manual_evidence" if st.type == "fetch" else "other"
                decision = Decision(
                    id=new_id(), project_id=task.project_id, task_id=task.id, kind=kind,
                    question=f"Approve: {st.description[:300]} — {st.last_error[:200]}",
                    context={"subtask_id": st.id, "type": st.type},
                )
                async with session_scope() as s:
                    s.add(decision)
                    await s.flush()
                await _set_subtask(st.id, status="waiting_decision", decision_id=decision.id,
                                   last_error=st.last_error or "requires approval")
                _rlog(f"Subtask {st.idx} → waiting on decision {decision.id}")
                break  # agent pauses; approval endpoint resumes it

            await _set_subtask(st.id, status="running", started_at=datetime.now(timezone.utc),
                               attempts=st.attempts + 1)
            _rlog(f"Subtask {st.idx} ({st.type}) running — {st.description[:160]}")
            ctx = await _load_project_ctx(task.project_id)
            try:
                out = await handler(task, st, ctx)
                await _set_subtask(st.id, status="complete", output=out or {},
                                   finished_at=datetime.now(timezone.utc), last_error="")
                _rlog(f"Subtask {st.idx} complete: {out}")
            except PermissionGate as pg:
                # persist the gate on the DB row — the next loop iteration
                # re-reads the subtask and will create the human decision.
                await _set_subtask(st.id, requires_approval=True, last_error=str(pg))
                _rlog(f"Subtask {st.idx} gated: {pg}")
                continue  # next loop iteration creates the decision
            except SubtaskSkip as sk:
                await _set_subtask(st.id, status="skipped", last_error=str(sk),
                                   finished_at=datetime.now(timezone.utc))
                _rlog(f"Subtask {st.idx} skipped: {sk}")
                continue
            except asyncio.CancelledError:
                await _set_subtask(st.id, status="queued", started_at=None)
                await _set_task(task_id, status="paused")
                _rlog("Task cancelled/paused by user")
                raise
            except Exception as e:
                msg = f"{e.__class__.__name__}: {str(e)[:300]}"
                if st.attempts < st.max_attempts and st.type in ("fetch",):
                    _rlog(f"Subtask {st.idx} attempt {st.attempts}/{st.max_attempts} failed, will retry: {msg}")
                    await _set_subtask(st.id, status="queued", last_error=msg)
                    continue
                await _set_subtask(st.id, status="failed", last_error=msg,
                                   finished_at=datetime.now(timezone.utc))
                await _set_task(task_id, status="failed", error=msg,
                                result_summary=await _incomplete_summary(task_id))
                _rlog(f"Subtask {st.idx} FAILED (task stopped, not silent): {msg}")
                await _activity(task.project_id, "task.failed", task.title, msg)
                break
        else:
            # for/else: cap hit — the loop failed to converge
            msg = f"Agent loop hit its {MAX_ITER}-iteration safety cap; task stopped to avoid a spin. See subtask logs."
            await _set_task(task_id, status="failed", error=msg,
                            result_summary=await _incomplete_summary(task_id))
            _rlog("SAFETY CAP HIT — stopped")
            await _activity(task.project_id, "task.failed", task.title, msg)

        # ---- final state ----
        subtasks = await _subtasks_of(task_id)
        done = sum(1 for x in subtasks if x.status == "complete")
        total = len(subtasks) or 1
        failed_any = any(x.status == "failed" for x in subtasks)
        waiting = any(x.status == "waiting_decision" for x in subtasks)
        progress = done / total * 100
        await _set_task(task_id, progress=progress,
                        status="failed" if failed_any else ("waiting_decision" if waiting else "complete"),
                        updated_at=datetime.now(timezone.utc))
        if not failed_any and not waiting:
            await _set_task(task_id, result_summary=(
                f"All {total} subtasks complete. Pages documented: see page inventory; "
                "completeness score in Analytics. Remaining gaps are listed in the "
                "completion report — none are claimed as closed."
            ))
            _rlog(f"Task complete: {done}/{total} subtasks")
            await _activity(task.project_id, "task.completed", task.title, f"{done}/{total} subtasks")

        async with session_scope() as s:
            r = (await s.execute(select(AgentRun).where(AgentRun.id == run_id))).scalars().first()
            r.status = "complete" if not failed_any else "failed"
            r.finished_at = datetime.now(timezone.utc)
    except asyncio.CancelledError:
        async with session_scope() as s:
            r = (await s.execute(select(AgentRun).where(AgentRun.id == run_id))).scalars().first()
            r.status = "failed"
            r.finished_at = datetime.now(timezone.utc)
        raise
    except Exception as e:
        msg = f"{e.__class__.__name__}: {str(e)[:300]}"
        _rlog(f"Agent run crashed: {msg}")
        await _set_task(task_id, status="failed", error=msg)
        async with session_scope() as s:
            r = (await s.execute(select(AgentRun).where(AgentRun.id == run_id))).scalars().first()
            if r:
                r.status = "failed"
                r.finished_at = datetime.now(timezone.utc)
        raise


async def _incomplete_summary(task_id: str) -> str:
    subs = await _subtasks_of(task_id)
    failed = [s for s in subs if s.status == "failed"]
    remaining = [s for s in subs if s.status in ("queued", "waiting_decision")]
    parts = []
    for s in failed[:3]:
        parts.append(f"failed at {s.type}: {s.last_error[:160]}")
    if remaining:
        parts.append(f"{len(remaining)} subtask(s) remain: " + ", ".join(s.type for s in remaining[:8]))
    return "Stopped with incomplete work (never silently dropped): " + "; ".join(parts)


def start_task(task_id: str) -> str:
    """Launch execute_task in the background; returns a run handle id."""
    t = asyncio.get_event_loop().create_task(execute_task(task_id))
    _running[task_id] = t
    t.add_done_callback(lambda _t: _running.pop(task_id, None))
    return task_id


async def resume_after_decision(decision_id: str, approved: bool) -> None:
    task_id = ""
    ctx: dict = {}
    async with session_scope() as s:
        d = (await s.execute(select(Decision).where(Decision.id == decision_id))).scalars().first()
        if d is None:
            return
        d.status = "approved" if approved else "rejected"
        d.decided_at = datetime.now(timezone.utc)
        task_id = d.task_id
        ctx = d.context or {}
        st_id = ctx.get("subtask_id", "")
        if st_id:
            st = (await s.execute(select(Subtask).where(Subtask.id == st_id))).scalars().first()
            if st is not None:
                if approved:
                    st.status = "queued"
                    st.requires_approval = False
                    st.decision_id = ""
                else:
                    st.status = "skipped"
                    st.decision_id = ""
                    st.last_error = "rejected by researcher"
        await s.commit()

    # non-task side effects of a human decision (their own sessions, so the
    # decision commit above is already durable)
    if approved and ctx.get("connector_id"):
        async with session_scope() as s:
            c = (await s.execute(
                select(ApiConnector).where(ApiConnector.id == ctx["connector_id"])
            )).scalars().first()
            if c is not None and c.status == "pending_approval":
                c.status = "active"
                c.error = ""
            await s.commit()
    if approved and ctx.get("scope_id") and ctx.get("robots_exception"):
        async with session_scope() as s:
            sc = (await s.execute(
                select(CollectionScope).where(CollectionScope.id == ctx["scope_id"])
            )).scalars().first()
            if sc is not None:
                sc.robots_mode = "approved_exception"
                sc.note = (sc.note + " | " if sc.note else "") + "robots exception approved by researcher"
            await s.commit()

    if approved and task_id:
        start_task(task_id)
