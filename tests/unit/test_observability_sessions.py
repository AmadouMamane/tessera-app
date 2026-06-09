"""Unit tests for session goal-completion metrics (ADR 0010, #21)."""

from __future__ import annotations

import pytest

from tessera.observability.sessions import aggregate_sessions


def test_aggregate_sessions_groups_by_conversation() -> None:
    turns = [
        ("conv-a", 0.9),
        ("conv-a", 0.7),  # conv-a has 2 turns
        ("conv-b", 0.5),  # conv-b has 1 turn (single-turn session)
    ]
    report = aggregate_sessions(turns)
    assert report.n_sessions == 2
    assert report.total_turns == 3
    assert report.mean_turns_per_session == pytest.approx(1.5)
    assert report.single_turn_rate == pytest.approx(0.5)
    assert report.mean_score == pytest.approx((0.9 + 0.7 + 0.5) / 3)


def test_aggregate_sessions_empty() -> None:
    report = aggregate_sessions([])
    assert report.n_sessions == 0
    assert report.mean_turns_per_session == 0.0
    assert report.single_turn_rate == 0.0
