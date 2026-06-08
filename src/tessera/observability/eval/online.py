"""Tiered, cost-aware online evaluation (ADR 0010, idea #6).

Judging every turn with an LLM is expensive. The policy: always judge *flagged*
turns (errors, guard denies, low-confidence), and judge a stratified *sample* of
the rest. The score is emitted as telemetry (#5), and a **guard↔judge
disagreement** — the guard allowed a turn the judge finds poorly grounded, or
denied one the judge finds fine — is surfaced as the signal that routes a trace
to human annotation and, later, the flywheel.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability.eval import scores
from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge
from tessera.settings import get_settings

if TYPE_CHECKING:
    from tessera.observability.eval.judge import Judge, JudgeVerdict

__all__ = ["OnlineEvalOutcome", "evaluate_turn", "should_judge"]

# Below this faithfulness an allowed turn is considered a miss; at/above this an
# otherwise-denied turn looks fine. The gap between them is the disagreement zone.
_LOW_SCORE: float = 0.5
_HIGH_SCORE: float = 0.8


@dataclass(frozen=True, slots=True)
class OnlineEvalOutcome:
    """Result of considering a turn for online evaluation."""

    verdict: JudgeVerdict | None
    disagreement: bool


def should_judge(*, flagged: bool, sample_rate: float, roll: float | None = None) -> bool:
    """Decide whether to score this turn.

    Flagged turns are always judged; the rest are sampled at ``sample_rate``.

    Args:
        flagged: Whether the turn is already flagged (error / guard deny / low
            confidence) and must be judged.
        sample_rate: Fraction of un-flagged turns to judge, in [0, 1].
        roll: Optional deterministic draw in [0, 1) (for tests); a cryptographic
            draw is used when omitted.
    """
    if flagged:
        return True
    draw = roll if roll is not None else secrets.randbelow(10_000) / 10_000
    return draw < sample_rate


async def evaluate_turn(
    *,
    question: str,
    answer: str,
    context: str,
    language: str,
    guard_denied: bool = False,
    flagged: bool = False,
    conversation_id: str | None = None,
    judge: Judge | None = None,
    sample_rate: float | None = None,
    roll: float | None = None,
) -> OnlineEvalOutcome:
    """Maybe score a turn, emit its telemetry, and flag guard↔judge disagreement.

    Returns an outcome with a ``None`` verdict when the turn was not sampled.
    """
    rate = (
        sample_rate
        if sample_rate is not None
        else get_settings().observability.online_eval_sample_rate
    )
    must_judge = flagged or guard_denied
    if not should_judge(flagged=must_judge, sample_rate=rate, roll=roll):
        return OnlineEvalOutcome(verdict=None, disagreement=False)

    active_judge: Judge = judge or LLMJudge()
    verdict = await active_judge.score(
        metric=FAITHFULNESS, question=question, answer=answer, context=context
    )
    scores.emit_score(
        verdict, language=language, conversation_id=conversation_id, sampled=not must_judge
    )

    disagreement = (not guard_denied and verdict.score < _LOW_SCORE) or (
        guard_denied and verdict.score >= _HIGH_SCORE
    )
    return OnlineEvalOutcome(verdict=verdict, disagreement=disagreement)
