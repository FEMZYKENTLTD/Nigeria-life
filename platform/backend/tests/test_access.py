"""Data & Access tests: polite HTTP capture (ETag/304), robots.txt gates,
robots-exception approval, scope page caps, API connectors (credential
hygiene), licensed dataset import, manual captures + batch import, and the
manual-evidence queue. All capture is against a local HTTP server — no
external network in tests."""
import base64
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402

PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


# ---------------------------------------------------------------- local server

def _page_html(path: str) -> str:
    if path == "/private":
        return ("<html><head><title>Private Area</title></head><body>"
                "<h1>Members only</h1><form action='/login'><input name='user'>"
                "<button>Sign in</button></form></body></html>")
    return ("<html><head><title>Test Store Home</title></head><body>"
            "<h1>Test Store</h1><nav><a href='/about'>About</a> "
            "<a href='/pricing'>Pricing</a></nav>"
            "<form action='/checkout'><input name='item'><button>Buy now</button></form>"
            "<p>Create account. Pricing starts at 10. Contact us.</p>"
            "</body></html>")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /private\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/data":
            body = json.dumps([{"name": "Item A", "price": 10},
                               {"name": "Item B", "price": 20}]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in ("/", "/about", "/pricing", "/private"):
            tag = f'"{self.path}-v1"'
            if self.headers.get("If-None-Match") == tag:
                self.send_response(304)
                self.end_headers()
                return
            body = _page_html(self.path).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("ETag", tag)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def _start_server() -> tuple:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


# ---------------------------------------------------------------- helpers

async def _make_project(name: str, base_url: str = "") -> str:
    from app.db import session_scope
    from app.engine.ids import new_id
    from app.models import Project

    async with session_scope() as s:
        uid = new_id()
        p = Project(id=uid, name=name, slug=name.lower().replace(" ", "-") + f"-{uid[-12:]}",
                    target_base_url=base_url,
                    permissions={"collection_methods": ["http", "manual"]})
        s.add(p)
        await s.flush()
        return p.id


async def _add_scope(project_id: str, domain: str, methods=None, delay=0.0,
                     max_pages=40, robots_mode="respect") -> dict:
    from app.db import session_scope
    from app.engine.ids import new_id
    from app.models import CollectionScope

    scope = CollectionScope(
        id=new_id(), project_id=project_id, domain=domain,
        allowed_methods=methods if methods is not None else ["http"],
        min_delay_s=delay, max_pages=max_pages, robots_mode=robots_mode)
    async with session_scope() as s:
        s.add(scope)
        await s.commit()
    return {"id": scope.id, "domain": domain}


def _plan_fetch(url: str, extra=None):
    from app.engine.ids import new_id

    subs = [{"id": new_id(), "idx": 0, "type": "fetch",
             "description": f"Capture page 1/1: {url}", "priority": 2,
             "requires_approval": False, "max_attempts": 1}]
    if extra:
        for i, t in enumerate(extra):
            subs.append({"id": new_id(), "idx": i + 1, "type": t,
                         "description": f"step {t}", "priority": 2,
                         "requires_approval": False, "max_attempts": 1})
    return {"planner": "test", "url_queue": [url], "subtasks": subs}


async def _task_status(task_id: str):
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import ResearchTask

    async with session_scope() as s:
        t = (await s.execute(
            select(ResearchTask).where(ResearchTask.id == task_id))).scalars().first()
        return t.status, (t.error or "")


# ---------------------------------------------------------------- tests

def test_http_fetch_etag_cache():
    """First fetch 200 (recorded + cached); second fetch sends conditional
    headers, gets 304, and is reported as a cache hit."""
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import http_fetch
        from app.models import FetchCache, PageRecord

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project(f"ETAG Test {port}")

        r1 = await http_fetch.fetch_page(pid, base + "/")
        assert r1["ok"] and not r1["cached"] and r1["status"] == 200

        r2 = await http_fetch.fetch_page(pid, base + "/")
        assert r2["ok"] and r2["cached"] and r2["status"] == 304
        assert r2["page_id"] == r1["page_id"]

        async with session_scope() as s:
            rows = (await s.execute(
                select(FetchCache).where(FetchCache.project_id == pid)
            )).scalars().all()
            pages = (await s.execute(
                select(PageRecord).where(PageRecord.project_id == pid)
            )).scalars().all()
        assert len(rows) == 1 and rows[0].etag == '"/-v1"'
        assert len(pages) == 1 and pages[0].status == "documented"
        assert pages[0].capture_method == "http"
        srv.shutdown()

    start(t)


def test_robots_gate_parks_task():
    """A robots-disallowed URL must park the task on a manual_evidence
    decision — never be fetched, never silently dropped."""
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import Decision, ResearchTask

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project(f"Robots Gate {port}", base)
        await _add_scope(pid, f"127.0.0.1:{port}", methods=["http"])

        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Fetch private",
                               objective="capture /private",
                               plan=_plan_fetch(base + "/private")))
        await agent_loop.execute_task(t_id)

        status, _ = await _task_status(t_id)
        assert status == "waiting_decision", status
        async with session_scope() as s:
            d = (await s.execute(
                select(Decision).where(Decision.task_id == t_id)
            )).scalars().first()
        assert d is not None and d.status == "pending" and d.kind == "manual_evidence"
        assert "robots.txt" in d.question
        # the URL must NOT have been captured
        from app.models import PageRecord
        async with session_scope() as s:
            p = (await s.execute(
                select(PageRecord).where(
                    PageRecord.project_id == pid,
                    PageRecord.canonical_url == base + "/private"))).scalars().first()
        assert p is None
        srv.shutdown()

    start(t)


