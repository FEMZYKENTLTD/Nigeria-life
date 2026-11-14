"""Advanced research analytics.

Every score is deterministic and *explained*: the output carries the formula
and the inputs used, so no number in the dashboard is arbitrary. (Directive
§9: “Do not use arbitrary percentages that have no defined calculation.”)

Inputs are plain dicts (rows from the database) so this module is unit-testable
without a running engine.
"""
from __future__ import annotations

from ..models import EVIDENCE_WEIGHTS, FEATURE_CATEGORIES
from .textsim import jaccard

# --- policy weights (documented in ARCHITECTURE.md; tunable per project) ---
COMPLETENESS_WEIGHTS = {
    "objective_progress": 0.30,
    "feature_completeness": 0.25,
    "page_coverage": 0.20,
    "evidence_quality": 0.15,
    "open_questions": 0.10,
}

FEATURE_REQUIRED_FIELDS = (
    "description", "purpose", "access_location", "inputs", "outputs",
    "observed_behaviour", "limitations", "evidence_ids",
)

DUPLICATE_THRESHOLD = 0.60


def _round(x: float, nd: int = 3) -> float:
    return round(float(x), nd)


def evidence_quality(evidence_rows: list[dict], observation_rows: list[dict]) -> dict:
    """Mean class weight across all evidence, plus a usage-weighted variant
    (evidence actually cited by observations weighs more)."""
    if not evidence_rows and not observation_rows:
        return {"score": 0.0, "explanation": "No evidence recorded yet — quality undefined (scored 0).",
                "by_class": {}, "used": {}, "total": 0}
    by_class: dict[str, int] = {}
    for e in evidence_rows:
        by_class[e["evidence_class"]] = by_class.get(e["evidence_class"], 0) + 1
    used: dict[str, int] = {}
    for o in observation_rows:
        for eid in o.get("evidence_ids") or []:
            used[eid] = used.get(eid, 0) + 1
    total_w = sum(EVIDENCE_WEIGHTS.get(c, 0.5) * n for c, n in by_class.items())
    total_n = sum(by_class.values()) or 1
    raw = total_w / total_n
    # blend with usage-weighted quality: cited evidence reflects what the
    # research actually rests on (50/50 blend).
    cited_w = 0.0
    cited_n = 0
    ev_by_id = {e["id"]: e for e in evidence_rows}
    for eid, n in used.items():
        e = ev_by_id.get(eid)
        if e:
            cited_w += EVIDENCE_WEIGHTS.get(e["evidence_class"], 0.5) * n
            cited_n += n
    cited = (cited_w / cited_n) if cited_n else raw
    score = 0.5 * raw + 0.5 * cited
    breakdown = {c: {"count": n, "weight": EVIDENCE_WEIGHTS.get(c, 0.5)} for c, n in by_class.items()}
    return {
        "score": _round(score),
        "by_class": breakdown,
        "cited_evidence": cited_n,
        "total": total_n,
        "explanation": (
            "score = 0.5·(mean class weight of all evidence) + 0.5·(mean class weight of "
            f"cited evidence). Class weights: "
            + ", ".join(f"{c}={w}" for c, w in EVIDENCE_WEIGHTS.items())
            + f". Evidence present: {total_n}, cited by findings: {cited_n}."
        ),
    }


def feature_completeness(features: list[dict]) -> dict:
    """Share of the required documentation fields present across features,
    plus breadth across the 20 categories. Neither claims exhaustiveness —
    the explanation says exactly what was measured."""
    if not features:
        return {"score": 0.0, "field_rate": 0.0, "category_breadth": 0.0,
                "categories_covered": 0, "total_categories": len(FEATURE_CATEGORIES),
                "incomplete": [], "explanation": "No features documented yet."}
    total_fields = 0
    present_fields = 0
    incomplete: list[dict] = []
    cats: set[str] = set()
    for f in features:
        cats.add(f.get("category") or "other")
        missing = []
        for field in FEATURE_REQUIRED_FIELDS:
            total_fields += 1
            v = f.get(field)
            has = bool((v or "").strip()) if isinstance(v, str) else bool(v)
            if has:
                present_fields += 1
            else:
                missing.append(field)
        if missing:
            incomplete.append({"feature": f.get("name"), "id": f.get("id"), "missing": missing})
    field_rate = present_fields / total_fields if total_fields else 0.0
    breadth = len(cats) / len(FEATURE_CATEGORIES)
    score = 0.7 * field_rate + 0.3 * breadth
    return {
        "score": _round(score),
        "field_rate": _round(field_rate),
        "category_breadth": _round(breadth),
        "categories_covered": len(cats),
        "total_categories": len(FEATURE_CATEGORIES),
        "incomplete": incomplete[:100],
        "explanation": (
            f"score = 0.7·(share of {len(FEATURE_REQUIRED_FIELDS)} required feature fields filled) "
            f"+ 0.3·(share of {len(FEATURE_CATEGORIES)} feature categories with ≥1 feature). "
            f"Field rate {field_rate:.0%}; breadth {len(cats)}/{len(FEATURE_CATEGORIES)}. "
            "Breadth measures documented coverage, NOT exhaustiveness of the target."
        ),
    }


