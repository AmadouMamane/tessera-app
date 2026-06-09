"""Unit tests for cross-session journey (ADR 0010, #99)."""

from __future__ import annotations

from tessera.observability.journey import build_journeys


def test_empty() -> None:
    report = build_journeys([])
    assert report.n_subjects == 0
    assert report.n_returning == 0


def test_single_session() -> None:
    events = [
        ("alice", "memory.write", "2026-06-09T10:00:00+00:00"),
        ("alice", "memory.read", "2026-06-09T10:05:00+00:00"),
    ]
    report = build_journeys(events, session_gap_minutes=30)
    assert report.n_subjects == 1
    j = report.subjects[0]
    assert j.n_sessions == 1
    assert j.returning is False
    assert j.n_writes == 1
    assert j.n_reads == 1


def test_time_gap_splits_sessions() -> None:
    events = [
        ("bob", "memory.read", "2026-06-09T10:00:00+00:00"),
        ("bob", "memory.read", "2026-06-10T10:00:00+00:00"),  # next day → new session
        ("bob", "memory.write", "2026-06-10T10:10:00+00:00"),
    ]
    report = build_journeys(events, session_gap_minutes=30)
    j = report.subjects[0]
    assert j.n_sessions == 2
    assert j.returning is True
    assert report.n_returning == 1
    assert j.span_days >= 1.0


def test_sorted_by_sessions_then_activity() -> None:
    events = [
        ("solo", "memory.read", "2026-06-09T10:00:00+00:00"),
        ("returner", "memory.read", "2026-06-09T10:00:00+00:00"),
        ("returner", "memory.read", "2026-06-11T10:00:00+00:00"),
    ]
    report = build_journeys(events)
    assert report.subjects[0].subject == "returner"


def test_ignores_unparseable_timestamps() -> None:
    report = build_journeys([("x", "memory.read", "not-a-date")])
    assert report.n_subjects == 0
    assert report.n_events == 0
