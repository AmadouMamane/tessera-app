"""Regression-risk signal for the Qualité IA "Signaux prédictifs" column.

This composes a forward-looking risk score from signals that already exist and
are real — never a fabricated number:

* the recent score trend (``compute_score_series`` delta — a falling judge score
  is the strongest leading indicator of a coming regression),
* judge drift (``compute_judge_drift`` divergence — an unstable judge widens the
  uncertainty band), and
* the share of compared models that regressed run-over-run
  (``release_status`` — the empirical base rate).

The blend is transparent: each component is returned alongside the composite so
the cockpit can show *why* the risk is what it is. The 7-day regression
probability is the empirical regression rate (open regressions / models
compared), an observed base rate rather than an invented forecast. When there is
no data on either side, the fields are ``None`` and the level is ``"unknown"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability.eval.series import compute_judge_drift, compute_score_series

if TYPE_CHECKING:
    from datetime import datetime

    from tessera.observability.eval.releases import ReleaseStatus

__all__ = ["RegressionRisk", "compute_regression_risk"]

# A score drop or a drift divergence of this magnitude saturates its component.
# 0.20 matches the judge-drift "critical" band edge, keeping the scales aligned.
_SATURATION = 0.20

# Component weights (sum to 1): the recent trend leads, the empirical base rate
# anchors, drift widens the band.
_W_SCORE = 0.40
_W_REGRESSION = 0.35
_W_DRIFT = 0.25

# Risk-score bands → level label.
_RISK_BANDS: tuple[tuple[float, str], ...] = (
    (0.25, "low"),
    (0.50, "moderate"),
    (0.75, "high"),
)


@dataclass(frozen=True, slots=True)
class RegressionRisk:
    """A forward-looking regression-risk read, with its real component inputs."""

    metric: str
    window_start: str
    window_end: str
    n: int  # judge scores in the window
    score_delta: float | None  # period-over-period mean change (negative = worse)
    divergence: float | None  # judge drift magnitude over the window
    regression_rate: float | None  # open regressions / models compared
    models_compared: int
    n_regressions: int
    score_component: float  # 0..1 contribution of the falling trend
    drift_component: float  # 0..1 contribution of judge drift
    regression_component: float  # 0..1 contribution of the empirical base rate
    risk_score: float | None  # 0..1 composite (None when no inputs at all)
    probability_7d: float | None  # empirical regression base rate (None when none compared)
    level: str  # low | moderate | high | critical | unknown
    buckets_used: int = field(default=0)  # populated score buckets behind the trend


def _clamp01(x: float) -> float:
    """Clamp a value into the unit interval."""
    return max(0.0, min(1.0, x))


def _risk_level(score: float | None) -> str:
    """Classify a composite risk score into a band label."""
    if score is None:
        return "unknown"
    for threshold, label in _RISK_BANDS:
        if score < threshold:
            return label
    return "critical"


def compute_regression_risk(
    rows: list[dict[str, object]],
    status: ReleaseStatus,
    *,
    end: datetime,
    metric: str = "faithfulness",
    days: int = 7,
    n_buckets: int = 7,
) -> RegressionRisk:
    """Blend the recent trend, judge drift and the regression base rate into a risk.

    Args:
        rows: Persisted score rows (any order) with ``scored_at``, ``metric`` and
            ``score`` — the same durable log the rest of the cockpit reads, so the
            risk honours as-of-T when ``end`` is a past instant.
        status: The current release status (its ``regressions`` / ``models_compared``
            supply the empirical base rate).
        end: Right edge of the window — instant T, or "now".
        metric: The judged metric whose trend and drift drive the risk.
        days: Window length in days.
        n_buckets: Number of equal time slices for the trend/drift buckets.

    Returns:
        A :class:`RegressionRisk`. With no judge scores *and* no compared models the
        composite is ``None`` and the level is ``"unknown"`` rather than fabricated.
    """
    series = compute_score_series(rows, metric=metric, end=end, days=days, n_buckets=n_buckets)
    drift = compute_judge_drift(rows, metric=metric, end=end, days=days, n_buckets=n_buckets)
    buckets_used = sum(1 for b in series.buckets if b.mean is not None)

    compared = status.models_compared
    n_reg = status.n_regressions
    regression_rate = (n_reg / compared) if compared else None

    # Each component is a real signal mapped onto 0..1.
    score_component = _clamp01(-series.delta / _SATURATION) if series.delta is not None else 0.0
    drift_component = (
        _clamp01(drift.divergence / _SATURATION) if drift.divergence is not None else 0.0
    )
    regression_component = regression_rate if regression_rate is not None else 0.0

    has_scores = series.n > 0
    has_releases = compared > 0
    if not has_scores and not has_releases:
        risk_score: float | None = None
    else:
        risk_score = round(
            _W_SCORE * score_component
            + _W_REGRESSION * regression_component
            + _W_DRIFT * drift_component,
            3,
        )

    return RegressionRisk(
        metric=metric,
        window_start=series.window_start,
        window_end=series.window_end,
        n=series.n,
        score_delta=series.delta,
        divergence=drift.divergence,
        regression_rate=regression_rate,
        models_compared=compared,
        n_regressions=n_reg,
        score_component=round(score_component, 3),
        drift_component=round(drift_component, 3),
        regression_component=round(regression_component, 3),
        risk_score=risk_score,
        probability_7d=regression_rate,
        level=_risk_level(risk_score),
        buckets_used=buckets_used,
    )
