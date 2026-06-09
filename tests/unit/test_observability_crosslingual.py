"""Unit tests for cross-lingual answer consistency (ADR 0010, #70)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.llm.router import ChatResponse
from tessera.observability import crosslingual

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tessera.llm.router import ChatMessage


class _LangBackend:
    """Returns a language-tagged answer so each call differs by language."""

    name = "stub"
    model = "stub-model"

    def __init__(self) -> None:
        self._i = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        self._i += 1
        return ChatResponse(
            content=f"answer {self._i}", model=self.model, input_tokens=1, output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(self, messages, **kwargs) -> AsyncIterator[str]:  # pragma: no cover
        raise NotImplementedError


async def _aligned_embed(texts: Sequence[str]) -> list[list[float]]:
    return [[1.0, 0.0] for _ in texts]


async def _divergent_embed(texts: Sequence[str]) -> list[list[float]]:
    return [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]


def test_consistent_when_answers_align() -> None:
    report = asyncio.run(
        crosslingual.measure_crosslingual(
            question="q", context="c", model="m", backend=_LangBackend(), embedder=_aligned_embed
        )
    )
    assert report.consistent is True
    assert set(report.answers) == {"fr", "de", "en"}


def test_divergence_flagged() -> None:
    report = asyncio.run(
        crosslingual.measure_crosslingual(
            question="q", context="c", model="m", backend=_LangBackend(), embedder=_divergent_embed
        )
    )
    assert report.consistent is False
    assert report.min_similarity < 0.6
