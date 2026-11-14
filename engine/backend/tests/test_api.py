import base64
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(env, monkeypatch):
    from conftest import REPO_ROOT
    monkeypatch.setenv("NLIE_REPO_PATH", str(REPO_ROOT))
    from nlie.app import app
    with TestClient(app) as c:
        yield c


def test_bootstrap_imports_repo_research_and_keeps_source_manual(client):
    from nlie import jobs
    h = client.get("/api/health").json()
    assert h["database"]["kind"] == "sqlite" and h["ai"]["provider"] == "heuristic"
    assert {e["engine"] for e in h["engines"]} == {"http", "chromium", "firefox", "webkit"}
    p = client.get("/api/projects").json()[0]
    assert p["tasks"]["queued"] == 1
    jobs.drain()
    feats = client.get(f"/api/projects/{p['id']}/features").json()["features"]
    assert len(feats) > 50
    src = client.get(f"/api/projects/{p['id']}/sources").json()[0]
    assert src["automation"] == "manual_only" and src["approved"] is False
    r = client.post(f"/api/projects/{p['id']}/capture", json={"url": "https://lagoslife.app/"}).json()
    jobs.drain()
    t = [t for t in client.get(f"/api/projects/{p['id']}/tasks").json() if t["id"] == r["task"]["id"]][0]
    assert t["status"] == "blocked" and "awaiting human approval" in t["error"]
    hits = client.get(f"/api/projects/{p['id']}/search", params={"q": "billboard advertising price"}).json()["results"]
    assert hits and hits[0]["score"] > 0


def test_source_approval_flow_and_manual_evidence(client, env):
    from nlie import jobs
    pid = client.post("/api/projects", json={"name": "API demo", "objective": "x"}).json()["id"]
    out = client.post(f"/api/projects/{pid}/sources", json={"name": "Demo", "base_url": "https://demo.test/", "automation": "automated", "rate_limit_seconds": 1}).json()
    assert out["source"]["approved"] is False and out["source"]["automation"] == "manual_only" and out["approval"]["status"] == "pending"
    assert client.post(f"/api/projects/{pid}/plan").json()["created"] == []
    d = client.post(f"/api/approvals/{out['approval']['id']}/decide", json={"approve": True}).json()
    assert d["status"] == "approved" and d["result"]["automation"] == "automated"
    assert client.post(f"/api/approvals/{out['approval']['id']}/decide", json={"approve": True}).status_code == 409
    assert len(client.post(f"/api/projects/{pid}/plan").json()["created"]) == 1
    jobs.drain()
    assert any(p["status"] == "analysed" for p in client.get(f"/api/projects/{pid}/pages").json())

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "navy").save(buf, "PNG")
    r = client.post(f"/api/projects/{pid}/evidence", json={"summary": "Screenshot of the wallet screen, token=ghp_" + "b" * 36, "classification": "confirmed",
                                                          "observation": "Wallet shows a balance in naira.", "filename": "wallet.png",
                                                          "content_base64": base64.b64encode(buf.getvalue()).decode()})
    assert r.status_code == 201
    body = r.json()
    assert "ghp_bbbb" not in body["evidence"]["summary"] and len(body["evidence"]["sha256"]) == 64 and body["finding"]["uid"].startswith("F-")
    shots = client.get(f"/api/projects/{pid}/screenshots").json()
    assert shots[0]["width"] == 64 and client.get(f"/api/screenshots/{shots[0]['id']}/file").status_code == 200
    a = client.post(f"/api/screenshots/{shots[0]['id']}/annotations", json={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "note": "Balance"}).json()
    assert a["annotations"][0]["note"] == "Balance"

    f = client.get(f"/api/projects/{pid}/features").json()["features"][0]
    e = client.patch(f"/api/features/{f['id']}", json={"fields": {"purpose": "Let a player sign in"}, "status": "verified", "expected_updated_at": f["updated_at"]})
    assert e.status_code == 200
    assert client.patch(f"/api/features/{f['id']}", json={"fields": {"purpose": "stale"}, "expected_updated_at": f["updated_at"]}).status_code == 409
    assert len(client.get(f"/api/versions/features/{f['id']}").json()) == 1

    reps = client.post(f"/api/projects/{pid}/reports", json={"kind": "completeness", "formats": ["md", "pdf"]}).json()
    assert client.get(f"/api/reports/{reps[1]['id']}/download").content[:5] == b"%PDF-"
    ag = client.get(f"/api/projects/{pid}/agent").json()
    assert ag["assessment"]["criteria_total"] == 9 and ag["ai"]["model_configured"] is False
    assert client.post("/api/backup").json()["bytes"] > 0
    assert client.post(f"/api/projects/{pid}/pause").json()["status"] == "paused"


def test_validation(client):
    assert client.post("/api/projects", json={"name": "x"}).status_code == 422
    pid = client.get("/api/projects").json()[0]["id"]
    assert client.post(f"/api/projects/{pid}/sources", json={"name": "bad", "base_url": "ftp://x"}).status_code == 422
    assert client.post(f"/api/projects/{pid}/reports", json={"kind": "nope"}).status_code == 422
    assert client.get("/api/projects/999/agent").status_code == 404
