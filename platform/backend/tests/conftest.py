"""Test bootstrap: isolated data dir + fresh DB per test (asyncio.run per test
keeps event loops clean)."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

_TMP = tempfile.mkdtemp(prefix="rice-test-")
os.environ["RICE_DATA_DIR"] = _TMP
os.environ["RICE_DB_URL"] = f"sqlite+aiosqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["RICE_AI_PROVIDER"] = "off"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.environ["RICE_LOCAL_REPO_PATH"] = REPO_ROOT
os.environ["RICE_GITHUB_REPO"] = "FEMZYKENTLTD/Nigeria-life"


def start(fn):
    """Run an async function to completion on a fresh event loop, booting the DB."""
    async def _run():
        from app.db import bootstrap_async, close_db
        await bootstrap_async()
        try:
            return await fn()
        finally:
            await close_db()
    return asyncio.run(_run())
