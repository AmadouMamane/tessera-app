"""Unit tests for the composite regression-risk signal (Signaux prédictifs)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability.eval.releases import ReleaseStatus
from tessera.observability.eval.risk import compute_regression_risk


def _row(ts: datetime, score: float, metric: str = "faithfulness") -> dict[str, object]:
    return {"scored_at": ts.isoformat(), "metric": metric, "score": score}


def _status(*, n_regressions: int = 0, compared: int = 0) -> ReleaseStatus:
    rate = (compared - n_regressions) / compared if compared else 1.0
    return ReleaseStatus(
        current=None,
        n_regressions=n_regressions,
        models_compared=compared,
        non_regression_rate=rate,
    )


def test_no_data_is_unknown_not_fabricated() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    risk = compute_regression_risk([], _status(), end=end)
    assert risk.risk_score is None
    assert risk.probability_7d is None
    assert risk.level == "unknown"
    assert risk.score_component == 0.0
    assert risk.regression_component == 0.0


def test_probability_is_empirical_regression_base_rate() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    # 1 of 4 compared models regressed → a 25% empirical base rate.
    risk = compute_regression_risk([], _status(n_regressions=1, compared=4), end=end)
    assert risk.probability_7d == 0.25
    assert risk.regression_component == 0.25
    # Only the regression component fires (no score trend, no drift).
    assert risk.risk_score == round(0.35 * 0.25, 3)
    assert risk.level == "low"


def test_falling_trend_raises_risk() -> None:
    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    # Prior window high, current window low → a clear downward delta.
    rows = [
        _row(end - timedelta(days=10), 0.9),  # preceding window
        _row(end - timedelta(days=6), 0.9),  # current, early bucket
        _row(end - timedelta(hours=2), 0.5),  # current, late bucket
    ]
    risk = compute_regression_risk(rows, _status(), end=end)
    assert risk.score_delta is not None and risk.score_delta < 0
    assert risk.score_component > 0.0
    assert risk.risk_score is not None and risk.risk_score > 0.0


def test_risk_score_is_bounded_and_banded() -> None:
    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    # Severe drop + every compared model regressed → risk pinned near the top.
    rows = [
        _row(end - timedelta(days=10), 1.0),
        _row(end - timedelta(days=6), 1.0),
        _row(end - timedelta(hours=1), 0.0),
    ]
    risk = compute_regression_risk(rows, _status(n_regressions=3, compared=3), end=end)
    assert risk.risk_score is not None and 0.0 <= risk.risk_score <= 1.0
    assert risk.level in {"high", "critical"}
