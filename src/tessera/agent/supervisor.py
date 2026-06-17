"""Inter-agent supervisor — routes each turn to an agent, above the graph.

This is the multi-agent orchestration layer that sits **above** the existing
LangGraph (``agent/graph.py`` + ``agent/router.py``): the intra-agent router
detects language and seeds state; this supervisor decides *which agent* handles
the turn. The customer keeps one door — routing is invisible.

Design mirrors the intra-agent router: **rule-based and deterministic**, so the
non-regression harness can replay it and so a routing decision is explainable
(``reason``) and auditable. Per-turn attribution: the chosen agent is the one
that handles (and is credited with) the whole turn. Default routing follows the
conversation's *parcours* (the agent currently on the conversation); a clear
intent signal can trigger a **handoff** to another agent — but only when the
governed handoff contract allows the edge (``registry.can_handoff``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import can_handoff, get_agent

__all__ = ["RoutingDecision", "route_turn"]


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """The supervisor's per-turn verdict.

    Attributes:
        agent_id: The agent that will handle (and be credited with) this turn.
        handoff: Whether this turn moves the conversation to a different agent.
        from_agent: The previous agent when ``handoff`` is true, else ``None``.
        reason: Short, explainable rationale (audited on a handoff).
    """

    agent_id: str
    handoff: bool
    from_agent: str | None
    reason: str


# Intent lexicon: a target agent + the regexes that signal a turn belongs to it.
# Deterministic and offline (same input -> same route), like the language router.
_INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "onboarding",
        (
            r"\bouv(?:rir|erture)\b",
            r"\bnouveau compte\b",
            r"\bdeuxi[eè]me compte\b",
            r"\bkyc\b",
            r"\b[ée]ligib",
            r"\bpi[eè]ces? justificative",
        ),
    ),
    (
        "recouvrement",
        (
            r"\bimpay[ée]",
            r"\brelance",
            r"\b[ée]ch[ée]ancier\b",
            r"\bretard de paiement\b",
            r"\brecouvrement\b",
            r"\bdette\b",
            r"\bje ne peux pas payer\b",
        ),
    ),
)


def _detect_intent(text: str) -> str | None:
    """Return the agent a turn's intent points to, or ``None`` if unclear."""
    low = text.lower()
    for agent_id, patterns in _INTENTS:
        if any(re.search(p, low) for p in patterns):
            return agent_id
    return None


def route_turn(current_agent: str | None, user_input: str) -> RoutingDecision:
    """Decide which agent handles this turn.

    Default = the conversation's current agent (parcours); a clear intent for a
    *different* agent triggers a handoff, but only if the governed contract
    allows the edge. Unknown/empty current agent falls back to the default agent.
    """
    base = current_agent or DEFAULT_AGENT_ID
    try:
        get_agent(base)
    except (KeyError, OSError, ValueError):
        base = DEFAULT_AGENT_ID

    intent = _detect_intent(user_input)
    if intent and intent != base and can_handoff(base, intent):
        return RoutingDecision(
            agent_id=intent,
            handoff=True,
            from_agent=base,
            reason=f"intent->{intent} (handoff {base}->{intent})",
        )
    return RoutingDecision(
        agent_id=base, handoff=False, from_agent=None, reason=f"stay->{base}"
    )
