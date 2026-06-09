"""Shadow / mirror traffic (ADR 0010, idea #16).

Shadow testing answers "what would the candidate model have done?" without ever
showing its output to a user. We mirror a batch of *real captured turns* to a
candidate model, re-judge each candidate answer, and compare it against the
original — aggregating wins, losses, ties and the mean faithfulness delta. The
production answer the user actually saw is untouched; this is a read-only,
side-effect-free comparison.

It builds directly on the replay machinery (:mod:`tessera.observability.replay`):
one shadow run is a batch of replays plus an aggregation, which is why a model
migration can be vetted against live traffic before any rollout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.eval.judge import Judge
    from tessera.observability.replay import ReplayBundle

__all__ = ["ShadowComparison", "ShadowReport", "run_shadow"]

# A score delta within this band counts as a tie, not a win/loss — judge scores
# are quantised, so a hair's-width difference is noise, not a regression.
_TIE_BAND = 0.05
_DEFAULT_LIMIT = 10
_SNIPPET = 80


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    """One captured turn replayed against the candidate model."""

    question: str
    language: str
    original_score: float
    candidate_score: float
    score_delta: float
    similarity: float
    outcome: str  # "win" | "loss" | "tie"


@dataclass(frozen=True, slots=True)
class ShadowReport:
    """Aggregate of a shadow run over a batch of captured turns."""

    candidate_model: str
    n_compared: int
    wins: int
    losses: int
    ties: int
    mean_delta: float
    mean_similarity: float
    mean_original_score: float
    mean_candidate_score: float
    comparisons: list[ShadowComparison] = field(default_factory=list)


def _outcome(delta: float) -> str:
    if delta > _TIE_BAND:
        return "win"
    if delta < -_TIE_BAND:
        return "loss"
    return "tie"


async def run_shadow(
    bundles: Sequence[ReplayBundle],
    *,
    model: str,
    limit: int = _DEFAULT_LIMIT,
    judge: Judge | None = None,
) -> ShadowReport:
    """Mirror the most recent captured turns to a candidate model and compare.

    Args:
        bundles: Captured turns (newest last); the last ``limit`` are mirrored.
        model: The candidate model id to shadow against.
        limit: Maximum number of turns to mirror, taken from the newest end.
        judge: Judge for scoring; defaults to the configured judge in
            :func:`tessera.observability.replay.replay`.

    Returns:
        A :class:`ShadowReport`. With no bundles, every count is zero.
    """
    batch = list(bundles)[-limit:]
    comparisons: list[ShadowComparison] = []
    for bundle in batch:
        result = await replay_mod.replay(bundle, model=model, judge=judge)
        comparisons.append(
            ShadowComparison(
                question=bundle.question[:_SNIPPET],
                language=bundle.language,
                original_score=result.original_score,
                candidate_score=result.candidate_score,
                score_delta=result.score_delta,
                similarity=result.similarity,
                outcome=_outcome(result.score_delta),
            )
        )

    n = len(comparisons)
    if n == 0:
        return ShadowReport(
            candidate_model=model,
            n_compared=0,
            wins=0,
            losses=0,
            ties=0,
            mean_delta=0.0,
            mean_similarity=0.0,
            mean_original_score=0.0,
            mean_candidate_score=0.0,
        )

    wins = sum(1 for c in comparisons if c.outcome == "win")
    losses = sum(1 for c in comparisons if c.outcome == "loss")
    ties = n - wins - losses
    return ShadowReport(
        candidate_model=model,
        n_compared=n,
        wins=wins,
        losses=losses,
        ties=ties,
        mean_delta=sum(c.score_delta for c in comparisons) / n,
        mean_similarity=sum(c.similarity for c in comparisons) / n,
        mean_original_score=sum(c.original_score for c in comparisons) / n,
        mean_candidate_score=sum(c.candidate_score for c in comparisons) / n,
        comparisons=comparisons,
    )
