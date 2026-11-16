"""Multi-user mode: Supabase JWT verification, per-user ownership, admin views.

The other suite runs in local mode (no Supabase env). These tests enable
auth for their own duration and restore the previous environment afterwards,
so the local-mode tests are unaffected whichever order pytest runs them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402

SECRET = "rice-test-jwt-secret-not-for-production-0123456789"
ADMIN_EMAIL = "boss@rice.test"
UID_ADMIN = "11111111-1111-4111-8111-111111111111"
UID_A = "33333333-3333-4333-8333-333333333333"
UID_B = "22222222-2222-4222-8222-222222222222"


def _token(uid: str, email: str) -> str:
    import jwt

    return "Bearer " + jwt.encode(
        {"sub": uid, "email": email, "exp": 9999999999}, SECRET, algorithm="HS256")


def _auth_headers(uid, email):
    return {"Authorization": _token(uid, email)}


def test_multiuser_ownership_and_admin():
    from app.config import get_settings

    saved = {k: os.environ.get(k) for k in (
        "RICE_SUPABASE_URL", "RICE_SUPABASE_JWT_SECRET", "RICE_ADMIN_EMAILS")}
    os.environ["RICE_SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["RICE_SUPABASE_JWT_SECRET"] = SECRET
    os.environ["RICE_ADMIN_EMAILS"] = ADMIN_EMAIL
    get_settings.cache_clear()
    try:
        async def t():
            import httpx

            from app.main import create_app

            app = create_app()
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                admin_h = _auth_headers(UID_ADMIN, ADMIN_EMAIL)
                a_h = _auth_headers(UID_A, "ada@rice.test")
                b_h = _auth_headers(UID_B, "ben@rice.test")

                # 1. unauthenticated → 401
                r = await c.get("/api/projects")
                assert r.status_code == 401, r.text
                r = await c.get("/api/health")
                assert r.status_code == 200  # health stays open

                # 2. user A creates a project → owned by A
                r = await c.post("/api/projects", json={
                    "name": "Ada Research", "target_base_url": "https://ada.example.com"},
                    headers=a_h)
                assert r.status_code == 201, r.text
                pid = r.json()["id"]
                assert r.json().get("owner_id") == UID_A

                # 3. user B: cannot see A's project (404, not 403 — no existence leak)
                r = await c.get("/api/projects", headers=b_h)
                assert all(p["id"] != pid for p in r.json())
                r = await c.get(f"/api/projects/{pid}", headers=b_h)
                assert r.status_code == 404
                r = await c.get(f"/api/projects/{pid}/analytics", headers=b_h)
                assert r.status_code == 404
                r = await c.post(f"/api/projects/{pid}/features",
                                 json={"name": "X", "category": "y"}, headers=b_h)
                assert r.status_code == 404

                # 4. user A sees their project
                r = await c.get("/api/projects", headers=a_h)
                assert any(p["id"] == pid for p in r.json())

                # 5. admin (A here) sees it too, and can read B's (empty) list
                r = await c.get(f"/api/projects/{pid}", headers=admin_h)
                assert r.status_code == 200

                # 6. /api/users is admin-only
                r = await c.get("/api/users", headers=b_h)
                assert r.status_code == 403
                r = await c.get("/api/users", headers=admin_h)
                assert r.status_code == 200, r.text
                users = {u["email"]: u for u in r.json()["users"]}
                assert ADMIN_EMAIL in users and "ben@rice.test" in users
                boss = users[ADMIN_EMAIL]
                assert boss["role"] == "admin"
                assert users["ada@rice.test"]["role"] == "member"

                # 7. admin can see what a user scraped and got
                r = await c.get(f"/api/users/{UID_B}", headers=admin_h)
                assert r.status_code == 200
                body = r.json()
                assert body["user"]["email"] == "ben@rice.test"
                for key in ("projects", "recent_tasks", "recent_pages",
                            "recent_evidence", "recent_activity"):
                    assert key in body

                # 8. give B a real page, then verify it shows in the admin view
                r = await c.post("/api/projects", json={
                    "name": "Ben Research", "target_base_url": "https://ben.example.com"},
                    headers=b_h)
                assert r.status_code == 201
                bpid = r.json()["id"]
                html = "<html><head><title>Ben Home</title></head><body><h1>Home</h1></body></html>"
                r = await c.post(f"/api/projects/{bpid}/pages/import",
                                 json={"url": "https://ben.example.com/", "html": html,
                                       "evidence_class": "C",
                                       "evidence_source": "manual read"},
                                 headers=b_h)
                assert r.status_code == 201, r.text

                r = await c.get(f"/api/users/{UID_B}", headers=admin_h)
                body = r.json()
                assert body["user"]["counts"]["pages"] >= 1
                assert any("ben.example.com" in p["url"] for p in body["recent_pages"])
                assert any(p["name"] == "Ben Research" for p in body["projects"])
                assert body["user"]["counts"]["evidence"] >= 1

                # 9. A (as member, not the admin token) cannot patch roles
                r = await c.patch(f"/api/users/{UID_B}/role",
                                  json={"role": "admin"}, headers=a_h)
                assert r.status_code == 403
                # admin can promote B → B then sees A's project
                r = await c.patch(f"/api/users/{UID_B}/role",
                                  json={"role": "admin"}, headers=admin_h)
                assert r.status_code == 200 and r.json()["role"] == "admin"
                r = await c.get(f"/api/projects/{pid}", headers=b_h)
                assert r.status_code == 200

                # 10. demote back
                r = await c.patch(f"/api/users/{UID_B}/role",
                                  json={"role": "member"}, headers=admin_h)
                assert r.status_code == 200
                r = await c.get(f"/api/projects/{pid}", headers=b_h)
                assert r.status_code == 404

                # 11. bad / expired token → 401
                import jwt as _jwt
                bad = "Bearer " + _jwt.encode({"sub": UID_B, "exp": 123},
                                              SECRET, algorithm="HS256")
                r = await c.get("/api/projects", headers={"Authorization": bad})
                assert r.status_code == 401
                r = await c.get("/api/projects",
                                headers={"Authorization": "Bearer not.a.token"})
                assert r.status_code == 401
        start(t)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()
