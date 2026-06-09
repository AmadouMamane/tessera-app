"""Unit tests for multi-judge ensemble agreement (ADR 0010, #95)."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from tessera.observability.eval.ensemble import evaluate_ensemble
from tessera.observability.eval.judge import JudgeVerdict


class _FixedJudge:
    """A judge that returns a preset score, keyed by model id."""

    _SCORES: ClassVar[dict[str, float]] = {"judge-a": 0.9, "judge-b": 0.2, "judge-c": 0.85}

    def __init__(self, model: str) -> None:
        self._model = model

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(
            metric=metric,
            score=self._SCORES[self._model],
            rationale=f"{self._model} says so",
            judge_model=self._model,
        )


def _run(models: tuple[str, ...]):
    return asyncio.run(
        evaluate_ensemble(
            question="q",
            answer="a",
            context="c",
            models=models,
            judge_factory=_FixedJudge,
        )
    )


def test_agreeing_judges_no_disagreement() -> None:
    report = _run(("judge-a", "judge-c"))
    assert report.max_spread <= 0.3
    assert report.disagreement is False
    assert report.mean_score == (0.9 + 0.85) / 2


def test_disagreeing_judges_flagged_as_hard_case() -> None:
    report = _run(("judge-a", "judge-b"))
    assert report.max_spread == 0.7
    assert report.disagreement is True
    assert report.agreement < 0.5
    assert len(report.scores) == 2
