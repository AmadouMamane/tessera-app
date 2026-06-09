"""Pre-judge failure prediction (ADR 0010, idea #121).

The LLM judge is the ground truth for answer quality, but it is *expensive* — a
second model call per turn. This module asks a cheaper question: can we flag a
turn that is *likely* to score badly **before** the judge runs, from signals that
cost nothing? A turn with almost no grounding context, an injection-shaped
instruction, or a one-word question is structurally at risk regardless of what
the model says.

:func:`predict_failure` is a transparent, dependency-free heuristic over those
cheap features — not a black-box model, so every flag carries its reasons.
:func:`evaluate_predictor` then back-tests the heuristic against the *actual*
judge scores of captured turns, reporting precision and recall: does the cheap
predictor agree with the expensive judge? That back-test is the honest measure of
whether the predictor is worth wiring in as a sampling gate (it pairs naturally
with tail-based sampling, #32).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Prediction", "PredictorEvaluation", "evaluate_predictor", "predict_failure"]

# A turn whose risk is at or above this is predicted to fail.
_RISK_THRESHOLD = 0.5
# A captured turn whose actual faithfulness is below this really did fail.
_FAIL_SCORE = 0.80

_MIN_CONTEXT = 50  # chars — below this the answer is barely grounded
_MIN_QUESTION = 10
_MAX_QUESTION = 400

# Injection / instruction-override shaped phrases across fr/de/en.
_INJECTION_RE = re.compile(
    r"\b(ignore|ignorer|ignoriere|disregard|reveal|révèle|system prompt|"
    r"system-prompt|systemprompt|pretend|fais comme si|act as|agis comme)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[^\W\d_]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class Prediction:
    """A pre-judge risk estimate for one turn."""

    risk: float  # 0..1
    will_fail: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PredictorEvaluation:
    """Back-test of the predictor against actual judge scores."""

    n: int
    n_predicted_fail: int
    n_actual_fail: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    precision: float
    recall: float


def predict_failure(
    *,
    question: str,
    context: str,
    threshold: float = _RISK_THRESHOLD,
) -> Prediction:
    """Estimate the failure risk of a turn from cheap structural signals."""
    reasons: list[str] = []
    risk = 0.0

    if len(context.strip()) < _MIN_CONTEXT:
        risk += 0.40
        reasons.append("thin_context")
    if _INJECTION_RE.search(question):
        risk += 0.50
        reasons.append("injection_shaped")
    q = question.strip()
    if len(q) < _MIN_QUESTION:
        risk += 0.15
        reasons.append("very_short_question")
    if len(q) > _MAX_QUESTION:
        risk += 0.20
        reasons.append("very_long_question")
    if q and not _WORD_RE.search(q):
        risk += 0.20
        reasons.append("no_letters")

    risk = min(1.0, risk)
    return Prediction(risk=risk, will_fail=risk >= threshold, reasons=reasons)


def evaluate_predictor(
    turns: Iterable[tuple[str, str, float]],
    *,
    threshold: float = _RISK_THRESHOLD,
) -> PredictorEvaluation:
    """Back-test the predictor against captured turns' actual scores.

    Args:
        turns: ``(question, context, actual_score)`` triples from captured turns.
        threshold: Risk at/above which a turn is predicted to fail.

    Returns:
        A :class:`PredictorEvaluation` with precision/recall vs the judge.
    """
    tp = fp = fn = tn = 0
    n_predicted = n_actual = 0
    n = 0
    for question, context, score in turns:
        n += 1
        predicted = predict_failure(
            question=question, context=context, threshold=threshold
        ).will_fail
        actual = score < _FAIL_SCORE
        n_predicted += int(predicted)
        n_actual += int(actual)
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return PredictorEvaluation(
        n=n,
        n_predicted_fail=n_predicted,
        n_actual_fail=n_actual,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        precision=precision,
        recall=recall,
    )
