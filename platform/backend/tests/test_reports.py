"""Report generation: all 14 types, all formats, evidence footer present."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT  # noqa: F401

from app.engine.reports import (REPORT_TYPES, render_report, to_csv, to_html,
                                to_json)


def _ctx():
    return {
        "project": {"name": "Test Co", "id": "p1", "description": "d", "status": "active"},
        "tasks": [],
        "pages": [
            {"id": "pg1", "url": "https://t.test/", "title": "Home", "status": "documented",
             "content_category": "landing", "purpose": "landing", "summary": "s",
             "structure": {"states": {"empty": False, "loading": False, "error": False},
                           "forms": [{"action": "/login", "method": "post",
                                      "fields": [{"name": "user"}, {"name": "pw", "type": "password"}]}],
                           "controls": [{"name": "user"}, {"name": "pw"}],
                           "navigation": [{"text": "About", "href": "/about"}],
                           "element_counts": {"div": 10}},
             "observed_at": "2026-11-14", "capture_method": "browser:chromium", "error": "",
             "evidence_refs": ["E01"]},
            {"id": "pg2", "url": "https://t.test/missing", "title": "", "status": "error",
             "content_category": "", "purpose": "", "summary": "", "structure": {},
             "observed_at": "", "capture_method": "", "error": "timeout after 30s",
             "evidence_refs": []},
        ],
        "features": [
            {"id": "f1", "name": "Log-in", "category": "authentication",
             "description": "Username + password", "purpose": "auth", "access_location": "/",
             "inputs": "user, pw", "outputs": "session", "observed_behaviour": "posts /login",
             "dependencies": [], "related_features": [], "user_journey": "arrives → enters credentials → then sees dashboard",
             "limitations": "not observed in full", "opportunities": "add 2FA",
             "implementation_implications": "", "evidence_refs": ["E01"],
             "evidence_ids": ["ev1"], "confidence": 0.9, "status": "documented"},
            {"id": "f2", "name": "Billboard ads", "category": "monetisation",
             "description": "₦250,000 per 7 days", "purpose": "revenue",
             "access_location": "/advertise", "inputs": "image", "outputs": "ad live",
             "observed_behaviour": "form + payment", "dependencies": [], "related_features": [],
             "user_journey": "", "limitations": "price history unknown. Passive inventory.",
             "opportunities": "programmatic bidding", "implementation_implications": "",
             "evidence_refs": ["E15"], "evidence_ids": ["ev2"], "confidence": 0.9,
             "status": "documented"},
        ],
        "observations": [
            {"id": "o1", "kind": "fact", "key": "billboard price", "value": "₦250,000/7d",
             "observation": "advertise page states ₦250,000 per 7 days", "evidence_class": "C",
             "status": "verified", "evidence_refs": ["E15"], "created_at": "2026-11-14"},
            {"id": "o2", "kind": "interaction", "key": "signup", "value": "",
             "observation": "user tapped 'Sign up free'", "evidence_class": "C",
             "status": "open", "evidence_refs": ["E01"], "created_at": "2026-11-14"},
        ],
        "evidence": [
            {"id": "ev1", "ref_code": "E01", "evidence_class": "C", "source_uri": "https://t.test/",
             "source_name": "Home", "capture_method": "read", "description": "landing",
             "captured_at": "2026-11-14", "cited_by": ["o1"]},
            {"id": "ev2", "ref_code": "E15", "evidence_class": "C", "source_uri": "https://t.test/advertise",
             "source_name": "Advertise", "capture_method": "read", "description": "ads",
             "captured_at": "2026-11-14", "cited_by": ["o1"]},
        ],
        "questions": [{"id": "q1", "question": "Why the price rose?", "status": "open"}],
        "reports": [],
        "analytics": None,
    }


def test_all_types_render_markdown():
    from app.engine import analytics as A
    ctx = _ctx()
    ctx["analytics"] = A.full_project_analytics(
        ctx["project"], ctx["pages"], ctx["features"], ctx["evidence"],
        ctx["observations"], ctx["questions"])
    for rtype in REPORT_TYPES:
        out = render_report(rtype, ctx, "md")
        assert len(out) > 100, rtype
        # every report carries evidence references + date
        assert "Evidence" in out or "evidence" in out, rtype
        assert "Generated" in out, rtype


def test_json_format():
    import json
    ctx = _ctx()
    out = to_json(ctx, "feature_inventory")
    data = json.loads(out)
    assert data["type"] == "feature_inventory"
    assert len(data["data"]["features"]) == 2


def test_csv_format():
    ctx = _ctx()
    out = to_csv(ctx, "feature_inventory")
    lines = out.strip().splitlines()
    assert lines[0].startswith("name,category")
    assert "Log-in" in out
    out2 = to_csv(ctx, "evidence_register")
    assert "E01" in out2


def test_html_format():
    ctx = _ctx()
    out = to_html("# Title\n\n| a | b |\n| --- | --- |\n| 1 | 2 |", "T")
    assert out.startswith("<!doctype html>")
    assert "<table>" in out


def test_mermaid_journey_block():
    ctx = _ctx()
    out = render_report("user_journeys", ctx, "md")
    assert "```mermaid" in out
    assert "journey" in out


def test_unknown_type_raises():
    import pytest
    ctx = _ctx()
    with pytest.raises(ValueError):
        render_report("nonsense", ctx, "md")
