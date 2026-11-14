"""Persistent task queue with retry, checkpointing, cancellation and crash recovery.

Tasks live in the database, so nothing is lost when the process stops. A task ends in exactly one of:
done | failed (with the error) | blocked (with the reason) | cancelled. It never just disappears.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

from . import knowledge, permissions, visual
from .browser import CaptureRequest, FatalCaptureError, RecoverableError
from .browser.registry import best_engine, get_adapter
from .config import get_settings
from .db import BrowserProfile, BrowserRun, Evidence, Page, Project, Screenshot, Source, Task, log, now, save_version, session
from .features import features_from_page
from .understanding import analyse, findings_from_record


class Blocked(Exception):
    """The task is not permitted or cannot proceed without a human. Not retried."""


HANDLERS = {}
_last_fetch: dict[str, float] = {}


def handler(kind):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def enqueue(s, project_id: int, kind: str, title: str, payload: dict | None = None, *, priority: int = 50,
            dedupe_key: str | None = None, max_attempts: int = 3) -> tuple[Task, bool]:
    """Idempotent: the same dedupe_key returns the existing task instead of queuing a duplicate."""
    key = dedupe_key or f"{project_id}:{kind}:{hashlib.sha256(repr(sorted((payload or {}).items())).encode()).hexdigest()[:24]}"
    t = s.query(Task).filter_by(dedupe_key=key).first()
    if t:
        return t, False
    t = Task(project_id=project_id, kind=kind, title=title[:400], payload=payload or {}, priority=priority, dedupe_key=key, max_attempts=max_attempts)
    s.add(t)
    s.flush()
    return t, True


def recover() -> int:
    """After a crash or restart: tasks left 'running' go back to the queue with their checkpoint intact."""
    with session() as s:
        stuck = s.query(Task).filter_by(status="running").all()
        for t in stuck:
            t.status, t.error = "queued", "Recovered after interruption; will run again."
            log(s, "task_recovered", t.project_id, level="warn", task_id=t.id, kind=t.kind, checkpoint=t.checkpoint)
        return len(stuck)


def cancel(s, task_id: int) -> Task:
    t = s.get(Task, task_id)
    if t and t.status in ("queued", "running", "blocked"):
        t.status, t.finished_at, t.error = "cancelled", now(), "Cancelled by user."
        log(s, "task_cancelled", t.project_id, actor="human", task_id=t.id)
    return t


def retry(s, task_id: int) -> Task:
    t = s.get(Task, task_id)
    if t and t.status in ("failed", "blocked", "cancelled"):
        t.status, t.attempts, t.error, t.not_before = "queued", 0, "", None
        log(s, "task_requeued", t.project_id, actor="human", task_id=t.id)
    return t


def run_one() -> bool:
    """Claims and runs the next eligible task. Returns False when nothing is runnable."""
    with session() as s:
        active = [p.id for p in s.query(Project).filter_by(status="active")]
        t = (s.query(Task).filter(Task.status == "queued", Task.project_id.in_(active or [-1]))
             .filter((Task.not_before.is_(None)) | (Task.not_before <= now())).order_by(Task.priority, Task.id).first())
        if not t:
            return False
        t.status, t.started_at, t.attempts = "running", now(), t.attempts + 1
        tid, kind = t.id, t.kind
    outcome, error, result = "done", "", {}
    try:
        if kind not in HANDLERS:
            raise FatalCaptureError(f"No handler for task kind '{kind}'")
        with session() as s:
            result = HANDLERS[kind](s, s.get(Task, tid)) or {}
    except Blocked as e:
        outcome, error = "blocked", str(e)
    except RecoverableError as e:
        outcome, error = "retry", str(e)
    except Exception as e:  # noqa: BLE001 - every failure is recorded on the task
        outcome, error = "failed", f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"
    with session() as s:
        t = s.get(Task, tid)
        if t.status == "cancelled":  # cancelled while running: keep the cancellation
            return True
        if outcome == "retry":
            if t.attempts < t.max_attempts:
                delay = 2 ** t.attempts
                t.status, t.error, t.not_before = "queued", f"Attempt {t.attempts} failed: {error}. Retrying in {delay}s.", now() + dt.timedelta(seconds=delay * _backoff_scale)
                log(s, "task_retry_scheduled", t.project_id, level="warn", task_id=tid, attempt=t.attempts, error=error)
                return True
            outcome, error = "failed", f"Gave up after {t.attempts} attempts. Last error: {error}"
        t.status, t.error, t.finished_at = outcome, error[:4000], now()
        if result:
            t.result = result
        log(s, f"task_{outcome}", t.project_id, level="info" if outcome == "done" else "error" if outcome == "failed" else "warn",
            task_id=tid, kind=kind, title=t.title, error=error[:500])
    return True


_backoff_scale = 1.0  # tests set this to 0


class Worker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.paused = False

    def start(self):
        recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nlie-worker", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                did = False if self.paused else run_one()
            except Exception:  # noqa: BLE001 - the loop itself must survive
                did = False
            if not did:
                self._stop.wait(get_settings().worker_poll_seconds)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())


worker = Worker()


def drain(max_tasks: int = 500) -> int:
    n = 0
    while n < max_tasks and run_one():
        n += 1
    return n


# ---------------- handlers ----------------
def source_for(s, project_id: int, url: str) -> Source | None:
    host = urlparse(url).netloc.lower()
    for src in s.query(Source).filter_by(project_id=project_id):
        if urlparse(src.base_url).netloc.lower() == host:
            return src
    return None


@handler("import_research")
def h_import(s, t: Task):
    from .importer import import_research
    project = s.get(Project, t.project_id)
    if not project.repo_path:
        raise Blocked("Project has no local repository path configured.")
    return import_research(s, project, project.repo_path)


@handler("capture_page")
def h_capture(s, t: Task):
    st, p = get_settings(), t.payload
    url = p["url"]
    src = source_for(s, t.project_id, url)
    verdict = permissions.check_capture(s, src, url)
    page = s.query(Page).filter_by(project_id=t.project_id, url=url).first()
    if not verdict.allowed:
        pid, project_id = (page.id if page else None), t.project_id
        s.rollback()
        with session() as s2:  # own transaction: the task's transaction is discarded when it is blocked
            pg = s2.get(Page, pid) if pid else None
            if pg and pg.status == "discovered":
                pg.status = "blocked"
            log(s2, "capture_blocked", project_id, level="warn", url=url, reason=verdict.reason)
        raise Blocked(verdict.reason + " Use manual evidence import for this page if it is needed.")

    profile = s.query(BrowserProfile).filter_by(name=p.get("profile", "")).first()
    engine = best_engine(p.get("engine") or (profile.engine if profile else "") or st.default_engine)
    adapter = get_adapter(engine)
    viewport = tuple(p.get("viewport") or ((profile.viewport_width, profile.viewport_height) if profile else (1440, 900)))
    host = urlparse(url).netloc
    wait = (src.rate_limit_seconds or 0) - (time.time() - _last_fetch.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    shot_dir = st.data_dir / "screenshots" / str(t.project_id) if (adapter.supports_screenshots and src.capture_screenshots) else None
    prof_dir = st.data_dir / "profiles" / profile.name if (profile and profile.persistent and adapter.renders_js) else None
    t0, project_id, task_id = time.time(), t.project_id, t.id
    try:
        cap = adapter.capture(CaptureRequest(url=url, viewport=viewport, mobile=bool(profile and profile.mobile), headless=not profile or profile.headless,
                                             screenshot_dir=shot_dir, profile_dir=prof_dir, user_agent=st.user_agent, timeout_ms=p.get("timeout_ms", 30000)))
    except (RecoverableError, FatalCaptureError) as e:
        _last_fetch[host] = time.time()
        s.rollback()
        with session() as s2:  # record the failed run even though this task's transaction is discarded
            s2.add(BrowserRun(project_id=project_id, task_id=task_id, engine=engine, url=url, status="failed", error=str(e)[:1000], duration_ms=int((time.time() - t0) * 1000)))
        raise
    _last_fetch[host] = time.time()
    s.add(BrowserRun(project_id=t.project_id, task_id=t.id, engine=engine, profile=profile.name if profile else "", url=url, status="ok",
                     http_status=cap.status, duration_ms=cap.duration_ms, console_errors=cap.console_errors))

    # Evidence: the captured HTML is archived to disk and hashed.
    digest = hashlib.sha256(cap.html.encode("utf-8", "replace")).hexdigest()
    ev_dir = st.data_dir / "evidence" / str(t.project_id)
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_path = ev_dir / f"{digest[:16]}.html"
    ev_path.write_text(cap.html, encoding="utf-8", errors="replace")
    ev = knowledge.add_evidence(s, t.project_id, kind="page_capture", source_url=cap.final_url, locator=f"{engine} {viewport[0]}x{viewport[1]}",
                                summary=f"HTML captured by {engine} (JavaScript {'executed' if cap.rendered else 'not executed'}), HTTP {cap.status}.",
                                classification="confirmed", file_path=str(ev_path), sha256=digest)
    t.checkpoint = {"captured": True, "evidence": ev.ref}

    rec = analyse(cap.html, cap.final_url, rendered=cap.rendered)
    rec.update({"http_status": cap.status, "engine": engine, "redirects": cap.redirects, "console_errors": cap.console_errors,
                "failed_requests": cap.failed_requests, "robots": verdict.robots, "requested_url": url})
    if not page:
        page = Page(project_id=t.project_id, url=url)
        s.add(page)
        s.flush()
    elif page.content_hash and page.content_hash != rec["content_hash"]:
        save_version(s, page, "content changed on re-capture")
    text = rec.pop("text")
    page.source_id, page.title, page.purpose, page.category = src.id, rec["title"][:400], rec["purpose"], rec["category"]
    page.status, page.http_status, page.engine, page.content_hash = "analysed", cap.status, engine, rec["content_hash"]
    page.text, page.record, page.evidence_id, page.fetched_at = text, rec, ev.id, now()

    new_findings = 0
    for f in findings_from_record(rec):
        _, created = knowledge.add_finding(s, t.project_id, f["observation"], page_id=page.id, evidence_id=ev.id, confidence="confirmed", kind=f["kind"])
        new_findings += created
    feats = 0
    for f in features_from_page(rec, ev.ref):
        _, action = knowledge.upsert_feature(s, t.project_id, f["name"], f["category"], f["fields"], evidence_refs=[ev.ref], confidence="confirmed", origin="engine:page-analysis")
        feats += action == "created"
    discovered = 0
    for link in rec["internal_links"]:
        if permissions.in_scope(src, link) and not s.query(Page).filter_by(project_id=t.project_id, url=link).first():
            s.add(Page(project_id=t.project_id, source_id=src.id, url=link, status="discovered", discovered_from=url))
            s.flush()
            discovered += 1
    for sh in cap.screenshots:
        info = visual.image_info(sh["path"])
        sev = knowledge.add_evidence(s, t.project_id, kind="screenshot", source_url=cap.final_url, locator=f"{engine} {viewport[0]}x{viewport[1]}",
                                     summary=f"{'Full-page' if sh['full_page'] else 'Viewport'} screenshot.", classification="confirmed", file_path=sh["path"], sha256=info["sha256"])
        s.add(Screenshot(project_id=t.project_id, page_id=page.id, evidence_id=sev.id, path=sh["path"], engine=engine, viewport=f"{viewport[0]}x{viewport[1]}",
                         full_page=sh["full_page"], width=info["width"], height=info["height"], sha256=info["sha256"], ahash=info["ahash"],
                         category=visual.categorise(viewport[0], sh["full_page"])))
    return {"evidence": ev.ref, "http_status": cap.status, "engine": engine, "rendered_js": cap.rendered, "findings_added": new_findings,
            "features_added": feats, "links_discovered": discovered, "screenshots": len(cap.screenshots), "states": rec["states"]}


@handler("plan")
def h_plan(s, t: Task):
    from .planner import plan
    return plan(s, s.get(Project, t.project_id))


@handler("generate_report")
def h_report(s, t: Task):
    from .reports import generate
    out = generate(s, s.get(Project, t.project_id), t.payload["kind"], t.payload.get("formats") or ["md"])
    return {"reports": [r["path"] for r in out]}
