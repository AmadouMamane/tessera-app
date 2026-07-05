"""Minimal specialised Recouvrement workflow v1.

This module introduces the first dedicated collections workflow without replacing
the generic :func:`tessera.agent.graph.build_graph` path. It shares the observed
runtime substrate where it already exists: LangGraph node spans via
``instrument_node``, business events, audit fan-out, Prometheus metrics, replay
capture, spine projection, and deterministic métier scoring.

Still intentionally outside this first extraction: SSE streaming, transcript
memory, and generic online LLM evaluation remain in ``api.routes.chat._stream_turn``.
The next step is to extract those cross-cutting pieces into a common observed
runtime wrapper before progressively wiring ``/fr/recouvrement-new`` to this
structured endpoint.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph

from tessera.observability import business_events as business_events_mod, business_scoring, replay
from tessera.observability.business_events import BusinessEventName, record_business_event
from tessera.observability.instrument import instrument_node

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

__all__ = [
    "RECOUVREMENT_AGENT_ID",
    "RECOUVREMENT_WORKFLOW_ID",
    "RecouvrementCaseSnapshot",
    "build_recouvrement_graph_v1",
    "run_recouvrement_graph_v1",
]

RECOUVREMENT_AGENT_ID = "recouvrement"
RECOUVREMENT_WORKFLOW_ID = "recouvrement_collections_v1"
DEFAULT_SURFACE = "dedicated-ui"


@dataclass(frozen=True, slots=True)
class RecouvrementCaseSnapshot:
    """Centralised mock snapshot for the first RC-2048 workflow slice."""

    case_id: str
    client: str
    amount_due_label: str
    amount_due: float
    days_late: int
    missed_promise: str
    contact_window_start: str
    contact_window_end: str
    recommended_channel: str
    alternative_channel: str

    @property
    def contact_window_label(self) -> str:
        """Human-readable contact window label."""
        return f"{self.contact_window_start}-{self.contact_window_end}"


_RC_2048 = RecouvrementCaseSnapshot(
    case_id="RC-2048",
    client="M. D.",
    amount_due_label="840,00 €",
    amount_due=840.0,
    days_late=32,
    missed_promise="promesse de paiement non tenue le 12 juin",
    contact_window_start="08:00",
    contact_window_end="20:00",
    recommended_channel="appel sortant",
    alternative_channel="email de confirmation",
)


class ContactPolicyDecision(TypedDict):
    """Decision produced by the contact-policy node."""

    decision: str
    reason_codes: list[str]
    requested_time: str | None
    is_within_window: bool | None


class RecouvrementArtifact(TypedDict):
    """Structured artifact consumed by the Recouvrement drawer contract."""

    id: str
    type: str
    task: str
    title: str
    status: str
    content: dict[str, object]


class RecouvrementOutput(TypedDict):
    """Structured output returned by the specialised workflow endpoint."""

    visibleReply: str
    artifact: RecouvrementArtifact
    cardUpdates: dict[str, list[str]]
    suggestedActions: list[str]
    businessEvents: list[dict[str, object]]
    businessScores: list[dict[str, object]]
    decisions: dict[str, object]


class BusinessEventCommon(TypedDict):
    """Common keyword dimensions passed to business event emission."""

    agent_id: str
    workflow_id: str
    surface: str
    conversation_id: str
    turn_id: str
    case_id: str
    node_name: str
    language: str
    model: str
    environment: str


class RecouvrementWorkflowState(TypedDict):
    """State for the minimal Recouvrement LangGraph."""

    conversation_id: str
    turn_id: str
    case_id: str
    message: str
    surface: str
    language: str
    model: str
    environment: str
    assistant_state: NotRequired[dict[str, object]]
    case: NotRequired[RecouvrementCaseSnapshot]
    intent: NotRequired[str]
    intent_confidence: NotRequired[float]
    slots: NotRequired[dict[str, object]]
    contact_policy: NotRequired[ContactPolicyDecision]
    artifact: NotRequired[RecouvrementArtifact]
    visible_reply: NotRequired[str]
    card_updates: NotRequired[dict[str, list[str]]]
    suggested_actions: NotRequired[list[str]]
    output: NotRequired[RecouvrementOutput]


def _case_for(case_id: str) -> RecouvrementCaseSnapshot:
    """Return the supported mock case snapshot for this first workflow slice."""
    if case_id != _RC_2048.case_id:
        return _RC_2048
    return _RC_2048


def _event_common(
    state: RecouvrementWorkflowState,
    *,
    node_name: str,
    case: RecouvrementCaseSnapshot | None = None,
) -> BusinessEventCommon:
    """Common dimensions for Recouvrement business events."""
    snapshot = case or state.get("case") or _case_for(state["case_id"])
    return {
        "agent_id": RECOUVREMENT_AGENT_ID,
        "workflow_id": RECOUVREMENT_WORKFLOW_ID,
        "surface": str(state.get("surface", DEFAULT_SURFACE)),
        "conversation_id": state["conversation_id"],
        "turn_id": state["turn_id"],
        "case_id": snapshot.case_id,
        "node_name": node_name,
        "language": str(state.get("language", "fr")),
        "model": str(state.get("model", RECOUVREMENT_WORKFLOW_ID)),
        "environment": str(state.get("environment", "dev")),
    }


def _parse_time(message: str) -> str | None:
    """Extract a simple requested contact hour from French free text."""
    normalized = message.lower().replace(" ", "")
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])(?:[:h]([0-5]\d)?)", normalized)
    if match is None:
        if "maintenant" not in normalized:
            return None
        now = datetime.now(ZoneInfo("Europe/Paris"))
        return f"{now.hour:02d}:{now.minute:02d}"
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return f"{hour:02d}:{minute:02d}"


def _time_to_minutes(value: str) -> int:
    hour, minute = value.split(":", maxsplit=1)
    return int(hour) * 60 + int(minute)


def _within_window(requested_time: str, case: RecouvrementCaseSnapshot) -> bool:
    requested = _time_to_minutes(requested_time)
    start = _time_to_minutes(case.contact_window_start)
    end = _time_to_minutes(case.contact_window_end)
    return start <= requested < end


def _context_items(case: RecouvrementCaseSnapshot) -> list[str]:
    return [
        f"Dossier : {case.case_id}",
        f"Client : {case.client}",
        f"Montant dû : {case.amount_due_label}",
        f"Retard : {case.days_late} jours",
        case.missed_promise,
        f"Contact autorisé aujourd'hui : {case.contact_window_label}",
    ]


def load_case_context(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Load the centralised RC-2048 snapshot."""
    case = _case_for(state["case_id"])
    record_business_event(
        event_name=BusinessEventName.CASE_CONTEXT_LOADED,
        payload={
            "client": case.client,
            "amount_due": case.amount_due,
            "days_late": case.days_late,
            "contact_window": case.contact_window_label,
        },
        **_event_common(state, node_name="load_case_context", case=case),
    )
    return {"case": case}


