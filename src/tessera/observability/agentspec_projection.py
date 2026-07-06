"""Manifest projection — generate cockpit facts from the AgentSpec (ADR 0017 §3/§4).

The AgentSpec is the single onboarding artifact; the cockpit's business surfaces are
*generated* from it, never hand-placed per agent. This module reads the manifest through
the one boundary-allowed seam (``tessera.agent.registry``, ADR 0017 §1 import contract) —
never the agent runtime — and derives:

- the observability **level** (L0-L2 in Phase B, computed from facts, never asserted);
- serialisable **business-signal descriptors** (the SignalSpec-equivalent metadata the
  fleet chip, Métier KPI strip and Conformité projection render).

L3 (Business) is computed in Phase C once the Métier surfaces read the grammar events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.agent.registry import BusinessSignalSource

if TYPE_CHECKING:
    from tessera.agent.registry import Agent

__all__ = [
    "LEVELS",
    "business_signal_descriptors",
    "north_star_descriptor",
    "observability_level",
]

#: The ladder labels the cockpit displays (ADR 0017 §4). L3 is unlocked in Phase C.
LEVELS = ("L0", "L1", "L2", "L3")


def observability_level(agent: Agent, *, governed: bool) -> str | None:
    """Compute the observability level from passing facts (ADR 0017 §4) — never asserted.

    Phase B computes L0-L2:

    - **L0 Registered** — a valid AgentSpec is present.
    - **L1 Observable** — L0 and the agent declares an observable contract (≥1 workflow
      mapped onto the grammar, plus telemetry capabilities): its spans/metrics have a
      declared shape the cockpit can read.
    - **L2 Governed** — L1 and the agent's guard/eval/release facts are visible to the
      cockpit (``governed`` — a real gating socle ran).

    Returns ``None`` for an un-manifested agent, so the absence of a manifest renders as an
    honest-empty badge, never as "L0".
    """
    spec = agent.observability
    if spec is None:
        return None
    if not (spec.workflows and spec.telemetry_capabilities):
        return "L0"
    if not governed:
        return "L1"
    return "L2"


def business_signal_descriptors(agent: Agent) -> list[dict[str, object]]:
    """The generated SignalSpec-equivalent descriptors for an agent's business signals.

    One descriptor per declared ``business_signals`` entry — the metadata the fleet chip,
    Métier KPI strip and Conformité projection render, plus the ``scorer`` that produces a
    ``business_score`` signal's value. Generated from the manifest, never hand-written per
    agent (ADR 0017 §3).
    """
    spec = agent.observability
    if spec is None:
        return []
    # v1: a single bound scorer per agent produces every ``business_score`` signal.
    scorer = next((w.scorer for w in spec.workflows if w.scorer), None)
    return [
        {
            "agent_id": agent.id,
            "key": sig.key,
            "source": sig.source.value,
            "level": sig.level.value,
            "unit": sig.unit,
            "aggregation": sig.aggregation,
            "dimensions": list(sig.dimensions),
            "engagement": sig.engagement.value,
            "north_star": sig.north_star,
            "scorer": scorer if sig.source is BusinessSignalSource.BUSINESS_SCORE else None,
        }
        for sig in spec.business_signals
    ]


def north_star_descriptor(agent: Agent) -> dict[str, object] | None:
    """The single north-star business-signal descriptor for the fleet card, or ``None``.

    Uniqueness (≤1 per agent) is enforced at manifest load (ADR 0017 §6.1).
    """
    return next(
        (d for d in business_signal_descriptors(agent) if d["north_star"]),
        None,
    )
