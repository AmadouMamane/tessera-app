"""Unit tests for the per-severity-band score-count trend (Signaux KPI strip)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability.eval.series import compute_status_counts_trend


def _row(ts: datetime, score: float, metric: str = "faithfulness") -> dict[str, object]:
    return {"scored_at": ts.isoformat(), "metric": metric, "score": score}


def test_empty_is_all_zeros() -> None:
    end = datetime(2026, 6, 12, tzinfo=UTC)
    t = compute_status_counts_trend([], end=end, days=7)
    assert t.n_buckets == 7
    assert t.active.counts == [0] * 7
    assert t.active.total == 0
    assert t.crit.delta == 0  # 7 daily buckets ⇒ a real (zero) day-over-day delta


def test_bands_classify_and_count() -> None:
    end = datetime(2026, 6, 12, 23, 0, tzinfo=UTC)
    rows = [
        _row(end - timedelta(hours=1), 0.4),  # crit (<0.6), last day
        _row(end - timedelta(hours=2), 0.7),  # warn (<0.8), last day
        _row(end - timedelta(hours=3), 0.9),  # ok, last day
        _row(end - timedelta(days=6, hours=1), 0.95),  # ok, first day
    ]
    t = compute_status_counts_trend(rows, end=end, days=7, warn_threshold=0.8, crit_threshold=0.6)
    assert t.active.total == 4
    assert t.crit.total == 1
    assert t.warn.total == 1
    assert t.ok.total == 2
    # The last bucket holds 3 scores; the first holds 1.
    assert t.active.counts[-1] == 3
    assert t.active.counts[0] == 1


def test_delta_is_last_vs_previous_bucket() -> None:
    end = datetime(2026, 6, 12, 23, 0, tzinfo=UTC)
    rows = [
        _row(end - timedelta(days=1, hours=1), 0.4),  # crit, previous day
        _row(end - timedelta(hours=1), 0.4),  # crit, last day
        _row(end - timedelta(hours=2), 0.4),  # crit, last day
    ]
    t = compute_status_counts_trend(rows, end=end, days=7)
    # last bucket 2 crit, previous bucket 1 crit → delta +1
    assert t.crit.delta == 1