def test_robots_exception_approval_allows_fetch():
    """An approved scope exception (via the decision endpoint) flips the
    robots posture and the same URL then fetches cleanly."""
    async def t():
        import httpx

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.main import create_app
        from app.models import ResearchTask

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project(f"Robots Exception {port}", base)

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/api/projects/{pid}/scope", json={
                "domain": f"127.0.0.1:{port}", "allowed_methods": ["http"],
                "min_delay_s": 0, "robots_mode": "approved_exception"})
            assert r.status_code == 201, r.text
            assert r.json()["robots_exception_pending"] is True

            rq = await c.get(f"/api/projects/{pid}/scope")
            assert rq.json()[0]["robots_mode"] == "respect"  # not live until approved

            rd = await c.get(f"/api/projects/{pid}/decisions")
            dec = [x for x in rd.json() if x["kind"] == "permission_change"]
            assert dec, rd.json()
            await agent_loop.resume_after_decision(dec[0]["id"], approved=True)

            rq = await c.get(f"/api/projects/{pid}/scope")
            assert rq.json()[0]["robots_mode"] == "approved_exception"

        # now the gated URL fetches through the normal pipeline
        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Fetch with exception",
                               objective="capture /private",
                               plan=_plan_fetch(base + "/private")))
        await agent_loop.execute_task(t_id)
        status, err = await _task_status(t_id)
        assert status == "complete", (status, err)
        srv.shutdown()

    start(t)


def test_scope_page_cap_skips_honestly():
    """Beyond the scope page cap, further fetch subtasks are skipped with an
    explanation — not silently dropped."""
    async def t():
        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import ResearchTask, Subtask
        from sqlalchemy import select

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project(f"Page Cap {port}", base)
        await _add_scope(pid, f"127.0.0.1:{port}", methods=["http"], max_pages=1)

        from app.engine.ids import new_id as nid
        plan = {"planner": "test", "url_queue": [], "subtasks": []}
        for i, path in enumerate(["/", "/about", "/pricing"]):
            plan["subtasks"].append({
                "id": nid(), "idx": i, "type": "fetch",
                "description": f"Capture page {i + 1}/3: {base}{path}",
                "priority": 2, "requires_approval": False, "max_attempts": 1})
        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Cap test",
                               objective="3 pages, cap 1", plan=plan))
        await agent_loop.execute_task(t_id)
        async with session_scope() as s:
            subs = (await s.execute(
                select(Subtask).where(Subtask.task_id == t_id)
                .order_by(Subtask.idx))).scalars().all()
        assert subs[0].status == "complete", subs[0].last_error
        assert subs[1].status == "skipped" and "page cap" in subs[1].last_error
        assert subs[2].status == "skipped" and "page cap" in subs[2].last_error
        srv.shutdown()

    start(t)


def test_agent_http_pipeline_end_to_end():
    """Full agent run over a local target using the polite HTTP method:
    fetch → understand → document → analyse → report, complete with real
    findings and a report."""
    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.models import Feature, PageRecord, Report, ResearchTask

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project(f"HTTP Pipeline {port}", base)
        await _add_scope(pid, f"127.0.0.1:{port}", methods=["http"])

        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Pipeline",
                               objective="research the store",
                               plan=_plan_fetch(base + "/", extra=["understand", "document",
                                                                  "analyse", "report"])))
        await agent_loop.execute_task(t_id)
        status, err = await _task_status(t_id)
        assert status == "complete", (status, err)
        async with session_scope() as s:
            pages = (await s.execute(
                select(PageRecord).where(PageRecord.project_id == pid)
            )).scalars().all()
            feats = (await s.execute(
                select(Feature).where(Feature.project_id == pid))).scalars().all()
            reports = (await s.execute(
                select(Report).where(Report.project_id == pid))).scalars().all()
        assert any(p.canonical_url == base + "/" and p.status == "documented"
                   for p in pages)
        assert len(feats) >= 2
        assert len(reports) >= 1
        srv.shutdown()

    start(t)


