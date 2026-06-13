"""Time-bucketed quality score series for the cockpit evolution chart (ADR 0011).

The trend module (:mod:`tessera.observability.trends`) buckets scores by *order*;
this one buckets by *calendar time* over a fixed window ending at instant T, so
the Qualité IA "Vue d'ensemble" can draw a real "score over the last N days" line
and a period-over-period delta. It reads the same durable score event log, so it
honours as-of-T: a T in the past yields the series exactly as it stood then.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

__all__ = [
    "JudgeDrift",
    "MetricPairs",
    "MetricPoint",
    "ScoreSeries",
    "SeriesBucket",
    "StatusBand",
    "StatusCountsTrend",
    "compute_judge_drift",
    "compute_metric_pairs",
    "compute_score_series",
    "compute_status_counts_trend",
]


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


@dataclass(frozen=True, slots=True)
class MetricPoint:
    """One turn scored on both metrics (a point in the X-vs-Y scatter)."""

    x: float
    y: float
    language: str


@dataclass(frozen=True, slots=True)
class MetricPairs:
    """Per-turn pairs of two metrics, for a scatter (e.g. faithfulness vs grounding)."""

    x_metric: str
    y_metric: str
    n: int
    points: list[MetricPoint] = field(default_factory=list)


def compute_metric_pairs(
    rows: list[dict[str, object]],
    *,
    x_metric: str = "faithfulness",
    y_metric: str = "grounding",
) -> MetricPairs:
    """Pair two metrics scored on the same turn, keyed by conversation.

    The online evaluator emits all metrics for one turn under the same
    ``conversation_id``; a point is produced only when a conversation has at least
    one score for *both* metrics (its per-conversation means). Conversations with
    only one of the two are skipped — no fabricated coordinate.

    Args:
        rows: Persisted score rows (any order) with ``metric``, ``score``,
            ``conversation_id`` and ``language``.
        x_metric: Metric mapped to the X axis.
        y_metric: Metric mapped to the Y axis.

    Returns:
        A :class:`MetricPairs` with one point per paired conversation.
    """
    bucket: dict[str, dict[str, list[float]]] = {}
    langs: dict[str, str] = {}
    for row in rows:
        metric = row.get("metric")
        conv = row.get("conversation_id")
        if not isinstance(conv, str) or metric not in (x_metric, y_metric):
            continue
        try:
            score = float(row["score"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            continue
        bucket.setdefault(conv, {}).setdefault(str(metric), []).append(score)
        lang = row.get("language")
        if isinstance(lang, str):
            langs[conv] = lang

    points: list[MetricPoint] = []
    for conv, metrics in bucket.items():
        xs = metrics.get(x_metric)
        ys = metrics.get(y_metric)
        if not xs or not ys:
            continue
        points.append(
            MetricPoint(
                x=sum(xs) / len(xs),
                y=sum(ys) / len(ys),
                language=langs.get(conv, ""),
            )
        )
    return MetricPairs(x_metric=x_metric, y_metric=y_metric, n=len(points), points=points)


# Drift bands on the per-bucket dispersion of the judge's mean score. A calibrated
# judge scores consistently over time; rising dispersion = the judge is drifting.
_DRIFT_BANDS: tuple[tuple[float, str], ...] = (
    (0.03, "stable"),
    (0.06, "low"),
    (0.12, "moderate"),
    (0.20, "high"),
)
_MIN_DRIFT_BUCKETS = 2


@dataclass(frozen=True, slots=True)
class JudgeDrift:
    """How much the judge's scoring of one metric drifts across a time window.

    Computed from the durable score event log, so it honours as-of-T like the
    rest of the cockpit. ``divergence`` is the population standard deviation of
    the per-bucket means — a calibrated, stable judge keeps this near zero.
    """

    metric: str
    judge_model: str | None
    window_start: str
    window_end: str
    n: int
    mean: float | None  # judge mean over the window
    divergence: float | None  # stdev of the per-bucket means (drift magnitude)
    delta: float | None  # last non-empty bucket mean - first (directional drift)
    level: str  # stable | low | moderate | high | critical | unknown
    buckets: list[SeriesBucket] = field(default_factory=list)


def _drift_level(divergence: float | None) -> str:
    """Classify a drift magnitude into a band label."""
    if divergence is None:
        return "unknown"
    for threshold, label in _DRIFT_BANDS:
        if divergence < threshold:
            return label
    return "critical"


def compute_judge_drift(
    rows: list[dict[str, object]],
    *,
    metric: str = "faithfulness",
    end: datetime,
    days: int = 7,
    n_buckets: int = 7,
) -> JudgeDrift:
    """Measure the judge's score drift for ``metric`` over the window ending at T.

    Reuses :func:`compute_score_series` to bucket the scores, then measures how
    much the per-bucket means disperse (population stdev) and the net change from
    the first to the last non-empty bucket. With fewer than two non-empty buckets
    the drift is undefined (``level="unknown"``) rather than fabricated.

    Args:
        rows: Persisted score rows (any order) with ``scored_at``, ``metric``,
            ``score`` and ``judge_model``.
        metric: The judged metric to track.
        end: Right edge of the window — instant T, or "now".
        days: Window length in days.
        n_buckets: Number of equal time slices.

    Returns:
        A :class:`JudgeDrift` with the drift magnitude, direction and bucket series.
    """
    series = compute_score_series(rows, metric=metric, end=end, days=days, n_buckets=n_buckets)

    # Dominant judge model over the window (most-scored), for display.
    judge_counts: dict[str, int] = {}
    start = datetime.fromisoformat(series.window_start)
    for row in rows:
        if row.get("metric") != metric:
            continue
        ts = _parse(row.get("scored_at"))
        if ts is None or not (start <= ts <= end):
            continue
        model = row.get("judge_model")
        if isinstance(model, str) and model:
            judge_counts[model] = judge_counts.get(model, 0) + 1
    judge_model = max(judge_counts, key=lambda m: judge_counts[m]) if judge_counts else None

    means = [b.mean for b in series.buckets if b.mean is not None]
    if len(means) < _MIN_DRIFT_BUCKETS:
        return JudgeDrift(
            metric=metric,
            judge_model=judge_model,
            window_start=series.window_start,
            window_end=series.window_end,
            n=series.n,
            mean=series.mean,
            divergence=None,
            delta=None,
            level="unknown",
            buckets=series.buckets,
        )

    bucket_mean = sum(means) / len(means)
    variance = sum((m - bucket_mean) ** 2 for m in means) / len(means)
    divergence = math.sqrt(variance)
    delta = means[-1] - means[0]
    return JudgeDrift(
        metric=metric,
        judge_model=judge_model,
        window_start=series.window_start,
        window_end=series.window_end,
        n=series.n,
        mean=series.mean,
        divergence=divergence,
        delta=delta,
        level=_drift_level(divergence),
        buckets=series.buckets,
    )


@dataclass(frozen=True, slots=True)
class StatusBand:
    """One severity band's per-bucket counts over the window, with a vs-previous delta."""

    counts: list[int]  # one count per time bucket (the sparkline)
    current: int  # count in the last bucket
    total: int  # count over the whole window
    delta: int | None  # last bucket - previous bucket ("vs hier" when buckets are daily)


