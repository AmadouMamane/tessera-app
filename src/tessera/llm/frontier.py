"""Vertex AI (Gemini family) chat backend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from tessera.llm.budget import get_budget_tracker
from tessera.llm.router import ChatMessage, ChatResponse
from tessera.observability.instrumentation import start_span
from tessera.observability.schema import TelemetrySpan
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from vertexai.generative_models import GenerativeModel

__all__ = ["VertexAIBackend"]


_ROLE_MAP: dict[str, str] = {
    "system": "user",  # Gemini has no system role; promote to a leading user turn
    "user": "user",
    "assistant": "model",
    "tool": "user",
}


class VertexAIBackend:
    """Frontier chat backend backed by Vertex AI."""

    name = "vertex-ai"

    def __init__(self) -> None:
        settings = get_settings().vertex
        self.model = settings.chat_model
        self._location = settings.location
        self._project = settings.project_id
        self._max_output_tokens = settings.max_output_tokens
        self._timeout = settings.timeout_seconds
        self._model_instance: GenerativeModel | None = None

    def _ensure_model(self) -> GenerativeModel:
        if self._model_instance is not None:
            return self._model_instance
        if self._project is None:
            raise RuntimeError(
                "Vertex AI project id is not configured; set TESSERA_VERTEX__PROJECT_ID"
            )
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self._project, location=self._location)
        self._model_instance = GenerativeModel(self.model)
        return self._model_instance

    @staticmethod
    def _convert(messages: Sequence[ChatMessage]) -> list[dict[str, object]]:
        return [
            {
                "role": _ROLE_MAP[message.role],
                "parts": [{"text": message.content}],
            }
            for message in messages
        ]

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,  # noqa: ARG002  fixed at init on the frontier path
    ) -> AsyncIterator[str]:
        """Yield tokens from Vertex AI as they arrive."""
        gemini = self._ensure_model()
        max_tokens = max_output_tokens or self._max_output_tokens
        with start_span(TelemetrySpan.LLM_CALL, {"backend": self.name, "model": self.model}):
            stream = await gemini.generate_content_async(
                self._convert(messages),
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
                stream=True,
            )
            async for chunk in stream:
                text = chunk.text if (chunk.candidates and chunk.text) else ""
                if text:
                    yield text

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,  # noqa: ARG002  fixed at init on the frontier path
    ) -> ChatResponse:
        """Stream-less chat completion."""
        gemini = self._ensure_model()
        max_tokens = max_output_tokens or self._max_output_tokens
        with start_span(TelemetrySpan.LLM_CALL, {"backend": self.name, "model": self.model}):
            response = await gemini.generate_content_async(
                self._convert(messages),
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
        text = response.text if response.candidates else ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        finish_reason = (
            getattr(response.candidates[0], "finish_reason", "stop")
            if response.candidates
            else "stop"
        )

        get_budget_tracker().record(
            backend=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ChatResponse(
            content=text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=_normalise_finish_reason(finish_reason),
        )


def _normalise_finish_reason(
    raw: object,
) -> Literal["stop", "length", "tool_call", "content_filter", "error"]:
    """Map Vertex's finish reason enum onto the four values we expose."""
    text = str(raw).lower()
    if "max" in text or "length" in text:
        return "length"
    if "safety" in text or "filter" in text or "blocked" in text:
        return "content_filter"
    if "tool" in text:
        return "tool_call"
    if "error" in text:
        return "error"
    return "stop"
