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


def test_calibrate_emits_per_sample_points() -> None:
    report = asyncio.run(cal.calibrate(_KeywordJudge(), _GOLD))
    assert len(report.points) == 4
    first = report.points[0]
    assert first.human_label == "good"
    assert first.judge_label == "good"
    assert first.judge_score == pytest.approx(0.9)
    assert first.length == len("good answer")
    assert all(p.match for p in report.points)


def test_calibrate_points_record_disagreement() -> None:
    report = asyncio.run(cal.calibrate(_LenientJudge(), _GOLD))
    # The lenient judge calls the two human-"bad" cases "good" → 2 disagreements.
    disagreements = [p for p in report.points if not p.match]
    assert len(disagreements) == 2
    assert all(p.human_label == "bad" and p.judge_label == "good" for p in disagreements)


def test_bundled_gold_set_loads() -> None:
    gold = cal.load_gold_set()
    assert len(gold) >= 4
    assert all(c.human_label in {"good", "bad"} for c in gold)


# ── multi-judge consensus ───────────────────────────────────────────────────────


class _ContrarianJudge:
    """Inverts the keyword judge: low when the answer contains 'good'."""

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        score = 0.1 if "good" in answer else 0.9
        return JudgeVerdict(metric=metric, score=score, rationale="", judge_model="stub")


def test_fleiss_kappa_perfect_agreement() -> None:
    # Every item unanimous (3 raters): two all-good, two all-bad.
    assert cal.fleiss_kappa_binary([(3, 0), (3, 0), (0, 3), (0, 3)]) == pytest.approx(1.0)


def test_fleiss_kappa_empty_or_single_rater_is_zero() -> None:
    assert cal.fleiss_kappa_binary([]) == 0.0
    assert cal.fleiss_kappa_binary([(1, 0), (1, 0)]) == 0.0


def test_gold_consensus_unanimous_panel() -> None:
    judges = [_KeywordJudge(), _KeywordJudge(), _KeywordJudge()]
    report = asyncio.run(cal.gold_consensus(judges, _GOLD, labels=["a", "b", "c"]))
    assert report.n_judges == 3
    assert report.n_cases == 4
    assert report.consensus_rate == pytest.approx(1.0)
    assert report.mean_pairwise_agreement == pytest.approx(1.0)
    assert report.fleiss_kappa == pytest.approx(1.0)
    assert [j.agreement for j in report.per_judge] == pytest.approx([1.0, 1.0, 1.0])
    assert report.judge_models == ["a", "b", "c"]


def test_gold_consensus_split_panel_lowers_agreement() -> None:
    # Two judges agree, one inverts every call → never unanimous.
    judges = [_KeywordJudge(), _KeywordJudge(), _ContrarianJudge()]
    report = asyncio.run(cal.gold_consensus(judges, _GOLD, labels=["a", "b", "c"]))
    assert report.consensus_rate == pytest.approx(0.0)
    # Pairwise: a↔b agree (1.0), a↔c and b↔c disagree (0.0) → mean 1/3.
    assert report.mean_pairwise_agreement == pytest.approx(1.0 / 3.0)
    # The contrarian disagrees with the 2-vs-1 majority on every case.
    by_model = {j.judge_model: j.agreement for j in report.per_judge}
    assert by_model["a"] == pytest.approx(1.0)
    assert by_model["c"] == pytest.approx(0.0)