def page_coverage(pages: list[dict]) -> dict:
    documented = [p for p in pages if p["status"] == "documented"]
    errored = [p for p in pages if p["status"] == "error"]
    empty = [p for p in pages if p["status"] == "empty"]
    pending = [p for p in pages if p["status"] == "pending"]
    n = len(pages)
    score = (len(documented) / n) if n else 0.0
    return {
        "score": _round(score),
        "documented": len(documented),
        "error": len(errored),
        "empty": len(empty),
        "pending": len(pending),
        "total": n,
        "error_pages": [{"id": p["id"], "url": p.get("url"), "error": p.get("error", "")[:200]} for p in errored][:50],
        "explanation": (
            f"score = documented pages / known pages = {len(documented)}/{n}. "
            f"{len(errored)} page(s) errored, {len(empty)} empty, {len(pending)} still pending. "
            "A page only counts once its content was actually understood — loading a URL is not enough."
        ),
    }


def confidence_distribution(observations: list[dict]) -> dict:
    if not observations:
        return {"mean": 0.0, "buckets": {"high (≥0.75)": 0, "medium (0.5–0.75)": 0, "low (<0.5)": 0},
                "count": 0, "explanation": "No findings recorded yet."}
    confs = [float(o.get("confidence") or 0.5) for o in observations]
    mean = sum(confs) / len(confs)
    hi = sum(1 for c in confs if c >= 0.75)
    mid = sum(1 for c in confs if 0.5 <= c < 0.75)
    lo = sum(1 for c in confs if c < 0.5)
    return {
        "mean": _round(mean),
        "count": len(confs),
        "buckets": {"high (≥0.75)": hi, "medium (0.5–0.75)": mid, "low (<0.5)": lo},
        "explanation": (
            f"Mean confidence across {len(confs)} findings = {mean:.3f}. Confidence is assigned at "
            "finding time from its evidence class (C→0.9, I→0.7, S→0.55, H→0.35, U→0.15) and may be "
            "adjusted by the researcher."
        ),
    }


def duplicate_detection(features: list[dict]) -> dict:
    pairs = []
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            a, b = features[i], features[j]
            sim = jaccard(a.get("name", "") + " " + (a.get("description") or "")[:200],
                          b.get("name", "") + " " + (b.get("description") or "")[:200])
            if sim >= DUPLICATE_THRESHOLD:
                pairs.append({
                    "a": {"id": a["id"], "name": a.get("name")},
                    "b": {"id": b["id"], "name": b.get("name")},
                    "similarity": _round(sim),
                })
    pairs.sort(key=lambda p: -p["similarity"])
    return {
        "candidates": pairs[:50],
        "count": len(pairs),
        "threshold": DUPLICATE_THRESHOLD,
        "explanation": (
            f"Candidate pairs share ≥{DUPLICATE_THRESHOLD:.0%} Jaccard similarity of content tokens "
            "between (name + first 200 chars of description). These are candidates for review, not "
            "confirmed duplicates."
        ),
    }


def contradiction_detection(observations: list[dict]) -> dict:
    """Group 'fact' findings by topic key; report keys with ≥2 distinct
    normalised values."""
    from .textsim import normalize

    groups: dict[str, dict[str, list[dict]]] = {}
    for o in observations:
        if not o.get("key"):
            continue
        key = normalize(o["key"])
        val = normalize(o.get("value") or "")
        if not val:
            continue
        groups.setdefault(key, {}).setdefault(val, []).append({
            "id": o["id"], "value": (o.get("value") or "")[:200],
            "evidence_class": o.get("evidence_class"), "observation": (o.get("observation") or "")[:200],
        })
    conflicts = []
    for key, vals in sorted(groups.items()):
        if len(vals) > 1:
            merged = []
            for val, items in sorted(vals.items(), key=lambda kv: -len(kv[1])):
                merged.append({"value": val, "sources": items[:6]})
            conflicts.append({"topic": key, "values": merged})
    return {
        "conflicts": conflicts[:100],
        "count": len(conflicts),
        "explanation": (
            "Fact findings are grouped by topic key; a conflict is any topic with ≥2 distinct "
            "normalised values. Each value lists the findings (and their evidence) that support it."
        ),
    }