def test_data_import_formats():
    async def t():
        from app.api.access import import_data_asset
        from app.db import session_scope
        from app.models import DataAsset, Observation
        from sqlalchemy import select

        pid = await _make_project("Data Import Test")

        # in-process call (multipart via UploadFile is covered by the API;
        # exercise the engine directly here for all three formats)
        from app.engine import data_import

        r = await data_import.import_dataset(
            pid, "Fruit Prices", "fruit.csv",
            b"name,price\nApples,5\nBananas,3\n",
            "Purchased from FruitData Ltd (2026-01)", "CC-BY 4.0", "S", 0.6)
        assert r["ok"] and r["rows"] == 2 and r["observations"] == 2, r

        r = await data_import.import_dataset(
            pid, "Items", "items.json",
            b'[{"id": 1, "x": "a"}, {"id": 2, "x": "b"}]',
            "Licensed export, vendor API", "proprietary-licensed", "S")
        assert r["ok"] and r["rows"] == 2, r

        r = await data_import.import_dataset(
            pid, "Workorders", "wo.xml",
            b"<root><item><name>W1</name></item><item><name>W2</name></item></root>",
            "Provided under NDA by the operator", "NDA", "S")
        assert r["ok"] and r["rows"] == 2, r

        async with session_scope() as s:
            assets = (await s.execute(
                select(DataAsset).where(DataAsset.project_id == pid))).scalars().all()
            obs = (await s.execute(
                select(Observation).where(Observation.project_id == pid))).scalars().all()
        assert len(assets) == 3
        assert all(a.status == "imported" for a in assets)
        assert len(obs) == 6
        assert all(len(o.evidence_ids) == 1 for o in obs)  # every finding cites evidence

    start(t)


def test_data_import_requires_provenance_and_rejects_bad_file():
    async def t():
        from app.engine import data_import

        pid = await _make_project("Data Import Bad")
        r = await data_import.import_dataset(
            pid, "NoProv", "x.csv", b"a,b\n1,2\n", "", "CC0")
        assert not r["ok"] and "provenance" in r["error"]

        r = await data_import.import_dataset(
            pid, "BadJson", "x.json", b"{not json", "src", "CC0")
        assert not r["ok"] and "parse failed" in r["error"]

    start(t)


def test_connector_flow_and_sync():
    async def t():
        import httpx

        from sqlalchemy import select

        from app.db import session_scope
        from app.engine import agent_loop
        from app.main import create_app
        from app.models import ApiConnector, Decision, Evidence, Observation

        srv, port = _start_server()
        pid = await _make_project("Connector Test")
        os.environ["RICE_TEST_API_KEY"] = "secret-value-xyz"
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/api/projects/{pid}/connectors", json={
                "name": "Test Store API",
                "base_url": f"http://127.0.0.1:{port}",
                "auth_type": "key",
                "env_var": "RICE_TEST_API_KEY",
                "key_header": "X-API-Key",
                "endpoints": [{"name": "items", "path": "/data", "method": "GET"}],
            })
            assert r.status_code == 201, r.text
            cid = r.json()["connector"]["id"]
            assert r.json()["connector"]["status"] == "pending_approval"

            # invalid definitions are rejected with a clear reason
            r = await c.post(f"/api/projects/{pid}/connectors", json={
                "name": "Bad", "base_url": "nope", "auth_type": "key",
                "env_var": "lowercase", "endpoints": []})
            assert r.status_code == 400

            # approval activates it
            rd = await c.get(f"/api/projects/{pid}/decisions")
            dec = [x for x in rd.json() if (x.get("context") or {}).get("connector_id") == cid]
            assert dec, rd.json()
            await agent_loop.resume_after_decision(dec[0]["id"], approved=True)
            rc = await c.get(f"/api/projects/{pid}/connectors")
            assert [x for x in rc.json() if x["id"] == cid][0]["status"] == "active"

            rs = await c.post(f"/api/projects/{pid}/connectors/{cid}/sync")
            assert rs.status_code == 200, rs.text
            body = rs.json()
            assert body["ok"] and body["rows"] == 2 and body["observations"] == 2

        async with session_scope() as s:
            obs = (await s.execute(
                select(Observation).where(Observation.project_id == pid))).scalars().all()
            evs = (await s.execute(
                select(Evidence).where(Evidence.project_id == pid))).scalars().all()
        assert len(obs) == 2 and all("Item" in o.observation for o in obs)
        assert len(evs) == 1 and evs[0].capture_method == "api_connector"
        assert "secret-value-xyz" not in json.dumps([o.observation for o in obs])
        srv.shutdown()

    start(t)


