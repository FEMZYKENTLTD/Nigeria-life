"""Adapter selection: by configuration and task complexity.

* routine  → small model (or offline)
* complex  → large model (or offline)

When the configured provider is unreachable the registry transparently
returns the offline adapter and the caller records the degradation in logs
and outputs (honest failure, no fake AI).
"""
from __future__ import annotations

import logging

from ..config import get_settings
from .base import ModelAdapter
from .offline import OfflineAdapter
from .openai_compat import OpenAICompatAdapter

log = logging.getLogger("rice.ai")

_offline = OfflineAdapter()
_cache: dict[str, ModelAdapter] = {}


def _build(spec: str) -> ModelAdapter:
    s = get_settings()
    if spec == "off" or not s.ai_base_url:
        return _offline
    if spec == "ollama":
        base = s.ai_base_url or "http://127.0.0.1:11434/v1"
        key = s.ai_api_key or "ollama"
    else:
        base = s.ai_base_url
        key = s.ai_api_key
    model = s.ai_model_small
    adapter = OpenAICompatAdapter(base_url=base, api_key=key, model=model,
                                  timeout=s.ai_request_timeout, name=f"{spec}:{model}")
    cache_key = f"{spec}|{base}|{model}"
    _cache[cache_key] = adapter
    return adapter


def get_adapter(complexity: str = "routine", prefer: str | None = None) -> ModelAdapter:
    """Return the best available adapter for the requested complexity."""
    s = get_settings()
    spec = prefer or s.ai_provider
    if spec == "off":
        return _offline
    model = s.ai_model_large if complexity == "complex" else s.ai_model_small
    cache_key = f"{spec}|{s.ai_base_url}|{model}"
    if cache_key in _cache:
        return _cache[cache_key]
    adapter = OpenAICompatAdapter(
        base_url=s.ai_base_url, api_key=s.ai_api_key, model=model,
        timeout=s.ai_request_timeout, name=f"{spec}:{model}",
    )
    _cache[cache_key] = adapter
    return adapter


async def resolve_adapter(complexity: str = "routine", prefer: str | None = None) -> tuple[ModelAdapter, bool]:
    """Returns (adapter, degraded). degraded=True means we fell back to the
    offline adapter because the configured provider was unavailable."""
    adapter = get_adapter(complexity, prefer)
    if adapter.name == "offline-heuristic":
        return adapter, False
    if await adapter.available():
        return adapter, False
    log.warning("AI provider %s unavailable; degrading to offline heuristic adapter", adapter.name)
    return _offline, True
