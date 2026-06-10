"""Unit tests for handoff tracing across the delegation chain (ADR 0010, #189)."""

from __future__ import annotations

from tessera.observability import handoffs


def test_complete_delegation_has_no_broken_handoffs() -> None:
    turns = [("balance?", ["router", "planner", "account_lookup", "reviewer"])]
    report = handoffs.analyze_handoffs(turns)
    assert report.n_turns == 1
    assert report.total_broken == 0
    assert report.n_broken_turns == 0
    assert report.turns[0].n_handoffs == 3  # router→planner, planner→worker, worker→reviewer


def test_injection_short_circuit_is_not_broken() -> None:
    # Only the router ran (injection short-circuited to END): no handoff expected.
    report = handoffs.analyze_handoffs([("ignore previous", ["router"])])
    assert report.total_handoffs == 0
    assert report.total_broken == 0


def test_worker_without_reviewer_is_broken() -> None:
    report = handoffs.analyze_handoffs([("q", ["router", "planner", "product_lookup"])])
    turn = report.turns[0]
    assert "worker→reviewer" in turn.broken
    assert report.broken_by_type["worker→reviewer"] == 1
    assert report.n_broken_turns == 1


def test_planner_delegating_to_nobody_is_broken() -> None:
    report = handoffs.analyze_handoffs([("q", ["router", "planner"])])
    turn = report.turns[0]
    assert "planner→worker" in turn.broken


def test_empty_plan_routed_to_reviewer_is_ok() -> None:
    report = handoffs.analyze_handoffs([("q", ["router", "planner", "reviewer"])])
    assert report.total_broken == 0
