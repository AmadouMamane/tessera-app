"""Long-horizon quality trend analysis (ADR 0010, idea #150).

A single bad turn is noise; a faithfulness score that drifts down half a point
over weeks is a *slow degradation* — the failure mode that point-in-time alerts
miss because no single sample ever breaches a threshold. This module fits the
shape of the score series: a least-squares slope (per-turn drift), a first-half
vs second-half delta (coarse before/after), and ordered time buckets for a
sparkline. A negative slope *and* a meaningful second-half drop flags a slow
regression before it becomes an incident.

The window here is the in-process ring buffer of online-eval scores
(:mod:`tessera.observability.eval.scores`); a true months-scale view is backed
by the BigQuery lakehouse (#120) in the GCP profile. The maths is identical — the
buffer is the local, no-dependency view of the same series.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["TrendBucket", "TrendReport", "analyze_trend"]

# Slope (score units per turn) below/above this is drift, not flatness.
_SLOPE_EPS = 0.001
# A second-half mean this much below the first half is a meaningful drop.
_DEGRADE_DELTA = 0.05
_MAX_BUCKETS = 8
_MIN_FOR_TREND = 4  # need a few points before a slope means anything


@dataclass(frozen=True, slots=True)
class TrendBucket:
    """A contiguous time slice of the score series."""

    index: int
    n: int
    mean: float


@dataclass(frozen=True, slots=True)
class TrendReport:
    """The shape of the score series over its horizon."""

    metric: str
    n: int
    slope: float  # least-squares score units per turn
    direction: str  # "improving" | "stable" | "degrading"
    first_half_mean: float
    second_half_mean: float
    delta: float  # second half minus first half
    degrading: bool  # slow downward drift worth attention
    buckets: list[TrendBucket] = field(default_factory=list)


def _slope(scores: Sequence[float]) -> float:
    """Least-squares slope of score versus index (0, 1, 2, ...)."""
    n = len(scores)
    if n < 2:  # noqa: PLR2004 — a slope needs at least two points
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(scores) / n
    num = sum((i - mean_x) * (s - mean_y) for i, s in enumerate(scores))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def analyze_trend(
    points: Sequence[tuple[str, float]],
    *,
    metric: str = "faithfulness",
) -> TrendReport:
    """Analyse the trend of an ordered score series.

    Args:
        points: ``(scored_at, score)`` pairs, oldest first, newest last. The
            timestamp is carried for context; the trend is computed over order.
        metric: The metric name these scores belong to.

    Returns:
        A :class:`TrendReport`. Below :data:`_MIN_FOR_TREND` points, the slope is
        zero, the direction ``"stable"`` and ``degrading`` ``False`` (too little
        evidence to call a trend).
    """
    scores = [score for _, score in points]
    n = len(scores)
    if n == 0:
        return TrendReport(
            metric=metric,
            n=0,
            slope=0.0,
            direction="stable",
            first_half_mean=0.0,
            second_half_mean=0.0,
            delta=0.0,
            degrading=False,
        )

    half = n // 2
    first = scores[:half] or scores[:1]
    second = scores[half:] or scores[-1:]
    first_mean = sum(first) / len(first)
    second_mean = sum(second) / len(second)
    delta = second_mean - first_mean

    # Buckets for the sparkline: evenly split the ordered series.
    n_buckets = min(_MAX_BUCKETS, n)
    buckets: list[TrendBucket] = []
    for b in range(n_buckets):
        lo = b * n // n_buckets
        hi = (b + 1) * n // n_buckets
        slice_ = scores[lo:hi]
        if slice_:
            buckets.append(TrendBucket(index=b, n=len(slice_), mean=sum(slice_) / len(slice_)))

    if n < _MIN_FOR_TREND:
        return TrendReport(
            metric=metric,
            n=n,
            slope=0.0,
            direction="stable",
            first_half_mean=first_mean,
            second_half_mean=second_mean,
            delta=delta,
            degrading=False,
            buckets=buckets,
        )

    slope = _slope(scores)
    if slope > _SLOPE_EPS:
        direction = "improving"
    elif slope < -_SLOPE_EPS:
        direction = "degrading"
    else:
        direction = "stable"
    # Slow degradation: a downward slope confirmed by a meaningful drop in the
    # half-over-half *median* (robust — a single late dip cannot move the median,
    # so it does not masquerade as a trend; cf. insights_claude_powered #12).
    median_delta = statistics.median(second) - statistics.median(first)
    degrading = slope < -_SLOPE_EPS and median_delta < -_DEGRADE_DELTA

    return TrendReport(
        metric=metric,
        n=n,
        slope=slope,
        direction=direction,
        first_half_mean=first_mean,
        second_half_mean=second_mean,
        delta=delta,
        degrading=degrading,
        buckets=buckets,
    )
