"""Import pipeline integration test: ingest the REAL docs/research package
(Lagos Life reconnaissance) and verify the structured records."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT, start  # noqa: E402

DOCS = os.path.join(REPO_ROOT, "docs", "research")


def _project():
    async def t():
        from app.engine.ids import new_id

        from app.db import session_scope
        from app.models import Project

        async with session_scope() as s:
            p = Project(id=new_id(), name="Import Test", slug="import-test",
                        target_base_url="https://lagoslife.app")
            s.add(p)
            await s.flush()
            return p.id

    return start(t)


def test_import_real_package():
    pid = _project()

    async def t():
        from sqlalchemy import select

        from app.db import session_scope
        from app.engine.evidence_import import import_research_package
        from app.models import (Evidence, Feature, Observation, PageRecord,
                                Source, UnresolvedQuestion)

        counts = await import_research_package(pid, DOCS)
        async with session_scope() as s:
            ev = list((await s.execute(select(Evidence).where(Evidence.project_id == pid))).scalars().all())
            feats = list((await s.execute(select(Feature).where(Feature.project_id == pid))).scalars().all())
            pages = list((await s.execute(select(PageRecord).where(PageRecord.project_id == pid))).scalars().all())
            obs = list((await s.execute(select(Observation).where(Observation.project_id == pid))).scalars().all())
            qs = list((await s.execute(select(UnresolvedQuestion).where(UnresolvedQuestion.project_id == pid))).scalars().all())
            srcs = list((await s.execute(select(Source).where(Source.project_id == pid))).scalars().all())
        # evidence register has 29 rows (E01–E29)
        assert counts["evidence"] == 29
        codes = {e.ref_code for e in ev}
        assert "E01" in codes and "E29" in codes
        classes = {e.evidence_class for e in ev}
        assert classes == {"C", "S"}
        # feature inventory: 11 sections with dozens of rows
        assert counts["features"] > 60, counts
        cats = {f.category for f in feats}
        assert "authentication" in cats and "monetisation" in cats
        # known feature present with its evidence link
        login = next(f for f in feats if f.name == "Log-in")
        assert login.evidence_ids
        # pages from the checklist
        assert counts["pages"] >= 25
        doc_pages = [p for p in pages if p.status == "documented"]
        assert len(doc_pages) >= 20
        # contradictions from 00 §5 (7 topics)
        assert counts["contradictions"] == 7
        conflict_obs = [o for o in obs if o.kind == "fact" and o.key]
        assert len(conflict_obs) >= 14  # two values per conflict
        # open items (00 §7: 5) + roadmap questions (11 §2)
        assert counts["questions"] >= 8
        # journeys imported as interaction observations
        assert sum(1 for o in obs if o.kind == "interaction") >= 10
        # sources: first-party domain must NOT be auto-authorised
        primary = [s for s in srcs if s.domain == "lagoslife.app"]
        assert primary and primary[0].status != "authorised"
        # no feature was invented: every feature's evidence refs trace to E-codes
        for f in feats:
            if f.status == "documented":
                assert f.evidence_refs or f.evidence_ids, f.name

    start(t)
