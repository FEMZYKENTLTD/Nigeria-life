"""HTTP API and dashboard host."""
from __future__ import annotations
import base64
import hashlib
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import __version__, ai, analytics, approvals, github, jobs, knowledge, planner, reports, visual
from .browser.registry import available_engines
from .config import get_settings
from .db import (Activity, Approval, BrowserProfile, BrowserRun, Decision, Evidence, Feature, Finding, Note, Page, Project, Question, Report,
                 Screenshot, Source, Task, Version, backup_database, init_db, log, now, save_version, session)
from .features import CATEGORIES, FIELDS, field_completeness
from .security import redact_text

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND = Path(os.environ.get("NLIE_FRONTEND_DIR", REPO_ROOT / "engine" / "frontend" / "dist"))


def bootstrap():
    """First run: create a project for the repository this engine lives in. No research is fabricated;
    the only queued work is importing what the repository already contains."""
    repo = os.environ.get("NLIE_REPO_PATH", str(REPO_ROOT))
    with session() as s:
        for name, engine, w, h, mobile in (("Desktop 1440", "chromium", 1440, 900, False), ("Tablet 820", "webkit", 820, 1180, True),
                                           ("Mobile 390", "webkit", 390, 844, True), ("Firefox desktop", "firefox", 1440, 900, False), ("HTTP only", "http", 1440, 900, False)):
            if not s.query(BrowserProfile).filter_by(name=name).first():
                s.add(BrowserProfile(name=name, engine=engine, viewport_width=w, viewport_height=h, mobile=mobile))
        if s.query(Project).count() or not (Path(repo) / "docs" / "research").is_dir():
            return
        p = Project(name="Nigeria Life — Lagos Life reconnaissance", repo_path=repo, repo_url="https://github.com/FEMZYKENTLTD/Nigeria-life",
                    objective="Maintain an evidence-backed knowledge base about Lagos Life to inform the design of Nigeria Life.",
                    scope="Public pages only. No login, no automation against lagoslife.app (its Terms prohibit scraping).")
        s.add(p)
        s.flush()
        s.add(Source(project_id=p.id, name="Lagos Life (operator: Vatar)", base_url="https://lagoslife.app/", automation="manual_only", approved=False,
                     notes="Terms prohibit scraping; Developer Agreement bars use for a competing platform. Manual evidence import only."))
        log(s, "project_bootstrapped", p.id, repo=repo)
        planner.plan(s, p)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap()
    if os.environ.get("NLIE_WORKER", "1") == "1":
        jobs.worker.start()
    yield
    jobs.worker.stop()


