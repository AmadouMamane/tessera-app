"""Cost / token-burn anomaly detection (ADR 0010, idea #33).

Cost observability is also a *security* signal: an injection loop that keeps
re-feeding context, or a runaway generation, burns tokens — and that shows up as
a spend spike before anything else fires. This module estimates the token
footprint of each captured turn (question + context + answer) and flags turns
whose footprint is a robust outlier (several times the median), surfacing the
disproportionately expensive turns for inspection.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CostReport", "TurnCost", "analyze_costs", "estimate_tokens"]

_CHARS_PER_TOKEN = 4  # rough GPT-style estimate
# A turn this many times the median footprint is a token-burn outlier. The median
# multiple is robust: unlike mean + stddev, a single huge turn cannot inflate the
# threshold above itself and hide.
_MEDIAN_MULTIPLE = 3.0
_MIN_TURNS_FOR_ANOMALY = 3  # need a few turns before the median is meaningful
_SNIPPET = 80
# Indicative blended €/1k tokens for the on-prem path (local inference is ~free;
# this is a comparability figure, not a bill).
_EUR_PER_1K = 0.002


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text`` (chars / 4, floored at 1)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


@dataclass(frozen=True, slots=True)
class TurnCost:
    """Estimated cost of a single turn."""

    question: str
    tokens: int
    anomaly: bool


@dataclass(frozen=True, slots=True)
class CostReport:
    """Token-cost distribution and anomalies over several turns."""

    n_turns: int
    total_tokens: int
    mean_tokens: float
    max_tokens: int
    threshold_tokens: float
    estimated_cost_eur: float
    n_anomalies: int
    anomalies: list[TurnCost] = field(default_factory=list)


def analyze_costs(turns: Iterable[tuple[str, str]]) -> CostReport:
    """Estimate per-turn token cost and flag outliers.

    Args:
        turns: ``(question, full_text)`` pairs, where ``full_text`` is the
            question + context + answer that drives token usage.

    Returns:
        A :class:`CostReport` with the distribution and flagged anomalies.
    """
    rows = [(question, estimate_tokens(full_text)) for question, full_text in turns]
    n_turns = len(rows)
    if n_turns == 0:
        return CostReport(
            n_turns=0,
            total_tokens=0,
            mean_tokens=0.0,
            max_tokens=0,
            threshold_tokens=0.0,
            estimated_cost_eur=0.0,
            n_anomalies=0,
        )

    token_counts = [tokens for _, tokens in rows]
    mean = statistics.mean(token_counts)
    median = statistics.median(token_counts)
    threshold = _MEDIAN_MULTIPLE * median
    total = sum(token_counts)

    anomalies: list[TurnCost] = []
    for question, tokens in rows:
        is_anomaly = n_turns >= _MIN_TURNS_FOR_ANOMALY and threshold > 0 and tokens > threshold
        if is_anomaly:
            anomalies.append(TurnCost(question=question[:_SNIPPET], tokens=tokens, anomaly=True))

    return CostReport(
        n_turns=n_turns,
        total_tokens=total,
        mean_tokens=mean,
        max_tokens=max(token_counts),
        threshold_tokens=threshold,
        estimated_cost_eur=total / 1000 * _EUR_PER_1K,
        n_anomalies=len(anomalies),
        anomalies=anomalies,
    )
