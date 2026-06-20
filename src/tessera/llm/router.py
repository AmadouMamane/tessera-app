"""Chat-backend selection and the common protocol.

The router is a thin selector — it does *not* implement chat itself. The
implementations live in :mod:`tessera.llm.frontier` (Vertex AI) and
:mod:`tessera.llm.local` (Ollama). The selector caches the chosen backend
for the lifetime of the process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

__all__ = [
    "ChatBackend",
    "ChatMessage",
    "ChatResponse",
    "backend_for_model",
    "get_chat_backend",
    "get_summary_backend",
]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single message in a chat exchange."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """A model response, with usage metadata for budgeting."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: Literal["stop", "length", "tool_call", "content_filter", "error"]


@runtime_checkable
class ChatBackend(Protocol):
    """The narrow interface both Vertex AI and Ollama backends implement."""

    name: str
    model: str

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        """Produce a single response for the given message sequence.

        ``model`` optionally overrides the backend's default model for this
        call (used by the UI model picker); ``None`` keeps the configured one.
        """
        ...

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        """Yield tokens as they are generated (streaming path).

        When ``usage`` is provided, the backend writes the real per-call
        ``input_tokens`` / ``output_tokens`` into it once the stream completes,
        so the caller can attribute usage to this exact turn without racing the
        process-wide budget tracker.
        """
        ...


@lru_cache(maxsize=1)
def get_chat_backend() -> ChatBackend:
    """Return the backend matching the resolved LLM profile.

    Imports are deferred so that on-prem hosts do not need Vertex AI
    credentials and frontier hosts do not need Ollama installed.
    """
    profile = get_settings().resolved_llm_profile()
    if profile is LLMProfile.FRONTIER:
        from tessera.llm.frontier import VertexAIBackend

        return VertexAIBackend()
    from tessera.llm.local import OllamaBackend

    return OllamaBackend()


@lru_cache(maxsize=1)
def _openai_backend() -> ChatBackend:
    from tessera.llm.openai_backend import OpenAIBackend

    return OpenAIBackend()


def backend_for_model(model: str | None) -> ChatBackend:
    """Resolve the backend for a per-request chat model (the UI picker).

    Explicit registry, not name-guessing: a model listed in
    ``OpenAISettings.models`` routes to the OpenAI backend; everything else —
    including no override — keeps the profile backend (Ollama on-prem / Vertex
    frontier). This lets a single running instance serve both local and OpenAI
    models without changing the deploy-level profile.
    """
    if model and model in get_settings().openai.models:
        return _openai_backend()
    return get_chat_backend()


def get_summary_backend() -> ChatBackend:
    """Return the backend used for cheap, background summarisation (ADR 0007).

    Summarisation runs off the hot path and does not need the frontier-grade
    model. This is the single seam where a smaller, cheaper model (e.g. a local
    Llama 3.2 3B, or Gemini Flash) is wired in; until that is configured it
    reuses the primary chat backend so the feature is fully functional.
    """
    return get_chat_backend()
