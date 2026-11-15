"""Reusable browser engine adapter interface.

Adding a new browser engine = implementing this interface and registering it
in ``engines.ENGINE_REGISTRY``. The research system, scheduler and dashboard
never reference a specific engine.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class CaptureOptions:
    url: str
    viewport: dict = field(default_factory=lambda: {"width": 1440, "height": 900, "dpr": 1})
    full_page_screenshot: bool = True
    wait_ms: int = 3000
    timeout_ms: int = 30000
    user_agent: str = ""


@dataclass
class CaptureResult:
    ok: bool
    final_url: str = ""
    status_code: int | None = None
    html: str = ""
    screenshot_paths: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    navigations: list[str] = field(default_factory=list)
    error: str = ""
    recoverable: bool = False  # True ⇒ scheduler may retry
    duration_ms: int = 0


class BrowserEngineAdapter(abc.ABC):
    engine: str = "base"  # chromium | firefox | webkit | ...

    @abc.abstractmethod
    async def health(self) -> dict:
        """Return {engine, installed, version, binary_path, error}."""

    @abc.abstractmethod
    async def capture(self, options: CaptureOptions, user_data_dir: str = "",
                      headless: bool = True,
                      extra_viewports: list[dict] | None = None) -> CaptureResult:
        """Navigate, wait, capture HTML + screenshots (viewport and full page,
        plus responsive sets), console errors and navigation history.

        Implementations must never store passwords/cookies/tokens in the
        returned result — only public observable state.
        """

    async def close(self) -> None:  # pragma: no cover - trivial
        pass
