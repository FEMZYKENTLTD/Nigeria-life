"""FastAPI application entry point.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8787
      (or `python -m app.main`)

Serves:
* /api/*        — REST API
* /             — the built dashboard (platform/frontend/dist) when present
* /data/*       — evidence files / screenshots / report exports
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import get_settings
from .db import bootstrap_async, close_db
from .logging_conf import setup_logging

log = logging.getLogger("rice.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    s = get_settings()
    os.makedirs(s.data_dir, exist_ok=True)
    await bootstrap_async()
    # task recovery: re-queue tasks left running by an interrupted process
    try:
        from sqlalchemy import select

        from .db import session_scope
        from .models import ResearchTask

        async with session_scope() as sess:
            stuck = (await sess.execute(
                select(ResearchTask).where(ResearchTask.status.in_(["running", "planned"]))
            )).scalars().all()
            for t in stuck:
                t.status = "queued"
                t.error = (t.error + " | " if t.error else "") + "recovered after interruption (in-flight state checkpointed)"
        if stuck:
            log.warning("recovered %d interrupted task(s) into the queue", len(stuck))
    except Exception as e:  # pragma: no cover
        log.warning("task recovery failed: %s", e)
    # initial browser health probe (non-fatal; reports honestly)
    try:
        from .engine.browser.manager import probe_engines

        health = await probe_engines()
        for h in health:
            log.info("browser health: %s installed=%s %s", h["engine"], h["installed"], h.get("error", "")[:120])
    except Exception as e:  # pragma: no cover
        log.warning("browser probe failed: %s", e)
    yield
    await close_db()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Nigeria Life Intelligence Engine",
        description="General-purpose AI website research, intelligence and analysis platform.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "rice",
                "ai_provider": s.ai_provider,
                "db": "sqlite" if s.db_url.startswith("sqlite") else "postgresql"}

    # data files (evidence, screenshots, report exports) — registered before the
    # SPA catch-all so it always wins for /data/*.
    data_dir = os.path.abspath(s.data_dir)
    os.makedirs(data_dir, exist_ok=True)
    app.mount("/data", StaticFiles(directory=data_dir), name="data")

    # built dashboard (single-origin production serving with SPA fallback)
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    if os.path.isdir(frontend_dist):
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str, request: Request):
            if full_path.startswith(("api/", "data/")):
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            candidate = os.path.normpath(os.path.join(frontend_dist, full_path))
            if full_path and candidate.startswith(frontend_dist + os.sep) and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, log_level="warning")
