"""Provider-independent model adapter.

`HeuristicProvider` needs no network and keeps the engine working when no model is configured.
`OpenAICompatibleProvider` talks to any /v1/chat/completions endpoint (cloud APIs, or local servers such as Ollama,
LM Studio, llama.cpp, vLLM). Anything a model says is stored as an *interpretation*, never as a confirmed fact.
"""
from __future__ import annotations
import json
import re
from typing import Any, Callable

import httpx

from .config import get_settings


class AIUnavailable(Exception):
    pass


class Provider:
    name = "base"
    available = False

    def complete(self, prompt: str, *, system: str = "", complexity: str = "simple") -> str:
        raise NotImplementedError

    def complete_json(self, prompt: str, *, system: str = "", complexity: str = "simple") -> Any:
        raise NotImplementedError

    def run_tools(self, prompt: str, tools: dict[str, Callable[..., Any]], tool_specs: list[dict], *, system: str = "", max_steps: int = 6) -> str:
        raise NotImplementedError


class HeuristicProvider(Provider):
    """Extractive, rule-based stand-in. It summarises by picking sentences; it does not reason."""
    name = "heuristic"
    available = True

    def complete(self, prompt: str, *, system: str = "", complexity: str = "simple") -> str:
        sents = re.split(r"(?<=[.!?])\s+", prompt.strip())
        return " ".join(sents[:3])[:600]

    def complete_json(self, prompt, *, system="", complexity="simple"):
        raise AIUnavailable("No language model configured; structured generation is unavailable.")

    def run_tools(self, *a, **k):
        raise AIUnavailable("No language model configured; tool calling is unavailable.")


class OpenAICompatibleProvider(Provider):
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str = "", models: dict[str, str] | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._key = api_key
        self.models = models or {}
        self._transport = transport
        self.available = bool(base_url and self.models.get("simple"))

    def model_for(self, complexity: str) -> str:
        """Route by task complexity: 'simple' | 'complex' | 'vision'. Falls back to the simple model."""
        return self.models.get(complexity) or self.models.get("simple", "")

    def _chat(self, messages: list[dict], complexity: str, **extra) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        try:
            with httpx.Client(timeout=120, transport=self._transport) as c:
                r = c.post(f"{self.base_url}/chat/completions", headers=headers,
                           json={"model": self.model_for(complexity), "messages": messages, **extra})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise AIUnavailable(f"Model request failed: {type(e).__name__}") from e  # never include headers or body

    def complete(self, prompt, *, system="", complexity="simple"):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self._chat(msgs, complexity).get("content") or ""

    def complete_json(self, prompt, *, system="", complexity="simple"):
        sys = (system + "\n" if system else "") + "Reply with a single valid JSON value and nothing else."
        msgs = [{"role": "system", "content": sys}, {"role": "user", "content": prompt}]
        text = self._chat(msgs, complexity, response_format={"type": "json_object"}).get("content") or ""
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        try:
            return json.loads(m.group(1) if m else text)
        except (ValueError, AttributeError) as e:
            raise AIUnavailable("Model did not return valid JSON.") from e

    def run_tools(self, prompt, tools, tool_specs, *, system="", max_steps=6):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        for _ in range(max_steps):
            msg = self._chat(msgs, "complex", tools=tool_specs)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content") or ""
            msgs.append(msg)
            for call in calls:
                fn = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    result = tools[fn](**args) if fn in tools else {"error": f"unknown tool {fn}"}
                except Exception as e:  # a tool failure is reported back to the model, not hidden
                    result = {"error": f"{type(e).__name__}: {e}"}
                msgs.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": json.dumps(result, default=str)[:8000]})
        return "Stopped: tool step limit reached."


def get_provider() -> Provider:
    st = get_settings()
    if st.ai_base_url and st.ai_model_simple:
        return OpenAICompatibleProvider(st.ai_base_url, st.ai_api_key,
                                        {"simple": st.ai_model_simple, "complex": st.ai_model_complex, "vision": st.ai_model_vision})
    return HeuristicProvider()


def status() -> dict:
    p = get_provider()
    st = get_settings()
    return {"provider": p.name, "model_configured": p.name != "heuristic",
            "models": {"simple": st.ai_model_simple, "complex": st.ai_model_complex, "vision": st.ai_model_vision},
            "note": "Rule-based mode: planning, page analysis, analytics and reports work without a model. "
                    "Summaries are extractive." if p.name == "heuristic" else "Model outputs are stored as interpretations, not confirmed facts."}
