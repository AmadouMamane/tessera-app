"""Unit tests for anomalous-conversation detection (ADR 0010, #69)."""

from __future__ import annotations

from tessera.observability import anomalies


def test_normal_session_not_flagged() -> None:
    sessions = {"c1": ["What is my balance?", "How do I block my card?"]}
    report = anomalies.detect_anomalies(sessions)
    assert report.n_anomalous == 0
    assert report.sessions[0].anomalous is False


def test_repetitive_session_flagged() -> None:
    sessions = {"c1": ["What is my balance?", "what is my balance?", "What is my BALANCE?"]}
    report = anomalies.detect_anomalies(sessions)
    session = report.sessions[0]
    assert session.anomalous is True
    assert "repetitive" in session.reasons
    # All three normalise to the same string → distinct ratio 1/3 → looping.
    assert "looping" in session.reasons


def test_long_session_flagged() -> None:
    sessions = {"c1": [f"distinct question number {i}" for i in range(6)]}
    report = anomalies.detect_anomalies(sessions)
    session = report.sessions[0]
    assert "long" in session.reasons
    assert session.anomalous is True


def test_aggregate_counts() -> None:
    sessions = {
        "c1": ["balance?", "balance?"],  # repetitive
        "c2": ["block card", "open account"],  # normal
    }
    report = anomalies.detect_anomalies(sessions)
    assert report.n_sessions == 2
    assert report.n_anomalous == 1