app = FastAPI(title="Nigeria Life Intelligence Engine", version=__version__, lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled(_, exc):
    return JSONResponse(status_code=500, content={"detail": redact_text(f"{type(exc).__name__}: {exc}")})


def proj(s, pid: int) -> Project:
    p = s.get(Project, pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def rows(q, limit=500):
    return [r.as_dict() for r in q.limit(limit)]


# ---------- system ----------
@app.get("/api/health")
def health():
    st = get_settings()
    with session() as s:
        n = s.query(Project).count()
    return {"version": __version__, "database": {"kind": st.database_url.split(":")[0], "ok": True, "projects": n}, "worker_alive": jobs.worker.alive,
            "engines": available_engines(), "ai": ai.status(), "data_dir": str(st.data_dir), "time": now().isoformat() + "Z"}


@app.post("/api/backup")
def backup():
    p = backup_database()
    with session() as s:
        log(s, "backup_created", actor="human", file=p.name)
    return {"file": p.name, "bytes": p.stat().st_size}


@app.get("/api/activity")
def activity(project_id: int | None = None, limit: int = 100):
    with session() as s:
        q = s.query(Activity)
        if project_id:
            q = q.filter_by(project_id=project_id)
        return rows(q.order_by(Activity.id.desc()), min(limit, 500))


# ---------- projects ----------
class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    objective: str = ""
    scope: str = ""
    repo_path: str = ""
    repo_url: str = ""


@app.get("/api/projects")
def projects():
    with session() as s:
        out = []
        for p in s.query(Project).order_by(Project.id):
            d = p.as_dict()
            d["tasks"] = {st: s.query(Task).filter_by(project_id=p.id, status=st).count() for st in ("queued", "running", "done", "failed", "blocked")}
            out.append(d)
        return out


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn):
    with session() as s:
        if s.query(Project).filter_by(name=body.name).first():
            raise HTTPException(409, "A project with this name already exists")
        p = Project(**body.model_dump())
        s.add(p)
        s.flush()
        log(s, "project_created", p.id, actor="human", name=p.name)
        return p.as_dict()


@app.post("/api/projects/{pid}/plan")
def project_plan(pid: int):
    with session() as s:
        return planner.plan(s, proj(s, pid))


@app.post("/api/projects/{pid}/pause")
def project_pause(pid: int):
    return _set_status(pid, "paused")


@app.post("/api/projects/{pid}/resume")
def project_resume(pid: int):
    return _set_status(pid, "active")


def _set_status(pid: int, status: str):
    with session() as s:
        p = proj(s, pid)
        p.status = status
        log(s, f"project_{status}", pid, actor="human")
        return p.as_dict()


@app.get("/api/projects/{pid}/agent")
def agent(pid: int):
    with session() as s:
        return planner.agent_status(s, proj(s, pid))


@app.get("/api/projects/{pid}/analytics")
def get_analytics(pid: int):
    with session() as s:
        return analytics.compute(s, proj(s, pid))


@app.get("/api/projects/{pid}/search")
def search(pid: int, q: str, types: str = ""):
    with session() as s:
        proj(s, pid)
        return {"query": q, "method": "TF-IDF lexical ranking (not embedding-based)", "results": knowledge.search(s, pid, q, types=[t for t in types.split(",") if t] or None)}


# ---------- sources & approvals ----------
class SourceIn(BaseModel):
    name: str
    base_url: str = Field(pattern=r"^https?://")
    automation: str = Field(default="manual_only", pattern="^(automated|manual_only)$")
    allowed_paths: list[str] = []
    max_pages: int = Field(default=25, ge=1, le=500)
    rate_limit_seconds: float = Field(default=2.0, ge=1.0, le=120)
    notes: str = ""


@app.get("/api/projects/{pid}/sources")
def sources(pid: int):
    with session() as s:
        return rows(s.query(Source).filter_by(project_id=pid))


@app.post("/api/projects/{pid}/sources", status_code=201)
def add_source(pid: int, body: SourceIn):
    """A new source is stored unapproved and manual-only. The requested settings wait in an approval."""
    with session() as s:
        proj(s, pid)
        if s.query(Source).filter_by(project_id=pid, base_url=body.base_url).first():
            raise HTTPException(409, "Source already exists")
        src = Source(project_id=pid, name=body.name, base_url=body.base_url, automation="manual_only", approved=False, notes=body.notes,
                     allowed_paths=body.allowed_paths, max_pages=body.max_pages, rate_limit_seconds=body.rate_limit_seconds)
        s.add(src)
        s.flush()
        a = approvals.request(s, pid, "approve_source", f"Use {body.base_url} as a research source ({body.automation.replace('_', ' ')}, up to {body.max_pages} pages)",
                              {"source_id": src.id, "automation": body.automation})
        return {"source": src.as_dict(), "approval": a.as_dict()}


class PermIn(BaseModel):
    automation: str | None = Field(default=None, pattern="^(automated|manual_only)$")
    max_pages: int | None = Field(default=None, ge=1, le=500)
    allowed_paths: list[str] | None = None
    rate_limit_seconds: float | None = Field(default=None, ge=1.0, le=120)


@app.post("/api/sources/{sid}/permissions")
def change_permissions(sid: int, body: PermIn):
    with session() as s:
        src = s.get(Source, sid)
        if not src:
            raise HTTPException(404, "Source not found")
        change = {k: v for k, v in body.model_dump().items() if v is not None}
        if not change:
            raise HTTPException(422, "No change given")
        a = approvals.request(s, src.project_id, "change_permissions", f"Change permissions for {src.name}: {change}", {"source_id": sid, **change})
        return a.as_dict()


@app.get("/api/approvals")
def list_approvals(project_id: int | None = None, status: str = ""):
    with session() as s:
        q = s.query(Approval)
        if project_id:
            q = q.filter_by(project_id=project_id)
        if status:
            q = q.filter_by(status=status)
        return rows(q.order_by(Approval.id.desc()))


class DecideIn(BaseModel):
    approve: bool
    decided_by: str = "human"


@app.post("/api/approvals/{aid}/decide")
def decide(aid: int, body: DecideIn):
    with session() as s:
        try:
            return approvals.decide(s, aid, body.approve, body.decided_by).as_dict()
        except KeyError:
            raise HTTPException(404, "Approval not found")
        except ValueError as e:
            raise HTTPException(409, str(e))


# ---------- tasks ----------
@app.get("/api/projects/{pid}/tasks")
def tasks(pid: int, status: str = ""):
    with session() as s:
        q = s.query(Task).filter_by(project_id=pid)
        if status:
            q = q.filter_by(status=status)
        return rows(q.order_by(Task.id.desc()))


@app.post("/api/tasks/{tid}/cancel")
def task_cancel(tid: int):
    return _task(tid, jobs.cancel)


@app.post("/api/tasks/{tid}/retry")
def task_retry(tid: int):
    return _task(tid, jobs.retry)


def _task(tid: int, fn):
    with session() as s:
        t = fn(s, tid)
        if not t:
            raise HTTPException(404, "Task not found")
        return t.as_dict()


class CaptureIn(BaseModel):
    url: str = Field(pattern=r"^https?://")
    engine: str = ""
    profile: str = ""


@app.post("/api/projects/{pid}/capture")
def capture(pid: int, body: CaptureIn):
    with session() as s:
        proj(s, pid)
        key = f"{pid}:capture:{body.url}" + (f":{body.profile or body.engine}" if (body.profile or body.engine) else "")
        t, new = jobs.enqueue(s, pid, "capture_page", f"Capture {body.url}", body.model_dump(), priority=30, dedupe_key=key)
        return {"task": t.as_dict(), "created": new}


# ---------- knowledge ----------
@app.get("/api/projects/{pid}/pages")
def pages(pid: int):
    with session() as s:
        return [{k: v for k, v in p.as_dict().items() if k not in ("text", "record")} for p in s.query(Page).filter_by(project_id=pid).order_by(Page.url)]


@app.get("/api/pages/{page_id}")
def page(page_id: int):
    with session() as s:
        p = s.get(Page, page_id)
        if not p:
            raise HTTPException(404, "Page not found")
        d = p.as_dict()
        d["text"] = d["text"][:3000]
        d["findings"] = rows(s.query(Finding).filter_by(page_id=page_id))
        d["screenshots"] = rows(s.query(Screenshot).filter_by(page_id=page_id))
        return d


@app.get("/api/projects/{pid}/findings")
def findings(pid: int):
    with session() as s:
        ev = {e.id: e.ref for e in s.query(Evidence).filter_by(project_id=pid)}
        pg = {p.id: p.url for p in s.query(Page).filter_by(project_id=pid)}
        return [{**f.as_dict(), "evidence_ref": ev.get(f.evidence_id), "page_url": pg.get(f.page_id)} for f in s.query(Finding).filter_by(project_id=pid).order_by(Finding.id.desc()).limit(1000)]


@app.get("/api/projects/{pid}/features")
def features(pid: int):
    with session() as s:
        out = []
        for f in s.query(Feature).filter_by(project_id=pid).order_by(Feature.category, Feature.name):
            d = f.as_dict()
            d["fields_filled"], d["fields_missing"] = field_completeness(f.fields or {})
            d["fields_total"] = len(FIELDS)
            out.append(d)
        return {"categories": CATEGORIES, "fields": FIELDS, "features": out}


class FeatureIn(BaseModel):
    fields: dict[str, str] = {}
    category: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|verified)$")
    reason: str = "researcher edit"
    expected_updated_at: str | None = None


