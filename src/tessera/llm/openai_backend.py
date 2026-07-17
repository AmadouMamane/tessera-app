"""Frontier chat backend backed by OpenAI (GPT-5.5).

Selected per request by the model registry (``OpenAISettings.models``) when the
UI picker chooses an OpenAI model; the on-prem/frontier profile backends are
unaffected. The API key is read by the SDK from ``OPENAI_API_KEY``.

Note: GPT-5 reasoning models reject a non-default ``temperature`` and require
``max_completion_tokens`` (not ``max_tokens``); we therefore omit temperature
and use ``max_completion_tokens``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import openai

from tessera.llm.budget import get_budget_tracker
from tessera.llm.router import ChatResponse
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tessera.llm.router import ChatMessage

_FINISH = {
    "stop": "stop",
    "length": "length",
    "content_filter": "content_filter",
    "tool_calls": "tool_call",
}


class OpenAIBackend:
    """OpenAI chat backend (frontier path), implementing the ChatBackend protocol."""

    name = "openai"

    def __init__(self) -> None:
        settings = get_settings().openai
        self.model = settings.chat_model
        self._timeout = settings.timeout_seconds
        # api_key is read from OPENAI_API_KEY by the SDK; base_url defaults to OpenAI.
        self._client = openai.AsyncOpenAI(
            base_url=settings.base_url, timeout=settings.timeout_seconds
        )

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,  # noqa: ARG002 — OpenAI reasoning models reject non-default
        top_p: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        frequency_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        presence_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        """Yield tokens from OpenAI as they arrive."""
        effective_model = model or self.model
        stream = await self._client.chat.completions.create(
            model=effective_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_completion_tokens=max_output_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        input_tokens = 0
        output_tokens = 0
        async for chunk in stream:
            if chunk.choices:
                token = chunk.choices[0].delta.content
                if token:
                    yield token
            if chunk.usage is not None:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens
        if usage is not None:
            usage["input_tokens"] = input_tokens
            usage["output_tokens"] = output_tokens
        get_budget_tracker().record(
            backend=self.name,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,  # noqa: ARG002 — OpenAI reasoning models reject non-default
        top_p: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        frequency_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        presence_penalty: float | None = None,  # noqa: ARG002 — not applied (SAMPLING_APPLIED)
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        """Stream-less chat completion."""
        effective_model = model or self.model
        response = await self._client.chat.completions.create(
            model=effective_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_completion_tokens=max_output_tokens,
        )
        choice = response.choices[0]
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        # Record on the non-streaming path too — the agent graph (and the eval
        # harness) use chat(), not stream_chat(); without this their gpt-5.5
        # usage never reaches the budget tracker (local/frontier already do this).
        get_budget_tracker().record(
            backend=self.name,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ChatResponse(
            content=choice.message.content or "",
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=_FINISH.get(choice.finish_reason, "stop"),
        )