def test_connector_missing_env_is_honest_error():
    async def t():
        import httpx

        from app.db import session_scope
        from app.engine import agent_loop
        from app.main import create_app
        from app.models import ApiConnector
        from sqlalchemy import select

        srv, port = _start_server()
        pid = await _make_project("Connector NoEnv")
        os.environ.pop("RICE_TEST_MISSING_KEY", None)
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/api/projects/{pid}/connectors", json={
                "name": "Needs Key", "base_url": f"http://127.0.0.1:{port}",
                "auth_type": "key", "env_var": "RICE_TEST_MISSING_KEY",
                "endpoints": [{"name": "items", "path": "/data"}]})
            cid = r.json()["connector"]["id"]
            rd = await c.get(f"/api/projects/{pid}/decisions")
            dec = [x for x in rd.json() if (x.get("context") or {}).get("connector_id") == cid]
            await agent_loop.resume_after_decision(dec[0]["id"], approved=True)
            rs = await c.post(f"/api/projects/{pid}/connectors/{cid}/sync")
            assert rs.status_code == 502
            assert "RICE_TEST_MISSING_KEY" in rs.text
        async with session_scope() as s:
            conn = (await s.execute(
                select(ApiConnector).where(ApiConnector.id == cid))).scalars().first()
        assert conn.status == "error" and "not set" in conn.error
        srv.shutdown()

    start(t)


def test_manual_capture_and_batch_import():
    async def t():
        import httpx

        from app.db import session_scope
        from app.main import create_app
        from app.models import Evidence, PageRecord, Screenshot
        from sqlalchemy import select

        pid = await _make_project("Manual Capture Test")
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            html = ("<html><head><title>Bridge Page</title></head><body>"
                    "<h1>Members area</h1><p>33 careers listed.</p></body></html>")
            r = await c.post(f"/api/projects/{pid}/manual-captures", json={
                "url": "https://example-gate.com/members",
                "title": "Members area",
                "notes": "captured by the researcher via the side panel",
                "html": html,
                "screenshot_b64": PNG_1PX,
            })
            assert r.status_code == 201, r.text
            page_id, ev_id = r.json()["page_id"], r.json()["evidence_id"]

            r = await c.post(f"/api/projects/{pid}/pages/import-batch", json=[
                {"url": "https://example-gate.com/a", "title": "A", "text": "page A"},
                {"url": "https://example-gate.com/b", "title": "B", "text": "page B"},
            ])
            assert r.status_code == 201 and r.json()["imported"] == 2, r.text

        async with session_scope() as s:
            page = (await s.execute(
                select(PageRecord).where(PageRecord.id == page_id))).scalars().first()
            ev = (await s.execute(
                select(Evidence).where(Evidence.id == ev_id))).scalars().first()
            shots = (await s.execute(
                select(Screenshot).where(Screenshot.page_id == page_id))).scalars().all()
        assert page.status == "documented" and page.capture_method == "manual_evidence"
        assert ev.evidence_class == "C" and ev.capture_method == "manual_evidence"
        assert len(shots) == 1 and os.path.exists(shots[0].file_path)

    start(t)


def test_manual_queue_and_robots_check():
    async def t():
        import httpx

        from app.db import session_scope
        from app.engine import agent_loop
        from app.engine.ids import new_id
        from app.main import create_app
        from app.models import ResearchTask

        srv, port = _start_server()
        base = f"http://127.0.0.1:{port}"
        pid = await _make_project("Manual Queue Test", base)
        await _add_scope(pid, f"127.0.0.1:{port}", methods=["http"])

        t_id = new_id()
        async with session_scope() as s:
            s.add(ResearchTask(id=t_id, project_id=pid, title="Gate then queue",
                               objective="x", plan=_plan_fetch(base + "/private")))
        await agent_loop.execute_task(t_id)

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            rq = await c.get(f"/api/projects/{pid}/manual-queue")
            assert rq.status_code == 200, rq.text
            q = rq.json()
            assert len(q["pending_decisions"]) == 1
            assert q["pending_decisions"][0]["task_id"] == t_id
            assert len(q["blocked_fetches"]) == 1
            assert q["blocked_fetches"][0]["status"] == "waiting_decision"

            rr = await c.get(f"/api/projects/{pid}/robots-check",
                             params={"url": base + "/private"})
            assert rr.json()["status"] == "disallowed"
            rr = await c.get(f"/api/projects/{pid}/robots-check",
                             params={"url": base + "/"})
            assert rr.json()["status"] == "allowed"
        srv.shutdown()

    start(t)
