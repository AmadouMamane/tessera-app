"""Unit tests for the calendar-time score series (Vue d'ensemble evolution chart)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability.eval.series import compute_metric_pairs, compute_score_series


def _row(ts: datetime, score: float, metric: str = "faithfulness") -> dict[str, object]:
    return {"scored_at": ts.isoformat(), "metric": metric, "score": score}


def test_empty_series_has_no_fabricated_values() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    s = compute_score_series([], end=end, days=7, n_buckets=7)
    assert s.n == 0
    assert s.mean is None
    assert s.prev_mean is None
    assert s.delta is None
    assert len(s.buckets) == 7
    assert all(b.mean is None and b.n == 0 for b in s.buckets)


def test_buckets_mean_and_period_delta() -> None:
    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    rows = [
        _row(end - timedelta(days=6, hours=1), 0.9),  # first bucket
        _row(end - timedelta(hours=1), 0.5),  # last bucket
        _row(end - timedelta(hours=2), 0.7),  # last bucket
        _row(end - timedelta(days=10), 0.8),  # preceding window
    ]
    s = compute_score_series(rows, end=end, days=7, n_buckets=7)
    assert s.n == 3
    assert s.mean is not None and abs(s.mean - (0.9 + 0.5 + 0.7) / 3) < 1e-9
    assert s.prev_mean == 0.8
    assert s.delta is not None and abs(s.delta - (s.mean - 0.8)) < 1e-9
    # Every in-window score lands in exactly one bucket.
    assert sum(b.n for b in s.buckets) == s.n
    assert s.buckets[0].n == 1
    assert s.buckets[-1].n == 2


def test_other_metrics_are_ignored() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    rows = [_row(end - timedelta(hours=1), 0.9, metric="grounding")]
    s = compute_score_series(rows, end=end, days=7, n_buckets=7)
    assert s.n == 0
    assert s.mean is None


def test_malformed_rows_are_skipped() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    rows = [
        {"scored_at": "not-a-date", "metric": "faithfulness", "score": 0.9},
        {
            "scored_at": (end - timedelta(hours=1)).isoformat(),
            "metric": "faithfulness",
            "score": "x",
        },
        {"metric": "faithfulness", "score": 0.9},
    ]
    s = compute_score_series(rows, end=end, days=7, n_buckets=7)
    assert s.n == 0


def _mrow(conv: str, metric: str, score: float, lang: str = "fr") -> dict[str, object]:
    return {"conversation_id": conv, "metric": metric, "score": score, "language": lang}


def test_metric_pairs_pairs_by_conversation() -> None:
    rows = [
        _mrow("c1", "faithfulness", 0.8),
        _mrow("c1", "grounding", 0.6),
        _mrow("c2", "faithfulness", 0.4),
        _mrow("c2", "grounding", 0.2),
        _mrow("c3", "faithfulness", 0.9),  # no grounding → skipped
    ]
    pairs = compute_metric_pairs(rows, x_metric="faithfulness", y_metric="grounding")
    assert pairs.n == 2
    coords = sorted((p.x, p.y) for p in pairs.points)
    assert coords == [(0.4, 0.2), (0.8, 0.6)]
    assert all(p.language == "fr" for p in pairs.points)


def test_metric_pairs_averages_multi_turn_conversations() -> None:
    rows = [
        _mrow("c1", "faithfulness", 0.6),
        _mrow("c1", "faithfulness", 0.8),
        _mrow("c1", "grounding", 0.5),
    ]
    pairs = compute_metric_pairs(rows, x_metric="faithfulness", y_metric="grounding")
    assert pairs.n == 1
    assert pairs.points[0].x == 0.7  # mean of 0.6, 0.8
    assert pairs.points[0].y == 0.5


# ── judge drift ─────────────────────────────────────────────────────────────────


def _jrow(ts: datetime, score: float, judge: str = "llama3.2:3b") -> dict[str, object]:
    return {
        "scored_at": ts.isoformat(),
        "metric": "faithfulness",
        "score": score,
        "judge_model": judge,
    }


def test_judge_drift_unknown_with_too_few_buckets() -> None:
    from tessera.observability.eval.series import compute_judge_drift

    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    drift = compute_judge_drift([_jrow(end - timedelta(hours=1), 0.9)], end=end, days=7, n_buckets=7)
    assert drift.level == "unknown"
    assert drift.divergence is None
    assert drift.delta is None
    assert drift.judge_model == "llama3.2:3b"


def test_judge_drift_stable_when_score_constant() -> None:
    from tessera.observability.eval.series import compute_judge_drift

    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    # One score in each of the seven daily buckets, all identical → no drift.
    rows = [_jrow(end - timedelta(days=6 - i, hours=1), 0.8) for i in range(7)]
    drift = compute_judge_drift(rows, end=end, days=7, n_buckets=7)
    assert drift.divergence == 0.0
    assert drift.delta == 0.0
    assert drift.level == "stable"


def test_judge_drift_detects_movement() -> None:
    from tessera.observability.eval.series import compute_judge_drift

    end = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
    # Judge mean ramps from 0.9 down to 0.3 across the buckets → clear drift.
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    rows = [_jrow(end - timedelta(days=6 - i, hours=1), s) for i, s in enumerate(scores)]
    drift = compute_judge_drift(rows, end=end, days=7, n_buckets=7)
    assert drift.divergence is not None and drift.divergence > 0.1
    assert drift.delta is not None and drift.delta < 0  # net downward
    assert drift.level in {"moderate", "high", "critical"}
