"""End-to-end behaviour against a fake website served through an in-memory HTTP transport."""
import json
import subprocess
import time
from pathlib import Path

import pytest

from nlie import analytics, approvals, github, importer, jobs, planner, reports
from nlie.db import (Activity, Approval, BrowserRun, Evidence, Feature, Finding, Page, Project, Question, Source, Task, Version, backup_database, session)

from conftest import REPO_ROOT


def run_agent(pid, rounds=6):
    for _ in range(rounds):
        with session() as s:
            planner.plan(s, s.get(Project, pid))
        if not jobs.drain():
            break


def test_agent_plans_captures_and_records_evidence(project, env):
    run_agent(project)
    with session() as s:
        pages = {p.url: p for p in s.query(Page).filter_by(project_id=project)}
        assert pages["https://demo.test/"].status == "analysed"
        assert pages["https://demo.test/login"].status == "analysed" and pages["https://demo.test/login"].category == "authentication"
        assert pages["https://demo.test/market"].status == "analysed"
        assert "https://other.example/x" not in pages  # off-host link never followed
        # every finding: unique id, page, observation, evidence, timestamp, confidence, status
        finds = s.query(Finding).filter_by(project_id=project).all()
        assert finds and len({f.uid for f in finds}) == len(finds)
        for f in finds:
            assert f.page_id and f.observation and f.evidence_id and f.created_at and f.confidence == "confirmed" and f.status == "recorded"
        # evidence archived on disk with a matching hash
        import hashlib
        ev = s.query(Evidence).filter_by(project_id=project, kind="page_capture").first()
        assert hashlib.sha256(Path(ev.file_path).read_bytes()).hexdigest() == ev.sha256
        names = {f.name for f in s.query(Feature).filter_by(project_id=project)}
        assert {"Log-in form", "Search"} <= names
        assert s.query(BrowserRun).filter_by(status="ok").count() >= 3


def test_robots_disallow_is_respected_and_explained(project, env):
    run_agent(project)
    assert "/private/admin" not in env.hits
    with session() as s:
        t = s.query(Task).filter(Task.title.like("%/private/admin")).one()
        assert t.status == "blocked" and "robots.txt disallows" in t.error
        assert s.query(Page).filter_by(url="https://demo.test/private/admin").one().status == "blocked"
        assert any(c["criterion"] == "No blocked tasks" and not c["met"] for c in planner.assess(s, s.get(Project, project))["criteria"])


def test_unapproved_and_manual_only_sources_are_never_fetched(env):
    with session() as s:
        p = Project(name="Gate")
        s.add(p)
        s.flush()
        s.add(Source(project_id=p.id, name="Unapproved", base_url="https://demo.test/", automation="automated", approved=False))
        pid = p.id
    with session() as s:
        out = planner.plan(s, s.get(Project, pid))
        assert out["created"] == [] and any("waiting for human approval" in n for n in out["notes"])
        t, _ = jobs.enqueue(s, pid, "capture_page", "forced", {"url": "https://demo.test/"})
    jobs.drain()
    assert env.hits == []
    with session() as s:
        assert s.get(Task, t.id).status == "blocked" and "awaiting human approval" in s.get(Task, t.id).error
        src = s.query(Source).filter_by(project_id=pid).one()
        src.approved, src.automation = True, "manual_only"
        t2, _ = jobs.enqueue(s, pid, "capture_page", "forced again", {"url": "https://demo.test/login"})
    jobs.drain()
    assert env.hits == []
    with session() as s:
        assert "manual-only" in s.get(Task, t2.id).error


def test_no_duplicate_work_on_replan(project, env):
    run_agent(project)
    hits = len(env.hits)
    with session() as s:
        n_tasks, n_find = s.query(Task).count(), s.query(Finding).count()
    run_agent(project)
    with session() as s:
        assert s.query(Task).count() == n_tasks and s.query(Finding).count() == n_find
    assert len(env.hits) == hits


def test_retry_then_success(project, env):
    env.flaky_failures = 2
    run_agent(project)
    with session() as s:
        t = s.query(Task).filter(Task.title.like("%/flaky")).one()
        assert t.status == "done" and t.attempts == 3
        assert s.query(Activity).filter_by(event="task_retry_scheduled").count() == 2


def test_failure_is_recorded_not_lost(project, env):
    env.down = True
    run_agent(project)
    with session() as s:
        t = s.query(Task).filter_by(kind="capture_page").one()
        assert t.status == "failed" and t.attempts == 3 and "Gave up after 3 attempts" in t.error and "ConnectError" in t.error
        assert s.query(BrowserRun).filter_by(status="failed").count() == 3
        a = planner.assess(s, s.get(Project, project))
        assert not a["complete"]
        assert any("Review failed task" in r["action"] for r in planner.recommendations(s, s.get(Project, project)))
    env.down = False
    with session() as s:
        jobs.retry(s, t.id)
    jobs.drain()
    with session() as s:
        assert s.get(Task, t.id).status == "done"


