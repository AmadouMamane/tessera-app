"""The calibrated fidelity floor is derived, never hand-picked (ADR 0054 §4-§5).

The rule under test: a labeled violation must never pass, so the suggested threshold is
the smallest OBSERVED faithful score strictly above every violation score — and when the
judge cannot separate the labels, the function must say so instead of inventing a floor.
"""

from __future__ import annotations

from eval.reformulation_bench import suggest_fidelity_threshold


def test_clean_separation_picks_the_smallest_clearing_faithful_score() -> None:
    result = suggest_fidelity_threshold([0.9, 0.95, 1.0], [0.2, 0.5, 0.6])
    assert result["separates"] is True
    assert result["suggested_threshold"] == 0.9
    assert result["faithful_accepted"] == 3
    assert result["faithful_refused"] == 0
    assert result["violations_max"] == 0.6


def test_overlap_costs_faithful_candidates_but_never_accepts_a_violation() -> None:
    # One faithful candidate scores below the worst violation: the floor sits above it,
    # that candidate falls back to the exact template, and no violation clears.
    result = suggest_fidelity_threshold([0.7, 0.95, 1.0], [0.8])
    assert result["suggested_threshold"] == 0.95
    assert result["faithful_accepted"] == 2
    assert result["faithful_refused"] == 1


def test_no_separation_yields_no_threshold_not_a_guess() -> None:
    # The judge scores violations as high as everything faithful: unusable at any floor.
    result = suggest_fidelity_threshold([0.8, 0.9], [0.9, 0.95])
    assert result["separates"] is False
    assert result["suggested_threshold"] is None
    assert result["faithful_accepted"] == 0


def test_no_scored_violations_is_low_power_not_a_free_pass() -> None:
    # Nothing measured to refuse: the floor is the smallest observed faithful score —
    # still data-derived — and the zero violation count travels with it.
    result = suggest_fidelity_threshold([0.85, 0.9], [])
    assert result["suggested_threshold"] == 0.85
    assert result["violations_scored"] == 0
    assert result["violations_max"] is None


def test_nothing_scored_at_all_yields_nothing() -> None:
    result = suggest_fidelity_threshold([], [])
    assert result["separates"] is False
    assert result["suggested_threshold"] is None
    assert result["faithful_scored"] == 0
