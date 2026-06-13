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

from tessera.observability.eval.judge import FAITHFULNESS, GROUNDING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.eval.judge import Judge

__all__ = [
    "CalibrationPoint",
    "CalibrationReport",
    "ConsensusReport",
    "GoldCase",
    "GroupAgreement",
    "JudgeAgreement",
    "agreement_rate",
    "calibrate",
    "cohen_kappa",
    "fleiss_kappa_binary",
    "gold_consensus",
    "load_gold_set",
    "metric_for_category",
    "pearson",
]

# Display category → judge rubric. PII, citation and style cases have no dedicated
# rubric, so they are scored on FAITHFULNESS (does the answer hold up against the
# policy/source context) while keeping their display category for the breakdowns.
_CATEGORY_METRIC: dict[str, str] = {
    "faithfulness": FAITHFULNESS,
    "grounding": GROUNDING,
    "pii": FAITHFULNESS,
    "citations": FAITHFULNESS,
    "style": FAITHFULNESS,
}


def metric_for_category(category: str) -> str:
    """Return the judge rubric used to score a gold case in ``category``."""
    return _CATEGORY_METRIC.get(category, FAITHFULNESS)


# src/tessera/observability/eval/calibration.py → parents[4] is the repo root.
_DEFAULT_GOLD = Path(__file__).resolve().parents[4] / "eval" / "calibration" / "judge_gold.json"

_PASS_THRESHOLD = 0.5
_MIN_PEARSON_POINTS = 2
_MIN_RATERS = 2


@dataclass(frozen=True, slots=True)
class GoldCase:
    """One human-labelled calibration case.

    The optional metadata (``language``/``category``/``segment``/``human_override``)
    powers the per-language, per-rubric and per-segment disagreement breakdowns of
    the "Calibration juge" tab (reference image 05). They default sensibly so the
    legacy four-field constructor and any older gold file keep working.
    """

    question: str
    answer: str
    context: str
    human_label: str  # "good" | "bad"
    case_id: str = ""
    language: str = "fr"  # "fr" | "en" | "de"
    category: str = "faithfulness"  # display rubric bucket
    segment: str = ""  # business segment label
    human_override: bool = False  # a human overrode the judge on this case

    @property
    def metric(self) -> str:
        """The judge rubric this case is scored against."""
        return metric_for_category(self.category)


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
    case_id: str = ""
    language: str = "fr"
    category: str = "faithfulness"
    segment: str = ""
    human_override: bool = False


@dataclass(frozen=True, slots=True)
class GroupAgreement:
    """Judge↔human agreement within one slice (a language, rubric or segment)."""

    label: str
    n: int
    agreement: float
    kappa: float
    n_disagree: int


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
    fp: int = 0  # judge "good", human "bad" (false positive)
    fn: int = 0  # judge "bad", human "good" (false negative)
    n_disagree: int = 0
    n_overrides: int = 0
    by_language: list[GroupAgreement] = field(default_factory=list)
    by_category: list[GroupAgreement] = field(default_factory=list)
    by_segment: list[GroupAgreement] = field(default_factory=list)
    disagreement_by_category: dict[str, int] = field(default_factory=dict)


def _group_agreement(points: Sequence[CalibrationPoint], key: str) -> list[GroupAgreement]:
    """Per-slice agreement/κ over ``points`` grouped by attribute ``key``.

    Sorted by descending disagreement count then descending size, so the most
    problematic slices surface first (the "Segments en désaccord" panel).
    """
    buckets: dict[str, list[CalibrationPoint]] = {}
    for p in points:
        buckets.setdefault(str(getattr(p, key)), []).append(p)
    groups = [
        GroupAgreement(
            label=label,
            n=len(ps),
            agreement=sum(1 for p in ps if p.match) / len(ps),
            kappa=cohen_kappa([(p.judge_label, p.human_label) for p in ps]),
            n_disagree=sum(1 for p in ps if not p.match),
        )
        for label, ps in buckets.items()
        if label
    ]
    groups.sort(key=lambda g: (-g.n_disagree, -g.n, g.label))
    return groups


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
            case_id=str(item.get("id", "")),
            language=str(item.get("language", "fr")),
            category=str(item.get("category", "faithfulness")),
            segment=str(item.get("segment", "")),
            human_override=bool(item.get("human_override", False)),
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
            metric=case.metric,
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
                case_id=case.case_id,
                language=case.language,
                category=case.category,
                segment=case.segment,
                human_override=case.human_override,
            )
        )

    mean_good = sum(good_scores) / len(good_scores) if good_scores else 0.0
    mean_bad = sum(bad_scores) / len(bad_scores) if bad_scores else 0.0
    disagreements = [p for p in points if not p.match]
    disagree_by_cat: dict[str, int] = {}
    for p in disagreements:
        disagree_by_cat[p.category] = disagree_by_cat.get(p.category, 0) + 1
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
        fp=sum(1 for p in points if p.judge_label == "good" and p.human_label != "good"),
        fn=sum(1 for p in points if p.judge_label != "good" and p.human_label == "good"),
        n_disagree=len(disagreements),
        n_overrides=sum(1 for p in points if p.human_override),
        by_language=_group_agreement(points, "language"),
        by_category=_group_agreement(points, "category"),
        by_segment=_group_agreement(points, "segment"),
        disagreement_by_category=disagree_by_cat,
    )


