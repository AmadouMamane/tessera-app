"""Escalation worker — opens a human-handoff ticket and ends the turn.

The reviewer sets ``needs_escalation = True`` when it cannot in good
conscience let the reporter respond — low grounding score, repeated guard
denies, or simply an intent (card block, dispute) that requires a human by
policy. This worker creates a ticket through the
:mod:`tessera.agent.tools.ticket_escalate` tool, surfaces the ticket
reference in the user's language, and short-circuits the rest of the graph.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from tessera.agent.reporter import load_prompts
from tessera.agent.state import AgentState, ConversationMessage, ToolCallRecord
from tessera.agent.tools import ticket_escalate
from tessera.guard.adapter import guarded_invoke
from tessera.observability.metrics import ESCALATIONS_TOTAL

NODE_NAME = "escalation_worker"

# A card emergency (theft / loss / fraud) gets an action-oriented handoff that
# tells the user to block the card immediately (opposition); every other
# escalation gets the neutral handoff. Detection mirrors the planner's
# urgent_card cues — kept multilingual and self-contained here because the
# direct urgent_card → ESCALATION path never sets escalation_reason.
_THEFT_RE = re.compile(
    r"\b(vol(?:é[e]?|er?)|perdu[e]?|fraude?|gestohlen|verloren|betrug|stolen|lost)\b",
    re.IGNORECASE,
)
_CARD_RE = re.compile(r"\b(carte|karte|card)\b", re.IGNORECASE)


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point."""
    reason = state.get("escalation_reason") or "human handoff requested"
    conversation_id = str(state["conversation_id"])
    language_val = state["language"].value
    transcript = state["user_input"][:500]
    arguments: dict[str, object] = {
        "conversation_id": conversation_id,
        "language": language_val,
        "reason": reason,
        "transcript_excerpt": transcript,
    }
    started = time.perf_counter()
    guarded_result = await guarded_invoke(
        tool_name="ticket_escalate",
        invoke=lambda: ticket_escalate.open_ticket(
            conversation_id=conversation_id,
            language=state["language"].value,
            reason=reason,
            transcript_excerpt=transcript,
        ),
        arguments=arguments,
        language=state["language"],
    )
    duration_ms = (time.perf_counter() - started) * 1000.0

    call = ToolCallRecord(
        tool_name="ticket_escalate",
        arguments=arguments,
        result=guarded_result.result,
        succeeded=guarded_result.allowed and guarded_result.error is None,
        error=guarded_result.error,
        decision_proof_id=(
            guarded_result.decision_proof.decision_id
            if guarded_result.decision_proof is not None
            else None
        ),
        decision_proof_hash=(
            guarded_result.decision_proof.proof_hash
            if guarded_result.decision_proof is not None
            else None
        ),
        started_at=datetime.now(UTC),
        duration_ms=duration_ms,
    )

    ticket_reference = (
        guarded_result.result.reference if call.succeeded and guarded_result.result else "PENDING"
    )
    ESCALATIONS_TOTAL.labels(
        language=state["language"].value,
        outcome="created" if call.succeeded else "failed",
    ).inc()

    prompts = load_prompts(state["language"])
    user_input = state["user_input"]
    is_card_emergency = bool(_THEFT_RE.search(user_input) and _CARD_RE.search(user_input))
    template_key = (
        "escalation_urgent_card"
        if is_card_emergency and "escalation_urgent_card" in prompts
        else "escalation"
    )
    final = prompts[template_key].format(ticket_reference=ticket_reference).strip()

    return {
        "tool_calls": [call],
        "guard_decisions": list(guarded_result.decisions),
        "final_response": final,
        "needs_escalation": True,
        "messages": [ConversationMessage(role="assistant", content=final)],
    }
