"""On-premises chat backend backed by Ollama (Llama 3.3 70B)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ollama

from tessera.llm.budget import get_budget_tracker
from tessera.llm.router import ChatMessage, ChatResponse
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

__all__ = ["OllamaBackend"]


def _sampling_options(
    temperature: float,
    top_p: float | None,
    top_k: float | None,
    frequency_penalty: float | None,
    presence_penalty: float | None,
) -> dict[str, object]:
    """Ollama applies all five sampling parameters (ADR 0031/0032, SAMPLING_APPLIED).

    Unset (``None``) parameters are NOT sent — the daemon's own default serves.
    ``top_k`` is integer-valued for the daemon.
    """
    options: dict[str, object] = {"temperature": temperature}
    if top_p is not None:
        options["top_p"] = top_p
    if top_k is not None:
        options["top_k"] = int(top_k)
    if frequency_penalty is not None:
        options["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        options["presence_penalty"] = presence_penalty
    return options


class OllamaBackend:
    """On-prem chat backend backed by a locally-served Ollama daemon."""

    name = "ollama"

    def __init__(self) -> None:
        settings = get_settings().ollama
        self.model = settings.chat_model
        self._host = str(settings.host)
        self._timeout = settings.timeout_seconds
        self._keep_alive = f"{settings.keep_alive_seconds}s"
        # Pass the timeout through to the underlying httpx client. Without it a
        # stalled daemon (e.g. a model being unloaded mid-request) hangs forever.
        # For streaming this is the inter-chunk read timeout, so a slow-but-
        # progressing model (e.g. Llama 3.3 70B) is not killed — only true stalls.
        self._client = ollama.AsyncClient(host=self._host, timeout=self._timeout)

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        top_p: float | None = None,
        top_k: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        max_output_tokens: int | None = None,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AsyncIterator[str]:
        """Yield tokens from Ollama as they arrive."""
        effective_model = model or self.model
        options = _sampling_options(temperature, top_p, top_k, frequency_penalty, presence_penalty)
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        payload = [{"role": m.role, "content": m.content} for m in messages]
        input_tokens = 0
        output_tokens = 0
        async for chunk in await self._client.chat(
            model=effective_model,
            messages=payload,
            options=options,
            keep_alive=self._keep_alive,
            stream=True,
        ):
            token: str = chunk["message"]["content"]
            if token:
                yield token
            if chunk.get("done"):
                input_tokens = int(chunk.get("prompt_eval_count", 0) or 0)
                output_tokens = int(chunk.get("eval_count", 0) or 0)
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
        temperature: float = 0.2,
        top_p: float | None = None,
        top_k: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        """Stream-less chat completion."""
        effective_model = model or self.model
        options = _sampling_options(temperature, top_p, top_k, frequency_penalty, presence_penalty)
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens

        payload = [{"role": message.role, "content": message.content} for message in messages]
        response = await self._client.chat(
            model=effective_model,
            messages=payload,
            options=options,
            keep_alive=self._keep_alive,
        )
        content = response["message"]["content"]
        input_tokens = int(response.get("prompt_eval_count", 0) or 0)
        output_tokens = int(response.get("eval_count", 0) or 0)
        done_reason = str(response.get("done_reason", "stop"))

        get_budget_tracker().record(
            backend=self.name,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ChatResponse(
            content=str(content),
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason="length" if done_reason == "length" else "stop",
        )
