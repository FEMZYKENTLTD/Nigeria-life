"""Stage-8 capabilities: dependency-free PDF reports, the plugin registry,
database backups and project export/import (portability)."""
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402

# ---------------------------------------------------------------- PDF engine

def test_pdf_valid_structure_and_text():
    from app.engine import pdf

    md = "# Lagos Life Platform\n\n" + ("Body line with content.\n" * 40) + "\n## Section two\n\n- item one\n- item two (with parens)\n"
    data = pdf.render_pdf("Test Report", md)
    assert data[:8] == b"%PDF-1.4"
    assert data.rstrip().endswith(b"%%EOF")
    # startxref must point at the xref table
    m = re.search(rb"startxref\n(\d+)\n%%EOF", data)
    assert m and data[int(m.group(1)):int(m.group(1)) + 4] == b"xref"
    # all text emitted via Tj is recoverable
    text = b" ".join(re.findall(rb"\((.*?)\) Tj", data))
    assert b"Lagos Life Platform" in text
    assert b"item one" in text
    assert b"(with" in text or b"with" in text  # parens escaped, text intact
    # pagination cap is respected for a long document
    long_md = "## H\n\n" + ("Para " * 80 + "\n\n") * 200
    pages = pdf._paginate(long_md)
    assert len(pages) <= 200


def test_pdf_render_report_roundtrip():
    from app.engine import analytics
    from app.engine.reports import render_report

    project = {"name": "PDF Co", "id": "p", "description": "d", "status": "active",
               "tasks": []}
    pages = [{"id": "pg1", "url": "https://t.test/", "title": "Home",
              "status": "documented", "content_category": "landing"}]
    features = [{"id": "f1", "name": "Ad booking", "category": "monetisation",
                 "description": "book a slot", "confidence": 0.8, "status": "documented",
                 "dependencies": [], "related_features": []}]
    observations = [{"id": "o1", "kind": "fact", "key": "price", "value": "250k",
                     "observation": "pricing table", "evidence_class": "C",
                     "confidence": 0.9, "status": "verified", "evidence_ids": ["e1"]}]
    evidence = [{"id": "e1", "ref_code": "E01", "evidence_class": "C",
                 "source_uri": "https://t.test/", "source_name": "home",
                 "capture_method": "manual", "description": "pricing", "meta": {},
                 "cited_by": ["o1"]}]
    ctx = {"project": project, "tasks": [], "pages": pages, "features": features,
           "observations": observations, "evidence": evidence, "questions": []}
    ctx["analytics"] = analytics.full_project_analytics(
        project, pages, features, evidence, observations, [])
    out = render_report("executive", ctx, "pdf")
    assert out.startswith("data:application/pdf;base64,")
    raw = base64.b64decode(out.split(",", 1)[1])
    assert raw[:8] == b"%PDF-1.4" and raw.rstrip().endswith(b"%%EOF")
    assert b"Executive Intelligence Report" in b" ".join(
        __import__("re").findall(rb"\((.*?)\) Tj", raw))


# ---------------------------------------------------------------- plugin registry

def test_plugin_registry_builtins_and_errors():
    from app.engine.plugins import KINDS, discover, registry

    handled = discover()
    assert any(h.startswith("ai_provider/") for h in handled)
    assert registry.has("ai_provider", "off")
    assert registry.has("ai_provider", "openai_compatible")
    assert registry.has("report_format", "pdf")
    assert all(registry.has("browser_engine", e) for e in ("chromium", "firefox", "webkit"))
    assert registry.has("analysis_module", "gap_and_opportunity")
    # idempotent discovery
    assert discover() is not None
    # unknown kind / name raise informative errors
    try:
        registry.register("nope", "x", lambda: None)
        assert False
    except ValueError:
        pass
    try:
        registry.get("ai_provider", "does-not-exist")
        assert False
    except KeyError as e:
        assert "off" in str(e)  # lists what IS available
    # list() returns only the requested kind
    names = [p.name for p in registry.list("report_format")]
    assert "pdf" in names and "off" not in names


def test_plugin_isolation_bad_external_cannot_break_core():
    """A raising plugin factory must not break built-in resolution."""
    from app.engine.plugins import registry

    registry.register("analysis_module", "broken", lambda: 1 / 0, source="test")
    p = registry.get("analysis_module", "broken")
    assert p.factory is not None
    # built-ins still resolve normally
    assert registry.has("ai_provider", "off")
    assert registry.has("analysis_module", "gap_and_opportunity")
    del registry._items["analysis_module"]["broken"]


# ---------------------------------------------------------------- backup + portability (API level)

