import json

from nlie import features, knowledge, security, understanding, visual
from nlie.db import Feature, Version, session


def test_redaction_removes_secrets():
    out = security.redact({"password": "hunter2", "note": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456", "token": "ghp_" + "a" * 36, "ok": "plain"})
    dumped = json.dumps(out)
    assert "hunter2" not in dumped and "abcdefghijklmnop" not in dumped and "ghp_aaaa" not in dumped
    assert out["ok"] == "plain"
    assert "4111 1111 1111 1111" not in security.redact_text("card 4111 1111 1111 1111 used")


def test_page_understanding_structures_a_page():
    html = """<html><head><title>Log in</title></head><body><nav><a href="/a">A</a><a href="https://x.test/b">B</a></nav>
    <main><h1>Sign in</h1><form method="post" action="/s"><input name="u" required><input type="password" name="p"><input type="hidden" name="csrf" value="z">
    <button type="submit">Go</button></form></main></body></html>"""
    rec = understanding.analyse(html, "https://demo.test/login")
    assert rec["title"] == "Log in" and rec["category"] == "authentication"
    assert rec["forms"][0]["method"] == "post" and [f["name"] for f in rec["forms"][0]["fields"]] == ["u", "p"]  # hidden field excluded
    assert rec["internal_links"] == ["https://demo.test/a"]
    assert "possibly_client_rendered" in rec["states"]  # under 200 characters and not rendered
    assert any(f["kind"] == "form" for f in understanding.findings_from_record(rec))


def test_feature_categories_and_fields():
    assert len(features.CATEGORIES) == 20 and len(features.FIELDS) + 1 == 15
    assert features.categorise("Password recovery")[0] == "Authentication"
    assert features.categorise("Zzz")[0] == "Other"
    filled, missing = features.field_completeness({"description": "x", "purpose": " "})
    assert filled == 1 and "purpose" in missing


def test_findings_are_deduplicated(project):
    with session() as s:
        a, created_a = knowledge.add_finding(s, project, "Button 'Start' is present.", page_id=None)
        b, created_b = knowledge.add_finding(s, project, "button  'start' is present", page_id=None)
        assert created_a and not created_b and a.uid == b.uid and a.uid.startswith("F-")


def test_feature_update_keeps_history_and_protects_verified(project):
    with session() as s:
        f, act = knowledge.upsert_feature(s, project, "Wallet", "Economy", {"description": "Holds money"}, evidence_refs=["EV-0001"])
        assert act == "created"
        _, act = knowledge.upsert_feature(s, project, "Wallet", "Economy", {"description": "CHANGED", "purpose": "Pay"}, evidence_refs=["EV-0002"])
        assert act == "updated" and f.fields["description"] == "Holds money" and f.fields["purpose"] == "Pay"  # existing text kept
        assert s.query(Version).filter_by(entity_type="features", entity_id=f.id).count() == 1
        assert s.query(Version).first().snapshot["fields"] == {"description": "Holds money"}
        f.status = "verified"
        _, act = knowledge.upsert_feature(s, project, "Wallet", "Economy", {"inputs": "amount"})
        assert act == "unchanged" and "inputs" not in f.fields
        _, act = knowledge.upsert_feature(s, project, "Wallet", "Economy", {"description": "CHANGED"}, overwrite=True)
        assert act == "updated" and s.query(Version).filter_by(entity_id=f.id).count() == 2
        assert s.query(Feature).count() == 1


def test_search_ranks_by_shared_words(project):
    with session() as s:
        knowledge.upsert_feature(s, project, "Wallet", "Economy", {"description": "Holds naira and shows transfers"})
        knowledge.upsert_feature(s, project, "Bus travel", "Transportation", {"description": "Move between cities"})
        res = knowledge.search(s, project, "naira transfers")
        assert res and res[0]["title"] == "Wallet" and res[0]["matched_terms"] == ["naira", "transfers"]
        assert knowledge.search(s, project, "zebra") == []


def test_visual_comparison(tmp_path):
    from PIL import Image, ImageDraw
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (200, 100), "white").save(a)
    im = Image.new("RGB", (200, 100), "white")
    ImageDraw.Draw(im).rectangle([50, 20, 99, 59], fill="black")
    im.save(b)
    same = visual.compare(a, a)
    diff = visual.compare(a, b)
    assert same["changed_ratio"] == 0 and same["identical_file"]
    assert abs(diff["changed_ratio"] - (50 * 40) / (200 * 100)) < 0.001
    assert diff["changed_region"] == [50, 20, 100, 60]
    assert visual.image_info(a)["width"] == 200
