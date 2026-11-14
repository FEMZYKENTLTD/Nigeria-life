"""Collection-scope enforcement. Every automated capture passes through `check_capture` first."""
from __future__ import annotations
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .db import Page, Source


@dataclass
class Verdict:
    allowed: bool
    reason: str
    robots: str = "not_checked"  # allowed | disallowed | missing | unreachable | not_checked


transport: httpx.BaseTransport | None = None  # tests inject a mock transport here
_robots_cache: dict[str, tuple[str, urllib.robotparser.RobotFileParser | None]] = {}


def _robots(base: str, client: httpx.Client | None = None):
    if base in _robots_cache:
        return _robots_cache[base]
    state, rp = "unreachable", None
    try:
        c = client or httpx.Client(timeout=10, headers={"User-Agent": get_settings().user_agent}, follow_redirects=True, transport=transport)
        r = c.get(base + "/robots.txt")
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and "html" not in ctype:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            state = "present"
        elif r.status_code in (401, 403):
            state = "forbidden"  # conventional reading: treat as disallow-all
        else:
            state = "missing"
    except Exception:
        state = "unreachable"
    _robots_cache[base] = (state, rp)
    return _robots_cache[base]


def in_scope(source: Source, url: str) -> bool:
    b, u = urlparse(source.base_url), urlparse(url)
    if u.scheme not in ("http", "https") or u.netloc.lower() != b.netloc.lower():
        return False
    prefixes = source.allowed_paths or []
    return not prefixes or any((u.path or "/").startswith(p) for p in prefixes)


def check_capture(s, source: Source | None, url: str, client: httpx.Client | None = None) -> Verdict:
    if source is None:
        return Verdict(False, "URL does not belong to any configured source for this project.")
    if not source.approved:
        return Verdict(False, f"Source '{source.name}' is awaiting human approval.")
    if source.automation != "automated":
        return Verdict(False, f"Source '{source.name}' is manual-only: import evidence by hand instead of automating.")
    if not in_scope(source, url):
        return Verdict(False, "URL is outside the source's host or allowed path prefixes.")
    captured = s.query(Page).filter(Page.source_id == source.id, Page.status.in_(("captured", "analysed"))).count()
    already = s.query(Page).filter(Page.project_id == source.project_id, Page.url == url, Page.status.in_(("captured", "analysed"))).count()
    if not already and captured >= source.max_pages:
        return Verdict(False, f"Page budget reached ({source.max_pages} pages) for source '{source.name}'.")
    robots = "not_checked"
    if source.respect_robots:
        p = urlparse(source.base_url)
        state, rp = _robots(f"{p.scheme}://{p.netloc}", client)
        if state == "forbidden":
            return Verdict(False, "robots.txt request was refused (401/403); treated as disallow-all.", "disallowed")
        if state == "unreachable":
            return Verdict(False, "robots.txt could not be fetched (network error); not proceeding without it.", "unreachable")
        if rp is not None and not rp.can_fetch(get_settings().user_agent, url):
            return Verdict(False, "robots.txt disallows this URL for automated agents.", "disallowed")
        robots = "allowed" if rp is not None else "missing"
    return Verdict(True, "Within approved scope.", robots)


def clear_cache():
    _robots_cache.clear()
