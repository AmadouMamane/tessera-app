"""Vertex AI (Gemini family) chat backend."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from tessera.llm.budget import get_budget_tracker
from tessera.llm.determinism import deterministic_sampling, effective_temperature
from tessera.llm.router import ChatMessage, ChatResponse
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
        self._model_instances: dict[str, GenerativeModel] = {}

    def _ensure_model(self, model: str | None = None) -> GenerativeModel:
        """Return the client for ``model``, memoised BY MODEL ID.

        It used to memoise a single instance built from ``settings.vertex.chat_model`` and
        ignore the per-call ``model=`` entirely — with a ``noqa: ARG002`` saying "fixed at init
        on the frontier path". ADR 0030 states the opposite in its own words: *"An override
        that the runtime ignores cannot be written under this design, because the store's only
        consumer is the serving path."* On a frontier deployment it could: a governed override
        was stored, validated, journalled, shown as active in the catalogue, stamped on the
        span and threaded into the eval lineage, while Vertex kept serving the base model —
        and the cost was ESTIMATED at the requested model's price and RECORDED at the served
        one. Two costs for one turn, and a lineage that named a model that never ran.
        Audit 2026-08-03.
        """
        wanted = model or self.model
        cached = self._model_instances.get(wanted)
        if cached is not None:
            return cached
        if self._project is None:
            raise RuntimeError(
                "Vertex AI project id is not configured; set TESSERA_VERTEX__PROJECT_ID"
            )
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=self._project, location=self._location)
        instance = GenerativeModel(wanted)
        self._model_instances[wanted] = instance
        return instance

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
        top_p: float | None = None,
        top_k: float | None = None,
        frequency_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        presence_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        """Yield tokens from Vertex AI as they arrive."""
        gemini = self._ensure_model(model)
        served_model = model or self.model
        max_tokens = max_output_tokens or self._max_output_tokens
        # `timeout_seconds` was read into self._timeout at init and then never used: the
        # deadline the settings advertised did not exist, and a frozen Vertex call held the
        # SSE stream open indefinitely (audit `robustness-timeout`). The Ollama backend has
        # always passed its timeout to the client; this brings the frontier path level.
        async with asyncio.timeout(self._timeout):
            stream = await gemini.generate_content_async(
                self._convert(messages),
                generation_config=_generation_config(temperature, top_p, top_k, max_tokens),
                stream=True,
            )
        input_tokens = 0
        output_tokens = 0
        chunks = stream.__aiter__()
        while True:
            # Bound the GAP BETWEEN CHUNKS, not the total answer: a long legitimate
            # response streams freely, while a backend that stalls mid-stream raises
            # instead of holding the turn — and the SSE connection — open forever.
            try:
                async with asyncio.timeout(self._timeout):
                    chunk = await chunks.__anext__()
            except StopAsyncIteration:
                break
            text = chunk.text if (chunk.candidates and chunk.text) else ""
            if text:
                yield text
            meta = getattr(chunk, "usage_metadata", None)
            if meta is not None:
                input_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
                output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
        if usage is not None:
            usage["input_tokens"] = input_tokens
            usage["output_tokens"] = output_tokens
        get_budget_tracker().record(
            backend=self.name,
            # The model that SERVED, so the bill and the lineage name the same thing.
            model=served_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        top_p: float | None = None,
        top_k: float | None = None,
        frequency_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        presence_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        """Stream-less chat completion."""
        gemini = self._ensure_model(model)
        served_model = model or self.model
        max_tokens = max_output_tokens or self._max_output_tokens
        async with asyncio.timeout(self._timeout):
            response = await gemini.generate_content_async(
                self._convert(messages),
                generation_config=_generation_config(temperature, top_p, top_k, max_tokens),
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
            # The model that SERVED, so the bill and the lineage name the same thing.
            model=served_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ChatResponse(
            content=text,
            model=served_model,
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


def _generation_config(
    temperature: float, top_p: float | None, top_k: float | None, max_tokens: int
) -> dict[str, float | int]:
    """Vertex applies temperature, top-p and top-k (ADR 0031/0032, SAMPLING_APPLIED).

    An unset (``None``) top-p / top-k is NOT sent — the model's own default
    serves. ``top_k`` is integer-valued for the API.

    Under ``TESSERA_EVAL_DETERMINISTIC=1`` the temperature is forced to 0 and ``top_k`` to 1,
    which is greedy decoding — the strongest reproducibility this API offers. No seed is sent:
    the parameter is not part of the generation config this SDK builds, and sending one it
    would reject to *look* deterministic would be worse than saying so
    (:mod:`tessera.llm.determinism`).
    """
    effective = effective_temperature(temperature)
    config: dict[str, float | int] = {"temperature": effective, "max_output_tokens": max_tokens}
    if top_p is not None:
        config["top_p"] = top_p
    if top_k is not None:
        config["top_k"] = int(top_k)
    if deterministic_sampling():
        config["top_k"] = 1
    return config
