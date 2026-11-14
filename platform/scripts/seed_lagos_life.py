"""Seed the platform with the FIRST research project: Lagos Life
Reconnaissance (the existing docs/research package).

The importer is generic — this script only supplies project metadata, proving
the platform is multi-project and that Lagos Life is just project #1.

Usage:  python scripts/seed_lagos_life.py [--force]
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("RICE_DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import bootstrap_async, close_db, session_scope  # noqa: E402
from app.engine.evidence_import import import_research_package  # noqa: E402
from app.engine.ids import new_id  # noqa: E402
from app.engine.knowledge import upsert_knowledge  # noqa: E402
from app.models import ActivityLog, Project, Source  # noqa: E402

PROJECT_NAME = "Lagos Life Reconnaissance"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "research")


async def main(force: bool = False) -> None:
    await bootstrap_async()
    s = get_settings()
    if not os.path.isdir(DOCS_DIR):
        print(f"ERROR: research docs not found at {DOCS_DIR}")
        sys.exit(1)
    async with session_scope() as sess:
        existing = (await sess.execute(
            select(Project).where(Project.name == PROJECT_NAME)
        )).scalars().first()
        if existing and not force:
            print(f"Project '{PROJECT_NAME}' already seeded (id={existing.id}). Use --force to re-import.")
            await close_db()
            return
        if existing and force:
            # wipe derived records by deleting the project (cascades)
            await sess.delete(existing)
            await sess.flush()
        p = Project(
            id=new_id(),
            name=PROJECT_NAME,
            slug="lagos-life-reconnaissance",
            description=("Competitive reconnaissance of the Lagos Life browser-based "
                         "life-simulation (operator: Vatar). First research project of the "
                         "platform; feeds the Nigeria Life product blueprint."),
            industry="virtual-society / economic-simulation / entertainment",
            target_base_url="https://lagoslife.app",
            repo_url="https://github.com/FEMZYKENTLTD/Nigeria-life",
            instructions=(
                "This project studies a competing product. Respect its published terms: "
                "read-only, human-scale collection; no automated scraping of first-party "
                "domains without explicit approval; fan guides and press are class-S. "
                "Anything marked S must be re-verified before it informs our build."
            ),
            permissions={
                "login_allowed": False,
                "screenshots_allowed": True,
                "collection_methods": ["browser", "manual_import", "page_reader"],
                "delay_between_fetches_s": 3.0,
                "max_pages_per_session": 25,
                "respect_robots": True,
            },
        )
        sess.add(p)
        await sess.flush()
        pid = p.id
        sess.add(ActivityLog(project_id=pid, actor="system", action="project.seeded",
                             subject=PROJECT_NAME, detail="seeded from docs/research package"))
    counts = await import_research_package(pid, DOCS_DIR)
    # the first-party domain must stay pending approval (terms restrict automation)
    async with session_scope() as sess:
        primary = (await sess.execute(
            select(Source).where(Source.project_id == pid, Source.domain == "lagoslife.app")
        )).scalars().first()
        if primary is not None:
            primary.status = "pending_approval"
            primary.notes = ("First-party domain. Published terms prohibit unauthorised scraping — "
                             "automated sessions require explicit researcher approval.")
    print("Seeded project:", PROJECT_NAME)
    print("Import counts:", counts)
    print("Data dir:", s.data_dir)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main(force="--force" in sys.argv))
