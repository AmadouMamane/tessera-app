"""Judge calibration — agreement with humans and bias signals (ADR 0010, #2).

A LLM-as-judge is only trustworthy if it is *calibrated*. This module measures
how well the judge agrees with a small human-labelled gold set:

* **Cohen's κ** — agreement beyond chance between the judge's pass/fail call and
  the human label.
* **Raw agreement** — the plain fraction of matching calls.
* **Separation** — mean judge score on human-"good" vs human-"bad" cases (a good
  judge scores the goods high and the bads low).
* **Leniency** — does the judge pass answers humans rejected?
* **Verbosity bias** — Pearson correlation between answer length and score (a
  classic LLM-judge failure mode: rewarding longer answers).

The statistics are pure functions (unit-tested without any model); ``calibrate``
runs a :class:`~tessera.observability.eval.judge.Judge` over the gold set and
assembles a :class:`CalibrationReport`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.observability.eval.judge import FAITHFULNESS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.eval.judge import Judge

__all__ = [
    "CalibrationPoint",
    "CalibrationReport",
    "GoldCase",
    "agreement_rate",
    "calibrate",
    "cohen_kappa",
    "load_gold_set",
    "pearson",
]

# src/tessera/observability/eval/calibration.py → parents[4] is the repo root.
_DEFAULT_GOLD = Path(__file__).resolve().parents[4] / "eval" / "calibration" / "judge_gold.json"

_PASS_THRESHOLD = 0.5
_MIN_PEARSON_POINTS = 2


@dataclass(frozen=True, slots=True)
class GoldCase:
    """One human-labelled calibration case."""

    question: str
    answer: str
    context: str
    human_label: str  # "good" | "bad"


@dataclass(frozen=True, slots=True)
class CalibrationPoint:
    """One gold case: the judge's score against the human label.

    The per-sample detail behind the calibration scatter and disagreement table
    (Qualité IA "Calibration juge" tab, reference image 05).
    """

    question: str  # truncated for display
    human_label: str  # "good" | "bad"
    judge_label: str  # "good" | "bad" (judge score thresholded)
    judge_score: float
    length: int  # answer length (for the verbosity-bias scatter)
    match: bool  # judge and human agree


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """The judge's calibration against the gold set."""

    n: int
    kappa: float
    agreement: float
    mean_score_good: float
    mean_score_bad: float
    verbosity_corr: float
    lenient: bool
    judge_model: str
    points: list[CalibrationPoint] = field(default_factory=list)


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float:
    """Cohen's κ between two raters over categorical labels."""
    n = len(pairs)
    if n == 0:
        return 0.0
    labels = {label for pair in pairs for label in pair}
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum(
        (sum(1 for a, _ in pairs if a == label) / n) * (sum(1 for _, b in pairs if b == label) / n)
        for label in labels
    )
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def agreement_rate(pairs: Sequence[tuple[str, str]]) -> float:
    """Plain fraction of matching label pairs."""
    if not pairs:
        return 0.0
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation; 0.0 when undefined (n<2 or zero variance)."""
    n = len(xs)
    if n < _MIN_PEARSON_POINTS or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def load_gold_set(path: Path | None = None) -> list[GoldCase]:
    """Load the human-labelled calibration gold set."""
    target = path or _DEFAULT_GOLD
    raw = json.loads(target.read_text(encoding="utf-8"))
    return [
        GoldCase(
            question=item["question"],
            answer=item["answer"],
            context=item["context"],
            human_label=item["human_label"],
        )
        for item in raw
    ]


async def calibrate(judge: Judge, gold: Sequence[GoldCase]) -> CalibrationReport:
    """Run ``judge`` over ``gold`` and assemble the calibration report."""
    pairs: list[tuple[str, str]] = []
    good_scores: list[float] = []
    bad_scores: list[float] = []
    lengths: list[float] = []
    scores: list[float] = []
    points: list[CalibrationPoint] = []
    judge_model = ""

    for case in gold:
        verdict = await judge.score(
            metric=FAITHFULNESS,
            question=case.question,
            answer=case.answer,
            context=case.context,
        )
        judge_model = verdict.judge_model
        judge_label = "good" if verdict.score >= _PASS_THRESHOLD else "bad"
        pairs.append((judge_label, case.human_label))
        lengths.append(float(len(case.answer)))
        scores.append(verdict.score)
        (good_scores if case.human_label == "good" else bad_scores).append(verdict.score)
        points.append(
            CalibrationPoint(
                question=case.question[:90],
                human_label=case.human_label,
                judge_label=judge_label,
                judge_score=verdict.score,
                length=len(case.answer),
                match=judge_label == case.human_label,
            )
        )

    mean_good = sum(good_scores) / len(good_scores) if good_scores else 0.0
    mean_bad = sum(bad_scores) / len(bad_scores) if bad_scores else 0.0
    return CalibrationReport(
        n=len(gold),
        kappa=cohen_kappa(pairs),
        agreement=agreement_rate(pairs),
        mean_score_good=mean_good,
        mean_score_bad=mean_bad,
        verbosity_corr=pearson(lengths, scores),
        lenient=mean_bad >= _PASS_THRESHOLD,
        judge_model=judge_model,
        points=points,
    )
