"""Provider-independent model adapter interface.

The rest of the platform only talks to :class:`ModelAdapter`. Concrete
providers (OpenAI-compatible cloud endpoints, local servers, or the offline
heuristic adapter) implement it. Selection is by configuration and task
complexity; when no provider is available the platform degrades to the
offline adapter and says so in its output — it never fabricates "AI" results.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ChatMessage:
    role: str  # system|user|assistant|tool
    content: str
    name: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelAdapter(abc.ABC):
    name: str = "base"
    supports_tools: bool = False

    @abc.abstractmethod
    async def complete(self, prompt: str, system: str = "", json_mode: bool = False,
                       max_tokens: int = 2000) -> str:
        """Single-turn completion. Providers that cannot do json_mode should
        still try to honour the prompt's JSON instruction."""

    async def chat(self, messages: list[ChatMessage], tools: list[ToolSpec] | None = None,
                   max_tokens: int = 2000) -> ChatMessage:
        """Multi-turn chat. The default implementation folds history into a
        single completion (sufficient for planning/synthesis use cases)."""
        parts = []
        for m in messages:
            if m.role in ("system", "user", "assistant"):
                parts.append(f"[{m.role.upper()}]\n{m.content}")
            elif m.role == "tool":
                parts.append(f"[TOOL RESULT {m.name}]\n{m.content}")
        return ChatMessage(role="assistant", content=await self.complete("\n\n".join(parts)))

    async def available(self) -> bool:
        return True