# ── multi-judge consensus ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class JudgeAgreement:
    """One judge's agreement with the panel majority over the gold set."""

    judge_model: str
    agreement: float  # fraction of cases where this judge matched the majority label


@dataclass(frozen=True, slots=True)
class ConsensusReport:
    """Agreement of a panel of judges scoring the same gold set.

    The judge-side analogue of inter-annotator agreement: several *different*
    local judges label every gold case and we measure how often they concur.
    ``consensus_rate`` is the share of cases the whole panel agrees on (unanimous);
    ``fleiss_kappa`` corrects that for chance across all raters.
    """

    n_judges: int
    n_cases: int
    judge_models: list[str]
    consensus_rate: float  # fraction of cases with unanimous labels
    mean_pairwise_agreement: float  # mean agreement over all judge pairs
    fleiss_kappa: float  # multi-rater agreement beyond chance
    per_judge: list[JudgeAgreement] = field(default_factory=list)


def fleiss_kappa_binary(votes: Sequence[tuple[int, int]]) -> float:
    """Fleiss' κ for a fixed panel scoring N items into two categories.

    Args:
        votes: One ``(n_good, n_bad)`` count pair per item; every item must have
            the same total number of raters.

    Returns:
        Fleiss' κ in ``[-1, 1]``; ``1.0`` for perfect agreement, ``0.0`` when no
        item has variation or the panel/category structure is degenerate.
    """
    n_items = len(votes)
    if n_items == 0:
        return 0.0
    n_raters = votes[0][0] + votes[0][1]
    if n_raters < _MIN_RATERS or any((g + b) != n_raters for g, b in votes):
        return 0.0
    # Per-item agreement P_i, then the mean over items.
    p_bar = (
        sum((g * (g - 1) + b * (b - 1)) / (n_raters * (n_raters - 1)) for g, b in votes) / n_items
    )
    # Category marginals and expected agreement P_e.
    total = n_items * n_raters
    p_good = sum(g for g, _ in votes) / total
    p_bad = sum(b for _, b in votes) / total
    p_e = p_good**2 + p_bad**2
    if p_e >= 1.0:
        return 1.0
    return (p_bar - p_e) / (1.0 - p_e)


async def gold_consensus(
    judges: Sequence[Judge],
    gold: Sequence[GoldCase],
    *,
    metric: str = FAITHFULNESS,
    labels: Sequence[str] | None = None,
) -> ConsensusReport:
    """Score the gold set with several judges and measure their consensus.

    Args:
        judges: The judge panel (two or more); each scores every gold case.
        gold: The human-labelled gold set.
        metric: The rubric every judge scores against.
        labels: Display names per judge (defaults to each judge's reported model,
            de-duplicated by index).

    Returns:
        A :class:`ConsensusReport` with the unanimous-consensus rate, mean pairwise
        agreement, Fleiss' κ and each judge's agreement with the panel majority.
    """
    # labels_per_judge[j] = "good"/"bad" call of judge j on each gold case.
    labels_per_judge: list[list[str]] = [[] for _ in judges]
    models: list[str] = list(labels) if labels is not None else ["" for _ in judges]
    for case in gold:
        for j, judge in enumerate(judges):
            verdict = await judge.score(
                metric=metric,
                question=case.question,
                answer=case.answer,
                context=case.context,
            )
            if labels is None and not models[j]:
                models[j] = verdict.judge_model or f"judge{j + 1}"
            labels_per_judge[j].append("good" if verdict.score >= _PASS_THRESHOLD else "bad")

    n_judges = len(judges)
    n_cases = len(gold)
    if n_judges == 0 or n_cases == 0:
        return ConsensusReport(
            n_judges=n_judges,
            n_cases=n_cases,
            judge_models=models,
            consensus_rate=0.0,
            mean_pairwise_agreement=0.0,
            fleiss_kappa=0.0,
        )

    # Per-case panel votes and the unanimous-consensus rate.
    votes: list[tuple[int, int]] = []
    unanimous = 0
    majority: list[str] = []
    for i in range(n_cases):
        calls = [labels_per_judge[j][i] for j in range(n_judges)]
        n_good = sum(1 for c in calls if c == "good")
        n_bad = n_judges - n_good
        votes.append((n_good, n_bad))
        if n_good == 0 or n_bad == 0:
            unanimous += 1
        majority.append("good" if n_good >= n_bad else "bad")
    consensus_rate = unanimous / n_cases

    # Mean pairwise agreement over all judge pairs.
    pair_rates: list[float] = []
    for a in range(n_judges):
        for b in range(a + 1, n_judges):
            agree = sum(
                1 for i in range(n_cases) if labels_per_judge[a][i] == labels_per_judge[b][i]
            )
            pair_rates.append(agree / n_cases)
    mean_pairwise = sum(pair_rates) / len(pair_rates) if pair_rates else 1.0

    per_judge = [
        JudgeAgreement(
            judge_model=models[j],
            agreement=sum(1 for i in range(n_cases) if labels_per_judge[j][i] == majority[i])
            / n_cases,
        )
        for j in range(n_judges)
    ]
    return ConsensusReport(
        n_judges=n_judges,
        n_cases=n_cases,
        judge_models=models,
        consensus_rate=consensus_rate,
        mean_pairwise_agreement=mean_pairwise,
        fleiss_kappa=fleiss_kappa_binary(votes),
        per_judge=per_judge,
    )
