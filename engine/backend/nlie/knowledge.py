"""Knowledge base: idempotent writes, version history, and search."""
from __future__ import annotations
import hashlib
import math
import re
from collections import Counter

from .db import Decision, Evidence, Feature, Finding, Page, Question, now, save_version
from .features import slugify

CONF_ORDER = ["unknown", "hypothesis", "inference", "secondary", "confirmed"]


def next_ref(s, project_id: int, prefix: str = "EV") -> str:
    n = s.query(Evidence).filter(Evidence.project_id == project_id, Evidence.ref.like(f"{prefix}-%")).count() + 1
    while s.query(Evidence).filter_by(project_id=project_id, ref=f"{prefix}-{n:04d}").first():
        n += 1
    return f"{prefix}-{n:04d}"


def add_evidence(s, project_id: int, *, kind: str, summary: str, classification: str, source_url: str = "", locator: str = "",
                 file_path: str = "", sha256: str = "", ref: str | None = None, captured_by: str = "engine") -> Evidence:
    if ref:
        ev = s.query(Evidence).filter_by(project_id=project_id, ref=ref).first()
        if ev:
            return ev
    ev = Evidence(project_id=project_id, ref=ref or next_ref(s, project_id), kind=kind, summary=summary, classification=classification,
                  source_url=source_url, locator=locator, file_path=file_path, sha256=sha256, captured_by=captured_by)
    s.add(ev)
    s.flush()
    return ev


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def add_finding(s, project_id: int, observation: str, *, page_id: int | None = None, evidence_id: int | None = None,
                confidence: str = "unknown", kind: str = "observation", related_features: list | None = None):
    """Returns (finding, created). The same observation on the same page is stored once."""
    fp = hashlib.sha256(f"{page_id}|{_norm(observation)}".encode()).hexdigest()
    f = s.query(Finding).filter_by(project_id=project_id, fingerprint=fp).first()
    if f:
        return f, False
    n = s.query(Finding).filter_by(project_id=project_id).count() + 1
    f = Finding(uid=f"F-{project_id}-{n:05d}-{fp[:6]}", project_id=project_id, page_id=page_id, observation=observation,
                evidence_id=evidence_id, confidence=confidence, kind=kind, related_features=related_features or [], fingerprint=fp)
    s.add(f)
    s.flush()
    return f, True


def upsert_feature(s, project_id: int, name: str, category: str, fields: dict, *, evidence_refs: list[str] | None = None,
                   confidence: str = "unknown", origin: str = "engine", overwrite: bool = False, reason: str = ""):
    """Returns (feature, action) where action is created | updated | unchanged.

    Existing non-empty fields are kept unless overwrite=True. Every change snapshots the previous version first.
    A feature marked 'verified' is never changed without overwrite=True."""
    slug = slugify(name)
    f = s.query(Feature).filter_by(project_id=project_id, slug=slug).first()
    if not f:
        f = Feature(project_id=project_id, slug=slug, name=name, category=category, fields=dict(fields),
                    evidence_refs=sorted(set(evidence_refs or [])), confidence=confidence, origin=origin)
        s.add(f)
        s.flush()
        return f, "created"
    new_fields = dict(f.fields or {})
    for k, v in fields.items():
        if v and (overwrite or not str(new_fields.get(k) or "").strip()):
            new_fields[k] = v
    refs = sorted(set(f.evidence_refs or []) | set(evidence_refs or []))
    changed = new_fields != (f.fields or {}) or refs != (f.evidence_refs or [])
    if not changed:
        return f, "unchanged"
    if f.status == "verified" and not overwrite:
        return f, "unchanged"
    save_version(s, f, reason or f"update from {origin}")
    f.fields, f.evidence_refs, f.updated_at = new_fields, refs, now()
    return f, "updated"


def add_question(s, project_id: int, text: str, origin: str = "") -> bool:
    text = text.strip()[:1000]
    if not text or s.query(Question).filter_by(project_id=project_id, text=text).first():
        return False
    s.add(Question(project_id=project_id, text=text, origin=origin))
    s.flush()
    return True


# ---------- search ----------
STOP = set("a an and are as at be by for from has have in is it its of on or that the this to was were will with not no can may".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9₦]+", (text or "").lower()) if t not in STOP and len(t) > 1]


def documents(s, project_id: int) -> list[dict]:
    docs = []
    for f in s.query(Feature).filter_by(project_id=project_id):
        docs.append({"type": "feature", "id": f.id, "title": f.name, "text": f"{f.name} {f.category} " + " ".join(str(v) for v in (f.fields or {}).values()),
                     "confidence": f.confidence, "evidence": f.evidence_refs})
    for x in s.query(Finding).filter_by(project_id=project_id):
        docs.append({"type": "finding", "id": x.id, "title": x.uid, "text": x.observation, "confidence": x.confidence, "evidence": []})
    for p in s.query(Page).filter_by(project_id=project_id):
        docs.append({"type": "page", "id": p.id, "title": p.title or p.url, "text": f"{p.url} {p.title} {p.purpose} {p.text[:4000]}", "confidence": "", "evidence": []})
    for e in s.query(Evidence).filter_by(project_id=project_id):
        docs.append({"type": "evidence", "id": e.id, "title": e.ref, "text": f"{e.ref} {e.source_url} {e.locator} {e.summary}", "confidence": e.classification, "evidence": [e.ref]})
    for q in s.query(Question).filter_by(project_id=project_id):
        docs.append({"type": "question", "id": q.id, "title": "Question", "text": f"{q.text} {q.answer}", "confidence": "", "evidence": []})
    for d in s.query(Decision).filter_by(project_id=project_id):
        docs.append({"type": "decision", "id": d.id, "title": "Decision", "text": f"{d.text} {d.rationale}", "confidence": "", "evidence": []})
    return docs


def search(s, project_id: int, query: str, *, types: list[str] | None = None, limit: int = 20) -> list[dict]:
    """TF-IDF cosine ranking over everything in the project. This is lexical relevance, not embedding-based
    semantic search: it matches shared words, weighted by rarity."""
    docs = [d for d in documents(s, project_id) if not types or d["type"] in types]
    if not docs:
        return []
    tf = [Counter(tokens(d["text"])) for d in docs]
    df = Counter(t for c in tf for t in c)
    N = len(docs)
    idf = {t: math.log((N + 1) / (n + 1)) + 1 for t, n in df.items()}
    q = Counter(tokens(query))
    if not q:
        return []
    qv = {t: c * idf.get(t, 0) for t, c in q.items()}
    qn = math.sqrt(sum(v * v for v in qv.values())) or 1
    out = []
    for d, c in zip(docs, tf):
        dot = sum(qv[t] * c[t] * idf[t] for t in qv if t in c)
        if dot <= 0:
            continue
        dn = math.sqrt(sum((n * idf[t]) ** 2 for t, n in c.items())) or 1
        matched = sorted(t for t in qv if t in c)
        i = d["text"].lower().find(matched[0]) if matched else 0
        out.append({"type": d["type"], "id": d["id"], "title": d["title"], "score": round(dot / (qn * dn), 4),
                    "matched_terms": matched, "confidence": d["confidence"], "evidence": d["evidence"],
                    "snippet": d["text"][max(0, i - 80): i + 200].strip()})
    return sorted(out, key=lambda r: -r["score"])[:limit]


def weakest(conf: list[str]) -> str:
    conf = [c for c in conf if c in CONF_ORDER]
    return min(conf, key=CONF_ORDER.index) if conf else "unknown"
