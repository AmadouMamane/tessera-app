"""Handoff tracing across the delegation chain (ADR 0010, idea #189).

The agent works by delegation: the router hands off to the planner, the planner
fans out to workers, and the workers hand back to the reviewer. A *broken
handoff* — a planner that delegates to no one, a worker that never rejoins the
reviewer — is a structural failure the per-input tests don't catch. This module
reconstructs the delegation chain from a turn's executed-node set and checks each
expected handoff completed.

It checks delegation as set membership rather than linear adjacency, because the
workers fan out in parallel (so their relative order is not a causal handoff).
It is pure: the route supplies ``(question, executed_nodes)`` per turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "WORKER_NODES",
    "HandoffReport",
    "HandoffTurn",
    "analyze_handoffs",
]

WORKER_NODES = frozenset(
    {"product_lookup", "regulation_lookup", "account_lookup", "simulator", "escalation_worker"}
)


@dataclass(frozen=True, slots=True)
class HandoffTurn:
    """The delegation-chain health of a single turn."""

    question: str
    n_handoffs: int
    n_broken: int
    broken: list[str] = field(default_factory=list)  # e.g. "planner→worker"


@dataclass(frozen=True, slots=True)
class HandoffReport:
    """Aggregate handoff-tracing findings across captured turns."""

    n_turns: int
    n_broken_turns: int
    total_handoffs: int
    total_broken: int
    broken_by_type: dict[str, int] = field(default_factory=dict)
    turns: list[HandoffTurn] = field(default_factory=list)


def _trace_turn(question: str, executed: set[str]) -> HandoffTurn:
    """Check the expected handoffs for one turn's executed-node set."""
    broken: list[str] = []
    n_handoffs = 0
    has_worker = bool(executed & WORKER_NODES)

    # router → planner: the router delegates to the planner unless it short-circuited
    # to END on an injection (only the router ran).
    if "router" in executed and executed != {"router"}:
        n_handoffs += 1
        if "planner" not in executed:
            broken.append("router→planner")

    # planner → workers: the planner must delegate to at least one worker, or route
    # an empty plan straight to the reviewer.
    if "planner" in executed:
        n_handoffs += 1
        if not has_worker and "reviewer" not in executed:
            broken.append("planner→worker")

    # workers → reviewer: every data worker hands back to the reviewer.
    if has_worker:
        n_handoffs += 1
        if "reviewer" not in executed:
            broken.append("worker→reviewer")

    return HandoffTurn(
        question=question, n_handoffs=n_handoffs, n_broken=len(broken), broken=broken
    )


def analyze_handoffs(turns: list[tuple[str, list[str]]]) -> HandoffReport:
    """Trace the delegation chain of each turn and flag broken handoffs.

    Args:
        turns: ``(question, executed_nodes)`` per captured turn.

    Returns:
        A :class:`HandoffReport` with per-turn handoff health and aggregate
        counts of each broken handoff type.
    """
    rows = [_trace_turn(q, set(nodes)) for q, nodes in turns]
    by_type: dict[str, int] = {}
    for row in rows:
        for edge in row.broken:
            by_type[edge] = by_type.get(edge, 0) + 1
    return HandoffReport(
        n_turns=len(rows),
        n_broken_turns=sum(1 for r in rows if r.n_broken > 0),
        total_handoffs=sum(r.n_handoffs for r in rows),
        total_broken=sum(r.n_broken for r in rows),
        broken_by_type=by_type,
        turns=rows,
    )
