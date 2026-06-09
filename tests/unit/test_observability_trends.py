"""Unit tests for long-horizon trend analysis (ADR 0010, #150)."""

from __future__ import annotations

from tessera.observability.trends import analyze_trend


def _points(scores: list[float]) -> list[tuple[str, float]]:
    return [(f"2026-06-09T00:00:{i:02d}+00:00", s) for i, s in enumerate(scores)]


def test_empty() -> None:
    report = analyze_trend([])
    assert report.n == 0
    assert report.direction == "stable"
    assert report.degrading is False
    assert report.buckets == []


def test_too_few_points_stays_stable() -> None:
    report = analyze_trend(_points([0.9, 0.1]))
    assert report.n == 2
    assert report.slope == 0.0
    assert report.direction == "stable"
    assert report.degrading is False


def test_steady_decline_is_degrading() -> None:
    report = analyze_trend(_points([0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]))
    assert report.slope < 0
    assert report.direction == "degrading"
    assert report.delta < 0
    assert report.degrading is True


def test_steady_improvement() -> None:
    report = analyze_trend(_points([0.3, 0.4, 0.5, 0.6, 0.7, 0.8]))
    assert report.slope > 0
    assert report.direction == "improving"
    assert report.degrading is False


def test_flat_series_is_stable() -> None:
    report = analyze_trend(_points([0.8, 0.8, 0.8, 0.8, 0.8]))
    assert abs(report.slope) < 1e-9
    assert report.direction == "stable"
    assert report.degrading is False


def test_late_single_dip_not_flagged_degrading() -> None:
    # A long flat history with one final dip: the half-over-half delta is small,
    # so it must not be called a slow degradation.
    report = analyze_trend(_points([0.9] * 19 + [0.2]))
    assert report.degrading is False


def test_buckets_capped_and_cover_all() -> None:
    report = analyze_trend(_points([0.5] * 40))
    assert len(report.buckets) == 8
    assert sum(b.n for b in report.buckets) == 40
