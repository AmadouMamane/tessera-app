"""Unit tests for cost-of-observability (ADR 0010, #84)."""

from __future__ import annotations

from tessera.observability.obs_cost import measure_overhead


def test_report_shape_and_bounds() -> None:
    report = measure_overhead(iterations=200, warmup=20)
    assert report.iterations == 200
    assert report.span_overhead_us > 0.0
    assert report.spans_per_turn == 8
    # Per-turn projection is consistent with per-span overhead.
    expected = report.span_overhead_us * report.spans_per_turn / 1000.0
    assert abs(report.overhead_per_turn_ms - expected) < 1e-9


def test_volume_estimate() -> None:
    report = measure_overhead(iterations=100, warmup=0, spans_per_turn=4)
    assert report.spans_per_turn == 4
    assert report.est_bytes_per_turn == report.est_bytes_per_span * 4


def test_overhead_is_a_small_fraction_of_budget() -> None:
    # Span creation is microseconds; a turn budget is seconds — the projected
    # overhead must be a tiny fraction of the budget, hence within budget.
    report = measure_overhead(iterations=500, warmup=50)
    assert report.overhead_pct_of_budget < 100.0
    assert report.within_budget is True


def test_iterations_floored_at_one() -> None:
    report = measure_overhead(iterations=0)
    assert report.iterations == 1
    assert report.span_overhead_us >= 0.0
