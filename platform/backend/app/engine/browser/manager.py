"""Browser session manager.

Owns profiles, research sessions, execution logs and screenshot persistence.
Every failure is persisted with its reason (honest-failure policy); nothing
in here silently drops a task.
"""
from __future__ import annotations

import hashlib
import logging
import os

from sqlalchemy import select

from ...config import get_settings
from ...db import session_scope
from ...engine.ids import new_id
from ...engine.browser.engines import PlaywrightAdapter, make_adapter, supported_engines
from ...engine.page_understanding import analyze_html
from ...models import (BrowserHealth, BrowserProfile, ExecutionLog, PageRecord,
                       ResearchSession, Screenshot)

log = logging.getLogger("rice.browser.manager")


async def probe_engines() -> list[dict]:
    """Check every registered engine and persist health rows."""
    results = []
    for engine in supported_engines():
        adapter = make_adapter(engine)
        if adapter is None:
            row = {"engine": engine, "installed": False, "version": "", "binary_path": "",
                   "error": "No adapter registered for this engine."}
        else:
            row = await adapter.health()
        async with session_scope() as s:
            existing = (await s.execute(
                select(BrowserHealth).where(BrowserHealth.engine == engine)
            )).scalars().first()
            if existing is None:
                s.add(BrowserHealth(id=new_id(), **row))
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
        results.append(row)
    return results


async def get_health() -> list[dict]:
    async with session_scope() as s:
        rows = (await s.execute(
            select(BrowserHealth).order_by(BrowserHealth.engine)
        )).scalars().all()
    if not rows:
        return await probe_engines()
    return [{"id": r.id, "engine": r.engine, "installed": r.installed, "version": r.version,
             "binary_path": r.binary_path, "error": r.error,
             "checked_at": r.checked_at.isoformat() if r.checked_at else ""} for r in rows]


