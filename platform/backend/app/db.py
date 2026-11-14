"""Async database setup. Local-first SQLite (aiosqlite); PostgreSQL via
RICE_DB_URL for central deployments (sqlalchemy asyncpg driver)."""
import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings
from .logging_conf import setup_logging
from .models import Base  # noqa: F401  (registers tables)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    global _engine, _session_factory
    s = get_settings()
    url = s.db_url
    if url.startswith("sqlite"):
        path = url.split("///")[-1]
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _engine = create_async_engine(url, echo=False, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine.sync_engine, "connect")
            def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=8000")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
    else:
        _engine = create_async_engine(url, echo=False, future=True, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    assert _engine is not None, "init_db() must run first"
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert _session_factory is not None, "init_db() must run first"
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Standalone session scope for engine code (scheduler, agent loop)."""
    assert _session_factory is not None, "init_db() must run first"
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def bootstrap() -> None:
    """Idempotent boot helper (used by tests and scripts)."""
    setup_logging()


async def bootstrap_async() -> None:
    setup_logging()
    await init_db()