@app.patch("/api/features/{fid}")
def edit_feature(fid: int, body: FeatureIn):
    with session() as s:
        f = s.get(Feature, fid)
        if not f:
            raise HTTPException(404, "Feature not found")
        if body.expected_updated_at and body.expected_updated_at != f.as_dict()["updated_at"]:
            raise HTTPException(409, "This feature changed since you loaded it. Reload before editing.")
        bad = [k for k in body.fields if k not in FIELDS]
        if bad or (body.category and body.category not in CATEGORIES):
            raise HTTPException(422, f"Unknown field or category: {bad or body.category}")
        save_version(s, f, body.reason)
        f.fields = {**(f.fields or {}), **{k: redact_text(v) for k, v in body.fields.items()}}
        f.category, f.status, f.updated_at = body.category or f.category, body.status or f.status, now()
        log(s, "feature_edited", f.project_id, actor="human", feature=f.name, reason=body.reason)
        return f.as_dict()


@app.get("/api/versions/{entity_type}/{entity_id}")
def versions(entity_type: str, entity_id: int):
    with session() as s:
        return rows(s.query(Version).filter_by(entity_type=entity_type, entity_id=entity_id).order_by(Version.version.desc()))


@app.get("/api/projects/{pid}/evidence")
def evidence(pid: int):
    with session() as s:
        out = []
        for e in s.query(Evidence).filter_by(project_id=pid).order_by(Evidence.id):
            d = e.as_dict()
            d["archived"] = bool(e.file_path and Path(e.file_path).exists())
            d["file_path"] = Path(e.file_path).name if e.file_path else ""
            out.append(d)
        return out


