"""Knowledge base: upsert, version history, search, related."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import start  # noqa: E402


def test_upsert_and_versioning():
    async def t():
        from app.engine.knowledge import upsert_knowledge
        from sqlalchemy import select

        from app.db import session_scope
        from app.models import KnowledgeEntry

        v1 = await upsert_knowledge("p1", "feature", "f1", "Feature: X", "first body")
        v2 = await upsert_knowledge("p1", "feature", "f1", "Feature: X", "second body changed")
        assert v1 == 1 and v2 == 2
        async with session_scope() as s:
            rows = list((await s.execute(
                select(KnowledgeEntry).where(
                    KnowledgeEntry.project_id == "p1",
                    KnowledgeEntry.kind == "feature",
                    KnowledgeEntry.ref_id == "f1",
                )
            )).scalars().all())
        assert len(rows) == 2  # old version kept, never deleted
        assert sorted(r.is_current for r in rows) == [False, True]
        assert [r.version for r in sorted(rows, key=lambda r: r.version)] == [1, 2]

    start(t)


def test_search_ranks_relevant():
    async def t():
        from app.engine.knowledge import search, upsert_knowledge

        await upsert_knowledge("p1", "feature", "f1", "Governor election",
                               "Weekly vote at a polling unit; candidates pay to run; winner sets a city policy")
        await upsert_knowledge("p1", "feature", "f2", "Password recovery",
                               "Owner questions used to reset credentials")
        res = await search("p1", "who wins the weekly governor vote")
        assert res["count"] >= 1
        assert "Governor" in res["results"][0]["title"]

    start(t)


def test_search_scoped_to_project():
    async def t():
        from app.engine.knowledge import search, upsert_knowledge

        await upsert_knowledge("pa", "note", "n1", "Unique token alpha", "zzz alpha")
        await upsert_knowledge("pb", "note", "n2", "Unique token beta", "zzz beta")
        res = await search("pa", "unique token")
        titles = [r["title"] for r in res["results"]]
        assert any("alpha" in t for t in titles)
        assert not any("beta" in t for t in titles)

    start(t)


def test_related_cross_kind():
    async def t():
        from app.engine.knowledge import related, upsert_knowledge

        await upsert_knowledge("p1", "feature", "f1", "Billboard advertising",
                               "Buy a billboard; ₦250,000 per 7 days; 20 digital boards")
        await upsert_knowledge("p1", "observation", "o1", "Billboard price",
                               "The advertise page lists ₦250,000 per billboard for 7 days")
        await upsert_knowledge("p1", "page", "pg1", "Advertise page",
                               "Self-serve ad booking form for billboards and sea plots")
        rel = await related("p1", "feature", "f1")
        assert len(rel) >= 1
        assert all(r["ref_id"] != "f1" for r in rel)

    start(t)