@dataclass(frozen=True, slots=True)
class StatusCountsTrend:
    """Per-severity-band score counts bucketed over time (Signaux KPI strip, image 01).

    Computed from the durable score event log: each judged score of ``metric`` is
    classified into ``crit`` / ``warn`` / ``ok`` against the SLO thresholds, then
    counted per time bucket. Gives every KPI tile a real sparkline + a real
    period-over-period delta — no fabricated history.
    """

    metric: str
    window_start: str
    window_end: str
    n_buckets: int
    active: StatusBand
    crit: StatusBand
    warn: StatusBand
    ok: StatusBand


def _band(buckets: list[int]) -> StatusBand:
    """Wrap per-bucket counts into a :class:`StatusBand` with current/total/delta."""
    current = buckets[-1] if buckets else 0
    prev = buckets[-2] if len(buckets) >= _MIN_DRIFT_BUCKETS else None
    return StatusBand(
        counts=buckets,
        current=current,
        total=sum(buckets),
        delta=(current - prev) if prev is not None else None,
    )


def compute_status_counts_trend(
    rows: list[dict[str, object]],
    *,
    metric: str = "faithfulness",
    end: datetime,
    days: int = 7,
    warn_threshold: float = 0.8,
    crit_threshold: float = 0.6,
) -> StatusCountsTrend:
    """Count judged scores per severity band, bucketed by day over the window.

    Args:
        rows: Persisted score rows (any order) with ``scored_at``, ``metric`` and
            ``score`` — the same durable log the rest of the cockpit reads, so the
            trend honours as-of-T when ``end`` is a past instant.
        metric: The judged metric whose score distribution drives the bands.
        end: Right edge of the window — instant T, or "now".
        days: Window length in days; one bucket per day.
        warn_threshold: Scores at/above this are ``ok``; below are at least ``warn``.
        crit_threshold: Scores below this are ``crit``.

    Returns:
        A :class:`StatusCountsTrend` with one :class:`StatusBand` per band, each
        carrying its per-bucket counts (sparkline), current/total and vs-previous
        delta. Empty buckets are real zeros (no score that day), never fabricated.
    """
    n_buckets = max(1, days)
    window = timedelta(days=max(1, days))
    start = end - window
    span = window.total_seconds() or 1.0

    active = [0] * n_buckets
    crit = [0] * n_buckets
    warn = [0] * n_buckets
    ok = [0] * n_buckets

    for row in rows:
        if row.get("metric") != metric:
            continue
        ts = _parse(row.get("scored_at"))
        if ts is None or not (start <= ts <= end):
            continue
        try:
            score = float(row["score"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            continue
        frac = (ts - start).total_seconds() / span
        idx = min(n_buckets - 1, max(0, int(frac * n_buckets)))
        active[idx] += 1
        if score < crit_threshold:
            crit[idx] += 1
        elif score < warn_threshold:
            warn[idx] += 1
        else:
            ok[idx] += 1

    return StatusCountsTrend(
        metric=metric,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        n_buckets=n_buckets,
        active=_band(active),
        crit=_band(crit),
        warn=_band(warn),
        ok=_band(ok),
    )