def missing_information(features: list[dict], pages: list[dict], questions: list[dict]) -> dict:
    gaps: list[dict] = []
    for f in features:
        for field in FEATURE_REQUIRED_FIELDS:
            v = f.get(field)
            has = bool((v or "").strip()) if isinstance(v, str) else bool(v)
            if not has:
                gaps.append({"kind": "feature_field", "subject": f.get("name"), "subject_id": f.get("id"),
                             "gap": field, "severity": "minor" if field in ("inputs", "outputs") else "major"})
    for p in pages:
        if p["status"] == "error":
            gaps.append({"kind": "page_error", "subject": p.get("url"), "subject_id": p.get("id"),
                         "gap": p.get("error", "page failed")[:200], "severity": "major"})
        elif p["status"] == "pending":
            gaps.append({"kind": "page_pending", "subject": p.get("url"), "subject_id": p.get("id"),
                         "gap": "not yet documented", "severity": "minor"})
    open_qs = [q for q in questions if q.get("status") == "open"]
    for q in open_qs:
        gaps.append({"kind": "unresolved_question", "subject": q.get("question"), "subject_id": q.get("id"),
                     "gap": "open question", "severity": "major"})
    major = sum(1 for g in gaps if g["severity"] == "major")
    return {
        "gaps": gaps[:200],
        "count": len(gaps),
        "major": major,
        "open_questions": len(open_qs),
        "explanation": (
            f"{len(gaps)} concrete gaps: unfilled required feature fields, errored/pending pages and "
            f"open questions ({len(open_qs)} open). Each item names exactly what is missing and where."
        ),
    }


def dependency_analysis(features: list[dict]) -> dict:
    by_name = {f["name"].lower(): f for f in features}
    depth: dict[str, int] = {}
    visiting: set[str] = set()
    cycles: list[list[str]] = []

    def _depth(name: str, seen: list[str]) -> int:
        key = name.lower()
        if key in depth:
            return depth[key]
        if key in visiting:
            idx = seen.index(key) if key in seen else -1
            if idx >= 0:
                cycles.append(seen[idx:] + [key])
            return 0
        visiting.add(key)
        d = 0
        f = by_name.get(key)
        if f:
            for dep in f.get("dependencies") or []:
                if isinstance(dep, str) and dep.lower() in by_name:
                    d = max(d, 1 + _depth(dep, seen + [key]))
        visiting.discard(key)
        depth[key] = d
        return d

    orphans = []
    for f in features:
        _depth(f["name"], [])
        if not (f.get("dependencies") or []) and not (f.get("related_features") or []):
            orphans.append(f["name"])
    return {
        "depths": {k: v for k, v in sorted(depth.items(), key=lambda kv: -kv[1])[:50]},
        "cycles": cycles[:10],
        "orphans": orphans[:50],
        "explanation": (
            "Dependency graph built from each feature's declared dependencies. 'depths' lists the "
            "longest dependency chain per feature; cycles indicate circular dependencies that need "
            "review; orphans have no declared relations."
        ),
    }