class EvidenceIn(BaseModel):
    summary: str = Field(min_length=3)
    source_url: str = ""
    locator: str = ""
    classification: str = Field(default="confirmed", pattern="^(confirmed|secondary|inference|hypothesis|unknown)$")
    observation: str = ""
    filename: str = ""
    content_base64: str = ""
    captured_by: str = "researcher"


@app.post("/api/projects/{pid}/evidence", status_code=201)
def add_manual_evidence(pid: int, body: EvidenceIn):
    """Manual import path for sources that do not permit automation. Text is redacted for secrets before storage."""
    with session() as s:
        proj(s, pid)
        path, digest, shot = "", "", None
        if body.content_base64:
            try:
                raw = base64.b64decode(body.content_base64, validate=True)
            except Exception:
                raise HTTPException(422, "content_base64 is not valid base64")
            if len(raw) > 15_000_000:
                raise HTTPException(413, "File larger than 15 MB")
            digest = hashlib.sha256(raw).hexdigest()
            ext = (re.search(r"\.([A-Za-z0-9]{1,5})$", body.filename) or [None, "bin"])[1].lower()
            is_img = ext in ("png", "jpg", "jpeg", "webp", "gif")
            folder = get_settings().data_dir / ("screenshots" if is_img else "evidence") / str(pid)
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / f"manual-{digest[:16]}.{ext}"
            dest.write_bytes(raw)
            path = str(dest)
            if is_img:
                shot = visual.image_info(dest)
        ev = knowledge.add_evidence(s, pid, kind="manual", summary=redact_text(body.summary), classification=body.classification, source_url=body.source_url,
                                    locator=body.locator, file_path=path, sha256=digest, captured_by=body.captured_by[:60], ref=None)
        if shot:
            s.add(Screenshot(project_id=pid, evidence_id=ev.id, path=path, engine="manual", width=shot["width"], height=shot["height"], sha256=shot["sha256"],
                             ahash=shot["ahash"], category="manual upload"))
        finding = None
        if body.observation.strip():
            f, _ = knowledge.add_finding(s, pid, redact_text(body.observation), evidence_id=ev.id, confidence=body.classification, kind="researcher")
            finding = f.as_dict()
        log(s, "manual_evidence_added", pid, actor="human", ref=ev.ref)
        return {"evidence": ev.as_dict(), "finding": finding}