def test_recovery_after_interruption(project, env):
    """Simulates a crash: a task is left 'running' in the database, the engine is torn down, then started again."""
    from nlie import db
    with session() as s:
        planner.plan(s, s.get(Project, project))
        t = s.query(Task).filter_by(kind="capture_page").one()
        t.status, t.attempts = "running", 1
        tid = t.id
    db._engine.dispose()
    db._engine = db._Session = None  # process "dies"
    db.init_db()  # process restarts on the same database file
    assert jobs.recover() == 1
    with session() as s:
        assert s.get(Task, tid).status == "queued" and "Recovered after interruption" in s.get(Task, tid).error
    run_agent(project)
    with session() as s:
        assert s.get(Task, tid).status == "done"
        assert s.query(Page).filter_by(status="analysed").count() >= 3


def test_cancel_and_pause(project, env):
    with session() as s:
        planner.plan(s, s.get(Project, project))
        t = s.query(Task).first()
        jobs.cancel(s, t.id)
        s.get(Project, project).status = "paused"
        t2, _ = jobs.enqueue(s, project, "capture_page", "x", {"url": "https://demo.test/login"})
    assert jobs.drain() == 0 and env.hits == []  # paused project: nothing runs
    with session() as s:
        assert s.get(Task, t.id).status == "cancelled" and s.get(Task, t2.id).status == "queued"
        s.get(Project, project).status = "active"
    assert jobs.drain() == 1


def test_page_budget(env):
    with session() as s:
        p = Project(name="Budget")
        s.add(p)
        s.flush()
        s.add(Source(project_id=p.id, name="Demo", base_url="https://demo.test/", automation="automated", approved=True, rate_limit_seconds=0, max_pages=2))
        pid = p.id
    run_agent(pid)
    with session() as s:
        assert s.query(Page).filter_by(project_id=pid, status="analysed").count() == 2


def test_recapture_versions_changed_page(project, env):
    import conftest
    run_agent(project)
    old = conftest.SITE["/market"]
    conftest.SITE["/market"] = ("text/html", old[1].replace("Goods for sale.", "New goods today."))
    try:
        with session() as s:
            jobs.enqueue(s, project, "capture_page", "re-capture market", {"url": "https://demo.test/market"}, dedupe_key="recapture-1")
        jobs.drain()
        with session() as s:
            pg = s.query(Page).filter_by(url="https://demo.test/market").one()
            v = s.query(Version).filter_by(entity_type="pages", entity_id=pg.id).one()
            assert "Goods for sale." in v.snapshot["text"] and "New goods today." in pg.text
    finally:
        conftest.SITE["/market"] = old


def test_import_of_real_repository_research(env):
    """Runs against the research actually committed in this repository."""
    with session() as s:
        p = Project(name="Real", repo_path=str(REPO_ROOT))
        s.add(p)
        s.flush()
        stats = importer.import_research(s, p, str(REPO_ROOT))
        assert stats["read"][:2] == ["README.md", "00-investigation-log.md"]  # index and log first
        assert stats["evidence"] == 29 and stats["missing_files"] == []
        assert s.query(Evidence).filter_by(project_id=p.id, ref="E01").one().classification == "confirmed"
        assert stats["features_created"] > 50 and stats["questions"] > 0 and stats["pages"] > 10
        ach = s.query(Feature).filter_by(project_id=p.id, slug="achievements").one()
        assert ach.confidence == "unknown" and not ach.fields["description"]  # 'not found' stays not found
        again = importer.import_research(s, p, str(REPO_ROOT))
        assert again["evidence"] == 0 and again["features_created"] == 0 and again["pages"] == 0 and again["questions"] == 0
        a = analytics.compute(s, p)
        assert a["contradictions"] and all(m["formula"] and m["inputs"] is not None for m in a["metrics"])
        known = {e.ref for e in s.query(Evidence).filter_by(project_id=p.id)}
        cited = {r for f in s.query(Feature).filter_by(project_id=p.id) for r in f.evidence_refs}
        assert cited and cited <= known


def test_analytics_values_match_their_inputs(project, env):
    run_agent(project)
    with session() as s:
        a = analytics.compute(s, s.get(Project, project))
        m = {x["name"]: x for x in a["metrics"]}
        cov = m["Page capture coverage"]
        i = cov["inputs"]
        assert cov["value"] == round(100 * i["captured"] / (i["captured"] + i["discovered_not_captured"] + i["blocked"] + i["failed"]), 1)
        assert i["blocked"] == 1
        comp = m["Documentation completeness"]
        assert comp["value"] == round(100 * comp["inputs"]["filled_fields"] / (comp["inputs"]["features"] * 14), 1)
        assert m["First-hand evidence share"]["value"] == 100.0