def gap_and_opportunity(features: list[dict]) -> dict:
    """Competitive gap analysis + product opportunity scoring.

    opportunity(feature) = 0.5·limitation_pressure + 0.3·evidence_weakness + 0.2·category_weight
      limitation_pressure: normalised count of limitation phrases (cap 4)
      evidence_weakness:   1 − mean weight of that feature's cited evidence (weak competitor evidence ⇒ bigger opening)
      category_weight:     1.0 for economy/social/entertainment/monetisation (strategic areas for the
                           Nigeria Life product), 0.6 for user-facing core areas, 0.3 otherwise.
    All three components are returned per feature so the score is inspectable.
    """
    STRATEGIC = {"economy", "social_interaction", "entertainment", "monetisation", "marketplace", "business_management"}
    CORE = {"authentication", "user_profiles", "character_systems", "progression", "notifications"}
    sev_words = ("not found", "unknown", "unverified", "unconfirmed", "limited", "no ", "shallow", "passive", "cannot", "not seen", "secondary")
    rows = []
    for f in features:
        lim = (f.get("limitations") or "").lower()
        opp = (f.get("opportunities") or "").lower()
        # count severity phrases (capped at 4) + 1 for long limitation notes (capped 4)
        pressure = min(4, sum(1 for w in sev_words if w in lim) + (1 if len(lim.split()) > 40 else 0))
        ev_ids = f.get("evidence_ids") or []
        if ev_ids:
            # caller passes weights via meta['evidence_weights'] = {id: weight}
            weights = (f.get("meta") or {}).get("evidence_weights") or {}
            w = [weights.get(e, 0.5) for e in ev_ids]
            ev_weak = 1.0 - (sum(w) / len(w))
        else:
            ev_weak = 0.8  # no evidence at all ⇒ strongest opening
        cat = f.get("category") or "other"
        cw = 1.0 if cat in STRATEGIC else (0.6 if cat in CORE else 0.3)
        score = 0.5 * (pressure / 4.0) + 0.3 * ev_weak + 0.2 * cw
        rows.append({
            "feature": f.get("name"), "id": f.get("id"), "category": cat,
            "score": _round(score),
            "components": {"limitation_pressure": _round(pressure / 4.0), "evidence_weakness": _round(ev_weak), "category_weight": cw},
            "opportunity_note": (f.get("opportunities") or "")[:200],
        })
    rows.sort(key=lambda r: -r["score"])
    return {
        "opportunities": rows[:100],
        "explanation": (
            "opportunity = 0.5·limitation_pressure + 0.3·evidence_weakness + 0.2·category_weight. "
            "limitation_pressure = up to 4 severity phrases found in the limitation notes (+1 for long notes, capped 4); "
            "evidence_weakness = 1 − mean evidence-class weight cited (no evidence ⇒ 0.8); "
            "category_weight = 1.0 strategic, 0.6 core, 0.3 other. Higher ⇒ bigger product opening."
        ),
    }


def research_completeness(task: dict, fc: dict, pc: dict, eq: dict, qd: dict) -> dict:
    """Weighted synthesis of the component scores. Weights are a documented
    policy (COMPLETENESS_WEIGHTS), not an arbitrary number."""
    open_qs = qd.get("open_questions", 0)
    # open-questions component: 1 when none, decaying 0.1 per open question (floor 0)
    oq = max(0.0, 1.0 - 0.1 * open_qs)
    components = {
        "objective_progress": task.get("progress", 0.0) / 100.0,
        "feature_completeness": fc["score"],
        "page_coverage": pc["score"],
        "evidence_quality": eq["score"],
        "open_questions": oq,
    }
    total_w = sum(COMPLETENESS_WEIGHTS.values())
    score = sum(components[k] * COMPLETENESS_WEIGHTS[k] for k in components) / total_w
    return {
        "score": _round(score),
        "components": {k: _round(v) for k, v in components.items()},
        "weights": COMPLETENESS_WEIGHTS,
        "explanation": (
            "completeness = Σ weight·component: "
            + " + ".join(f"{w}·{k}" for k, w in COMPLETENESS_WEIGHTS.items())
            + ". Components: objective progress (subtasks complete/total), feature documentation "
            "completeness, page coverage, evidence quality, and open-question load. "
            "This is a coverage measure for THIS objective — it never claims the target is fully known."
        ),
    }


def full_project_analytics(project: dict, pages: list[dict], features: list[dict],
                           evidence: list[dict], observations: list[dict],
                           questions: list[dict]) -> dict:
    # attach evidence weights to features for opportunity scoring
    ev_weight = {e["id"]: EVIDENCE_WEIGHTS.get(e["evidence_class"], 0.5) for e in evidence}
    features = [dict(f, meta={"evidence_weights": ev_weight}) for f in features]
    eq = evidence_quality(evidence, observations)
    fc = feature_completeness(features)
    pc = page_coverage(pages)
    cd = confidence_distribution(observations)
    dd = duplicate_detection(features)
    cc = contradiction_detection(observations)
    mi = missing_information(features, pages, questions)
    da = dependency_analysis(features)
    go = gap_and_opportunity(features)
    active_tasks = [t for t in project.get("tasks", []) if t["status"] in ("running", "planned", "queued", "waiting_decision", "paused")]
    latest_task = max(project.get("tasks", [{}]), key=lambda t: t.get("updated_at") or "", default={})
    rc = research_completeness(latest_task, fc, pc, eq, {"open_questions": mi["open_questions"]})
    return {
        "project_id": project["id"],
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "research_completeness": rc,
        "evidence_quality": eq,
        "feature_completeness": fc,
        "page_coverage": pc,
        "confidence": cd,
        "duplicates": dd,
        "contradictions": cc,
        "missing_information": mi,
        "dependencies": da,
        "gaps_and_opportunities": go,
        "active_task_count": len(active_tasks),
    }
