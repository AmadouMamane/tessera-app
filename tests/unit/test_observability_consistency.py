"""Unit tests for self-consistency uncertainty (ADR 0010, #18)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tessera.llm.router import ChatResponse
from tessera.observability import consistency

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tessera.llm.router import ChatMessage


class _RepeatBackend:
    name = "stub"
    model = "stub-model"

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            content="an answer",
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            yield "an answer"

        return _gen()


async def _identical_embed(texts: Sequence[str]) -> list[list[float]]:
    return [[1.0, 0.0, 0.0] for _ in texts]


async def _orthogonal_embed(texts: Sequence[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i, _ in enumerate(texts):
        vec = [0.0, 0.0, 0.0]
        vec[i % 3] = 1.0
        out.append(vec)
    return out


def test_identical_answers_zero_uncertainty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consistency, "embed", _identical_embed)
    report = asyncio.run(
        consistency.measure_consistency(
            question="q", context="c", model="m", samples=3, backend=_RepeatBackend()
        )
    )
    assert report.samples == 3
    assert report.consistency == pytest.approx(1.0)
    assert report.uncertainty == pytest.approx(0.0)


def test_divergent_answers_high_uncertainty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consistency, "embed", _orthogonal_embed)
    report = asyncio.run(
        consistency.measure_consistency(
            question="q", context="c", model="m", samples=3, backend=_RepeatBackend()
        )
    )
    assert report.consistency == pytest.approx(0.0)
    assert report.uncertainty == pytest.approx(1.0)
