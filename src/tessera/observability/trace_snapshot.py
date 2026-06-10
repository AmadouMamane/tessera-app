"""Golden-trace snapshot diffing (ADR 0010, idea #41).

Where #87 fingerprints the graph *definition*, this catches unintended changes in
the *runtime* trace shape: the set of nodes a turn actually executed. Each turn is
snapshotted and diffed against a recorded golden — the known node universe and the
backbone that every grounded turn must run — so a deploy that introduces a node
that then shows up in a live trace (or a turn that skips the reviewer) is flagged
as drift, the way a golden-snapshot test fails in CI.

It is pure: the route supplies ``(question, executed_nodes)`` per turn, with the
executed nodes read from the captured per-node latency map.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "GOLDEN_KNOWN_NODES",
    "REQUIRED_BACKBONE",
    "SnapshotDiffReport",
    "TurnSnapshot",
    "diff_traces",
]

# The recorded golden node universe (mirrors tessera.agent.graph.build_graph).
# A node appearing in a trace that is *not* here means the graph grew unexpectedly.
GOLDEN_KNOWN_NODES = frozenset(
    {
        "router",
        "planner",
        "reviewer",
        "reporter",
        "product_lookup",
        "regulation_lookup",
        "account_lookup",
        "simulator",
        "escalation_worker",
    }
)

# The spine every grounded (non-injection) turn must run. Reporter is excluded:
# capture happens at the reviewer boundary, so it is not always in the latency map.
REQUIRED_BACKBONE = frozenset({"router", "planner", "reviewer"})


@dataclass(frozen=True, slots=True)
class TurnSnapshot:
    """The trace-shape snapshot of a single turn diffed against the golden."""

    question: str
    executed: list[str]
    unknown_nodes: list[str]  # ran but not in the golden node universe
    missing_required: list[str]  # required backbone nodes that did not run
    matches_golden: bool


@dataclass(frozen=True, slots=True)
class SnapshotDiffReport:
    """Aggregate golden-trace diffing across captured turns."""

    n_turns: int
    n_matching: int
    n_drifted: int
    known_nodes: list[str]
    required_backbone: list[str]
    drifts: list[TurnSnapshot] = field(default_factory=list)


def _snapshot(
    question: str, executed: list[str], known: frozenset[str], required: frozenset[str]
) -> TurnSnapshot:
    """Diff one turn's executed nodes against the golden known/required sets."""
    ran = set(executed)
    unknown = sorted(ran - known)
    missing = sorted(required - ran)
    return TurnSnapshot(
        question=question,
        executed=executed,
        unknown_nodes=unknown,
        missing_required=missing,
        matches_golden=not unknown and not missing,
    )


def diff_traces(
    turns: list[tuple[str, list[str]]],
    *,
    known: frozenset[str] = GOLDEN_KNOWN_NODES,
    required: frozenset[str] = REQUIRED_BACKBONE,
) -> SnapshotDiffReport:
    """Diff each turn's executed-node snapshot against the golden.

    Args:
        turns: ``(question, executed_nodes)`` per captured turn.
        known: The golden node universe; a node outside it is unexpected.
        required: The backbone nodes every grounded turn must run.

    Returns:
        A :class:`SnapshotDiffReport` listing the drifted turns (those running an
        unknown node or missing a required backbone node).
    """
    snaps = [_snapshot(q, nodes, known, required) for q, nodes in turns]
    drifts = [s for s in snaps if not s.matches_golden]
    return SnapshotDiffReport(
        n_turns=len(snaps),
        n_matching=len(snaps) - len(drifts),
        n_drifted=len(drifts),
        known_nodes=sorted(known),
        required_backbone=sorted(required),
        drifts=drifts,
    )