@app.get("/api/projects/{pid}/screenshots")
def screenshots(pid: int):
    with session() as s:
        return [{**x.as_dict(), "path": Path(x.path).name} for x in s.query(Screenshot).filter_by(project_id=pid).order_by(Screenshot.id.desc())]


@app.get("/api/screenshots/{sid}/file")
def screenshot_file(sid: int):
    with session() as s:
        x = s.get(Screenshot, sid)
        if not x or not Path(x.path).exists():
            raise HTTPException(404, "Screenshot not found")
        return FileResponse(x.path)


class AnnotIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)
    note: str = Field(min_length=1, max_length=500)
    author: str = "researcher"


@app.post("/api/screenshots/{sid}/annotations")
def annotate(sid: int, body: AnnotIn):
    with session() as s:
        x = s.get(Screenshot, sid)
        if not x:
            raise HTTPException(404, "Screenshot not found")
        x.annotations = [*(x.annotations or []), {**body.model_dump(), "note": redact_text(body.note), "at": now().isoformat() + "Z"}]
        return x.as_dict()


@app.get("/api/screenshots/compare")
def compare(a: int, b: int):
    with session() as s:
        xa, xb = s.get(Screenshot, a), s.get(Screenshot, b)
        if not xa or not xb:
            raise HTTPException(404, "Screenshot not found")
        return visual.compare(xa.path, xb.path)


class QIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class AnswerIn(BaseModel):
    answer: str = ""
    status: str = Field(default="answered", pattern="^(open|answered|dropped)$")


@app.get("/api/projects/{pid}/questions")
def questions(pid: int):
    with session() as s:
        return rows(s.query(Question).filter_by(project_id=pid).order_by(Question.id))


@app.post("/api/projects/{pid}/questions", status_code=201)
def add_q(pid: int, body: QIn):
    with session() as s:
        return {"created": knowledge.add_question(s, pid, body.text, "researcher")}


@app.post("/api/questions/{qid}/answer")
def answer_q(qid: int, body: AnswerIn):
    with session() as s:
        q = s.get(Question, qid)
        if not q:
            raise HTTPException(404, "Question not found")
        save_version(s, q, "answer changed")
        q.answer, q.status = redact_text(body.answer), body.status
        return q.as_dict()


class NoteIn(BaseModel):
    text: str = Field(min_length=1)
    rationale: str = ""


@app.get("/api/projects/{pid}/notes")
def notes(pid: int):
    with session() as s:
        return {"notes": rows(s.query(Note).filter_by(project_id=pid).order_by(Note.id.desc())), "decisions": rows(s.query(Decision).filter_by(project_id=pid).order_by(Decision.id.desc()))}


@app.post("/api/projects/{pid}/notes", status_code=201)
def add_note(pid: int, body: NoteIn):
    with session() as s:
        n = Note(project_id=pid, text=redact_text(body.text))
        s.add(n)
        s.flush()
        return n.as_dict()


@app.post("/api/projects/{pid}/decisions", status_code=201)
def add_decision(pid: int, body: NoteIn):
    with session() as s:
        d = Decision(project_id=pid, text=redact_text(body.text), rationale=redact_text(body.rationale))
        s.add(d)
        s.flush()
        return d.as_dict()


# ---------- reports ----------
class ReportIn(BaseModel):
    kind: str
    formats: list[str] = ["md"]


@app.get("/api/reports/kinds")
def report_kinds():
    return {"kinds": reports.KINDS, "formats": reports.FORMATS}


