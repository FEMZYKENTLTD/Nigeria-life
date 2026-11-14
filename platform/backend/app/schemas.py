"""Pydantic request models for the REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    industry: str = ""
    target_base_url: str = ""
    instructions: str = ""
    repo_url: str = ""
    permissions: dict = Field(default_factory=lambda: {
        "login_allowed": False,
        "screenshots_allowed": True,
        "collection_methods": ["browser", "manual_import", "page_reader"],
        "delay_between_fetches_s": 2.0,
        "max_pages_per_session": 40,
        "respect_robots": True,
    })


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    industry: str | None = None
    target_base_url: str | None = None
    status: str | None = None
    instructions: str | None = None
    repo_url: str | None = None
    permissions: dict | None = None


class TaskIn(BaseModel):
    title: str
    objective: str
    priority: int = 3
    report_types: list[str] | None = None


class SourceIn(BaseModel):
    name: str
    url: str
    status: str = "pending_approval"
    notes: str = ""
    auto_authorise: bool = False


class PageImportIn(BaseModel):
    url: str
    title: str = ""
    text: str = ""          # rendered text or markdown of the page
    html: str = ""          # or raw HTML (analysed by the page understanding engine)
    status: str = "documented"
    evidence_class: str = "C"
    evidence_source: str = ""
    notes: str = ""


class ObservationIn(BaseModel):
    kind: str = "note"
    observation: str
    key: str = ""
    value: str = ""
    page_id: str = ""
    feature_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_class: str = "I"
    confidence: float = 0.5
    status: str = "open"


class FeatureIn(BaseModel):
    name: str
    category: str = "other"
    description: str = ""
    purpose: str = ""
    user_type: str = ""
    access_location: str = ""
    inputs: str = ""
    outputs: str = ""
    observed_behaviour: str = ""
    dependencies: list[str] = Field(default_factory=list)
    related_features: list[str] = Field(default_factory=list)
    user_journey: str = ""
    limitations: str = ""
    opportunities: str = ""
    implementation_implications: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    status: str = "draft"


class QuestionIn(BaseModel):
    question: str
    context: str = ""


class ReportGenIn(BaseModel):
    type: str
    format: str = "md"


class SearchIn(BaseModel):
    query: str
    kinds: list[str] | None = None
    limit: int = 20


class CaptureIn(BaseModel):
    url: str
    engine: str = "chromium"
    headless: bool = True
    viewport: dict | None = None
    extra_viewports: list[dict] | None = None
    full_page: bool = True
    profile_id: str = ""


class ProfileIn(BaseModel):
    name: str
    engine: str = "chromium"
    viewports: list[dict] | None = None
    shared: bool = False
    project_id: str = ""


class GitHubWriteIn(BaseModel):
    path: str
    content: str
    commit_message: str
    branch: str | None = None
    open_pr: bool = False
    pr_title: str = ""
    pr_body: str = ""
