"""Polite HTTP capture.

A plain ``httpx`` GET with a declared User-Agent, per-scope delays, and
ETag / Last-Modified conditional re-requests (304 or unchanged content is a
cache hit — the page is not re-processed). No stealth, no header
spoofing, no rendering: when the content is JS-rendered or the server
refuses a plain GET, the caller falls back to the browser path or the
manual-evidence gate — never around a restriction.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import FetchCache, PageRecord
from . import politeness, robots
from .ids import new_id
from .page_understanding import analyze_html

log = logging.getLogger("rice.http")


async def _record_page(project_id: str, url: str, html: str, capture_method: str) -> str:
    """Idempotent page record per canonical URL (same pattern as the browser
    capture path). Returns the page id."""
    analysis = analyze_html(html, url=url, base_url=url)
    st = {k: analysis[k] for k in
          ("regions", "navigation", "forms", "controls", "interactive", "buttons",
           "sections", "links", "images", "states", "repeated_components", "element_counts")}
    now = datetime.now(timezone.utc)
    async with session_scope() as sess:
        existing = (await sess.execute(
            select(PageRecord).where(
                PageRecord.project_id == project_id,
                PageRecord.canonical_url == url[:700],
            )
        )).scalars().first()
        if existing is not None:
            page_id = existing.id
            existing.status = "documented"
            existing.title = analysis["title"]
            existing.content_category = analysis["content_category"]
            existing.purpose = analysis.get("purpose") or existing.purpose
            existing.summary = analysis.get("summary") or existing.summary
            existing.structure = st
            existing.body_text = analysis.get("body_text") or existing.body_text
            existing.observed_at = now
            existing.capture_method = capture_method
            existing.error = ""
        else:
            page = PageRecord(
                id=new_id(), project_id=project_id, url=url[:700], canonical_url=url[:700],
                title=analysis["title"], status="documented",
                content_category=analysis["content_category"],
                purpose=analysis.get("purpose", ""), summary=analysis.get("summary", ""),
                structure=st, body_text=analysis.get("body_text", ""),
                observed_at=now, capture_method=capture_method, error="",
            )
            page_id = page.id
            sess.add(page)
        await sess.commit()
    return page_id


async def fetch_page(project_id: str, url: str, delay_s: float = 0.0) -> dict:
    """Fetch one page politely. Returns:
    {ok, status(200|304|<http>), cached, page_id, error}
    """
    import asyncio

    import httpx

    if delay_s and delay_s > 0:
        await asyncio.sleep(delay_s)

    s = get_settings()
    async with session_scope() as db:
        row = (await db.execute(
            select(FetchCache).where(
                FetchCache.project_id == project_id, FetchCache.url == url
            )
        )).scalars().first()
    headers = {"User-Agent": robots.USER_AGENT}
    headers.update(politeness.conditional_headers(row))

    try:
        async with httpx.AsyncClient(
            timeout=max(5.0, s.browser_timeout_ms / 1000.0), follow_redirects=True
        ) as client:
            r = await client.get(url, headers=headers)
    except Exception as e:
        return {"ok": False, "status": 0, "cached": False, "page_id": "",
                "error": f"HTTP fetch failed: {e.__class__.__name__}: {e}"}

    if r.status_code == 304:
        if row and row.page_id:
            return {"ok": True, "status": 304, "cached": True, "page_id": row.page_id, "error": ""}
        # stale cache row without a usable page — refetch unconditionally once
        return await _refetch(project_id, url, headers_without_conditions(headers))

    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "cached": False, "page_id": "",
                "error": f"server responded HTTP {r.status_code} for {url} (not bypassed)"}

    html = r.text or ""
    if row and row.content_sha and row.content_sha == politeness.sha256(html):
        return {"ok": True, "status": 200, "cached": True, "page_id": row.page_id, "error": ""}

    page_id = await _record_page(project_id, url, html, "http")
    await _upsert_cache(project_id, url, r.headers, html, page_id)
    return {"ok": True, "status": 200, "cached": False, "page_id": page_id, "error": ""}


def headers_without_conditions(headers: dict) -> dict:
    return {k: v for k, v in headers.items()
            if k not in ("If-None-Match", "If-Modified-Since")}


async def _refetch(project_id: str, url: str, headers: dict) -> dict:
    import httpx

    s = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=max(5.0, s.browser_timeout_ms / 1000.0), follow_redirects=True
        ) as client:
            r = await client.get(url, headers=headers)
    except Exception as e:
        return {"ok": False, "status": 0, "cached": False, "page_id": "",
                "error": f"HTTP fetch failed: {e.__class__.__name__}: {e}"}
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "cached": False, "page_id": "",
                "error": f"server responded HTTP {r.status_code} for {url} (not bypassed)"}
    page_id = await _record_page(project_id, url, r.text or "", "http")
    await _upsert_cache(project_id, url, r.headers, r.text or "", page_id)
    return {"ok": True, "status": r.status_code, "cached": False, "page_id": page_id, "error": ""}


async def _upsert_cache(project_id: str, url: str, headers: dict, html: str, page_id: str) -> None:
    """Persist the cache row inside one session (re-fetched — the earlier read
    was in a closed session)."""
    now = datetime.now(timezone.utc)
    sha = politeness.sha256(html)
    async with session_scope() as db:
        row = (await db.execute(
            select(FetchCache).where(FetchCache.project_id == project_id, FetchCache.url == url)
        )).scalars().first()
        if row is not None:
            row.etag = headers.get("etag") or row.etag
            row.last_modified = headers.get("last-modified") or row.last_modified
            row.content_sha = sha
            row.page_id = page_id
            row.fetched_at = now
        else:
            db.add(FetchCache(
                id=new_id(), project_id=project_id, url=url,
                etag=headers.get("etag") or "",
                last_modified=headers.get("last-modified") or "",
                content_sha=sha, page_id=page_id, fetched_at=now,
            ))
        await db.commit()