@app.get("/api/projects/{pid}/reports")
def list_reports(pid: int):
    with session() as s:
        return [{**r.as_dict(), "path": Path(r.path).name, "exists": Path(r.path).exists()} for r in s.query(Report).filter_by(project_id=pid).order_by(Report.id.desc())]


@app.post("/api/projects/{pid}/reports", status_code=201)
def make_report(pid: int, body: ReportIn):
    with session() as s:
        try:
            return reports.generate(s, proj(s, pid), body.kind, body.formats)
        except ValueError as e:
            raise HTTPException(422, str(e))


@app.get("/api/reports/{rid}/download")
def download(rid: int):
    with session() as s:
        r = s.get(Report, rid)
        if not r or not Path(r.path).exists():
            raise HTTPException(404, "Report file not found")
        return FileResponse(r.path, filename=Path(r.path).name)


# ---------- browser ----------
class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    engine: str = Field(pattern="^(http|chromium|firefox|webkit)$")
    viewport_width: int = Field(default=1440, ge=240, le=3840)
    viewport_height: int = Field(default=900, ge=240, le=3840)
    mobile: bool = False
    headless: bool = True
    persistent: bool = False


@app.get("/api/browser")
def browser(project_id: int | None = None):
    with session() as s:
        q = s.query(BrowserRun)
        if project_id:
            q = q.filter_by(project_id=project_id)
        profs = []
        for p in s.query(BrowserProfile).order_by(BrowserProfile.id):
            d = p.as_dict()
            d["session_on_disk"] = (get_settings().data_dir / "profiles" / p.name).exists()
            profs.append(d)
        return {"engines": available_engines(), "profiles": profs, "runs": rows(q.order_by(BrowserRun.id.desc()), 100),
                "session_note": "Persistent profiles keep a login the user performed themselves in a visible browser window. "
                                "Session files stay in the profile folder and are never copied into research records or logs."}


@app.post("/api/browser/profiles", status_code=201)
def add_profile(body: ProfileIn):
    with session() as s:
        if s.query(BrowserProfile).filter_by(name=body.name).first():
            raise HTTPException(409, "Profile name already used")
        p = BrowserProfile(**body.model_dump())
        s.add(p)
        s.flush()
        return p.as_dict()


# ---------- github ----------
@app.get("/api/projects/{pid}/github")
def gh_status(pid: int):
    with session() as s:
        p = proj(s, pid)
        st = github.status(p.repo_path)
        if st["connected"]:
            st["gaps"] = github.doc_gaps(p.repo_path)
        st["repo_url"] = p.repo_url
        return st


class PublishIn(BaseModel):
    kinds: list[str] = Field(min_length=1)
    branch: str = Field(pattern=r"^[A-Za-z0-9._/-]{1,120}$")
    message: str = "Add generated research reports"
    push: bool = False
    open_pr: bool = False


@app.post("/api/projects/{pid}/github/publish")
def gh_publish(pid: int, body: PublishIn):
    """Does not write anything. Creates an approval; the commit happens only when a person approves it."""
    with session() as s:
        proj(s, pid)
        bad = [k for k in body.kinds if k not in reports.KINDS]
        if bad:
            raise HTTPException(422, f"Unknown report kinds: {bad}")
        what = "commit" + (", push" if body.push else "") + (" and open a pull request" if body.open_pr else "")
        return approvals.request(s, pid, "publish_to_repo", f"Create branch '{body.branch}', {what} with reports: {', '.join(body.kinds)}", body.model_dump()).as_dict()


# ---------- dashboard ----------
@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    f = (FRONTEND / path).resolve()
    if path and FRONTEND.resolve() in f.parents and f.is_file():
        return FileResponse(f)
    index = FRONTEND / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return JSONResponse({"detail": "Dashboard not built. Run: cd engine/frontend && npm install && npm run build. The API is at /api and /docs."}, status_code=503)
