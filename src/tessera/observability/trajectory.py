"""Agent-trajectory time-travel — "session theater" (ADR 0010, ideas #40/#113).

A captured turn already holds everything needed to *replay its journey* for a
human: the question, whether the guard let it through, what was retrieved and
from where (lineage), how long each LangGraph node took (latency waterfall), and
the final answer with its faithfulness score. This module flattens all of that
into an ordered list of steps so the dashboard can step through a turn like a
debugger — the on-screen demo object.

It is read-only and side-effect free: the input guard is re-evaluated by matching
deny patterns directly, so opening the theater never writes to the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.guard.decisions import load_policy

if TYPE_CHECKING:
    from tessera.guard.decisions import Policy
    from tessera.observability.replay import ReplayBundle

__all__ = ["Trajectory", "TrajectoryStep", "build_trajectory"]


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """One step in a turn's journey, for step-through replay."""

    index: int
    kind: str  # input | guard | retrieval | node | answer
    title: str
    detail: str
    duration_ms: float
    status: str  # ok | warn | info


@dataclass(frozen=True, slots=True)
class Trajectory:
    """The full step-by-step trajectory of one captured turn."""

    bundle_id: str
    language: str
    model: str
    score: float
    total_ms: float
    n_steps: int
    steps: list[TrajectoryStep] = field(default_factory=list)


def _guard_denied(text: str, policy: Policy) -> bool:
    """Re-evaluate the input guard without the audit side effect."""
    return any(pattern.search(text) for pattern in policy.prompt_injection_deny)


def build_trajectory(bundle: ReplayBundle, *, policy: Policy | None = None) -> Trajectory:
    """Assemble the step-by-step trajectory for ``bundle``.

    Args:
        bundle: The captured turn to expand.
        policy: Guard policy for the (side-effect-free) input check.

    Returns:
        A :class:`Trajectory` with ordered, demo-ready steps.
    """
    active_policy = policy or load_policy()
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    timings = bundle.latency_ms or {}
    steps: list[TrajectoryStep] = []

    def add(
        kind: str, title: str, detail: str, *, duration_ms: float = 0.0, status: str = "info"
    ) -> None:
        steps.append(
            TrajectoryStep(
                index=len(steps),
                kind=kind,
                title=title,
                detail=detail,
                duration_ms=duration_ms,
                status=status,
            )
        )

    add("input", "User question", bundle.question, status="info")

    denied = _guard_denied(bundle.question, active_policy)
    add(
        "guard",
        "Guard — input screen",
        "denied (injection pattern matched)" if denied else "allowed",
        status="warn" if denied else "ok",
    )

    sources = bundle.lineage.doc_sources if bundle.lineage else []
    sources_detail = ", ".join(sources[:5]) if sources else f"{len(chunks)} chunk(s)"
    add("retrieval", "Retrieval", f"{len(chunks)} chunk(s) · {sources_detail}", status="info")

    for name, ms in timings.items():
        add("node", name, f"{round(ms)} ms", duration_ms=ms, status="info")

    score_status = "ok" if bundle.original_score >= 0.8 else "warn"  # noqa: PLR2004
    add(
        "answer",
        f"Answer · faithfulness {bundle.original_score:.2f}",
        bundle.original_answer,
        status=score_status,
    )

    return Trajectory(
        bundle_id=bundle.bundle_id,
        language=bundle.language,
        model=bundle.original_model,
        score=bundle.original_score,
        total_ms=sum(timings.values()),
        n_steps=len(steps),
        steps=steps,
    )