def route_recouvrement_intent(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Route the first supported Recouvrement intent."""
    intent = "check_contact_rule"
    confidence = 0.96
    record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        payload={"intent": intent, "confidence": confidence},
        **_event_common(state, node_name="route_recouvrement_intent"),
    )
    return {"intent": intent, "intent_confidence": confidence}


def extract_recouvrement_slots(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Extract slots needed by the contact-rule workflow."""
    requested_time = _parse_time(state["message"])
    slots: dict[str, object] = {
        "requested_time": requested_time,
        "rule_impacting": requested_time is not None,
        "case_id": state["case_id"],
    }
    record_business_event(
        event_name=BusinessEventName.SLOTS_EXTRACTED,
        payload=slots,
        **_event_common(state, node_name="extract_recouvrement_slots"),
    )
    return {"slots": slots}


def evaluate_contact_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Evaluate the outbound contact window for Julie's requested action."""
    case = state["case"]
    requested_time = state.get("slots", {}).get("requested_time")
    requested = str(requested_time) if requested_time is not None else None
    is_within = _within_window(requested, case) if requested is not None else None
    blocked = requested is not None and is_within is False
    decision: ContactPolicyDecision = {
        "decision": "blocked" if blocked else "allowed",
        "reason_codes": ["OUTSIDE_CONTACT_WINDOW"] if blocked else [],
        "requested_time": requested,
        "is_within_window": is_within,
    }
    record_business_event(
        event_name=BusinessEventName.BUSINESS_RULE_CHECKED,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "rule_id": "CONTACT_WINDOW",
            "requested_time": requested,
            "allowed_window": case.contact_window_label,
            "recommended_channel": case.recommended_channel,
        },
        **_event_common(state, node_name="evaluate_contact_policy"),
    )
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.contact_window",
            "rule_id": "CONTACT_WINDOW",
        },
        **_event_common(state, node_name="evaluate_contact_policy"),
    )
    if blocked:
        record_business_event(
            event_name=BusinessEventName.ACTION_BLOCKED,
            decision="blocked",
            reason_codes=decision["reason_codes"],
            payload={"action": "prepare_outbound_call", "requested_time": requested},
            **_event_common(state, node_name="evaluate_contact_policy"),
        )
    return {"contact_policy": decision}


