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
    # domcontentloaded | load | networkidle
    wait_until: str = "domcontentloaded"


@dataclass
class CaptureResult:
    ok: bool
    final_url: str = ""
    status_code: int | None = None
    html: str = ""
    screenshot_paths: list[str] = field(default_factory=list)
    screenshot_sizes: dict[str, int] = field(default_factory=dict)  # path → bytes on disk
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

    async def inspect_page(self, url: str, screenshot_path: str = "",
                           timeout_ms: int = 30000,
                           wait_until: str = "domcontentloaded") -> dict:
        """Standalone quick probe (no session, no analysis). Always returns a
        dict — never raises: {"url", "status", "title", "screenshot_size",
        "error"}. On a target failure the dict carries the honest error; a
        500 is reserved for the engine itself being unable to run."""
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - trivial
        pass
