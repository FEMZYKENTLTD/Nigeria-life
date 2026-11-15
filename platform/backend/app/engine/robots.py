"""Robots.txt compliance — politeness, not evasion.

Fetches each domain's robots.txt at most once per TTL and applies the
standard rules:

* file readable          → follow it (Disallowed URLs are gated, never bypassed)
* 404 (no rules)         → nothing is disallowed
* 401/400/403 (unreadable) → safe default: treat as disallowed
* network error          → "unknown": the caller proceeds, and the fetch
  itself will honestly fail if the domain is also unreachable

A per-project scope may carry an ``approved_exception`` (set ONLY through an
approved human decision) that authorises fetching URLs robots.txt disallows
for that domain — the sign-off is recorded on the scope row.
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

USER_AGENT = "rice-research/1.0 (polite research agent; respects robots.txt)"
TTL_S = 3600

# domain -> (fetched_at, status_code, text)
_cache: dict[str, tuple[float, int, str]] = {}


def _robots_url(target_url: str) -> str:
    p = urlparse(target_url)
    scheme = p.scheme or "https"
    return f"{scheme}://{p.netloc}/robots.txt"


def clear_cache() -> None:
    _cache.clear()


async def robots_status(url: str) -> tuple[str, str]:
    """Return (status, detail) with status in {allowed, disallowed, unknown}."""
    domain = urlparse(url).netloc
    if not domain:
        return "allowed", "no domain"
    now = time.time()
    entry = _cache.get(domain)
    if entry and now - entry[0] < TTL_S:
        status_code, text = entry[1], entry[2]
    else:
        rurl = _robots_url(url)
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                r = await c.get(rurl, headers={"User-Agent": USER_AGENT})
            status_code, text = r.status_code, (r.text or "")[:200_000]
            _cache[domain] = (now, status_code, text)
        except Exception as e:  # network path absent → unknown, not "disallowed"
            return "unknown", f"robots.txt unreadable ({e.__class__.__name__}); proceeding, fetch may fail honestly"

    if status_code in (401, 400, 403):
        return "disallowed", f"robots.txt not readable (HTTP {status_code}) — safe default is no automated fetch"
    parser = urllib.robotparser.RobotFileParser()
    if status_code < 400:
        parser.parse(text.splitlines())
    # status >= 404 → empty rules → allow_all
    if parser.can_fetch(USER_AGENT, url):
        return "allowed", "robots.txt permits this URL"
    return "disallowed", f"robots.txt for {domain} disallows this URL"