async def list_profiles() -> list[dict]:
    async with session_scope() as s:
        rows = (await s.execute(select(BrowserProfile))).scalars().all()
    return [{"id": r.id, "project_id": r.project_id, "name": r.name, "engine": r.engine,
             "user_data_dir": r.user_data_dir, "viewports": r.viewports or [],
             "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]


DEFAULT_VIEWPORTS = [
    {"name": "mobile", "width": 375, "height": 812, "dpr": 2},
    {"name": "tablet", "width": 768, "height": 1024, "dpr": 1},
    {"name": "desktop", "width": 1440, "height": 900, "dpr": 1},
]


async def create_profile(project_id: str, name: str, engine: str,
                         viewports: list[dict] | None = None, shared: bool = False) -> dict:
    s = get_settings()
    uid = new_id()
    pdir = os.path.join(s.data_dir, "profiles", uid)
    os.makedirs(pdir, exist_ok=True)
    prof = BrowserProfile(
        id=uid,
        project_id="" if shared else project_id,
        name=name,
        engine=engine if engine in supported_engines() else "chromium",
        user_data_dir=pdir,
        viewports=viewports or DEFAULT_VIEWPORTS,
    )
    async with session_scope() as sess:
        sess.add(prof)
    return {"id": prof.id, "name": prof.name, "engine": prof.engine, "user_data_dir": pdir,
            "viewports": prof.viewports}


def _phash_png(path: str) -> str:
    """Perceptual dHash for change detection. Pure-Python PNG decode via zlib
    (grayscale 8x8 average hash) — no image dependencies."""
    try:
        import struct
        import zlib

        with open(path, "rb") as f:
            data = f.read()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return ""
        pos = 8
        width = height = 0
        bit_depth = color_type = None
        idat = b""
        while pos < len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            chunk = data[pos + 8:pos + 8 + length]
            if ctype == b"IHDR":
                width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            elif ctype == b"IDAT":
                idat += chunk
            elif ctype == b"IEND":
                break
            pos += 12 + length
        if width < 9 or height < 9 or not idat:
            return ""
        raw = zlib.decompress(idat)
        # unfilter scanlines (simplified: handle filter 0/1/2; enough for dHash)
        channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type, 1)
        stride = width * channels
        out = bytearray()
        prev = bytearray(stride)
        i = 0
        for _ in range(height):
            ft = raw[i]
            i += 1
            line = bytearray(raw[i:i + stride])
            i += stride
            if ft == 0:
                pass
            elif ft == 1:
                for x in range(channels, stride):
                    line[x] = (line[x] + line[x - channels]) & 0xFF
            elif ft == 2:
                for x in range(stride):
                    line[x] = (line[x] + prev[x]) & 0xFF
            elif ft == 3:
                for x in range(stride):
                    left = line[x - channels] if x >= channels else 0
                    line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
            elif ft == 4:
                for x in range(stride):
                    left = line[x - channels] if x >= channels else 0
                    up = prev[x]
                    upleft = prev[x - channels] if x >= channels else 0
                    p = left + up - upleft
                    pa, pb, pc = abs(p - left), abs(p - up), abs(p - upleft)
                    pred = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                    line[x] = (line[x] + pred) & 0xFF
            out.extend(line)
            prev = line
        # sample 9x9 grid → dHash 8x8
        grid = []
        for gy in range(8):
            row = []
            for gx in range(9):
                px = int((gx + 0.5) * width / 9)
                py = int((gy + 0.5) * height / 9)
                idx = py * stride + px * channels
                if idx + 2 < len(out):
                    if color_type in (2, 6):
                        v = (out[idx] + out[idx + 1] + out[idx + 2]) // 3
                    elif color_type == 4:
                        v = out[idx]
                    else:
                        v = out[idx]
                    row.append(v)
                else:
                    row.append(0)
            grid.append(row)
        bits = 0
        for gy in range(8):
            for gx in range(8):
                bits = (bits << 1) | (1 if grid[gy][gx] < grid[gy][gx + 1] else 0)
        return format(bits, "016x")
    except Exception:
        return ""


async def run_capture(project_id: str, source_url: str, engine: str = "chromium",
                      headless: bool = True, viewport: dict | None = None,
                      extra_viewports: list[dict] | None = None,
                      full_page: bool = True, profile_id: str = "",
                      task_id: str = "", session_id: str = "",
                      delay_s: float = 1.0, max_retries: int = 1) -> dict:
    """Capture one page through a browser engine, persist a PageRecord +
    screenshots + execution logs. Returns a status dict (never raises for
    expected failures)."""
    import asyncio

    s = get_settings()
    session = None
    async with session_scope() as sess:
        if session_id:
            session = (await sess.execute(
                select(ResearchSession).where(ResearchSession.id == session_id)
            )).scalars().first()
    if session is None:
        session = ResearchSession(id=new_id(), project_id=project_id, profile_id=profile_id,
                                  engine=engine, mode="visible" if not headless else "headless",
                                  status="active")
        async with session_scope() as sess:
            sess.add(session)
        session_id = session.id

    async def _log(level: str, event: str, message: str, detail: dict | None = None) -> None:
        async with session_scope() as sess:
            sess.add(ExecutionLog(id=new_id(), session_id=session_id, task_id=task_id,
                                  engine=engine, level=level, event=event,
                                  message=message[:500], detail=detail or {}))

    profile_row = None
    if profile_id:
        async with session_scope() as sess:
            profile_row = (await sess.execute(
                select(BrowserProfile).where(BrowserProfile.id == profile_id)
            )).scalars().first()
    user_data_dir = profile_row.user_data_dir if profile_row else ""
    shots_dir = os.path.join(s.data_dir, "screenshots", project_id, session_id)

    adapter = make_adapter(engine)
    if adapter is None:
        await _log("error", "session.failed", f"No adapter registered for engine '{engine}'.",
                   {"engine": engine})
        async with session_scope() as sess:
            row = (await sess.execute(
                select(ResearchSession).where(ResearchSession.id == session_id)
            )).scalars().first()
            row.status = "failed"
            row.error = f"No adapter for engine {engine}"
            row.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        return {"ok": False, "session_id": session_id, "error": f"No adapter for engine {engine}",
                "recoverable": False}

    from ...engine.browser.base import CaptureOptions

    options = CaptureOptions(
        url=source_url,
        viewport=viewport or {"width": 1440, "height": 900, "dpr": 1},
        full_page_screenshot=full_page,
        timeout_ms=s.browser_timeout_ms,
    )
    result = None
    for attempt in range(1, max(1, max_retries) + 1):
        await _log("info", "capture.attempt", f"Attempt {attempt}: {source_url}",
                   {"engine": engine, "attempt": attempt, "viewport": options.viewport})
        result = await adapter.capture(
            options, user_data_dir=user_data_dir, headless=headless,
            extra_viewports=extra_viewports, screenshot_dir=shots_dir,
            screenshots_allowed=True,
        )
        if result.ok:
            break
        if not result.recoverable or attempt == max_retries:
            break
        await _log("warn", "capture.retry", f"Recoverable failure, retrying in {s.browser_retry_backoff_s}s: {result.error[:200]}")
        await asyncio.sleep(s.browser_retry_backoff_s * attempt)

    # persist page record (idempotent per canonical URL)
    page_id = ""
    status = "documented" if result.ok else "error"
    if result.ok:
        analysis = analyze_html(result.html, url=result.final_url or source_url, base_url=result.final_url or source_url)
        purpose = analysis.get("purpose", "")
        summary = analysis.get("summary", "")
        body_text = analysis.get("body_text", "")
        st = {k: analysis[k] for k in
              ("regions", "navigation", "forms", "controls", "interactive", "buttons",
               "sections", "links", "images", "states", "repeated_components", "element_counts")}
    else:
        analysis = None
        purpose = summary = body_text = ""
        st = {}

    async with session_scope() as sess:
        existing = None
        if result.ok:
            existing = (await sess.execute(
                select(PageRecord).where(
                    PageRecord.project_id == project_id,
                    PageRecord.canonical_url == (result.final_url or source_url)[:700],
                )
            )).scalars().first()
        if existing is not None:
            page_id = existing.id
            existing.status = status
            existing.title = analysis["title"] if analysis else existing.title
            existing.content_category = analysis["content_category"] if analysis else existing.content_category
            existing.purpose = purpose or existing.purpose
            existing.summary = summary or existing.summary
            existing.structure = st or existing.structure
            existing.body_text = body_text or existing.body_text
            existing.observed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            existing.capture_method = f"browser:{engine}"
            existing.browser_engine = engine
            existing.session_id = session_id
            existing.error = result.error if not result.ok else ""
        else:
            page = PageRecord(
                id=new_id(), project_id=project_id, url=source_url[:700],
                canonical_url=(result.final_url or source_url)[:700],
                title=analysis["title"] if analysis else "",
                status=status,
                content_category=analysis["content_category"] if analysis else "",
                purpose=purpose, summary=summary, structure=st,
                body_text=body_text,
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc) if result.ok else None,
                capture_method=f"browser:{engine}", browser_engine=engine,
                session_id=session_id, error=result.error,
            )
            page_id = page.id
            sess.add(page)

    # screenshots
    shot_records = []
    if result.ok and result.screenshot_paths:
        ev = None
        from ...models import Evidence
        async with session_scope() as sess:
            ev = Evidence(
                id=new_id(), project_id=project_id, ref_code="",
                evidence_class="C", source_uri=result.final_url or source_url,
                source_name=f"Browser capture ({engine})", capture_method="screenshot",
                description=f"Screenshot evidence for {result.final_url or source_url}",
                meta={"session_id": session_id, "engine": engine},
                captured_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            sess.add(ev)
            await sess.flush()
            evidence_id = ev.id
            for p in result.screenshot_paths:
                if not os.path.exists(p):
                    continue
                checksum = hashlib.sha256(open(p, "rb").read()).hexdigest()
                phash = _phash_png(p)
                name = os.path.basename(p)
                category = "responsive" if name.startswith("responsive") else ("fullpage" if name.startswith("fullpage") else "viewport")
                shot = Screenshot(
                    id=new_id(), project_id=project_id, page_id=page_id, evidence_id=evidence_id,
                    url=result.final_url or source_url,
                    viewport=options.viewport, full_page=name.startswith("fullpage"),
                    file_path=os.path.relpath(p, s.data_dir), file_checksum=checksum,
                    perceptual_hash=phash, category=category,
                    captured_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                )
                shot_records.append({"id": shot.id, "file": shot.file_path, "category": category,
                                     "hash": phash})
                sess.add(shot)
                # link evidence to page
                if page_id:
                    pg = (await sess.execute(
                        select(PageRecord).where(PageRecord.id == page_id)
                    )).scalars().first()
                    if pg and evidence_id not in pg.evidence_ids:
                        pg.evidence_ids.append(evidence_id)

    await _log("info" if result.ok else "error", "session.completed" if result.ok else "session.failed",
               f"{'Captured' if result.ok else 'FAILED'} {source_url}"
               + ("" if result.ok else f" — {result.error}"),
               {"final_url": result.final_url, "status_code": result.status_code,
                "console_errors": result.console_errors[:10], "navigations": result.navigations[:10],
                "screenshots": len(result.screenshot_paths), "duration_ms": result.duration_ms})

    async with session_scope() as sess:
        row = (await sess.execute(
            select(ResearchSession).where(ResearchSession.id == session_id)
        )).scalars().first()
        row.status = "completed" if result.ok else "failed"
        row.error = result.error or ""
        row.summary = {
            "pages_visited": 1,
            "ok": bool(result.ok),
            "screenshots": len(result.screenshot_paths),
            "console_errors": len(result.console_errors),
            "recoverable": result.recoverable,
        }
        row.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    return {
        "ok": bool(result.ok),
        "session_id": session_id,
        "page_id": page_id,
        "url": result.final_url or source_url,
        "status_code": result.status_code,
        "error": result.error,
        "recoverable": result.recoverable,
        "screenshots": shot_records,
        "console_errors": result.console_errors[:10],
        "navigations": result.navigations[:10],
    }


async def list_sessions(project_id: str | None = None, limit: int = 50,
                        project_ids: list[str] | None = None) -> list[dict]:
    async with session_scope() as s:
        q = select(ResearchSession)
        if project_id:
            q = q.where(ResearchSession.project_id == project_id)
        elif project_ids is not None:
            q = q.where(ResearchSession.project_id.in_(project_ids))
        rows = (await s.execute(q.order_by(ResearchSession.started_at.desc()).limit(limit))).scalars().all()
    return [{"id": r.id, "project_id": r.project_id, "engine": r.engine, "mode": r.mode,
             "status": r.status, "summary": r.summary or {}, "error": r.error,
             "started_at": r.started_at.isoformat() if r.started_at else "",
             "ended_at": r.ended_at.isoformat() if r.ended_at else ""} for r in rows]


async def session_log(session_id: str, limit: int = 200) -> list[dict]:
    async with session_scope() as s:
        rows = (await s.execute(
            select(ExecutionLog).where(ExecutionLog.session_id == session_id)
            .order_by(ExecutionLog.ts.desc()).limit(limit)
        )).scalars().all()
    return [{"id": r.id, "level": r.level, "event": r.event, "message": r.message,
             "detail": r.detail or {}, "engine": r.engine,
             "ts": r.ts.isoformat() if r.ts else ""} for r in rows]


async def detect_visual_changes(project_id: str, page_id: str) -> list[dict]:
    """Compare all captures of a page via perceptual hash distance."""
    async with session_scope() as s:
        rows = (await s.execute(
            select(Screenshot).where(
                Screenshot.project_id == project_id,
                Screenshot.page_id == page_id,
            ).order_by(Screenshot.captured_at)
        )).scalars().all()
    out = []
    prev = None
    for r in rows:
        if prev is not None and prev.perceptual_hash and r.perceptual_hash:
            xor = int(prev.perceptual_hash, 16) ^ int(r.perceptual_hash, 16)
            dist = bin(xor).count("1")
            out.append({"from": prev.id, "to": r.id, "hamming_distance": dist,
                        "changed": dist > 10,
                        "at": r.captured_at.isoformat() if r.captured_at else ""})
        prev = r
    return out
