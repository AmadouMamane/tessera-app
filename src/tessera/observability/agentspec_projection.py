"""Manifest projection — generate cockpit facts from the AgentSpec (ADR 0017 §3/§4).

The AgentSpec is the single onboarding artifact; the cockpit's business surfaces are
*generated* from it, never hand-placed per agent. This module reads the manifest through
the one boundary-allowed seam (``tessera.agent.registry``, ADR 0017 §1 import contract) —
never the agent runtime — and derives:

- the observability **level** (L0-L3, computed from facts, never asserted);
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
    "declared_observability_level",
    "north_star_descriptor",
    "observability_level",
]

#: The ladder labels the cockpit displays (ADR 0017 §4). L3 is unlocked in Phase C.
LEVELS = ("L0", "L1", "L2", "L3")


def observability_level(
    agent: Agent,
    *,
    governed: bool,
    has_turn_evidence: bool,
    business_events: bool = False,
) -> str | None:
    """Compute the observability level from passing facts (ADR 0017 §4) — never asserted.

    - **L0 Registered** — a valid AgentSpec is present.
    - **L1 Observable** — L0, the agent declares an observable contract (≥1 workflow mapped
      onto the grammar + telemetry capabilities), AND the cockpit has **observed** it emitting
      turns (``has_turn_evidence`` — the Prometheus turn counter, ADR 0017 §F). A
      declared-but-unobserved agent stays L0: "Observable" means the spine sees emission, not
      that the manifest promises it.
    - **L2 Governed** — L1 and the agent's guard/eval/release facts are visible to the
      cockpit (``governed`` — a real gating socle ran).
    - **L3 Business** — L2 and typed workflow-grammar business events are visible.

    ``has_turn_evidence`` is **required**: it once defaulted to ``True``, which let a caller
    obtain a computed-looking rung from an assumption. To ask what the manifest *promises*,
    call :func:`declared_observability_level` — and say so at the call site.

    Returns ``None`` for an un-manifested agent, so the absence of a manifest renders as an
    honest-empty badge, never as "L0".
    """
    spec = agent.observability
    if spec is None:
        return None
    if not (spec.workflows and spec.telemetry_capabilities):
        return "L0"
    if not has_turn_evidence:
        return "L0"  # declares the contract but the cockpit has observed no turns yet
    if not governed:
        return "L1"
    if business_events:
        return "L3"
    return "L2"


def declared_observability_level(
    agent: Agent,
    *,
    governed: bool,
    business_events: bool = False,
) -> str | None:
    """The rung the agent's declarations would reach **if the turn evidence existed**.

    Never a substitute for :func:`observability_level`: it is what the badge shows in the
    attenuated "declared · no evidence" variant, and what a UI names as the agent's ambition.
    A release gate must never read it (ADR 0017 §A2.4 — an unproven rung gates nothing).
    """
    return observability_level(
        agent, governed=governed, business_events=business_events, has_turn_evidence=True
    )


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
