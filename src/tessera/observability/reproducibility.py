"""Reproducibility hash / non-determinism detection (ADR 0010, idea #86).

Deterministic replay (#1) only means something if the same input yields the same
*trace structure*: if asking the same question sometimes runs a different set of
nodes, a replay can't be trusted as a regression baseline. This module hashes the
executed-node sequence of each turn into a stable **trace-shape hash**, groups
turns by their (normalised) question, and flags any question that produced more
than one distinct shape — non-determinism in the graph runtime.

It is pure: the route supplies ``(question, executed_nodes)`` per turn, where the
executed nodes come from the captured per-node latency map.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

__all__ = [
    "Divergence",
    "ReproReport",
    "detect_nondeterminism",
    "trace_shape_hash",
]


def trace_shape_hash(node_names: list[str]) -> str:
    """Return a stable short hash of an executed-node sequence (order-sensitive).

    Args:
        node_names: The nodes that ran, in execution order.

    Returns:
        The first 16 hex chars of a SHA-256 over the ``>``-joined sequence.
    """
    signature = ">".join(node_names)
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Divergence:
    """A question that produced more than one trace shape."""

    question: str
    n_runs: int
    n_variants: int
    shapes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReproReport:
    """Aggregate non-determinism findings across captured turns."""

    n_turns: int
    n_groups: int
    n_repeated_inputs: int  # questions seen more than once
    n_nondeterministic: int
    divergences: list[Divergence] = field(default_factory=list)


def _normalise(question: str) -> str:
    """Collapse whitespace and case so re-asks group together."""
    return " ".join(question.lower().split())


def detect_nondeterminism(turns: list[tuple[str, list[str]]]) -> ReproReport:
    """Group turns by question and flag those with divergent trace shapes.

    Args:
        turns: ``(question, executed_nodes)`` per captured turn.

    Returns:
        A :class:`ReproReport`. A question whose repeats produced more than one
        distinct shape hash is a non-determinism divergence.
    """
    groups: dict[str, list[tuple[str, str]]] = {}  # key -> [(original_question, shape)]
    for question, nodes in turns:
        groups.setdefault(_normalise(question), []).append((question, trace_shape_hash(nodes)))

    n_repeated = 0
    divergences: list[Divergence] = []
    for runs in groups.values():
        if len(runs) > 1:
            n_repeated += 1
        shapes = sorted({shape for _q, shape in runs})
        if len(shapes) > 1:
            divergences.append(
                Divergence(
                    question=runs[0][0],
                    n_runs=len(runs),
                    n_variants=len(shapes),
                    shapes=shapes,
                )
            )
    return ReproReport(
        n_turns=len(turns),
        n_groups=len(groups),
        n_repeated_inputs=n_repeated,
        n_nondeterministic=len(divergences),
        divergences=divergences,
    )
