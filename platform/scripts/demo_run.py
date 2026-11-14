"""End-to-end demonstration of the autonomous research pipeline against the
seeded Lagos Life project (no external network required):

  seed → plan → understand → document → analyse → reports → GitHub sync

Run:  python scripts/demo_run.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("RICE_DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
os.environ.setdefault("RICE_LOCAL_REPO_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import bootstrap_async, close_db, session_scope  # noqa: E402
from app.engine import analytics, agent_loop  # noqa: E402
from app.engine.ids import new_id  # noqa: E402
from app.engine.reports import render_report  # noqa: E402
from app.github_int.client import get_adapter  # noqa: E402
from app.models import (Feature, Observation, PageRecord, Project,  # noqa: E402
                        Report, ResearchTask)
from app.schemas import TaskIn  # noqa: E402


def step(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


async def main() -> None:
    await bootstrap_async()
    s = get_settings()

    step("1. Load project")
    async with session_scope() as sess:
        p = (await sess.execute(select(Project).where(Project.name == "Lagos Life Reconnaissance"))).scalars().first()
        if p is None:
            print("Project not seeded yet — run scripts/seed_lagos_life.py first.")
            sys.exit(1)
        pid = p.id
        print(f"project: {p.name} ({p.id})")

    step("2. Create research task + plan")
    task_in = TaskIn(
        title="Consolidate Lagos Life reconnaissance into structured intelligence",
        objective=("Verify and consolidate the existing Lagos Life reconnaissance: ensure every "
                   "documented page is understood, features are documented with evidence, analytics "
                   "are current, and the core reports are regenerated. Target: https://lagoslife.app "
                   "(first-party automated capture remains pending approval)."),
        priority=1,
        report_types=["feature_inventory", "evidence_register", "completion_report"],
    )
    async with session_scope() as sess:
        t = ResearchTask(id=new_id(), project_id=pid, title=task_in.title,
                         objective=task_in.objective, priority=task_in.priority,
                         plan={"report_types": task_in.report_types})
        sess.add(t)
        await sess.flush()
        tid = t.id
    print(f"task: {task_in.title} ({tid})")

    step("3. Run autonomous agent")
    agent_loop.start_task(tid)
    while True:
        import time
        await asyncio.sleep(1.0)
        async with session_scope() as sess:
            t = (await sess.execute(select(ResearchTask).where(ResearchTask.id == tid))).scalars().first()
            if t.status in ("complete", "failed", "waiting_decision", "cancelled"):
                break
        if not agent_loop.is_running(tid) and t.status in ("running", "planned"):
            break
    print(f"task status: {t.status} (progress {t.progress:.0f}%)")
    if t.error:
        print(f"task error (recorded, not hidden): {t.error}")
    if t.result_summary:
        print(f"summary: {t.result_summary}")

    step("4. Analytics (deterministic, explained)")
    from app.api.systems import _ctx
    async with session_scope() as sess:
        ctx = await _ctx(pid, sess)
    a = analytics.full_project_analytics(
        ctx["project"], ctx["pages"], ctx["features"],
        ctx["evidence"], ctx["observations"], ctx["questions"])
    print(f"completeness:      {a['research_completeness']['score']}")
    print(f"feature doc rate:  {a['feature_completeness']['field_rate']}")
    print(f"page coverage:     {a['page_coverage']['documented']}/{a['page_coverage']['total']}")
    print(f"evidence quality:  {a['evidence_quality']['score']}")
    print(f"open questions:    {a['missing_information']['open_questions']}")
    print(f"contradictions:    {a['contradictions']['count']}")
    print(f"duplicate pairs:   {a['duplicates']['count']}")
    print("top opportunities: " + ", ".join(
        f"{o['feature']} ({o['score']:.2f})" for o in a["gaps_and_opportunities"]["opportunities"][:5]))

    step("5. Generate reports")
    for rt in ("executive", "feature_inventory", "completion_report"):
        content = render_report(rt, {**ctx, "analytics": a}, "md")
        async with session_scope() as sess:
            r = Report(id=new_id(), project_id=pid, type=rt,
                       title=f"{rt} — {ctx['project']['name']}", format="md", content=content)
            sess.add(r)
        print(f"  {rt}: {len(content)} chars")

    step("6. GitHub integration (local checkout)")
    adapter = get_adapter(local_path=s.local_repo_path or None, remote=s.github_repo)
    if adapter is not None:
        info = adapter.repo_info()
        print(f"repo: {info.get('remote')} branch={info.get('branch')} last={info.get('last_commit_sha', '')[:12]}")
        tree = adapter.docs_tree("docs")
        print(f"docs: {len(tree)} markdown files under docs/")
        readme = adapter.read_doc("docs/research/README.md")[:200].replace("\n", " ")
        print(f"research README digest: {readme}…")
    else:
        print("no GitHub adapter available in this environment")

    step("7. Knowledge base search")
    from app.engine.knowledge import search as kb
    res = await kb(pid, "governor election", limit=3)
    for r in res["results"]:
        print(f"  [{r['score']:.3f}] {r['kind']}: {r['title'][:80]}")

    step("8. Browser health (honest status)")
    from app.engine.browser.manager import probe_engines
    for h in await probe_engines():
        print(f"  {h['engine']}: installed={h['installed']} {h.get('error', '')[:100]}")

    print("\nDemo complete. Dashboard: http://localhost:8787")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
