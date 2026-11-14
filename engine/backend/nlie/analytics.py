"""Research analytics. Every figure carries its formula and the counts it was computed from.
Nothing here is an estimate: if the inputs are empty the value is None and the explanation says so."""
from __future__ import annotations
import re
from collections import Counter

from .db import Evidence, Feature, Finding, Page, Project, Question, Screenshot, Source, Task
from .features import CATEGORIES, FIELDS, field_completeness
from .knowledge import tokens


def metric(name, value, unit, formula, inputs, note=""):
    return {"name": name, "value": value, "unit": unit, "formula": formula, "inputs": inputs, "note": note}


def ratio(a, b):
    return round(100 * a / b, 1) if b else None


def compute(s, project: Project) -> dict:
    pid = project.id
    pages = s.query(Page).filter_by(project_id=pid).all()
    feats = s.query(Feature).filter_by(project_id=pid).all()
    evid = s.query(Evidence).filter_by(project_id=pid).all()
    finds = s.query(Finding).filter_by(project_id=pid).all()
    questions = s.query(Question).filter_by(project_id=pid).all()
    known_refs = {e.ref for e in evid}

    pstat = Counter(p.status for p in pages)
    first_hand = pstat["analysed"] + pstat["captured"]
    in_engine = first_hand + pstat["discovered"] + pstat["blocked"] + pstat["failed"]
    cats = Counter(f.category for f in feats)
    filled = [field_completeness(f.fields or {})[0] for f in feats]
    missing = Counter(m for f in feats for m in field_completeness(f.fields or {})[1])
    eclass = Counter(e.classification for e in evid)
    fconf = Counter(f.confidence for f in feats)
    archived = sum(1 for e in evid if e.file_path and e.sha256)
    cited = [f for f in feats if f.evidence_refs]
    dangling = sorted({r for f in feats for r in (f.evidence_refs or []) if r not in known_refs})

    metrics = [
        metric("Page capture coverage", ratio(first_hand, in_engine), "%", "pages captured first-hand ÷ pages known to the engine (captured + discovered + blocked + failed)",
               {"captured": first_hand, "discovered_not_captured": pstat["discovered"], "blocked": pstat["blocked"], "failed": pstat["failed"]},
               "Covers only pages the engine has discovered through links. It says nothing about pages that are not linked. "
               f"{pstat['imported']} further page(s) are known only from imported research and are not counted."),
        metric("Feature category coverage", ratio(sum(1 for c in CATEGORIES if cats[c]), len(CATEGORIES)), "%", "categories with at least one documented feature ÷ 20 categories",
               {"categories_with_features": sum(1 for c in CATEGORIES if cats[c]), "categories": len(CATEGORIES)},
               "A category with a feature is not a fully documented category."),
        metric("Documentation completeness", ratio(sum(filled), len(feats) * len(FIELDS)), "%", f"filled feature fields ÷ (features × {len(FIELDS)} fields)",
               {"filled_fields": sum(filled), "features": len(feats), "fields_per_feature": len(FIELDS)}, "Counts whether a field has text, not whether the text is correct."),
        metric("First-hand evidence share", ratio(eclass["confirmed"], len(evid)), "%", "evidence items classed 'confirmed' ÷ all evidence items",
               {"confirmed": eclass["confirmed"], "total": len(evid), **{k: v for k, v in eclass.items() if k != "confirmed"}}),
        metric("Archived evidence share", ratio(archived, len(evid)), "%", "evidence items with a stored file and SHA-256 ÷ all evidence items",
               {"archived": archived, "total": len(evid)}, "Imported evidence refers to external URLs and has no archived copy."),
        metric("Features with cited evidence", ratio(len(cited), len(feats)), "%", "features citing at least one evidence ID ÷ all features", {"cited": len(cited), "features": len(feats)}),
        metric("Features confirmed first-hand", ratio(fconf["confirmed"], len(feats)), "%", "features whose weakest evidence class is 'confirmed' ÷ all features",
               {**dict(fconf), "features": len(feats)}, "A feature's confidence is the weakest class among its evidence tags."),
    ]

    # duplicates: name-token Jaccard
    toks = [(f, set(tokens(f.name))) for f in feats]
    dups = []
    for i, (a, ta) in enumerate(toks):
        for b, tb in toks[i + 1:]:
            if ta and tb:
                j = len(ta & tb) / len(ta | tb)
                if j >= 0.6:
                    dups.append({"a": a.name, "b": b.name, "similarity": round(j, 2), "basis": "shared name words ÷ all name words (Jaccard ≥ 0.6)"})

    contradictions = [{"text": q.text, "origin": q.origin, "status": q.status} for q in questions if q.origin.startswith("conflict")]

    # dependencies: another feature's name appearing in this feature's dependency text
    names = sorted(((f.name, f) for f in feats if len(f.name) >= 4), key=lambda x: -len(x[0]))
    deps = []
    for f in feats:
        text = " " + (f.fields or {}).get("dependencies", "").lower() + " "
        for n, g in names:
            if g.id != f.id and re.search(r"(?<![a-z])" + re.escape(n.lower()) + r"(?![a-z])", text):
                deps.append({"from": f.name, "to": g.name})
    indeg = Counter(d["to"] for d in deps)

    # journeys: link graph between captured pages
    urls = {p.url for p in pages}
    edges = []
    for p in pages:
        for l in (p.record or {}).get("internal_links", [])[:100]:
            if l in urls and l != p.url:
                edges.append({"from": p.url, "to": l})

    gaps = [{"gap": f"No feature documented in category '{c}'", "basis": "category count is zero"} for c in CATEGORIES if not cats[c] and c != "Other"]
    gaps += [{"gap": f"'{f.name}' is not backed by first-hand evidence ({f.confidence})", "basis": "weakest evidence class"} for f in feats if f.confidence in ("unknown", "hypothesis")]
    gaps += [{"gap": f"Evidence ID {r} is cited but not in the register", "basis": "dangling reference"} for r in dangling]
    opportunities = [{"feature": f.name, "text": f.fields["opportunities"], "evidence": f.evidence_refs} for f in feats if (f.fields or {}).get("opportunities")]

    tasks = Counter(t.status for t in s.query(Task).filter_by(project_id=pid))
    return {
        "metrics": metrics,
        "counts": {"pages": dict(pstat), "features": len(feats), "findings": len(finds), "evidence": len(evid), "questions_open": sum(q.status == "open" for q in questions),
                   "screenshots": s.query(Screenshot).filter_by(project_id=pid).count(), "sources": s.query(Source).filter_by(project_id=pid).count(), "tasks": dict(tasks)},
        "features_by_category": [{"category": c, "count": cats[c]} for c in CATEGORIES],
        "evidence_by_class": [{"class": k, "count": eclass[k]} for k in ("confirmed", "secondary", "inference", "hypothesis", "unknown")],
        "feature_confidence": [{"class": k, "count": fconf[k]} for k in ("confirmed", "secondary", "inference", "hypothesis", "unknown")],
        "missing_fields": [{"field": f, "missing": missing[f], "of": len(feats)} for f in FIELDS],
        "duplicates": dups, "contradictions": contradictions,
        "contradiction_note": "Only conflicts recorded in the research are listed. The engine does not detect contradictions between free-text statements automatically.",
        "dependencies": {"edges": deps, "most_depended_on": [{"feature": k, "dependants": v} for k, v in indeg.most_common(10)],
                         "note": "An edge exists when one feature's 'dependencies' text names another feature. Unnamed dependencies are not detected."},
        "journeys": {"edges": edges[:500], "note": "Links between pages the engine knows. This is a navigation graph, not observed user behaviour."},
        "gaps": gaps, "opportunities": opportunities,
        "opportunity_note": "Listed only where a researcher or imported document wrote an opportunity. The engine does not invent them.",
    }
