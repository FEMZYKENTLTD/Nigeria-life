"""API integration tests (in-process ASGI transport)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402


def test_health_projects_and_lifecycle():
    async def t():
        import httpx

        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/health")
            assert r.status_code == 200 and r.json()["status"] == "ok"

            # create project
            r = await c.post("/api/projects", json={
                "name": "API Test Co", "target_base_url": "https://api-test.example.com",
                "description": "integration",
            })
            assert r.status_code == 201, r.text
            pid = r.json()["id"]

            # duplicate rejected
            r = await c.post("/api/projects", json={"name": "API Test Co"})
            assert r.status_code == 409

            # list + get
            r = await c.get("/api/projects")
            assert any(p["id"] == pid for p in r.json())
            r = await c.get(f"/api/projects/{pid}")
            assert r.json()["name"] == "API Test Co"

            # add source (stays pending without auto_authorise)
            r = await c.post(f"/api/projects/{pid}/sources",
                             json={"name": "site", "url": "https://api-test.example.com/about"})
            assert r.json()["status"] == "pending_approval"

            # manual page import with HTML → analysed
            html = "<html><head><title>API Test Home</title></head><body><h1>Home</h1><form action='/x'><input name='q'><button>Go</button></form></body></html>"
            r = await c.post(f"/api/projects/{pid}/pages/import",
                             json={"url": "https://api-test.example.com/", "html": html,
                                   "evidence_class": "C", "evidence_source": "manual read"})
            assert r.status_code == 201, r.text
            page_id = r.json()["page_id"]

            # feature create + update
            r = await c.post(f"/api/projects/{pid}/features", json={
                "name": "Search", "category": "marketplace", "description": "finds items"})
            assert r.status_code == 201, r.text
            fid = r.json()["id"]
            r = await c.patch(f"/api/features/{fid}", json={"confidence": 0.8, "status": "documented"})
            assert r.json()["updated"] is True

            # observation
            r = await c.post(f"/api/projects/{pid}/observations",
                             json={"observation": "form seen", "key": "search form",
                                   "value": "1 form", "evidence_class": "C", "confidence": 0.9})
            assert r.status_code == 201

            # analytics
            r = await c.get(f"/api/projects/{pid}/analytics")
            assert r.status_code == 200
            a = r.json()
            assert "research_completeness" in a and "explanation" in a["research_completeness"]
            assert a["page_coverage"]["documented"] == 1

            # report generation (all formats)
            for fmt in ("md", "json", "csv", "html"):
                r = await c.post(f"/api/projects/{pid}/reports/generate",
                                 json={"type": "feature_inventory", "format": fmt})
                assert r.status_code == 200, (fmt, r.text)

            # knowledge search
            r = await c.post(f"/api/projects/{pid}/knowledge/search",
                             json={"query": "search form items"})
            assert r.status_code == 200
            assert r.json()["count"] >= 1

            # overview
            r = await c.get("/api/overview")
            assert r.status_code == 200
            assert any(p["id"] == pid for p in r.json()["projects"])

            # destructive delete requires confirm
            r = await c.delete(f"/api/projects/{pid}")
            assert r.status_code == 400
            r = await c.delete(f"/api/projects/{pid}?confirm=API Test Co")
            assert r.status_code == 200

    start(t)


def test_agent_endpoints():
    async def t():
        import httpx

        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/projects", json={"name": "Agent Co"})
            pid = r.json()["id"]
            r = await c.post(f"/api/projects/{pid}/tasks",
                             json={"title": "T1", "objective": "Do something",
                                   "report_types": ["completion_report"]})
            assert r.status_code == 201, r.text
            tid = r.json()["id"]
            r = await c.get(f"/api/projects/{pid}/tasks")
            assert any(t["id"] == tid for t in r.json())
            r = await c.get("/api/agent/status")
            assert r.status_code == 200
            r = await c.get("/api/agent/logs")
            assert r.status_code == 200

    start(t)


def test_browser_endpoints_report_honestly():
    async def t():
        import httpx

        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/browsers/health")
            assert r.status_code == 200
            rows = r.json()
            assert {h["engine"] for h in rows} == {"chromium", "firefox", "webkit"}
            for h in rows:
                assert "installed" in h and "error" in h  # honest state either way

            # unknown project → 404
            r = await c.post("/api/projects/whatever/captures",
                             json={"url": "https://example.com", "engine": "chromium"})
            assert r.status_code == 404
            # real project: a capture must fail with a recorded reason, never 500
            r = await c.post("/api/projects", json={"name": "Capture Co"})
            pid = r.json()["id"]
            r = await c.post(f"/api/projects/{pid}/captures",
                             json={"url": "https://example.com", "engine": "chromium"})
            assert r.status_code == 200
            body = r.json()
            assert body["ok"] is False
            assert body["error"], "failure must explain itself"

            r = await c.get("/api/sessions")
            assert r.status_code == 200

    start(t)


def test_github_endpoints():
    async def t():
        import httpx

        from app.main import create_app

        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/github/status")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["connected"] is True
            assert body["info"]["branch"]
            assert any(d["path"].endswith("README.md") for d in body["docs_tree"])
            r = await c.post("/api/github/sync")
            assert r.status_code == 200
            assert r.json()["docs"] >= 14
            # write-back is restricted + gated
            r = await c.post("/api/github/write-back",
                             json={"path": "src/app.py", "content": "x", "commit_message": "c"})
            assert r.status_code == 400  # not docs/**
            r = await c.post("/api/github/write-back",
                             json={"path": "docs/research/test.md", "content": "# t",
                                   "commit_message": "c"})
            assert r.status_code == 400  # no approved decision

    start(t)
