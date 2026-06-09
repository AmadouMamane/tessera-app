"""Unit tests for conversation funnel per language (ADR 0010, #66)."""

from __future__ import annotations

from tessera.observability import funnel


def test_empty() -> None:
    report = funnel.aggregate_funnel([])
    assert report.n_turns == 0
    assert report.languages == []


def test_per_language_breakdown() -> None:
    turns = [
        ("fr", "c1", 0.9),
        ("fr", "c1", 0.8),  # c1 is multi-turn
        ("fr", "c2", 0.3),  # low score, single-turn session
        ("de", "c3", 1.0),  # single-turn
    ]
    report = funnel.aggregate_funnel(turns)
    assert report.n_turns == 4
    by_lang = {f.language: f for f in report.languages}

    fr = by_lang["fr"]
    assert fr.n_turns == 3
    assert fr.n_sessions == 2
    assert fr.single_turn_rate == 0.5  # c2 single, c1 multi
    assert round(fr.low_score_rate, 3) == round(1 / 3, 3)

    de = by_lang["de"]
    assert de.n_turns == 1
    assert de.single_turn_rate == 1.0
    assert de.low_score_rate == 0.0
