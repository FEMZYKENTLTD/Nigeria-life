"""OpenAI-compatible chat-completions adapter (any base URL: OpenAI, Groq,
Together, local llama.cpp server, Ollama's /v1, etc.). Tool calling is passed
through when the endpoint supports it.
"""
from __future__ import annotations

import json

import httpx

from .base import ChatMessage, ModelAdapter, ToolCall, ToolSpec


class OpenAICompatAdapter(ModelAdapter):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0,
                 name: str = "openai_compatible") -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.timeout = timeout
        self.name = name
        self.supports_tools = True

    async def available(self) -> bool:
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(self.base_url + "/models",
                                     headers=self._headers())
                return r.status_code < 500
        except Exception:
            return False

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def complete(self, prompt: str, system: str = "", json_mode: bool = False,
                       max_tokens: int = 2000) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.base_url + "/chat/completions",
                                  headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"] or ""

    async def chat(self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
                   max_tokens: int = 2000) -> ChatMessage:
        payload: dict = {"model": self.model, "max_tokens": max_tokens}
        payload["messages"] = [{"role": m.role, "content": m.content} for m in messages]
        if tools and self.supports_tools:
            payload["tools"] = [
                {"type": "function", "function": {
                    "name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.base_url + "/chat/completions",
                                  headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data["choices"][0]["message"]
        calls = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(name=tc["function"]["name"], arguments=args))
        return ChatMessage(role="assistant", content=msg.get("content") or "", tool_calls=calls)
