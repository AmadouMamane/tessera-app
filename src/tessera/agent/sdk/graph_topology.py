"""Graph topology versioning (ADR 0010, idea #87).

The agent's behaviour is shaped by the *structure* of its LangGraph: which nodes
exist and how they are wired. An unintended edit to :func:`tessera.agent.graph.build_graph`
— a worker dropped from the fan-out, an edge rerouted — can silently change what
the agent does without any test failing on a specific input. This module turns
the live graph into a stable, hashable **topology fingerprint** and diffs it
against a pinned *golden* fingerprint, so a deploy that reshapes the graph raises
a visible drift signal (the runtime analogue of #41's CI snapshot diff).

It is pure and read-only: it inspects the built (uncompiled) ``StateGraph`` and
never runs the agent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.graph import StateGraph

    from tessera.agent.state import AgentState

    AgentStateGraph = StateGraph[AgentState]

__all__ = [
    "GOLDEN_FINGERPRINT",
    "TopologyDrift",
    "TopologySnapshot",
    "compare_topology",
    "topology_snapshot",
]


@dataclass(frozen=True, slots=True)
class TopologySnapshot:
    """A canonical, hashable description of a graph's structure."""

    nodes: list[str]
    edges: list[str]  # "src->dst", sorted; includes conditional-branch targets
    n_nodes: int
    n_edges: int
    fingerprint: str  # SHA-256 over the canonical signature


@dataclass(frozen=True, slots=True)
class TopologyDrift:
    """The difference between a current snapshot and the golden fingerprint."""

    drifted: bool
    fingerprint: str
    golden_fingerprint: str
    added_nodes: list[str] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    added_edges: list[str] = field(default_factory=list)
    removed_edges: list[str] = field(default_factory=list)
    n_nodes: int = 0
    n_edges: int = 0


def _branch_edges(graph: AgentStateGraph) -> set[str]:
    """Collect ``src->dst`` edges contributed by conditional branches."""
    edges: set[str] = set()
    branches = getattr(graph, "branches", {}) or {}
    for source, named in branches.items():
        for branch in named.values():
            ends = getattr(branch, "ends", None) or {}
            for target in ends.values():
                edges.add(f"{source}->{target}")
    return edges


def topology_snapshot(graph: AgentStateGraph) -> TopologySnapshot:
    """Compute the canonical topology snapshot of a built ``StateGraph``.

    Args:
        graph: The uncompiled graph from :func:`tessera.agent.graph.build_graph`.

    Returns:
        A :class:`TopologySnapshot` whose ``fingerprint`` is a SHA-256 over the
        sorted node and edge lists — stable across runs, sensitive to any added,
        removed, or rerouted node/edge.
    """
    nodes = sorted(str(n) for n in graph.nodes)
    direct = {f"{src}->{dst}" for src, dst in getattr(graph, "edges", set())}
    edges = sorted(direct | _branch_edges(graph))
    signature = "nodes:" + ",".join(nodes) + "|edges:" + ",".join(edges)
    fingerprint = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return TopologySnapshot(
        nodes=nodes,
        edges=edges,
        n_nodes=len(nodes),
        n_edges=len(edges),
        fingerprint=fingerprint,
    )


def compare_topology(current: TopologySnapshot, *, golden: str) -> TopologyDrift:
    """Diff ``current`` against the pinned ``golden`` fingerprint.

    When the fingerprints match, the drift fields are empty. They are populated
    only when the structure changed — but the node/edge deltas are computed from
    the snapshot alone, so a caller wanting the *named* changes must also pass the
    golden snapshot's node/edge lists; here we report drift presence plus the
    current structure, which the dashboard surfaces against the recorded golden.

    Args:
        current: The freshly computed topology snapshot.
        golden: The expected (pinned) fingerprint to compare against.

    Returns:
        A :class:`TopologyDrift` flagging whether the topology changed.
    """
    return TopologyDrift(
        drifted=current.fingerprint != golden,
        fingerprint=current.fingerprint,
        golden_fingerprint=golden,
        n_nodes=current.n_nodes,
        n_edges=current.n_edges,
    )


def diff_snapshots(current: TopologySnapshot, golden: TopologySnapshot) -> TopologyDrift:
    """Diff two snapshots, naming the added/removed nodes and edges.

    Args:
        current: The live topology snapshot.
        golden: The recorded golden snapshot.

    Returns:
        A :class:`TopologyDrift` with the symmetric node/edge differences.
    """
    cur_nodes, gold_nodes = set(current.nodes), set(golden.nodes)
    cur_edges, gold_edges = set(current.edges), set(golden.edges)
    return TopologyDrift(
        drifted=current.fingerprint != golden.fingerprint,
        fingerprint=current.fingerprint,
        golden_fingerprint=golden.fingerprint,
        added_nodes=sorted(cur_nodes - gold_nodes),
        removed_nodes=sorted(gold_nodes - cur_nodes),
        added_edges=sorted(cur_edges - gold_edges),
        removed_edges=sorted(gold_edges - cur_edges),
        n_nodes=current.n_nodes,
        n_edges=current.n_edges,
    )


# The golden fingerprint of the current, reviewed agent graph. Regenerate via
# ``topology_snapshot(build_graph()).fingerprint`` and update here intentionally
# whenever the graph is reshaped on purpose — an *unexpected* change shows up as
# drift on the dashboard and in CI.
GOLDEN_FINGERPRINT = "c4a95878d4f54985cfc171a0373ad6e0341f00694dcaa6a38df977ed6ac20851"
