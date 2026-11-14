"""Redaction: secrets must never reach logs, research records or reports."""
from __future__ import annotations
import re
from typing import Any

SENSITIVE_KEYS = re.compile(r"(pass(word)?|secret|token|cookie|authorization|api[_-]?key|session|card|cvv|pin)", re.I)
PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # card-like digit runs
]
MASK = "[REDACTED]"


def redact_text(text: str) -> str:
    for p in PATTERNS:
        text = p.sub(MASK, text)
    return text


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: (MASK if SENSITIVE_KEYS.search(str(k)) and not isinstance(v, (dict, list)) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