async def _seed(pid, name):
    from app.db import session_scope
    from app.models import (Evidence, Feature, Observation, PageRecord,
                            Project)

    ev1, ev2 = "EV_" + pid[:8] + "A", "EV_" + pid[:8] + "B"
    async with session_scope() as s:
        s.add(Project(id=pid, name=name, slug=name.lower().replace(" ", "-"),
                      description="portability", industry="media",
                      target_base_url="https://bundle.test"))
        await s.flush()  # parent first (codebase convention; see test_agent_e2e)
        s.add(Evidence(id=ev1, project_id=pid, ref_code="E01",
                       evidence_class="C", source_uri="https://bundle.test/",
                       source_name="home", capture_method="manual",
                       description="pricing table", meta={}))
        s.add(Evidence(id=ev2, project_id=pid, ref_code="E02",
                       evidence_class="I", source_uri="https://bundle.test/about",
                       source_name="about", capture_method="manual",
                       description="company note", meta={}))
        s.add(PageRecord(id="PG1" + pid[:6], project_id=pid,
                         url="https://bundle.test/", canonical_url="https://bundle.test/",
                         title="Home",
                         status="documented", content_category="landing",
                         purpose="landing", summary="home page",
                         structure={}, body_text="Pricing: 250k",
                         capture_method="manual", error="",
                         evidence_ids=[ev1]))
        s.add(PageRecord(id="PG2" + pid[:6], project_id=pid,
                         url="https://bundle.test/about",
                         canonical_url="https://bundle.test/about", title="About",
                         status="documented", content_category="about",
                         purpose="about", summary="about page",
                         structure={}, body_text="We help people",
                         capture_method="manual", error="",
                         evidence_ids=[ev2]))
        s.add(Feature(id="FE1" + pid[:6], project_id=pid, name="Ad booking",
                      slug="ad-booking",
                      category="monetisation", description="book a slot",
                      purpose="revenue", access_location="/advertise",
                      limitations="", opportunities="", dependencies=[],
                      related_features=[], confidence=0.8,
                      status="documented", evidence_ids=[ev1]))
        s.add(Observation(project_id=pid, kind="fact", key="price",
                          value="250k/7d", observation="pricing table",
                          evidence_ids=[ev1], evidence_class="C",
                          confidence=0.9, status="verified",
                          created_by="seed"))
        await s.commit()


def test_backup_endpoint_creates_consistent_copy():
    from app.db import get_engine

    async def _run():
        from app.main import create_app
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
        ) as c:
            r = await c.post("/api/systems/backup")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] and body["bytes"] > 0
            assert os.path.exists(os.path.join(
                os.environ["RICE_DATA_DIR"], body["path"]))
            r2 = await c.get("/api/systems/backups")
            assert r2.status_code == 200
            assert any(b["name"] == os.path.basename(body["path"])
                       for b in r2.json())
    start(_run)


def _client():
    from app.main import create_app
    import httpx

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def test_export_import_roundtrip_remapping():
    from app.engine.ids import new_id

    pid = new_id()[:26]  # unique per run; stable within the test
    name = f"Bundle Co {pid[-6:]}"

    async def _run():
        async with _client() as c:
            await _seed(pid, name)
            # ---- export
            r = await c.get(f"/api/projects/{pid}/export")
            assert r.status_code == 200, r.text
            bundle = r.json()
            assert bundle["version"] == 1
            assert len(bundle["pages"]) == 2
            assert len(bundle["evidence"]) == 2
            assert len(bundle["features"]) == 1
            # evidence refs normalised to positional ints
            assert bundle["pages"][0]["evidence_ids"] == [0]
            assert bundle["features"][0]["evidence_ids"] == [0]
            # ---- import as a new project
            r = await c.post("/api/projects/import",
                             params={"name": "Imported Bundle"},
                             content=json.dumps(bundle),
                             headers={"Content-Type": "application/json"})
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["ok"]
            new_pid = body["project_id"]
            assert new_pid != pid
            assert body["counts"] == {"pages": 2, "features": 1,
                                      "evidence": 2, "observations": 1}
            # ---- new project is isolated and remapped
            r = await c.get(f"/api/projects/{new_pid}")
            assert r.status_code == 200
            pr = r.json()
            assert pr["name"] == "Imported Bundle"
            # feature in the NEW project must reference a NEW evidence id
            r = await c.get(f"/api/projects/{new_pid}/features")
            assert r.status_code == 200
            feats = r.json()
            assert len(feats) == 1
            new_refs = feats[0].get("evidence_ids") or feats[0].get("evidence_refs") or []
            assert new_refs and all(ref != "EV_" + pid[:8] + "A" for ref in new_refs)
            # original project untouched
            r = await c.get(f"/api/projects/{pid}")
            assert r.status_code == 200 and r.json()["name"] == name
    start(_run)


def test_import_rejects_bad_bundles():
    async def _run():
        async with _client() as c:
            for bad in ({}, {"version": 99},
                        {"version": 1, "project": {}, "pages": [], "features": [],
                         "evidence": [], "observations": []}):
                r = await c.post("/api/projects/import",
                                 content=json.dumps(bad),
                                 headers={"Content-Type": "application/json"})
                assert r.status_code == 400, (bad, r.status_code, r.text)
    start(_run)


def test_plugins_endpoint_shape():
    async def _run():
        async with _client() as c:
            r = await c.get("/api/plugins")
            assert r.status_code == 200, r.text
            body = r.json()
            assert set(body) == {"ai_provider", "browser_engine",
                                 "report_format", "analysis_module"}
            assert any(p["name"] == "off" for p in body["ai_provider"])
            assert any(p["name"] == "pdf" for p in body["report_format"])
    start(_run)
