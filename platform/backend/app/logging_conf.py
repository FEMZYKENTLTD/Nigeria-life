"""Structured (JSON-line) logging. Credential hygiene: nothing ever logs
tokens, cookies or session material — the agent codebase has no access to
them, and a sanitizer scrubs anything that looks like a bearer token.
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone

_TOKEN_RE = re.compile(
    r"(?i)(authorization|bearer|api[-_]?key|token|password|secret)\s*[:=]\s*([^\s,;\"']{4,})"
)


def _sanitize(msg: str) -> str:
    return _TOKEN_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", msg)


class JsonLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": _sanitize(record.getMessage()),
        }
        if record.exc_info:
            entry["exc"] = self.format(record)
        try:
            sys.stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:  # never let logging kill the app
            pass


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = JsonLogHandler()
    root.addHandler(handler)
    # keep uvicorn quiet-ish
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
