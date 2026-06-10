"""Unit tests for graph topology versioning (ADR 0010, #87)."""

from __future__ import annotations

from tessera.agent.graph import build_graph
from tessera.observability import graph_topology


def test_snapshot_is_stable_and_matches_golden() -> None:
    snap = graph_topology.topology_snapshot(build_graph())
    # The live graph must match the pinned golden — an unintended reshape fails here.
    assert snap.fingerprint == graph_topology.GOLDEN_FINGERPRINT
    assert snap.n_nodes == len(snap.nodes)
    assert snap.n_edges == len(snap.edges)
    # Re-computing is deterministic.
    again = graph_topology.topology_snapshot(build_graph())
    assert again.fingerprint == snap.fingerprint


def test_compare_topology_flags_no_drift_against_golden() -> None:
    snap = graph_topology.topology_snapshot(build_graph())
    drift = graph_topology.compare_topology(snap, golden=graph_topology.GOLDEN_FINGERPRINT)
    assert drift.drifted is False
    assert drift.fingerprint == drift.golden_fingerprint


def test_compare_topology_flags_drift_against_wrong_fingerprint() -> None:
    snap = graph_topology.topology_snapshot(build_graph())
    drift = graph_topology.compare_topology(snap, golden="deadbeef")
    assert drift.drifted is True
    assert drift.golden_fingerprint == "deadbeef"


def test_diff_snapshots_names_added_and_removed() -> None:
    golden = graph_topology.topology_snapshot(build_graph())
    # Forge a "current" snapshot with a node and edge removed.
    mutated = graph_topology.TopologySnapshot(
        nodes=[n for n in golden.nodes if n != "simulator"],
        edges=[e for e in golden.edges if "simulator" not in e],
        n_nodes=golden.n_nodes - 1,
        n_edges=golden.n_edges - 2,
        fingerprint="forged",
    )
    diff = graph_topology.diff_snapshots(mutated, golden)
    assert diff.drifted is True
    assert "simulator" in diff.removed_nodes
    assert diff.added_nodes == []
    assert any("simulator" in e for e in diff.removed_edges)