def test_empty_project_has_no_made_up_numbers(env):
    with session() as s:
        p = Project(name="Empty")
        s.add(p)
        s.flush()
        m = {x["name"]: x["value"] for x in analytics.compute(s, p)["metrics"]}
        assert m.pop("Feature category coverage") == 0.0  # 0 of a fixed 20 categories is a real zero
        assert all(v is None for v in m.values())  # nothing to divide by: no value, rather than an invented one


def test_reports_in_every_format(project, env):
    run_agent(project)
    with session() as s:
        p = s.get(Project, project)
        out = reports.generate(s, p, "site_map", ["md", "json", "csv", "html", "pdf", "mmd"])
        files = {r["format"]: Path(r["path"]) for r in out}
        assert files["pdf"].read_bytes()[:5] == b"%PDF-" and files["pdf"].stat().st_size > 1500
        assert files["mmd"].read_text().startswith("flowchart LR") and "-->" in files["mmd"].read_text()
        d = json.loads(files["json"].read_text())
        assert d["generated_at"] and d["investigation_dates"] != "no evidence recorded"
        assert "Investigation dates:" in files["md"].read_text() and "```mermaid" in files["md"].read_text()
        assert "<table>" in files["html"].read_text()
        for kind in reports.KINDS:
            md = reports.to_md(reports.build(s, p, kind))
            assert md.startswith("# ") and "Generated:" in md
        assert "EV-0001" in reports.to_md(reports.build(s, p, "feature_inventory"))
        with pytest.raises(ValueError):
            reports.generate(s, p, "executive", ["mmd"])


def test_github_publish_needs_approval_and_leaves_working_tree_alone(project, env, git_repo):
    repo, origin = git_repo
    run_agent(project)
    with session() as s:
        s.get(Project, project).repo_path = str(repo)
        a = approvals.request(s, project, "publish_to_repo", "publish", {"kinds": ["executive", "evidence_register"], "branch": "nlie/reports-1", "push": True})
        aid = a.id
    git = lambda *x: subprocess.run(["git", "-C", str(repo), *x], capture_output=True, text=True).stdout.strip()  # noqa: E731
    assert git("branch", "--list", "nlie/reports-1") == ""  # nothing happens before approval
    with session() as s:
        res = approvals.decide(s, aid, True, "tester")
        assert res.status == "approved" and res.result["pushed"] and "error" not in res.result
    assert git("rev-parse", "--abbrev-ref", "HEAD") == "main" and git("status", "--porcelain") == ""
    assert "docs/engine/generated/executive.md" in git("ls-tree", "-r", "--name-only", "nlie/reports-1")
    assert "nlie/reports-1" in subprocess.run(["git", "-C", str(origin), "branch"], capture_output=True, text=True).stdout
    st = github.status(str(repo))
    assert st["connected"] and st["branch"] == "main"
    assert any(g["path"] == "LICENSE" and g["issue"] == "missing" for g in github.doc_gaps(str(repo)))
    with pytest.raises(github.GitError):
        github.publish(str(repo), "nlie/reports-1", {"a.md": "x"}, "again")  # existing branch is never overwritten
    with pytest.raises(github.GitError):
        github.publish(str(repo), "nlie/escape", {"../outside.md": "x"}, "escape")
    assert git("branch", "--list", "nlie/escape") == ""


def test_rejected_approval_does_nothing(project, env, git_repo):
    repo, _ = git_repo
    with session() as s:
        s.get(Project, project).repo_path = str(repo)
        aid = approvals.request(s, project, "publish_to_repo", "publish", {"kinds": ["executive"], "branch": "nlie/no"}).id
        assert approvals.decide(s, aid, False).status == "rejected"
        with pytest.raises(ValueError):
            approvals.decide(s, aid, True)
    assert subprocess.run(["git", "-C", str(repo), "branch", "--list", "nlie/no"], capture_output=True, text=True).stdout.strip() == ""


def test_backup_is_a_readable_copy(project, env):
    import sqlite3
    run_agent(project)
    dest = backup_database()
    with sqlite3.connect(dest) as c:
        assert c.execute("select count(*) from pages").fetchone()[0] >= 3


def test_capture_throughput(project, env):
    """Performance check on the pipeline itself (network excluded: the site is in memory)."""
    t0 = time.perf_counter()
    run_agent(project)
    elapsed = time.perf_counter() - t0
    with session() as s:
        n = s.query(Task).filter_by(status="done").count()
    print(f"\nPERF pipeline: {n} tasks in {elapsed:.2f}s ({elapsed / n * 1000:.0f} ms per task)")
    assert elapsed / n < 2.0
