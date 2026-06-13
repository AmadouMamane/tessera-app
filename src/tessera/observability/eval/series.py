"""Time-bucketed quality score series for the cockpit evolution chart (ADR 0011).

The trend module (:mod:`tessera.observability.trends`) buckets scores by *order*;
this one buckets by *calendar time* over a fixed window ending at instant T, so
the Qualité IA "Vue d'ensemble" can draw a real "score over the last N days" line
and a period-over-period delta. It reads the same durable score event log, so it
honours as-of-T: a T in the past yields the series exactly as it stood then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

__all__ = ["ScoreSeries", "SeriesBucket", "compute_score_series"]


@dataclass(frozen=True, slots=True)
class SeriesBucket:
    """One equal time slice of the score series."""

    start: str  # ISO start of the bucket
    n: int
    mean: float | None  # None when the bucket has no scores (chart shows a gap)


@dataclass(frozen=True, slots=True)
class ScoreSeries:
    """A metric's mean over a window, its buckets, and its period-over-period delta."""

    metric: str
    window_start: str
    window_end: str
    n: int
    mean: float | None  # mean over the window
    prev_mean: float | None  # mean over the immediately preceding equal window
    delta: float | None  # mean - prev_mean (None when either side is empty)
    buckets: list[SeriesBucket] = field(default_factory=list)


def _parse(ts: object) -> datetime | None:
    """Parse an ISO timestamp, returning ``None`` on anything malformed."""
    try:
        return datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None


def compute_score_series(
    rows: list[dict[str, object]],
    *,
    metric: str = "faithfulness",
    end: datetime,
    days: int = 7,
    n_buckets: int = 7,
) -> ScoreSeries:
    """Bucket the scores of one metric into ``n_buckets`` equal time slices.

    Args:
        rows: Persisted score rows in any order; each needs ``scored_at``,
            ``metric`` and ``score``. Rows after ``end`` or of another metric are
            ignored. The window's left edge is ``end - days``; the equal window
            before that feeds the period-over-period ``delta``.
        metric: The metric to build the series for.
        end: The right edge of the window — instant T, or "now".
        days: Window length in days.
        n_buckets: Number of equal slices across the window.

    Returns:
        A :class:`ScoreSeries`. Empty buckets carry ``mean=None`` so the chart can
        draw a gap rather than a fabricated zero.
    """
    n_buckets = max(1, n_buckets)
    window = timedelta(days=max(1, days))
    start = end - window
    prev_start = start - window
    span = window.total_seconds() or 1.0

    cur: list[float] = []
    prev: list[float] = []
    bucket_scores: list[list[float]] = [[] for _ in range(n_buckets)]

    for row in rows:
        if row.get("metric") != metric:
            continue
        ts = _parse(row.get("scored_at"))
        if ts is None:
            continue
        try:
            score = float(row["score"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            continue
        if prev_start <= ts < start:
            prev.append(score)
        elif start <= ts <= end:
            cur.append(score)
            frac = (ts - start).total_seconds() / span
            idx = min(n_buckets - 1, max(0, int(frac * n_buckets)))
            bucket_scores[idx].append(score)

    buckets = [
        SeriesBucket(
            start=(start + timedelta(seconds=span * i / n_buckets)).isoformat(),
            n=len(bs),
            mean=(sum(bs) / len(bs)) if bs else None,
        )
        for i, bs in enumerate(bucket_scores)
    ]
    mean = sum(cur) / len(cur) if cur else None
    prev_mean = sum(prev) / len(prev) if prev else None
    delta = (mean - prev_mean) if (mean is not None and prev_mean is not None) else None
    return ScoreSeries(
        metric=metric,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        n=len(cur),
        mean=mean,
        prev_mean=prev_mean,
        delta=delta,
        buckets=buckets,
    )
