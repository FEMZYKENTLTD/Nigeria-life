"""Database models. SQLite locally, PostgreSQL centrally (same models)."""
from __future__ import annotations
import datetime as dt
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings
from .security import redact


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    def as_dict(self) -> dict[str, Any]:
        out = {}
        for c in self.__table__.columns:
            v = getattr(self, c.name)
            out[c.name] = v.isoformat() + "Z" if isinstance(v, dt.datetime) else v
        return out


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    objective: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(Text, default="")
    repo_url: Mapped[str] = mapped_column(String(400), default="")
    repo_path: Mapped[str] = mapped_column(String(600), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("project_id", "base_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(600))
    automation: Mapped[str] = mapped_column(String(20), default="manual_only")  # automated | manual_only
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_paths: Mapped[list] = mapped_column(JSON, default=list)  # path prefixes; empty = whole host
    max_pages: Mapped[int] = mapped_column(Integer, default=25)
    rate_limit_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    respect_robots: Mapped[bool] = mapped_column(Boolean, default=True)
    capture_screenshots: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(400))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued running done failed cancelled blocked
    priority: Mapped[int] = mapped_column(Integer, default=50)  # lower runs first
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    not_before: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(300), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("project_id", "ref"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    ref: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(30))  # page_capture screenshot manual import
    source_url: Mapped[str] = mapped_column(String(800), default="")
    locator: Mapped[str] = mapped_column(String(400), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(20), default="unknown")  # confirmed secondary inference hypothesis unknown
    file_path: Mapped[str] = mapped_column(String(600), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    captured_by: Mapped[str] = mapped_column(String(60), default="engine")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("project_id", "url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(800))
    title: Mapped[str] = mapped_column(String(400), default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="discovered")  # discovered captured analysed failed blocked imported
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine: Mapped[str] = mapped_column(String(30), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    record: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    discovered_from: Mapped[str] = mapped_column(String(800), default="")
    fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("project_id", "fingerprint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(40), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="observation")
    observation: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="unknown")
    status: Mapped[str] = mapped_column(String(20), default="recorded")  # recorded verified disputed superseded
    related_features: Mapped[list] = mapped_column(JSON, default=list)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (UniqueConstraint("project_id", "slug"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    slug: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(40), default="Other")
    fields: Mapped[dict] = mapped_column(JSON, default=dict)  # the 15 documented fields
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(20), default="unknown")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft verified
    origin: Mapped[str] = mapped_column(String(40), default="engine")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Screenshot(Base):
    __tablename__ = "screenshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(600))
    engine: Mapped[str] = mapped_column(String(30), default="")
    viewport: Mapped[str] = mapped_column(String(40), default="")
    full_page: Mapped[bool] = mapped_column(Boolean, default=False)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    ahash: Mapped[str] = mapped_column(String(32), default="")
    category: Mapped[str] = mapped_column(String(60), default="")
    annotations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("project_id", "text"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open answered dropped
    origin: Mapped[str] = mapped_column(String(100), default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    made_by: Mapped[str] = mapped_column(String(60), default="human")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(40))
    format: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(300))
    path: Mapped[str] = mapped_column(String(600))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    level: Mapped[str] = mapped_column(String(10), default="info")
    actor: Mapped[str] = mapped_column(String(40), default="engine")
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Version(Base):
    __tablename__ = "versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(300), default="")
    changed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(String(600))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending approved rejected
    decided_by: Mapped[str] = mapped_column(String(60), default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class BrowserProfile(Base):
    __tablename__ = "browser_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    engine: Mapped[str] = mapped_column(String(30), default="http")
    viewport_width: Mapped[int] = mapped_column(Integer, default=1440)
    viewport_height: Mapped[int] = mapped_column(Integer, default=900)
    mobile: Mapped[bool] = mapped_column(Boolean, default=False)
    headless: Mapped[bool] = mapped_column(Boolean, default=True)
    persistent: Mapped[bool] = mapped_column(Boolean, default=False)  # keep a user-authorised login session on disk


class BrowserRun(Base):
    __tablename__ = "browser_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine: Mapped[str] = mapped_column(String(30))
    profile: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(20))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    console_errors: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


_engine = None
_Session = None


def init_db(url: str | None = None):
    global _engine, _Session
    url = url or get_settings().database_url
    kw = {"connect_args": {"check_same_thread": False, "timeout": 30}} if url.startswith("sqlite") else {}
    _engine = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _pragma(conn, _):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session():
    if _Session is None:
        init_db()
    s: Session = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def log(s: Session, event_name: str, project_id: int | None = None, level: str = "info", actor: str = "engine", **detail):
    """Structured activity log. Details pass through redaction first."""
    s.add(Activity(project_id=project_id, level=level, actor=actor, event=event_name, detail=redact(json.loads(json.dumps(detail, default=str)))))


def save_version(s: Session, obj: Base, reason: str = ""):
    """Snapshot an entity before it is changed, so verified research is never silently overwritten."""
    etype = obj.__tablename__
    last = s.query(Version).filter_by(entity_type=etype, entity_id=obj.id).order_by(Version.version.desc()).first()
    s.add(Version(entity_type=etype, entity_id=obj.id, version=(last.version + 1 if last else 1), snapshot=obj.as_dict(), reason=reason))


def backup_database() -> Path:
    """Copy the SQLite file to the backups folder. (For PostgreSQL use pg_dump; not handled here.)"""
    st = get_settings()
    if not st.database_url.startswith("sqlite"):
        raise RuntimeError("Built-in backup only supports SQLite. Use pg_dump for PostgreSQL.")
    src = Path(st.database_url.replace("sqlite:///", ""))
    dest = st.data_dir / "backups" / f"nlie-{now().strftime('%Y%m%dT%H%M%S%f')}.db"
    import sqlite3
    with sqlite3.connect(src) as a, sqlite3.connect(dest) as b:
        a.backup(b)
    return dest
