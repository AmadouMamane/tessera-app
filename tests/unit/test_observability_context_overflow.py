"""Unit tests for context truncation/overflow observability (ADR 0010, #89)."""

from __future__ import annotations

from tessera.observability import context_overflow


def test_no_overflow_under_budget() -> None:
    report = context_overflow.analyze_overflow(
        [("q1", ["short chunk", "another short one"])], window_tokens=8192
    )
    assert report.n_turns == 1
    assert report.n_overflowed == 0
    assert report.overflow_rate == 0.0
    assert report.turns[0].n_dropped == 0
    assert report.turns[0].overflowed is False


def test_overflow_drops_trailing_chunks() -> None:
    # Two ~400-token chunks (1600 chars); usable=500 → first fits, second drops.
    big = "x " * 800  # ~1600 chars ≈ 400 tokens
    report = context_overflow.analyze_overflow([("q", [big, big])], window_tokens=1024 + 500)
    turn = report.turns[0]
    assert turn.overflowed is True
    assert turn.n_dropped == 1
    assert report.overflow_rate == 1.0


def test_usable_subtracts_reservation() -> None:
    report = context_overflow.analyze_overflow([], window_tokens=8192)
    assert report.usable_tokens == 8192 - 1024
    assert report.window_tokens == 8192
    assert report.max_context_tokens == 0


def test_max_context_tokens_is_reported() -> None:
    report = context_overflow.analyze_overflow(
        [("q1", ["a b c d"]), ("q2", ["a much longer chunk of text here repeated " * 5])]
    )
    assert report.max_context_tokens > 0
    assert report.n_turns == 2
