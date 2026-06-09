"""Quality SLOs + error budgets (ADR 0010, idea #15).

SRE treats reliability as a budget: you pick an SLO (e.g. *95 % of turns score
at least 0.80 on faithfulness*), and every turn below the bar spends a slice of
the *error budget* that the SLO implicitly grants. When you spend faster than the
budget replenishes — the *burn rate* — you alert.

This module brings that discipline to *quality*. A faithfulness regression burns
budget exactly like a latency regression, and a slow leak (burn rate just over
1.0) is caught long before a hard outage. The computation is local, over the
in-process ring buffer of online-eval scores (:mod:`tessera.observability.eval.scores`)
— no Prometheus or BigQuery required — which mirrors the GCP-side SLO alert in
``infra/terraform/observability_genai.tf`` (faithfulness < 0.80).

We report a two-window burn rate (a short recent window and the whole buffer),
following Google's multi-window burn-rate alerting: a fast window catches sudden
regressions, a slow window suppresses flapping on a single bad turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["SLOReport", "compute_slo"]

# A turn is "good" when its faithfulness meets this bar — the same 0.80 the GCP
# SLO alert uses, so the local and cloud views agree.
_DEFAULT_THRESHOLD = 0.80
# Target fraction of good turns. 0.95 grants a 5 % error budget.
_DEFAULT_TARGET = 0.95
# Size of the fast burn-rate window (most recent turns).
_FAST_WINDOW = 20
# Burn rate above this is breaching the budget faster than it replenishes.
_BURN_ALERT = 1.0
_METRIC = "faithfulness"


@dataclass(frozen=True, slots=True)
class SLOReport:
    """SLO compliance and error-budget burn over the recent scores."""

    metric: str
    threshold: float  # a turn is good when score >= threshold
    target: float  # target fraction of good turns (the SLO)
    n: int
    n_good: int
    n_bad: int
    good_rate: float  # observed fraction of good turns
    error_budget: float  # 1 - target, the tolerated bad fraction
    budget_consumed: float  # observed bad rate / error budget (>1 = exhausted)
    budget_remaining: float  # max(0, 1 - budget_consumed)
    burn_rate: float  # slow-window burn rate (whole buffer)
    burn_rate_fast: float  # fast-window burn rate (most recent turns)
    breaching: bool  # both windows burning faster than the budget replenishes


def _burn_rate(scores: Sequence[float], *, threshold: float, error_budget: float) -> float:
    """Burn rate = observed bad fraction / tolerated bad fraction."""
    if not scores or error_budget <= 0:
        return 0.0
    bad = sum(1 for s in scores if s < threshold)
    return (bad / len(scores)) / error_budget


def compute_slo(
    scores: Sequence[float],
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    target: float = _DEFAULT_TARGET,
) -> SLOReport:
    """Compute SLO compliance and error-budget burn for a series of scores.

    Args:
        scores: Faithfulness scores (0..1), oldest first, newest last.
        threshold: A turn is "good" when its score is at least this value.
        target: The SLO — the target fraction of good turns.

    Returns:
        An :class:`SLOReport`. With no scores, every field is zero and
        ``breaching`` is ``False`` (no evidence of a breach).
    """
    n = len(scores)
    error_budget = max(0.0, 1.0 - target)
    if n == 0:
        return SLOReport(
            metric=_METRIC,
            threshold=threshold,
            target=target,
            n=0,
            n_good=0,
            n_bad=0,
            good_rate=0.0,
            error_budget=error_budget,
            budget_consumed=0.0,
            budget_remaining=1.0,
            burn_rate=0.0,
            burn_rate_fast=0.0,
            breaching=False,
        )

    n_good = sum(1 for s in scores if s >= threshold)
    n_bad = n - n_good
    good_rate = n_good / n
    bad_rate = n_bad / n
    budget_consumed = bad_rate / error_budget if error_budget > 0 else 0.0

    burn_rate = _burn_rate(scores, threshold=threshold, error_budget=error_budget)
    burn_rate_fast = _burn_rate(
        scores[-_FAST_WINDOW:], threshold=threshold, error_budget=error_budget
    )
    # Multi-window: only breach when both the recent burst and the longer trend
    # exceed the budget, so a single bad turn does not page.
    breaching = burn_rate > _BURN_ALERT and burn_rate_fast > _BURN_ALERT

    return SLOReport(
        metric=_METRIC,
        threshold=threshold,
        target=target,
        n=n,
        n_good=n_good,
        n_bad=n_bad,
        good_rate=good_rate,
        error_budget=error_budget,
        budget_consumed=budget_consumed,
        budget_remaining=max(0.0, 1.0 - budget_consumed),
        burn_rate=burn_rate,
        burn_rate_fast=burn_rate_fast,
        breaching=breaching,
    )
