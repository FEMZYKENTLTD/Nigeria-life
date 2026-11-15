"""Politeness helpers: content hashing + conditional (ETag / Last-Modified)
headers for the fetch cache."""
from __future__ import annotations

import hashlib

from ..models import FetchCache


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


def conditional_headers(row: FetchCache | None) -> dict:
    """Headers for a conditional re-request; empty dict for a cold cache."""
    if row is None:
        return {}
    headers: dict[str, str] = {}
    if row.etag:
        headers["If-None-Match"] = row.etag
    if row.last_modified:
        headers["If-Modified-Since"] = row.last_modified
    return headers
