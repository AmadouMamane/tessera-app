"""Unit tests for cost / token-burn anomaly detection (ADR 0010, #33)."""

from __future__ import annotations

from tessera.observability import cost_anomaly as ca


def test_estimate_tokens() -> None:
    assert ca.estimate_tokens("a" * 40) == 10
    assert ca.estimate_tokens("") == 1


def test_empty_is_zero() -> None:
    report = ca.analyze_costs([])
    assert report.n_turns == 0
    assert report.n_anomalies == 0


def test_outlier_turn_flagged() -> None:
    turns = [
        ("q1", "x" * 40),
        ("q2", "x" * 40),
        ("q3", "x" * 40),
        ("loop", "x" * 4000),  # huge — token-burn outlier
    ]
    report = ca.analyze_costs(turns)
    assert report.n_anomalies == 1
    assert report.anomalies[0].question == "loop"
    assert report.max_tokens == 1000


def test_uniform_turns_no_anomaly() -> None:
    turns = [("q", "x" * 40) for _ in range(5)]
    report = ca.analyze_costs(turns)
    assert report.n_anomalies == 0