def build_contact_rule_artifact(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Build the drawer-compatible contact-rule artifact."""
    case = state["case"]
    policy = state["contact_policy"]
    requested_time = policy["requested_time"]
    blocked = policy["decision"] == "blocked"
    if requested_time and blocked:
        contact_status = f"Appel à {requested_time} : non autorisé"
        validation = (
            f"Un appel à {requested_time} n'est pas autorisé. Reportez le contact sur "
            "une plage autorisée ou utilisez un canal autorisé si applicable."
        )
        next_actions = [
            "Planifier un rappel demain",
            "Rédiger un email de confirmation",
            "Reporter le contact",
            "Voir la règle de contact",
        ]
    else:
        contact_status = "Contact autorisé aujourd'hui"
        validation = (
            "Aucune validation supplémentaire n'est nécessaire pour ce contact aujourd'hui."
        )
        next_actions = [
            "Préparer un script d'appel",
            "Rédiger un email de confirmation",
            "Reporter le contact",
            "Voir la règle de contact",
        ]
    artifact: RecouvrementArtifact = {
        "id": f"{case.case_id}-contact-rule-v1",
        "type": "contact_rule_v1",
        "task": "check_rule",
        "title": f"Cadre de contact — {case.case_id}",
        "status": "draft",
        "content": {
            "case_id": case.case_id,
            "client": case.client,
            "requested_time": requested_time,
            "contact_status": contact_status,
            "allowed_window": case.contact_window_label,
            "recommended_channel": case.recommended_channel,
            "alternative_channel": case.alternative_channel,
            "decision": policy["decision"],
            "reason_codes": policy["reason_codes"],
        },
    }
    card_updates = {
        "context": _context_items(case),
        "contactFrame": [
            f"Dossier : {case.case_id}",
            f"Client : {case.client}",
            contact_status,
            f"Plage autorisée : {case.contact_window_label}",
            f"Canal conseillé : {case.recommended_channel}",
            f"Alternative : {case.alternative_channel}",
        ],
        "allowedItems": [
            (
                f"Vous pouvez contacter {case.client} aujourd'hui entre "
                f"{case.contact_window_start} et {case.contact_window_end}."
            ),
            f"Le canal recommandé est l'{case.recommended_channel}.",
        ],
        "validationItems": [validation],
        "nextActions": next_actions,
    }
    record_business_event(
        event_name=BusinessEventName.ARTIFACT_CREATED,
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=artifact["status"],
        payload={
            "task": artifact["task"],
            "title": artifact["title"],
            "decision": policy["decision"],
        },
        **_event_common(state, node_name="build_contact_rule_artifact"),
    )
    return {
        "artifact": artifact,
        "card_updates": card_updates,
        "suggested_actions": next_actions,
    }


def generate_visible_reply(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Generate the natural-language response visible to Julie."""
    case = state["case"]
    policy = state["contact_policy"]
    requested_time = policy["requested_time"]
    if requested_time and policy["decision"] == "blocked":
        reply = (
            f"Non, vous ne devez pas appeler {case.client} à {requested_time}. "
            "Le contact téléphonique est autorisé aujourd'hui uniquement entre "
            f"{case.contact_window_start} et {case.contact_window_end}. "
            "Je peux vous aider à planifier un rappel demain ou à préparer un "
            f"{case.alternative_channel}."
        )
    else:
        reply = (
            f"Pour {case.case_id}, vous pouvez contacter {case.client} aujourd'hui entre "
            f"{case.contact_window_start} et {case.contact_window_end}. "
            f"Le canal conseillé est l'{case.recommended_channel}. En alternative, "
            f"vous pouvez préparer un {case.alternative_channel}."
        )
    record_business_event(
        event_name=BusinessEventName.MESSAGE_GENERATED,
        payload={
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": "check_rule",
        },
        **_event_common(state, node_name="generate_visible_reply"),
    )
    return {"visible_reply": reply}


def finalize_business_observability(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Project business events, scores and replay into the output contract."""
    events = business_events_mod.business_event_rows(
        agent_id=RECOUVREMENT_AGENT_ID,
        conversation_id=state["conversation_id"],
        turn_id=state["turn_id"],
    )
    scores = business_scoring.score_rows(events)
    output: RecouvrementOutput = {
        "visibleReply": state["visible_reply"],
        "artifact": state["artifact"],
        "cardUpdates": state["card_updates"],
        "suggestedActions": state["suggested_actions"],
        "businessEvents": events,
        "businessScores": scores,
        "decisions": {
            "intent": state.get("intent"),
            "confidence": state.get("intent_confidence"),
            "slots": state.get("slots", {}),
            "contactPolicy": state.get("contact_policy", {}),
        },
    }
    replay.capture_bundle(
        question=state["message"],
        context="\n".join(_context_items(state["case"])),
        original_answer=state["visible_reply"],
        language=state.get("language", "fr"),
        original_score=1.0,
        original_model=RECOUVREMENT_WORKFLOW_ID,
        conversation_id=state["conversation_id"],
        agent_id=RECOUVREMENT_AGENT_ID,
        turn_id=state["turn_id"],
        business_events=events,
    )
    return {"output": output}


def build_recouvrement_graph_v1() -> StateGraph[RecouvrementWorkflowState]:
    """Construct the minimal specialised Recouvrement graph."""
    graph: StateGraph[RecouvrementWorkflowState] = StateGraph(RecouvrementWorkflowState)
    graph.add_node("load_case_context", instrument_node("load_case_context", load_case_context))
    graph.add_node(
        "route_recouvrement_intent",
        instrument_node("route_recouvrement_intent", route_recouvrement_intent),
    )
    graph.add_node(
        "extract_recouvrement_slots",
        instrument_node("extract_recouvrement_slots", extract_recouvrement_slots),
    )
    graph.add_node(
        "evaluate_contact_policy",
        instrument_node("evaluate_contact_policy", evaluate_contact_policy),
    )
    graph.add_node(
        "build_contact_rule_artifact",
        instrument_node("build_contact_rule_artifact", build_contact_rule_artifact),
    )
    graph.add_node(
        "generate_visible_reply",
        instrument_node("generate_visible_reply", generate_visible_reply),
    )
    graph.add_node(
        "finalize_business_observability",
        instrument_node("finalize_business_observability", finalize_business_observability),
    )
    graph.add_edge(START, "load_case_context")
    graph.add_edge("load_case_context", "route_recouvrement_intent")
    graph.add_edge("route_recouvrement_intent", "extract_recouvrement_slots")
    graph.add_edge("extract_recouvrement_slots", "evaluate_contact_policy")
    graph.add_edge("evaluate_contact_policy", "build_contact_rule_artifact")
    graph.add_edge("build_contact_rule_artifact", "generate_visible_reply")
    graph.add_edge("generate_visible_reply", "finalize_business_observability")
    graph.add_edge("finalize_business_observability", END)
    return graph


def _compiled_recouvrement_graph_v1() -> (
    CompiledStateGraph[
        RecouvrementWorkflowState, None, RecouvrementWorkflowState, RecouvrementWorkflowState
    ]
):
    return build_recouvrement_graph_v1().compile()


def run_recouvrement_graph_v1(
    *,
    case_id: str,
    message: str,
    assistant_state: dict[str, object] | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    surface: str = DEFAULT_SURFACE,
    language: str = "fr",
    model: str = RECOUVREMENT_WORKFLOW_ID,
    environment: str = "dev",
) -> RecouvrementOutput:
    """Run the minimal Recouvrement graph and return the drawer-ready contract."""
    initial: RecouvrementWorkflowState = {
        "conversation_id": conversation_id or uuid.uuid4().hex,
        "turn_id": turn_id or uuid.uuid4().hex,
        "case_id": case_id,
        "message": message,
        "surface": surface,
        "language": language,
        "model": model,
        "environment": environment,
    }
    if assistant_state is not None:
        initial["assistant_state"] = assistant_state
    final_state = cast(RecouvrementWorkflowState, _compiled_recouvrement_graph_v1().invoke(initial))
    return final_state["output"]
