"""Unit tests for robustness under noise (ADR 0010, #46)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tessera.llm.router import ChatResponse
from tessera.observability import robustness
from tessera.observability.eval.judge import JudgeVerdict

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tessera.llm.router import ChatMessage


class _FixedBackend:
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
            content="a stable grounded answer",
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
            yield "a stable grounded answer"

        return _gen()


class _FixedJudge:
    async def score(
        self, *, metric: str, question: str, answer: str, context: str
    ) -> JudgeVerdict:
        return JudgeVerdict(metric=metric, score=0.8, rationale="", judge_model="stub")


def test_perturbations_change_the_text() -> None:
    perts = robustness.perturbations()
    assert perts["uppercase"]("quel est le solde") == "QUEL EST LE SOLDE"
    assert perts["homoglyph"]("banco") != "banco"
    assert len(perts["homoglyph"]("banco")) == len("banco")
    assert perts["typos"]("question") != "question"


def test_measure_robustness_stable_answer() -> None:
    report = asyncio.run(
        robustness.measure_robustness(
            question="quel est le plafond",
            context="le plafond est 100000",
            model="m",
            backend=_FixedBackend(),
            judge=_FixedJudge(),
        )
    )
    assert report.baseline_faithfulness == pytest.approx(0.8)
    assert report.mean_similarity == pytest.approx(1.0)  # identical answers
    assert report.min_faithfulness == pytest.approx(0.8)
    assert len(report.results) == 3
