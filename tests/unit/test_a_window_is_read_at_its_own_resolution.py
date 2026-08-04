"""A 24 h window is a window, not one bar.

Fiabilité & coût offers four analysis windows. The cockpit's window store already held
``h24`` — any SURVEILLER page could set it — but this page cut *every* window into calendar
days, so choosing 24 hours produced a series of exactly **one** point: a "period" with
nothing to compare inside it, a period rail whose "from → to" collapsed onto the same label,
and a preset the ``<select>`` could not even show as chosen (a native select whose value
matches no option silently displays the first one, so the control claimed 7 days while the
page queried 1).

The grain now follows the window instead of the window being clamped to the grain. These
tests pin both halves: that a short window really is read hourly, and that no multi-day
window's numbers moved to get there.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tessera.observability import reliability as rel

_METRIC = rel._TREND_METRICS[0]
_END = datetime(2026, 8, 4, 19, 30, tzinfo=UTC)


def _rows(*offsets: timedelta) -> list[dict[str, object]]:
    """One scored turn per offset *before* the window end."""
    return [
        {"metric": _METRIC, "scored_at": (_END - off).isoformat(), "score": 0.8} for off in offsets
    ]


def _series(rows: list[dict[str, object]], days: int) -> list[rel.DayPoint]:
    return rel._series(
        rows, cost_per_request=0.01, availability=0.99, error_rate=0.01, end=_END, days=days
    )


def test_the_grain_follows_the_window() -> None:
    assert rel.resolution_for(1) == ("hour", 3600)
    assert rel.resolution_for(7) == ("day", 86_400)
    assert rel.resolution_for(14) == ("day", 86_400)
    assert rel.resolution_for(30) == ("day", 86_400)


def test_a_24h_window_is_twenty_four_points_not_one() -> None:
    """The defect, stated as a number: `days=1` used to yield a single bucket."""
    points = _series(_rows(timedelta(hours=2)), 1)
    assert len(points) == rel._HOURS_IN_DAY
    assert (
        len({p.bucket_start for p in points}) == rel._HOURS_IN_DAY
    ), "two buckets share an opening instant — the rail would render duplicate rows"


def test_the_last_hourly_bucket_ends_exactly_at_the_window_end() -> None:
    """A 24 h window read at T must contain T.

    Aligning hourly buckets on the wall clock instead would leave the current, partial hour
    outside the window — the most recent hour is precisely the one an operator opens this
    page for.
    """
    points = _series(_rows(timedelta(minutes=5)), 1)
    last_start = datetime.fromisoformat(points[-1].bucket_start)
    assert last_start + timedelta(hours=1) == _END
    assert points[-1].volume == 1, "a turn 5 minutes old fell outside the last hour"
    assert sum(p.volume for p in points) == 1


def test_each_turn_is_counted_once_in_the_hour_that_contains_it() -> None:
    points = _series(_rows(timedelta(minutes=30), timedelta(hours=1, minutes=30)), 1)
    assert sum(p.volume for p in points) == 2
    assert [p.volume for p in points][-2:] == [1, 1]


def test_a_turn_older_than_the_window_is_not_counted() -> None:
    """Negative control: without it, "24 buckets" could be 24 buckets of everything."""
    points = _series(_rows(timedelta(hours=25), timedelta(days=3)), 1)
    assert sum(p.volume for p in points) == 0


def test_a_multi_day_window_keeps_the_alignment_it_always_had() -> None:
    """Regression control: the fix must not move any number a 7/14/30-day window reported.

    Daily buckets stay keyed on the calendar day, labelled by the day they close, so the
    existing series is byte-for-byte the series it was.
    """
    rows = _rows(timedelta(hours=2), timedelta(days=1), timedelta(days=3))
    points = _series(rows, 7)
    assert len(points) == 7
    assert [p.date for p in points] == [
        (_END - timedelta(days=6 - i)).date().isoformat() for i in range(7)
    ]
    assert sum(p.volume for p in points) == 3
    assert points[-1].volume == 1  # today
    assert points[-2].volume == 1  # yesterday


def test_every_bucket_states_the_instant_it_opens() -> None:
    """``bucket_start`` is a bucket's only unambiguous identity once hours are possible."""
    for days in (1, 7, 30):
        for point in _series(_rows(timedelta(hours=1)), days):
            opened = datetime.fromisoformat(point.bucket_start)
            assert opened.tzinfo is not None, "a bucket instant without a zone is not an instant"
            assert opened <= _END


def test_the_report_says_which_grain_and_which_window_it_used() -> None:
    """The payload carries its own bounds, so no client re-derives them from a point count.

    Constructed directly rather than through ``compute_reliability``: that path needs the
    spine (Postgres/ClickHouse), and what is under test here is the contract the dashboard
    reads, not the data source.
    """
    report = rel.ReliabilityReport(
        availability=0.99,
        error_rate=0.01,
        latency_p50_ms=1.0,
        latency_p95_ms=2.0,
        latency_p99_ms=3.0,
        tool_success=1.0,
        total_cost_eur=0.0,
        cost_per_request_eur=0.0,
        n_requests=0,
        total_tokens=0,
        cache_overhead_pct=0.0,
        within_budget=True,
        budget_monthly_eur=1.0,
        budget_spent_eur=0.0,
        budget_projected_eur=0.0,
    )
    # The defaults describe the common case and never claim an hourly grain by accident.
    assert report.resolution == "day"
    assert report.bucket_seconds == 86_400
    assert report.window_start == "" and report.window_end == ""
