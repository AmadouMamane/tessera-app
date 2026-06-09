"""Multi-judge ensemble agreement (ADR 0010, idea #95).

A single LLM judge is itself a fallible model. Running two *different* local
judges over the same turn and measuring how much they agree gives two things:
a more robust score (their mean) and, more usefully, a **hard-case detector** —
when two judges disagree sharply about the same answer, that turn is exactly the
one worth a human's time. This is the judge-side analogue of self-consistency
(#18), and it stays sovereign: both judges run locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from tessera.observability.eval.judge import Judge

__all__ = ["EnsembleReport", "JudgeScore", "evaluate_ensemble"]

# Two small, locally-served Ollama judges with different lineages.
DEFAULT_MODELS: tuple[str, ...] = ("llama3.2:3b", "mistral:7b")
_DISAGREEMENT_THRESHOLD = 0.3  # score spread above this = hard case


@dataclass(frozen=True, slots=True)
class JudgeScore:
    """One judge's verdict in the ensemble."""

    model: str
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class EnsembleReport:
    """Agreement of several judges scoring the same turn."""

    metric: str
    mean_score: float
    max_spread: float  # max minus min judge score
    agreement: float  # 1 - max_spread, 0..1
    disagreement: bool  # spread exceeds the hard-case threshold
    scores: list[JudgeScore] = field(default_factory=list)


async def evaluate_ensemble(
    *,
    question: str,
    answer: str,
    context: str,
    metric: str = FAITHFULNESS,
    models: Sequence[str] = DEFAULT_MODELS,
    judge_factory: Callable[[str], Judge] | None = None,
) -> EnsembleReport:
    """Score one turn with several judges and measure their agreement.

    Args:
        question: The user question.
        answer: The answer under evaluation.
        context: The grounding context.
        metric: The rubric to score against.
        models: The judge model ids to run (defaults to two local judges).
        judge_factory: Builds a judge for a model id; defaults to
            ``LLMJudge(model=...)`` so each judge runs locally.

    Returns:
        An :class:`EnsembleReport` with per-judge scores and the spread.
    """
    factory = judge_factory or (lambda model: LLMJudge(model=model))
    scores: list[JudgeScore] = []
    for model in models:
        verdict = await factory(model).score(
            metric=metric, question=question, answer=answer, context=context
        )
        scores.append(JudgeScore(model=model, score=verdict.score, rationale=verdict.rationale))

    values = [s.score for s in scores]
    max_spread = (max(values) - min(values)) if values else 0.0
    return EnsembleReport(
        metric=metric,
        mean_score=(sum(values) / len(values) if values else 0.0),
        max_spread=max_spread,
        agreement=max(0.0, 1.0 - max_spread),
        disagreement=max_spread > _DISAGREEMENT_THRESHOLD,
        scores=scores,
    )
