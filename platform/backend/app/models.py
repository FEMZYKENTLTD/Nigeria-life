"""Core data model.

Design notes
------------
* Fully multi-project: every research entity carries ``project_id`` and the
  core never references a specific target or product.
* Evidence integrity: findings (Observation) always point at Evidence;
  evidence carries a class (C/S/I/H/U) and a capture method.
* Version history: KnowledgeEntry keeps an immutable history per searchable
  entity (``version`` increments, ``is_current`` flips) so verified research
  is never silently overwritten.
* Honest failure: tasks/subtasks keep status + last_error; browser health and
  sessions record what could not be done and why.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .engine.ids import new_id

# ---------------------------------------------------------------- evidence classes

EVIDENCE_CLASSES = ("C", "I", "S", "H", "U")
EVIDENCE_WEIGHTS = {"C": 1.0, "I": 0.7, "S": 0.55, "H": 0.3, "U": 0.15}

FEATURE_CATEGORIES = (
    "authentication", "user_profiles", "character_systems", "economy", "employment",
    "business_management", "marketplace", "virtual_assets", "property", "transportation",
    "geography", "social_interaction", "entertainment", "achievements", "progression",
    "notifications", "settings", "administration", "monetisation", "other",
)

TASK_STATUSES = (
    "queued", "planned", "running", "paused", "waiting_decision",
    "complete", "failed", "cancelled",
)
SUBTASK_STATUSES = (
    "queued", "running", "complete", "failed", "skipped", "waiting_decision",
)
DECISION_KINDS = (
    "new_source", "permission_change", "publication", "repo_change",
    "destructive", "transaction", "manual_evidence", "other",
)
SUBTASK_TYPES = (
    "discover", "fetch", "understand", "document", "analyse", "report",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- projects & config

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    target_base_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused|complete
    instructions: Mapped[str] = mapped_column(Text, default="")  # project-specific AI instructions
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    # permissions shape:
    # { "login_allowed": bool, "screenshots_allowed": bool,
    #   "collection_methods": ["browser","manual_import","page_reader"],
    #   "delay_between_fetches_s": float, "max_pages_per_session": int,
    #   "respect_robots": bool }
    repo_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tasks: Mapped[list["ResearchTask"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sources: Mapped[list["Source"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    pages: Mapped[list["PageRecord"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    features: Mapped[list["Feature"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Source(Base):
    """A research source (site/page/API doc) within a project, with its own
    collection permission state. Adding a *new* domain requires an approved
    Decision before it becomes usable by the scheduler."""
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500), index=True)
    domain: Mapped[str] = mapped_column(String(250), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_approval")  # pending_approval|authorised|denied|unreachable
    collection_permission: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    discovered_by: Mapped[str] = mapped_column(String(60), default="user")  # user|agent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="sources")


class UnresolvedQuestion(Base):
    __tablename__ = "unresolved_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved|dropped
    resolution: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- tasks (agent)

class ResearchTask(Base):
    """A research objective. The agent planner decomposes it into Subtasks."""
    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=highest
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[dict] = mapped_column(JSON, default=dict)  # planner output (llm/heuristic)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Subtask"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
        order_by="Subtask.idx",
    )


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(24))  # SUBTASK_TYPES
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str] = mapped_column(Text, default="")
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)  # resume state
    output: Mapped[dict] = mapped_column(JSON, default=dict)  # ids of produced records
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    decision_id: Mapped[str] = mapped_column(String(32), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[ResearchTask] = relationship(back_populates="subtasks")


class Decision(Base):
    """Anything consequential requires human approval (directive §16)."""
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(32), default="")
    kind: Mapped[str] = mapped_column(String(24))  # DECISION_KINDS
    question: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- research records

class PageRecord(Base):
    __tablename__ = "page_records"
    __table_args__ = (
        # duplicate prevention: one documented record per canonical URL per project
        {"sqlite_autoincrement": False},
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    url: Mapped[str] = mapped_column(String(700), index=True)
    canonical_url: Mapped[str] = mapped_column(String(700), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|documented|error|empty
    content_category: Mapped[str] = mapped_column(String(40), default="")  # landing|legal|docs|form|content|app|error|system
    purpose: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    structure: Mapped[dict] = mapped_column(JSON, default=dict)
    # structure: {regions:{}, nav:[], forms:[], controls:[], interactive:[],
    #             sections:[{level,text}], links:{internal:[],external:[]},
    #             states:{empty,loading,error}, repeated:[]}
    body_text: Mapped[str] = mapped_column(Text, default="")  # truncated, for search
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_method: Mapped[str] = mapped_column(String(40), default="")  # browser|page_reader|manual_import|imported_package
    browser_engine: Mapped[str] = mapped_column(String(20), default="")
    session_id: Mapped[str] = mapped_column(String(32), default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="pages")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    ref_code: Mapped[str] = mapped_column(String(16), index=True, default="")  # human code e.g. E07
    evidence_class: Mapped[str] = mapped_column(String(1), default="I")  # C|I|S|H|U
    source_uri: Mapped[str] = mapped_column(String(700), default="")
    source_name: Mapped[str] = mapped_column(String(300), default="")
    capture_method: Mapped[str] = mapped_column(String(40), default="")  # read|search|screenshot|import|author_observation
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")  # screenshots / imported files
    file_checksum: Mapped[str] = mapped_column(String(64), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="evidence")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    page_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    evidence_id: Mapped[str] = mapped_column(String(32), default="")
    url: Mapped[str] = mapped_column(String(700), default="")
    viewport: Mapped[dict] = mapped_column(JSON, default=dict)  # {width,height,dpr,device?}
    full_page: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path: Mapped[str] = mapped_column(String(500))
    file_checksum: Mapped[str] = mapped_column(String(64), default="")
    perceptual_hash: Mapped[str] = mapped_column(String(16), default="")  # dHash hex, for change detection
    category: Mapped[str] = mapped_column(String(40), default="")  # landing|docs|legal|form|content|system|responsive
    notes: Mapped[str] = mapped_column(Text, default="")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Observation(Base):
    """A finding. Unique ID, page reference, evidence reference, timestamp,
    confidence and research status are mandatory by design."""
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    page_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    feature_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)  # page|feature|interaction|visual|decision|note|fact
    observation: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(String(200), default="", index=True)  # for contradiction detection (topic)
    value: Mapped[str] = mapped_column(Text, default="")  # normalised value (for contradiction detection)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_class: Mapped[str] = mapped_column(String(1), default="I")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|verified|superseded
    related: Mapped[list] = mapped_column(JSON, default=list)  # feature/observation ids
    created_by: Mapped[str] = mapped_column(String(40), default="agent")  # agent|user|import|system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    slug: Mapped[str] = mapped_column(String(320), index=True)
    category: Mapped[str] = mapped_column(String(40), default="other")  # FEATURE_CATEGORIES
    description: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    user_type: Mapped[str] = mapped_column(String(80), default="")
    access_location: Mapped[str] = mapped_column(Text, default="")
    inputs: Mapped[str] = mapped_column(Text, default="")
    outputs: Mapped[str] = mapped_column(Text, default="")
    observed_behaviour: Mapped[str] = mapped_column(Text, default="")
    dependencies: Mapped[list] = mapped_column(JSON, default=list)      # feature names
    related_features: Mapped[list] = mapped_column(JSON, default=list)  # feature names
    user_journey: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    opportunities: Mapped[str] = mapped_column(Text, default="")
    implementation_implications: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)  # raw ref strings e.g. "C (E06 §4)"
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|documented|verified
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="features")


# ---------------------------------------------------------------- browser automation

class BrowserProfile(Base):
    __tablename__ = "browser_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(32), default="")  # '' = shared
    name: Mapped[str] = mapped_column(String(200))
    engine: Mapped[str] = mapped_column(String(20))  # chromium|firefox|webkit
    user_data_dir: Mapped[str] = mapped_column(String(500), default="")
    viewports: Mapped[list] = mapped_column(JSON, default=list)  # [{name,width,height,dpr,device?}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BrowserHealth(Base):
    __tablename__ = "browser_health"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    engine: Mapped[str] = mapped_column(String(20), index=True)
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[str] = mapped_column(String(60), default="")
    binary_path: Mapped[str] = mapped_column(String(500), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    profile_id: Mapped[str] = mapped_column(String(32), default="")
    engine: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(12), default="headless")  # headless|visible
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|completed|failed|aborted
    summary: Mapped[dict] = mapped_column(JSON, default=dict)  # {pages_visited, errors, screenshots, ...}
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    task_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    engine: Mapped[str] = mapped_column(String(20), default="")
    level: Mapped[str] = mapped_column(String(10), default="info")  # info|warn|error
    event: Mapped[str] = mapped_column(String(80), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- knowledge base

class KnowledgeEntry(Base):
    """Searchable mirror of a research entity with version history."""
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)  # project|page|feature|observation|evidence|report|note
    ref_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- reports & github

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))  # executive|page_audit|feature_inventory|...
    title: Mapped[str] = mapped_column(String(300))
    format: Mapped[str] = mapped_column(String(12), default="md")  # md|json|csv|html|mermaid
    content: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GitHubState(Base):
    __tablename__ = "github_state"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    repo_full_name: Mapped[str] = mapped_column(String(300), default="")
    default_branch: Mapped[str] = mapped_column(String(120), default="")
    current_branch: Mapped[str] = mapped_column(String(120), default="")
    last_commit_sha: Mapped[str] = mapped_column(String(64), default="")
    last_commit_message: Mapped[str] = mapped_column(String(500), default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    docs_tree: Mapped[list] = mapped_column(JSON, default=list)
    sync_status: Mapped[str] = mapped_column(String(20), default="never")  # never|ok|error
    pending_updates: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    actor: Mapped[str] = mapped_column(String(20), default="system")  # agent|user|system|import
    action: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- agent runs

class AgentRun(Base):
    """One execution of the autonomous agent over a task (with model + mode)."""
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    mode: Mapped[str] = mapped_column(String(24))  # offline-heuristic | provider:<name>
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|complete|failed
    log: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
