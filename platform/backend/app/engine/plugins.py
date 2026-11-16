"""Modular plugin architecture.

Extensible component kinds:

* ``ai_provider``     — model adapters (``off`` built-in; cloud/local via entry points)
* ``browser_engine``  — capture engines (chromium/firefox/webkit built-in)
* ``report_format``   — extra report renderers (``pdf`` built-in)
* ``analysis_module`` — additional analytics computations exposed to reports

Built-ins register at ``discover()`` time. Third-party plugins install via
the ``rice.plugins`` setuptools entry-point group; each entry must be a
callable receiving this registry. A failing plugin is logged and skipped —
it can never take the core down (the offline/no-provider guarantees hold).

This is the extension point the core is designed around: new research
capabilities, browser integrations, AI providers and analysis modules plug
in without redesigning the application.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("rice.plugins")

KINDS = ("ai_provider", "browser_engine", "report_format", "analysis_module")


@dataclass
class Plugin:
    kind: str
    name: str
    factory: Callable[..., Any]
    meta: dict = field(default_factory=dict)


class PluginRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Plugin]] = {k: {} for k in KINDS}

    def register(self, kind: str, name: str, factory: Callable[..., Any], **meta: Any) -> Plugin:
        if kind not in self._items:
            raise ValueError(f"unknown plugin kind '{kind}' (expected one of {KINDS})")
        p = Plugin(kind=kind, name=name, factory=factory, meta=meta)
        existing = self._items[kind].get(name)
        if existing is not None:
            log.warning("plugin %s/%s re-registered (overriding %s)", kind, name,
                        meta.get("source", "unknown"))
        self._items[kind][name] = p
        return p

    def get(self, kind: str, name: str) -> Plugin:
        try:
            return self._items[kind][name]
        except KeyError:
            available = ", ".join(sorted(self._items.get(kind, {}))) or "none"
            raise KeyError(f"plugin {kind}/{name} not registered (available: {available})") from None

    def has(self, kind: str, name: str) -> bool:
        return name in self._items.get(kind, {})

    def list(self, kind: str) -> list[Plugin]:
        return sorted(self._items.get(kind, {}).values(), key=lambda p: p.name)


registry = PluginRegistry()
_discovered = False


def _register_builtins() -> None:
    from ..ai.offline import OfflineAdapter
    from ..ai.openai_compat import OpenAICompatAdapter
    from ..engine import pdf as pdf_mod

    if not registry.has("ai_provider", "off"):
        registry.register("ai_provider", "off", OfflineAdapter, source="builtin",
                          description="Deterministic offline heuristics (default; no provider required)")
    if not registry.has("ai_provider", "openai_compatible"):
        registry.register("ai_provider", "openai_compatible", OpenAICompatAdapter,
                          source="builtin",
                          description="Any OpenAI-compatible /chat/completions endpoint")
    if not registry.has("report_format", "pdf"):
        registry.register("report_format", "pdf", pdf_mod.render_pdf, source="builtin",
                          description="Dependency-free multi-page PDF from markdown")
    for engine in ("chromium", "firefox", "webkit"):
        if not registry.has("browser_engine", engine):
            registry.register("browser_engine", engine, lambda e=engine: e, source="builtin",
                              description=f"Playwright {engine} adapter")
    from ..engine import analytics

    for name in ("evidence_quality", "feature_completeness", "page_coverage",
                 "confidence_distribution", "duplicate_detection",
                 "contradiction_detection", "missing_information",
                 "dependency_analysis", "gap_and_opportunity",
                 "research_completeness"):
        fn = getattr(analytics, name, None)
        if callable(fn) and not registry.has("analysis_module", name):
            registry.register("analysis_module", name, fn, source="builtin")


def discover(force: bool = False) -> list[str]:
    """Register built-ins and scan entry points. Returns the names handled.
    Idempotent; safe to call from any layer."""
    global _discovered
    if _discovered and not force:
        return [p.name for kind in KINDS for p in registry.list(kind)]
    handled: list[str] = []
    _register_builtins()
    for kind in KINDS:
        handled += [f"{kind}/{p.name}" for p in registry.list(kind)]
    try:
        from importlib.metadata import entry_points

        try:
            eps = entry_points(group="rice.plugins")  # py>=3.12 style
        except TypeError:  # pragma: no cover - older importlib API
            eps = entry_points().get("rice.plugins", [])
        for ep in eps:
            try:
                fn = ep.load()
                fn(registry)
                log.info("loaded external plugin %s from %s", ep.name, ep.value)
                handled.append(f"entry-point:{ep.name}")
            except Exception as e:
                log.warning("external plugin %s failed to load: %s", ep.name, e)
    except Exception as e:  # importlib itself unavailable — built-ins still work
        log.warning("entry-point discovery unavailable: %s", e)
    _discovered = True
    return handled
