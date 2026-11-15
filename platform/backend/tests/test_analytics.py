"""Analytics engine tests — every score verified against its documented
formula (no arbitrary percentages)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT  # noqa: F401

from app.engine import analytics as A
from app.models import EVIDENCE_WEIGHTS


def _ev(code, cls):
    return {"id": f"ev-{code}", "evidence_class": cls}


def _obs(evidence_ids, confidence=0.5):
    return {"id": "o1", "evidence_ids": evidence_ids, "confidence": confidence, "key": "", "value": "", "observation": "", "evidence_class": "I", "status": "open"}


def test_evidence_quality_pure_c():
    eq = A.evidence_quality([_ev(1, "C"), _ev(2, "C")], [_obs(["ev-1"])])
    # all C ⇒ raw 1.0; cited: ev-1 cited once ⇒ 1.0; score 1.0
    assert eq["score"] == 1.0


def test_evidence_quality_pure_s():
    eq = A.evidence_quality([_ev(1, "S"), _ev(2, "S")], [])
    assert abs(eq["score"] - EVIDENCE_WEIGHTS["S"]) < 1e-9


def test_evidence_quality_empty():
    eq = A.evidence_quality([], [])
    assert eq["score"] == 0.0


def test_feature_completeness_math():
    f1 = {k: "" for k in A.FEATURE_REQUIRED_FIELDS}
    f1.update({"name": "F1", "id": "f1", "category": "economy"})
    f2 = {k: "x" for k in A.FEATURE_REQUIRED_FIELDS}
    f2.update({"name": "F2", "id": "f2", "category": "social_interaction"})
    fc = A.feature_completeness([f1, f2])
    # field rate: 8 of 16 filled = 0.5
    assert abs(fc["field_rate"] - 0.5) < 1e-9
    assert fc["categories_covered"] == 2
    assert fc["incomplete"][0]["feature"] == "F1"


def test_page_coverage_math():
    pages = [
        {"id": "p1", "url": "a", "status": "documented", "error": ""},
        {"id": "p2", "url": "b", "status": "documented", "error": ""},
        {"id": "p3", "url": "c", "status": "error", "error": "timeout"},
        {"id": "p4", "url": "d", "status": "pending", "error": ""},
    ]
    pc = A.page_coverage(pages)
    assert pc["documented"] == 2 and pc["error"] == 1 and pc["pending"] == 1
    assert abs(pc["score"] - 0.5) < 1e-9
    assert pc["error_pages"][0]["error"] == "timeout"


def test_contradiction_detection():
    obs = [
        {"id": "a", "key": "billboard price", "value": "₦250,000 / 7 days", "observation": "", "evidence_class": "C"},
        {"id": "b", "key": "billboard price", "value": "₦50,000 / week", "observation": "", "evidence_class": "S"},
        {"id": "c", "key": "launch date", "value": "1 Oct 2026", "observation": "", "evidence_class": "S"},
    ]
    cc = A.contradiction_detection(obs)
    assert cc["count"] == 1
    assert cc["conflicts"][0]["topic"] == "billboard price"
    assert len(cc["conflicts"][0]["values"]) == 2


def test_duplicate_detection():
    feats = [
        {"id": "a", "name": "Password recovery", "description": "Reset password via owner questions"},
        {"id": "b", "name": "Password recovery", "description": "Reset the password using owner questions"},
        {"id": "c", "name": "Billboard advertising", "description": "Buy a billboard for ads"},
    ]
    dd = A.duplicate_detection(feats)
    assert dd["count"] >= 1
    assert dd["candidates"][0]["similarity"] >= 0.6


def test_completeness_weighted():
    task = {"progress": 50.0}
    fc = {"score": 0.8}
    pc = {"score": 0.5}
    eq = {"score": 1.0}
    rc = A.research_completeness(task, fc, pc, eq, {"open_questions": 0})
    expected = (0.30 * 0.5 + 0.25 * 0.8 + 0.20 * 0.5 + 0.15 * 1.0 + 0.10 * 1.0)
    assert abs(rc["score"] - expected) < 1e-9
    assert set(rc["weights"].keys()) == set(A.COMPLETENESS_WEIGHTS.keys())


def test_missing_information_lists_gaps():
    mi = A.missing_information(
        [{"name": "F", "id": "f", "description": "", "purpose": "p", "access_location": "a",
          "inputs": "", "outputs": "", "observed_behaviour": "b", "limitations": "l",
          "evidence_ids": ["e"]}],
        [{"id": "p", "url": "u", "status": "error", "error": "timeout"}],
        [{"id": "q", "question": "why?", "status": "open"}],
    )
    kinds = {g["kind"] for g in mi["gaps"]}
    assert "feature_field" in kinds
    assert "page_error" in kinds
    assert "unresolved_question" in kinds
    assert mi["open_questions"] == 1


def test_opportunity_formula():
    f = {"name": "Business", "id": "f", "category": "economy",
         "limitations": "Passive only: no staff, stock, pricing or customers reported. Unknown limits.",
         "opportunities": "Add production and staff",
         "evidence_ids": ["ev-1"], "meta": {"evidence_weights": {"ev-1": 0.55}}}
    go = A.gap_and_opportunity([f])
    row = go["opportunities"][0]
    pressure = row["components"]["limitation_pressure"]
    weak = row["components"]["evidence_weakness"]
    cw = row["components"]["category_weight"]
    assert abs(row["score"] - (0.5 * pressure + 0.3 * weak + 0.2 * cw)) < 1e-9
    assert cw == 1.0  # strategic category
