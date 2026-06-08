"""Unit tests for judge calibration (ADR 0010, Phase 5, #2)."""

from __future__ import annotations

import asyncio

import pytest

from tessera.observability.eval import calibration as cal
from tessera.observability.eval.judge import JudgeVerdict


class _KeywordJudge:
    """Scores high when the answer contains 'good', low otherwise."""

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        score = 0.9 if "good" in answer else 0.1
        return JudgeVerdict(metric=metric, score=score, rationale="", judge_model="stub")


class _LenientJudge:
    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(metric=metric, score=0.9, rationale="", judge_model="stub")


# ── pure statistics ────────────────────────────────────────────────────────────


def test_cohen_kappa_perfect_agreement() -> None:
    assert cal.cohen_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)


def test_cohen_kappa_chance_agreement_is_zero() -> None:
    assert cal.cohen_kappa([("a", "a"), ("a", "b"), ("b", "b"), ("b", "a")]) == pytest.approx(0.0)


def test_cohen_kappa_empty() -> None:
    assert cal.cohen_kappa([]) == 0.0


def test_agreement_rate() -> None:
    assert cal.agreement_rate([("a", "a"), ("a", "b")]) == pytest.approx(0.5)


def test_pearson_perfect_positive() -> None:
    assert cal.pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)


def test_pearson_zero_variance_is_zero() -> None:
    assert cal.pearson([1.0, 1.0, 1.0], [2.0, 4.0, 6.0]) == 0.0


# ── calibrate() over a gold set ─────────────────────────────────────────────────

_GOLD = [
    cal.GoldCase(question="q1", answer="good answer", context="c", human_label="good"),
    cal.GoldCase(question="q2", answer="good reply", context="c", human_label="good"),
    cal.GoldCase(question="q3", answer="bad answer", context="c", human_label="bad"),
    cal.GoldCase(question="q4", answer="bad reply", context="c", human_label="bad"),
]


def test_calibrate_well_calibrated_judge() -> None:
    report = asyncio.run(cal.calibrate(_KeywordJudge(), _GOLD))
    assert report.n == 4
    assert report.kappa == pytest.approx(1.0)
    assert report.agreement == pytest.approx(1.0)
    assert report.mean_score_good == pytest.approx(0.9)
    assert report.mean_score_bad == pytest.approx(0.1)
    assert report.lenient is False


def test_calibrate_flags_lenient_judge() -> None:
    report = asyncio.run(cal.calibrate(_LenientJudge(), _GOLD))
    # A judge that always passes scores the human-"bad" cases above threshold.
    assert report.lenient is True
    assert report.mean_score_bad == pytest.approx(0.9)


def test_bundled_gold_set_loads() -> None:
    gold = cal.load_gold_set()
    assert len(gold) >= 4
    assert all(c.human_label in {"good", "bad"} for c in gold)
