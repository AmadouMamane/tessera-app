"""Unit tests for golden-trace snapshot diffing (ADR 0010, #41)."""

from __future__ import annotations

from tessera.agent.graph import build_graph
from tessera.observability import trace_snapshot


def test_golden_known_nodes_match_the_graph() -> None:
    # The pinned golden universe must equal the live graph's real nodes — an
    # unintended node add/remove in build_graph fails this assertion.
    graph_nodes = {str(n) for n in build_graph().nodes}
    assert graph_nodes == set(trace_snapshot.GOLDEN_KNOWN_NODES)


def test_backbone_turn_matches_golden() -> None:
    turns = [("balance?", ["router", "planner", "account_lookup", "reviewer"])]
    report = trace_snapshot.diff_traces(turns)
    assert report.n_turns == 1
    assert report.n_matching == 1
    assert report.n_drifted == 0


def test_unknown_node_is_drift() -> None:
    turns = [("q", ["router", "planner", "reviewer", "mystery_node"])]
    report = trace_snapshot.diff_traces(turns)
    assert report.n_drifted == 1
    assert report.drifts[0].unknown_nodes == ["mystery_node"]


def test_missing_required_backbone_is_drift() -> None:
    turns = [("q", ["router", "planner"])]  # no reviewer
    report = trace_snapshot.diff_traces(turns)
    assert report.n_drifted == 1
    assert report.drifts[0].missing_required == ["reviewer"]
    assert report.drifts[0].matches_golden is False


def test_report_carries_golden_sets() -> None:
    report = trace_snapshot.diff_traces([])
    assert "router" in report.known_nodes
    assert set(report.required_backbone) == set(trace_snapshot.REQUIRED_BACKBONE)
