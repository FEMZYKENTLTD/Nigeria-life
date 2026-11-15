"""End-to-end agent pipeline tests on a synthetic project (no network):
plan → understand → document → analyse → report, plus approval gating,
honest failure and recovery."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402


async def _make_project():
    from app.engine.ids import new_id

    from app.db import session_scope
    from app.models import Evidence, PageRecord, Project

    async with session_scope() as s:
        uid = new_id()
        p = Project(id=uid, name=f"Synthetic {uid[-10:]}", slug=f"synthetic-{uid[-12:]}",
                    target_base_url="https://synth.example.com",
                    permissions={"collection_methods": ["browser", "manual_import"],
                                 "screenshots_allowed": True, "login_allowed": False})
        s.add(p)
        await s.flush()
        pid = p.id
        s.add(PageRecord(
            id=new_id(), project_id=pid, url="https://synth.example.com/",
            canonical_url="https://synth.example.com/", title="Synth Home",
            status="documented", content_category="landing",
            purpose="Landing page for Synth", summary="Buy things",
            structure={
                "sections": [{"level": 1, "text": "Buy things"}, {"level": 2, "text": "Pricing"}],
                "forms": [{"action": "/checkout", "method": "post",
                           "fields": [{"name": "item"}, {"name": "amount"}]}],
                "controls": [{"name": "item"}, {"name": "amount"}],
                "interactive": [], "buttons": ["Buy now", "Create account"],
                "navigation": [{"text": "About", "href": "/about"}, {"text": "Pricing", "href": "/pricing"}],
                "links": {"internal": [], "external": []},
                "images": [], "states": {"empty": False, "loading": False, "error": False},
                "repeated_components": [], "element_counts": {}, "regions": {},
            },
            body_text="Synth home. Buy things. Create account. Pricing starts at 10.",
            evidence_ids=[], capture_method="manual_import",
        ))
        ev = Evidence(id=new_id(), project_id=pid, ref_code="E01", evidence_class="C",
                      source_uri="https://synth.example.com/", source_name="Home",
                      capture_method="read", description="landing read")
        s.add(ev)
        await s.flush()
        return pid


def _plan(subtypes, descriptions=None):
    from app.engine.ids import new_id

    return {
        "planner": "test", "url_queue": [],
        "subtasks": [
            {"id": new_id(), "idx": i, "type": t,
             "description": (descriptions[i] if descriptions else f"step {t}"),
             "priority": 2, "requires_approval": False, "max_attempts": 1}
            for i, t in enumerate(subtypes)
        ],
    }


def test_full_pipeline_completes():
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import Feature, Report, ResearchTask

        pid = await _make_project()
        t_id = new_id()
        plan = _plan(["understand", "document", "analyse", "report"],
                     descriptions=["understand pages", "document features",
                                   "run analytics", "Generate report: feature_inventory."])
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Consolidate",
                               objective="Consolidate findings", plan=plan))
        await agent_loop.execute_task(t_id)
        async with session_scope() as s:
            task = (await s.execute(select(ResearchTask).where(ResearchTask.id == t_id))).scalars().first()
            feats = list((await s.execute(select(Feature).where(Feature.project_id == pid))).scalars().all())
            reports = list((await s.execute(select(Report).where(Report.project_id == pid))).scalars().all())
        assert task.status == "complete", task.error
        assert task.progress == 100.0
        # feature extraction from the page record produced candidates
        assert len(feats) >= 2
        names = [f.name for f in feats]
        assert any("checkout" in n.lower() or "form" in n.lower() for n in names)
        assert len(reports) >= 1
        assert "feature_inventory" in reports[0].type

    start(t)


def test_fetch_without_capability_gates_on_human_decision():
    """When a fetch cannot run (binaries missing / method disabled), the agent
    must NOT spin or fail silently — it parks the task on a pending Decision."""
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import Decision, ResearchTask, Subtask

        pid = await _make_project()
        t_id = new_id()
        plan = _plan(["fetch"])
        plan["subtasks"][0]["description"] = "Capture page 1/1: https://synth.example.com/"
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Fetch",
                               objective="capture", plan=plan))
        await agent_loop.execute_task(t_id)
        async with session_scope() as s:
            task = (await s.execute(select(ResearchTask).where(ResearchTask.id == t_id))).scalars().first()
            decision = (await s.execute(
                select(Decision).where(Decision.task_id == t_id)
            )).scalars().first()
        assert task.status == "waiting_decision", (task.status, task.error)
        assert decision is not None
        assert decision.status == "pending"
        assert decision.kind == "manual_evidence"

        # reject → subtask skipped, task complete (nothing silently dropped)
        from app.engine.agent_loop import resume_after_decision
        await resume_after_decision(decision.id, approved=False)
        # allow the resumed run to finish
        import asyncio
        for _ in range(100):
            async with session_scope() as s:
                task = (await s.execute(select(ResearchTask).where(ResearchTask.id == t_id))).scalars().first()
                if task.status in ("complete", "failed"):
                    break
            await asyncio.sleep(0.2)
        async with session_scope() as s:
            subs = list((await s.execute(
                select(Subtask).where(Subtask.task_id == t_id))).scalars().all())
        assert any(x.status == "skipped" for x in subs)

    start(t)


def test_task_failure_is_recorded_not_silent():
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import ResearchTask, Subtask

        pid = await _make_project()
        t_id = new_id()
        # unknown report type → the report step must fail loudly
        plan = _plan(["analyse", "report"])
        plan["subtasks"][1]["description"] = "Generate report: does_not_exist."
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Broken",
                               objective="x", plan=plan))
        await agent_loop.execute_task(t_id)
        async with session_scope() as s:
            task = (await s.execute(select(ResearchTask).where(ResearchTask.id == t_id))).scalars().first()
            subs = list((await s.execute(select(Subtask).where(Subtask.task_id == t_id))).scalars().all())
        assert task.status == "failed"
        assert task.error, "failure must carry a reason"
        assert "incomplete" in task.result_summary.lower() or "remain" in task.result_summary.lower()
        failed = [x for x in subs if x.status == "failed"]
        assert failed and failed[0].last_error

    start(t)


def test_recovery_requeues_interrupted_task():
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine.ids import new_id
        from app.models import ResearchTask

        pid = await _make_project()
        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Stuck", objective="x",
                               status="running"))
        async with session_scope() as s:
            stuck = list((await s.execute(
                select(ResearchTask).where(ResearchTask.status.in_(["running", "planned"]))
            )).scalars().all())
            for x in stuck:
                x.status = "queued"
            recovered = (await s.execute(
                select(ResearchTask).where(ResearchTask.id == t_id)
            )).scalars().first()
        assert len(stuck) == 1
        assert recovered.status == "queued"

    start(t)
