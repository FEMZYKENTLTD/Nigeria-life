"""Offline heuristic adapter.

Guarantees the platform keeps functioning with zero external AI: planning,
summarisation and enrichment fall back to deterministic logic. Every output
is explicitly labelled so users know it is not a model's answer.
"""
from __future__ import annotations

import json
import re

from .base import ModelAdapter, ChatMessage


class OfflineAdapter(ModelAdapter):
    name = "offline-heuristic"
    supports_tools = False

    async def complete(self, prompt: str, system: str = "", json_mode: bool = False,
                       max_tokens: int = 2000) -> str:
        p = (prompt or "").lower()
        if json_mode or "strict json" in p or '"subtasks"' in p:
            return json.dumps({
                "planner": "offline-heuristic",
                "note": "No AI provider configured; returning the standard deterministic plan. Configure RICE_AI_PROVIDER for LLM planning.",
                "subtasks": [
                    {"type": "discover", "description": "Compile page queue from authorised sources.", "priority": 1},
                    {"type": "understand", "description": "Analyse captured pages into structured records.", "priority": 2},
                    {"type": "document", "description": "Extract and upsert feature documentation.", "priority": 2},
                    {"type": "analyse", "description": "Run deterministic analytics.", "priority": 2},
                    {"type": "report", "description": "Generate reports.", "priority": 3},
                ],
            })
        if "summaris" in p or "summar" in p:
            m = re.search(r"(?:summarise|summarize)[^\n]*\n(.*)$", prompt or "", re.S)
            text = (m.group(1) if m else prompt or "")[:1200]
            sentences = re.split(r"(?<=[.!?])\s+", text.strip())[:4]
            return "[offline-heuristic] " + " ".join(sentences).strip()[:600]
        return ("[offline-heuristic] No AI provider is configured (RICE_AI_PROVIDER=off). "
                "This response is produced by deterministic platform logic, not a language model. "
                "Configure a provider for model-generated analysis.")
