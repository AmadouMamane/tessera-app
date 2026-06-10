"""Unit tests for reproducibility / non-determinism detection (ADR 0010, #86)."""

from __future__ import annotations

from tessera.observability import reproducibility


def test_shape_hash_is_order_sensitive_and_stable() -> None:
    a = reproducibility.trace_shape_hash(["router", "planner", "reviewer"])
    b = reproducibility.trace_shape_hash(["router", "planner", "reviewer"])
    c = reproducibility.trace_shape_hash(["router", "reviewer", "planner"])
    assert a == b
    assert a != c
    assert len(a) == 16


def test_deterministic_repeats_flag_nothing() -> None:
    turns = [
        ("What is my balance?", ["router", "planner", "account_lookup", "reviewer"]),
        ("what is my balance?", ["router", "planner", "account_lookup", "reviewer"]),
    ]
    report = reproducibility.detect_nondeterminism(turns)
    assert report.n_turns == 2
    assert report.n_repeated_inputs == 1
    assert report.n_nondeterministic == 0


def test_divergent_shape_is_flagged() -> None:
    turns = [
        ("Tell me about DORA", ["router", "planner", "regulation_lookup", "reviewer"]),
        ("tell me about dora", ["router", "planner", "regulation_lookup", "reviewer", "reporter"]),
    ]
    report = reproducibility.detect_nondeterminism(turns)
    assert report.n_nondeterministic == 1
    div = report.divergences[0]
    assert div.n_runs == 2
    assert div.n_variants == 2
    assert len(div.shapes) == 2


def test_distinct_questions_are_not_compared() -> None:
    turns = [
        ("question one", ["router", "planner"]),
        ("question two", ["router", "reviewer"]),
    ]
    report = reproducibility.detect_nondeterminism(turns)
    assert report.n_groups == 2
    assert report.n_repeated_inputs == 0
    assert report.n_nondeterministic == 0
