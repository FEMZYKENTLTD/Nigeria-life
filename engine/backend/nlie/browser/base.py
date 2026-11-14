"""Browser adapter contract. A new engine only needs to implement `capture` and `health`."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


class RecoverableError(Exception):
    """Timeouts, connection resets, 5xx: worth retrying."""


class FatalCaptureError(Exception):
    """Will not succeed on retry (bad URL, engine not installed, 4xx)."""


@dataclass
class CaptureRequest:
    url: str
    viewport: tuple[int, int] = (1440, 900)
    mobile: bool = False
    headless: bool = True
    timeout_ms: int = 30000
    screenshot_dir: Path | None = None  # None = no screenshots
    full_page: bool = True
    profile_dir: Path | None = None  # persistent, user-authorised session directory (never copied into research records)
    user_agent: str = ""


@dataclass
class Capture:
    url: str
    final_url: str
    status: int | None
    html: str
    title: str = ""
    engine: str = ""
    duration_ms: int = 0
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    redirects: list[str] = field(default_factory=list)
    screenshots: list[dict] = field(default_factory=list)  # {path, full_page, width, height}
    rendered: bool = False  # True when JavaScript was executed


class BrowserAdapter:
    name = "base"
    renders_js = False
    supports_screenshots = False

    def health(self) -> dict:
        raise NotImplementedError

    def capture(self, req: CaptureRequest) -> Capture:
        raise NotImplementedError
