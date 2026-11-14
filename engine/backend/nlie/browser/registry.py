"""Adapter registry. Register a new engine with `register(name, factory)`; nothing else changes."""
from __future__ import annotations
from typing import Callable

from .base import BrowserAdapter
from .http_adapter import HttpAdapter
from .playwright_adapter import PlaywrightAdapter

_registry: dict[str, Callable[[], BrowserAdapter]] = {
    "http": HttpAdapter,
    "chromium": lambda: PlaywrightAdapter("chromium"),
    "firefox": lambda: PlaywrightAdapter("firefox"),
    "webkit": lambda: PlaywrightAdapter("webkit"),
}


def register(name: str, factory: Callable[[], BrowserAdapter]) -> None:
    _registry[name] = factory


def get_adapter(name: str) -> BrowserAdapter:
    if name not in _registry:
        raise KeyError(f"Unknown browser engine '{name}'. Known: {sorted(_registry)}")
    return _registry[name]()


def available_engines() -> list[dict]:
    return [get_adapter(n).health() for n in _registry]


def best_engine(preferred: str = "") -> str:
    """Preferred engine if installed, else the first installed rendering engine, else plain HTTP."""
    order = [preferred] if preferred else []
    order += ["chromium", "firefox", "webkit", "http"]
    for n in order:
        if n in _registry and get_adapter(n).health()["available"]:
            return n
    return "http"
