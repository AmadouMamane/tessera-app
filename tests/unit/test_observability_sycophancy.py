"""Unit tests for sycophancy detection (ADR 0010, #59)."""

from __future__ import annotations

import asyncio

from tessera.observability.eval.judge import JudgeVerdict
from tessera.observability.eval.sycophancy import detect_sycophancy


class _FixedJudge:
    def __init__(self, score: float) -> None:
        self._score = score

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(
            metric=metric, score=self._score, rationale="r", judge_model="stub-judge"
        )


def test_sycophantic_answer_flagged() -> None:
    report = asyncio.run(
        detect_sycophancy(question="q", answer="a", context="c", judge=_FixedJudge(0.9))
    )
    assert report.sycophantic is True
    assert report.score == 0.9


def test_corrective_answer_not_flagged() -> None:
    report = asyncio.run(
        detect_sycophancy(question="q", answer="a", context="c", judge=_FixedJudge(0.1))
    )
    assert report.sycophantic is False
    assert report.judge_model == "stub-judge"
