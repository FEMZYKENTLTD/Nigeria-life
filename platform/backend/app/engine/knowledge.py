"""Persistent knowledge base: searchable mirror of all research entities with
version history + lexical semantic search (TF-IDF cosine).

Local-first and offline. The search index is built on demand from current
entries and cached in-process; a swap-in for a vector/embedding store only
needs to replace :func:`search`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import select

from ..db import session_scope
from ..models import KnowledgeEntry
from ..engine.textsim import cosine, tfidf_vectorize


@dataclass
class _Index:
    entries: list[dict] = field(default_factory=list)
    vectors: list[dict[str, float]] = field(default_factory=list)
    built_at: float = 0.0


_cache: dict[str, _Index] = {}  # project_id -> index
_CACHE_TTL = 30.0


async def upsert_knowledge(project_id: str, kind: str, ref_id: str, title: str, body: str) -> int:
    """Create or update the searchable mirror for an entity. Version history:
    the previous current row is marked is_current=False and never deleted."""
    async with session_scope() as s:
        row = (await s.execute(
            select(KnowledgeEntry).where(
                KnowledgeEntry.project_id == project_id,
                KnowledgeEntry.kind == kind,
                KnowledgeEntry.ref_id == ref_id,
            )
        )).scalars().first()
        if row is None:
            from ..engine.ids import new_id
            e = KnowledgeEntry(project_id=project_id, kind=kind, ref_id=ref_id, title=title[:500], body=body[:20000], version=1)
            s.add(e)
            _cache.pop(project_id, None)
            await s.flush()
            return 1
        if (row.title or "") != title[:500] or (row.body or "") != body[:20000]:
            old = KnowledgeEntry(project_id=project_id, kind=row.kind, ref_id=row.ref_id,
                                 title=row.title, body=row.body, version=row.version, is_current=False)
            s.add(old)
            row.title = title[:500]
            row.body = body[:20000]
            row.version += 1
            row.is_current = True
            _cache.pop(project_id, None)
        return row.version


def _get_index(project_id: str) -> tuple[list[dict], list[dict[str, float]]] | None:
    """Synchronous index read for API-layer use (FastAPI endpoint runs it in
    a worker thread via starlette)."""
    raise NotImplementedError  # use async search()


async def _build(project_id: str) -> _Index:
    idx = _Index()
    async with session_scope() as s:
        rows = (await s.execute(
            select(KnowledgeEntry).where(
                KnowledgeEntry.project_id == project_id,
                KnowledgeEntry.is_current.is_(True),
            )
        )).scalars().all()
    idx.entries = [{"id": r.id, "kind": r.kind, "ref_id": r.ref_id, "title": r.title or "",
                    "body": r.body or "", "version": r.version,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else ""} for r in rows]
    idx.vectors = tfidf_vectorize([f"{e['title']} {e['body']}" for e in idx.entries])
    idx.built_at = time.time()
    return idx


async def search(project_id: str | None, query: str, kinds: list[str] | None = None,
                 limit: int = 20, project_filter: list[str] | None = None) -> dict:
    """Semantic-ish lexical search. project_id limits to one project; when
    None and project_filter is given, searches across the listed projects."""
    from ..engine.textsim import tokens

    qtok = tokens(query)
    if not qtok:
        return {"query": query, "results": [], "count": 0,
                "explanation": "Empty query."}
    targets = [project_id] if project_id else (project_filter or [])
    if not targets:
        # global search: discover project ids lazily is expensive; require a scope.
        return {"query": query, "results": [], "count": 0,
                "explanation": "Provide a project to search."}
    entries: list[dict] = []
    vectors: list[dict[str, float]] = []
    for pid in targets:
        idx = _cache.get(pid)
        if idx is None or time.time() - idx.built_at > _CACHE_TTL:
            idx = await _build(pid)
            _cache[pid] = idx
        entries.extend(idx.entries)
        vectors.extend(idx.vectors)
    if not entries:
        return {"query": query, "results": [], "count": 0, "explanation": "Knowledge base is empty for this scope."}
    qvec = tfidf_vectorize([f" ".join(qtok)] + [f"{e['title']} {e['body']}" for e in entries])
    qv = qvec[0]
    scored = []
    for i, e in enumerate(entries):
        if kinds and e["kind"] not in kinds:
            continue
        score = cosine(qv, vectors[i]) if i + 1 < len(vectors) else 0.0
        # bonus for title hits (exact-term match in title ranks higher)
        title_terms = set(tokens(e["title"]))
        overlap = len(set(qtok) & title_terms)
        score += 0.25 * overlap / max(1, len(qtok))
        if score > 0.01:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    top = scored[:limit]
    return {
        "query": query,
        "count": len(top),
        "results": [
            {
                "score": round(s, 4),
                "kind": e["kind"], "ref_id": e["ref_id"], "id": e["id"],
                "title": e["title"], "snippet": e["body"][:400],
                "version": e["version"], "updated_at": e["updated_at"],
            }
            for s, e in top
        ],
        "explanation": (
            "TF-IDF cosine over the project's current knowledge entries (title + body), with a "
            "title-overlap bonus. Deterministic and offline; replaceable with an embedding store."
        ),
    }


async def related(project_id: str, kind: str, ref_id: str, limit: int = 8) -> list[dict]:
    """Entries most similar to a given entity (cross-kind)."""
    async with session_scope() as s:
        from sqlalchemy import select as _sel
        row = (await s.execute(
            _sel(KnowledgeEntry).where(
                KnowledgeEntry.project_id == project_id,
                KnowledgeEntry.is_current.is_(True),
            )
        )).scalars().all()
    src = next((r for r in row if r.kind == kind and r.ref_id == ref_id), None)
    if src is None:
        return []
    idx_entries = [{"kind": r.kind, "ref_id": r.ref_id, "title": r.title or "", "body": r.body or ""}
                   for r in row if not (r.kind == kind and r.ref_id == ref_id)]
    if not idx_entries:
        return []
    all_texts = [f"{src.title} {src.body}"] + [f"{e['title']} {e['body']}" for e in idx_entries]
    vecs = tfidf_vectorize(all_texts)
    scored = [(cosine(vecs[0], v), e) for v, e in zip(vecs[1:], idx_entries)]
    scored = [(s, e) for s, e in scored if s > 0.02]
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 4), "kind": e["kind"], "ref_id": e["ref_id"], "title": e["title"]}
            for s, e in scored[:limit]]
