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
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph

from tessera.agent.registry import get_agent
from tessera.authz import Surface
from tessera.observability import business_events as business_events_mod, business_scoring, replay
from tessera.observability.business_events import BusinessEventName, record_business_event
from tessera.observability.instrument import instrument_node
from tessera.recouvrement import ensure_recouvrement_scorer_registered
from tessera.recouvrement.message_templates import (
    RECOUVREMENT_REMINDER_EMPATHIC_V1,
    RECOUVREMENT_REMINDER_SHORT_V1,
    RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1,
    RECOUVREMENT_SCHEDULE_MESSAGE_V1,
    RecouvrementMessageTemplate,
    render_schedule_sentence,
)

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

__all__ = [
    "RECOUVREMENT_AGENT_ID",
    "RECOUVREMENT_WORKFLOW_ID",
    "RecouvrementCaseSnapshot",
    "build_recouvrement_graph_v1",
    "run_recouvrement_action_workflow_v1",
    "run_recouvrement_graph_v1",
]

RECOUVREMENT_AGENT_ID = "recouvrement"
RECOUVREMENT_WORKFLOW_ID = "recouvrement_collections_v1"
DEFAULT_SURFACE = "dedicated-ui"
AUTHORIZED_SURFACES = {Surface.DEDICATED_UI.value, Surface.COCKPIT_EMBEDDED.value}

ensure_recouvrement_scorer_registered()


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


class SchedulePolicyDecision(TypedDict):
    """Decision produced by the schedule-policy node."""

    decision: str
    reason_codes: list[str]
    requested_months: int
    monthly_amount: float
    monthly_amount_label: str
    validation_required: bool
    client_agreement_required: bool
    schedule_created: bool


class DraftPolicyDecision(TypedDict):
    """Deterministic review decision for a prepared client message."""

    decision: str
    reason_codes: list[str]
    policy_review_status: str
    tone: str
    mentions_schedule: bool
    amount_consistent: bool
    validation_required: bool
    client_agreement_required: bool
    schedule_created: bool
    message_sent: bool
    no_schedule_created: bool
    no_message_sent: bool


class SummaryPolicyDecision(TypedDict):
    """Deterministic review decision for a case-summary artifact."""

    decision: str
    reason_codes: list[str]
    policy_review_status: str
    amount_consistent: bool
    message_sent: bool
    schedule_created: bool
    external_effect: bool
    validation_decision: bool


class PaymentOptionsPolicyDecision(TypedDict):
    """Deterministic review decision for payment-options guidance."""

    decision: str
    reason_codes: list[str]
    policy_review_status: str
    amount_consistent: bool
    validation_required: bool
    client_agreement_required: bool
    payment_initiated: bool
    payment_link_created: bool
    payment_link_sent: bool
    schedule_created: bool
    no_payment_initiated: bool
    no_payment_link_created: bool
    no_payment_link_sent: bool
    no_schedule_created: bool
    no_external_effect: bool


class DraftGenerationMetadata(TypedDict):
    """Provenance metadata for a generated or selected client-message artifact."""

    generation_mode: str
    template_id: str | None
    template_version: str | None
    template_label: str | None
    template_tone: str | None
    allowed_use_cases: list[str]
    model_id: str | None
    prompt_version: str | None


class RecouvrementArtifact(TypedDict):
    """Structured artifact consumed by the Recouvrement drawer contract."""

    id: str
    type: str
    task: str
    title: str
    status: str
    content: dict[str, object]


class ArtifactActionDecision(TypedDict):
    """Governed action decision for a Recouvrement artifact."""

    artifact_id: str
    artifact_type: str
    action_name: str
    requested_by: str
    case_id: str
    current_status: str
    target_status: str
    requires_validation: bool
    reason_codes: list[str]
    no_external_effect: bool
    blocked: bool


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
    authorized: NotRequired[bool]
    authorization_reason: NotRequired[str]
    case: NotRequired[RecouvrementCaseSnapshot]
    intent: NotRequired[str]
    intent_confidence: NotRequired[float]
    slots: NotRequired[dict[str, object]]
    contact_policy: NotRequired[ContactPolicyDecision]
    schedule_policy: NotRequired[SchedulePolicyDecision]
    draft_message: NotRequired[str]
    draft_generation: NotRequired[DraftGenerationMetadata]
    draft_policy: NotRequired[DraftPolicyDecision]
    summary_policy: NotRequired[SummaryPolicyDecision]
    payment_options_policy: NotRequired[PaymentOptionsPolicyDecision]
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


def _surface_allowed(surface: str) -> bool:
    """Whether the requested surface is governed for the Recouvrement operator agent."""
    try:
        parsed = Surface(surface)
    except ValueError:
        return False
    if parsed.value not in AUTHORIZED_SURFACES:
        return False
    try:
        agent = get_agent(RECOUVREMENT_AGENT_ID)
    except KeyError:
        return False
    return parsed in agent.surface


def verify_surface_authorization(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Fail closed unless Recouvrement is called from an operator-authorised surface."""
    surface = str(state.get("surface", DEFAULT_SURFACE))
    if _surface_allowed(surface):
        return {"authorized": True}
    record_business_event(
        event_name=BusinessEventName.ACTION_BLOCKED,
        decision="blocked",
        reason_codes=["UNAUTHORIZED_SURFACE"],
        payload={"action_name": "run_recouvrement_workflow", "requested_surface": surface},
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        surface=surface,
        conversation_id=state["conversation_id"],
        turn_id=state["turn_id"],
        case_id=state["case_id"],
        node_name="verify_surface_authorization",
        language=str(state.get("language", "fr")),
        model=str(state.get("model", RECOUVREMENT_WORKFLOW_ID)),
        environment=str(state.get("environment", "dev")),
    )
    return {"authorized": False, "authorization_reason": "UNAUTHORIZED_SURFACE"}


def _after_surface_authorization(state: RecouvrementWorkflowState) -> str:
    """Route the graph after the surface gate."""
    return "authorized" if state.get("authorized") is True else "blocked"


def _normalize_message(message: str) -> str:
    """Normalize French free text for deterministic intent routing."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", message.lower())
        if unicodedata.category(char) != "Mn"
    )


def _has_schedule_intent(normalized_message: str) -> bool:
    """Whether the current Julie turn asks for a payment schedule."""
    return (
        re.search(
            r"\b(echeancier|etalement|etaler|mensualite|mensualites|mois|paiement|payer|"
            r"regler|regulariser|duree)\b",
            normalized_message,
        )
        is not None
    )


def _has_draft_intent(normalized_message: str) -> bool:
    """Whether the current Julie turn asks for a client message or reminder draft."""
    return (
        re.search(
            r"\b(relance|brouillon|courrier|email|mail|rediger|redige|prepare|preparer|"
            r"message client|version courte|empathique|modifier|modifie|rends-le|rend le)\b",
            normalized_message,
        )
        is not None
    )


def _has_summary_intent(normalized_message: str) -> bool:
    """Whether the current Julie turn asks for an operational case summary."""
    return (
        re.search(
            r"\b(resume|resumer|synthese|synthetise|points cles|prioritaire|priorite|"
            r"situation du client|que dois je retenir|a retenir)\b",
            normalized_message,
        )
        is not None
    )


def _has_payment_options_intent(normalized_message: str) -> bool:
    """Whether Julie asks for available payment or settlement options."""
    return (
        re.search(
            r"\b(options? de paiement|moyens? de paiement|comment peut[- ]?il payer|"
            r"comment peut[- ]?il regler|paiement total|paiement partiel|"
            r"paiement en plusieurs fois|echeancier possible|alternatives? de reglement|"
            r"solution de paiement|options? de reglement|moyens? de reglement)\b",
            normalized_message,
        )
        is not None
    )


def _has_contact_rule_intent(normalized_message: str) -> bool:
    """Whether the current Julie turn asks for contact-rule verification."""
    has_contact_action = (
        re.search(
            r"\b(appel|appeler|telephone|telephoner|contacter|contact|joindre|email|mail)\b",
            normalized_message,
        )
        is not None
    )
    has_rule_signal = (
        re.search(
            r"\b(regle|regles|autorise|autorisation|interdit|peux|peut|puis|comment|quand|"
            r"heure|plage|cadre|conforme|conformite)\b",
            normalized_message,
        )
        is not None
        or re.search(r"(?:[01]?\d|2[0-3])(?:h|:)", normalized_message) is not None
    )
    return (
        "regle de contact" in normalized_message
        or "cadre de contact" in normalized_message
        or (has_contact_action and has_rule_signal)
    )


def _active_task(state: RecouvrementWorkflowState) -> str:
    """Return the active task passed by the drawer, when available."""
    assistant_state = state.get("assistant_state") or {}
    active = assistant_state.get("activeTask")
    return str(active) if active is not None else ""


def _current_artifact(state: RecouvrementWorkflowState) -> RecouvrementArtifact | None:
    """Return the current drawer artifact, if the frontend provided one."""
    assistant_state = state.get("assistant_state") or {}
    raw = assistant_state.get("currentArtifact") or assistant_state.get("artifact")
    if not isinstance(raw, dict):
        return None
    artifact_type = raw.get("type")
    artifact_task = raw.get("task")
    artifact_title = raw.get("title")
    artifact_status = raw.get("status")
    artifact_content = raw.get("content")
    artifact_id = raw.get("id")
    if (
        not isinstance(artifact_id, str)
        or not isinstance(artifact_type, str)
        or not isinstance(artifact_task, str)
        or not isinstance(artifact_title, str)
        or not isinstance(artifact_status, str)
        or not isinstance(artifact_content, dict)
    ):
        return None
    return {
        "id": artifact_id,
        "type": artifact_type,
        "task": artifact_task,
        "title": artifact_title,
        "status": artifact_status,
        "content": cast(dict[str, object], dict(artifact_content)),
    }


def _artifact_content_int(artifact: RecouvrementArtifact | None, key: str) -> int | None:
    if artifact is None:
        return None
    value = artifact["content"].get(key)
    return value if isinstance(value, int) else None


def _artifact_content_str(artifact: RecouvrementArtifact | None, key: str) -> str | None:
    if artifact is None:
        return None
    value = artifact["content"].get(key)
    return value if isinstance(value, str) else None


def _parse_duration_months(message: str) -> int | None:
    """Extract a requested schedule duration from French free text."""
    normalized = _normalize_message(message)
    match = re.search(r"\b(\d{1,3})\s*(?:mois|mensualite|mensualites)\b", normalized)
    if match is None:
        return None
    months = int(match.group(1))
    return months if months > 0 else None


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


def _format_euro(value: float) -> str:
    """Format a deterministic euro amount with French decimal punctuation."""
    return f"{value:.2f}".replace(".", ",") + " €"


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
    """Route the supported Recouvrement intents from the current Julie message."""
    normalized = _normalize_message(state["message"])
    active_task = _active_task(state)
    has_schedule_intent = _has_schedule_intent(normalized)
    has_draft_intent = _has_draft_intent(normalized)
    has_summary_intent = _has_summary_intent(normalized)
    has_payment_options_intent = _has_payment_options_intent(normalized)
    has_requested_duration = _parse_duration_months(state["message"]) is not None
    if has_draft_intent and not has_schedule_intent and not has_payment_options_intent:
        intent = "draft_reminder"
        confidence = 0.93
    elif has_schedule_intent and (has_requested_duration or not has_payment_options_intent):
        intent = "propose_schedule"
        confidence = 0.94
    elif has_payment_options_intent:
        intent = "explain_payment_options"
        confidence = 0.94
    elif has_summary_intent:
        intent = "summarize_case"
        confidence = 0.95
    elif _has_contact_rule_intent(normalized):
        intent = "check_contact_rule"
        confidence = 0.96
    elif active_task == "explain_payment_options":
        intent = "explain_payment_options"
        confidence = 0.82
    elif active_task == "summary":
        intent = "summarize_case"
        confidence = 0.82
    elif active_task in {"check_rule", "check_contact_rule"}:
        intent = "check_contact_rule"
        confidence = 0.82
    elif active_task == "draft_reminder":
        intent = "draft_reminder"
        confidence = 0.82
    else:
        intent = "check_contact_rule"
        confidence = 0.72
    record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        payload={"intent": intent, "confidence": confidence, "active_task": active_task},
        **_event_common(state, node_name="route_recouvrement_intent"),
    )
    return {"intent": intent, "intent_confidence": confidence}


def extract_recouvrement_slots(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Extract slots needed by the routed Recouvrement workflow."""
    case = state["case"]
    intent = state.get("intent", "check_contact_rule")
    current_artifact = _current_artifact(state)
    if intent == "propose_schedule":
        requested_months = _parse_duration_months(state["message"]) or 3
        monthly_amount = round(case.amount_due / requested_months, 2)
        slots: dict[str, object] = {
            "case_id": state["case_id"],
            "requested_months": requested_months,
            "amount_due": case.amount_due,
            "amount_due_label": case.amount_due_label,
            "monthly_amount": monthly_amount,
            "monthly_amount_label": _format_euro(monthly_amount),
            "rule_impacting": True,
        }
    elif intent == "draft_reminder":
        normalized = _normalize_message(state["message"])
        current_artifact_type = current_artifact["type"] if current_artifact is not None else None
        schedule_months = _artifact_content_int(current_artifact, "duration_months")
        schedule_monthly_amount = _artifact_content_str(current_artifact, "monthly_amount")
        mentions_schedule = _has_schedule_intent(normalized) or current_artifact_type in {
            "schedule_proposal_v2",
            "client_message_artifact",
        }
        slots = {
            "case_id": state["case_id"],
            "amount_due": case.amount_due,
            "amount_due_label": case.amount_due_label,
            "mentions_schedule": mentions_schedule,
            "current_artifact_type": current_artifact_type,
            "requested_months": schedule_months,
            "monthly_amount_label": schedule_monthly_amount,
            "tone": "empathique"
            if "empathique" in normalized or "rends-le" in normalized or "rend le" in normalized
            else "amiable et factuel",
            "rule_impacting": mentions_schedule,
        }
    elif intent == "summarize_case":
        slots = {
            "case_id": state["case_id"],
            "amount_due": case.amount_due,
            "amount_due_label": case.amount_due_label,
            "days_late": case.days_late,
            "missed_promise": case.missed_promise,
            "contact_window": case.contact_window_label,
            "recommended_channel": case.recommended_channel,
            "alternative_channel": case.alternative_channel,
            "no_external_effect": True,
        }
    elif intent == "explain_payment_options":
        slots = {
            "case_id": state["case_id"],
            "amount_due": case.amount_due,
            "amount_due_label": case.amount_due_label,
            "days_late": case.days_late,
            "missed_promise": case.missed_promise,
            "contact_window": case.contact_window_label,
            "schedule_option_mentioned": True,
            "validation_required": True,
            "client_agreement_required": True,
            "no_payment_initiated": True,
            "no_payment_link_created": True,
            "no_payment_link_sent": True,
            "no_schedule_created": True,
            "no_external_effect": True,
        }
    else:
        requested_time = _parse_time(state["message"])
        slots = {
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


def _route_after_slot_extraction(state: RecouvrementWorkflowState) -> str:
    """Route to the policy node that matches the detected business intent."""
    if state.get("intent") == "propose_schedule":
        return "schedule"
    if state.get("intent") == "draft_reminder":
        return "draft"
    if state.get("intent") == "summarize_case":
        return "summary"
    if state.get("intent") == "explain_payment_options":
        return "payment_options"
    return "contact"


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


def evaluate_schedule_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Evaluate the validation policy for an indicative payment schedule."""
    case = state["case"]
    slots = state["slots"]
    requested_months_raw = slots.get("requested_months")
    requested_months = requested_months_raw if isinstance(requested_months_raw, int) else 3
    monthly_amount_raw = slots.get("monthly_amount")
    monthly_amount = (
        float(monthly_amount_raw)
        if isinstance(monthly_amount_raw, int | float)
        else round(case.amount_due / requested_months, 2)
    )
    monthly_amount_label = str(slots.get("monthly_amount_label", _format_euro(monthly_amount)))
    decision: SchedulePolicyDecision = {
        "decision": "validation_required",
        "reason_codes": [
            "VALIDATION_REQUIRED",
            "CLIENT_AGREEMENT_REQUIRED",
            "SCHEDULE_NOT_CREATED",
        ],
        "requested_months": requested_months,
        "monthly_amount": monthly_amount,
        "monthly_amount_label": monthly_amount_label,
        "validation_required": True,
        "client_agreement_required": True,
        "schedule_created": False,
    }
    record_business_event(
        event_name=BusinessEventName.BUSINESS_RULE_CHECKED,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "rule_id": "SCHEDULE_VALIDATION",
            "result": "validation_required",
            "decision": decision["decision"],
        },
        **_event_common(state, node_name="evaluate_schedule_policy"),
    )
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.schedule_validation",
            "rule_id": "SCHEDULE_VALIDATION",
        },
        **_event_common(state, node_name="evaluate_schedule_policy"),
    )
    return {"schedule_policy": decision}


def _template_generation_metadata(
    template: RecouvrementMessageTemplate,
) -> DraftGenerationMetadata:
    """Build auditable provenance metadata for an approved template."""
    return {
        "generation_mode": template.generation_mode,
        "template_id": template.template_id,
        "template_version": template.template_version,
        "template_label": template.template_label,
        "template_tone": template.template_tone,
        "allowed_use_cases": list(template.allowed_use_cases),
        "model_id": template.model_id,
        "prompt_version": template.prompt_version,
    }


def _select_draft_template(slots: dict[str, object]) -> RecouvrementMessageTemplate:
    """Select the approved template matching the current Recouvrement drafting task."""
    if bool(slots.get("mentions_schedule")):
        return RECOUVREMENT_SCHEDULE_MESSAGE_V1
    if str(slots.get("tone", "")) == "empathique":
        return RECOUVREMENT_REMINDER_EMPATHIC_V1
    return RECOUVREMENT_REMINDER_SHORT_V1


def draft_client_message(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Select and render an approved template; replaceable by an LLM rewrite node later."""
    case = state["case"]
    slots = state["slots"]
    template = _select_draft_template(slots)
    requested_months = slots.get("requested_months")
    monthly_amount_label = slots.get("monthly_amount_label")
    draft = template.render(
        {
            "client": case.client,
            "case_id": case.case_id,
            "amount_due_label": case.amount_due_label,
            "days_late": case.days_late,
            "schedule_sentence": render_schedule_sentence(requested_months, monthly_amount_label),
        }
    )
    return {
        "draft_message": draft,
        "draft_generation": _template_generation_metadata(template),
    }


def review_client_message_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Review a drafted client message with deterministic Recouvrement safety checks."""
    case = state["case"]
    draft = state["draft_message"]
    slots = state["slots"]
    generation = state["draft_generation"]
    normalized_draft = _normalize_message(draft)
    forbidden_terms = {
        "mise en demeure",
        "sanction",
        "resiliation",
        "frais d'incident",
        "pression",
        "immediatement obligatoire",
        "nous acceptons",
        "nous vous accordons",
        "echeancier accepte",
        "echeancier valide",
    }
    unsafe = any(term in normalized_draft for term in forbidden_terms)
    amount_consistent = case.amount_due_label in draft
    mentions_schedule = bool(slots.get("mentions_schedule"))
    validation_required = mentions_schedule
    reason_codes = ["MESSAGE_SAFE", "AMOUNT_CONSISTENT", "MESSAGE_NOT_SENT"]
    if validation_required:
        reason_codes = [
            "VALIDATION_REQUIRED",
            "CLIENT_AGREEMENT_REQUIRED",
            "SCHEDULE_NOT_CREATED",
            "AMOUNT_CONSISTENT",
            "MESSAGE_NOT_SENT",
        ]
    if not amount_consistent:
        reason_codes = ["AMOUNT_MISMATCH"]
        unsafe = True
    if unsafe:
        reason_codes = (
            reason_codes if reason_codes == ["AMOUNT_MISMATCH"] else ["UNSAFE_CLIENT_MESSAGE"]
        )
    policy_decision = (
        "blocked" if unsafe else ("validation_required" if validation_required else "approved")
    )
    decision: DraftPolicyDecision = {
        "decision": policy_decision,
        "reason_codes": reason_codes,
        "policy_review_status": policy_decision,
        "tone": str(slots.get("tone", "amiable et factuel")),
        "mentions_schedule": mentions_schedule,
        "amount_consistent": amount_consistent,
        "validation_required": validation_required,
        "client_agreement_required": validation_required,
        "schedule_created": False,
        "message_sent": False,
        "no_schedule_created": True,
        "no_message_sent": True,
    }
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.client_message_safety",
            "rule_id": "CLIENT_MESSAGE_SAFETY",
            "generation_mode": generation["generation_mode"],
            "template_id": generation["template_id"],
            "template_version": generation["template_version"],
            "template_label": generation["template_label"],
            "policy_review_status": decision["policy_review_status"],
            "amount_consistent": amount_consistent,
        },
        **_event_common(state, node_name="review_client_message_policy"),
    )
    return {"draft_policy": decision}


def review_case_summary_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Review that the case summary only uses the centralised snapshot."""
    case = state["case"]
    slots = state["slots"]
    amount_consistent = (
        slots.get("amount_due") == case.amount_due
        and slots.get("amount_due_label") == case.amount_due_label
    )
    reason_codes = [
        "SNAPSHOT_ONLY",
        "MESSAGE_NOT_SENT",
        "SCHEDULE_NOT_CREATED",
        "NO_EXTERNAL_EFFECT",
        "NO_VALIDATION_DECISION",
    ]
    if not amount_consistent:
        reason_codes = ["AMOUNT_MISMATCH"]
    decision: SummaryPolicyDecision = {
        "decision": "approved" if amount_consistent else "blocked",
        "reason_codes": reason_codes,
        "policy_review_status": "approved" if amount_consistent else "blocked",
        "amount_consistent": amount_consistent,
        "message_sent": False,
        "schedule_created": False,
        "external_effect": False,
        "validation_decision": False,
    }
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.case_summary_safety",
            "rule_id": "CASE_SUMMARY_SAFETY",
            "amount_consistent": amount_consistent,
            "requires_validation": False,
            "no_external_effect": True,
        },
        **_event_common(state, node_name="review_case_summary_policy"),
    )
    return {"summary_policy": decision}


def review_payment_options_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Review that payment-option guidance stays indicative and side-effect free."""
    case = state["case"]
    slots = state["slots"]
    amount_consistent = (
        slots.get("amount_due") == case.amount_due
        and slots.get("amount_due_label") == case.amount_due_label
    )
    reason_codes = [
        "PAYMENT_NOT_INITIATED",
        "PAYMENT_LINK_NOT_CREATED",
        "PAYMENT_LINK_NOT_SENT",
        "SCHEDULE_NOT_CREATED",
        "VALIDATION_REQUIRED",
        "CLIENT_AGREEMENT_REQUIRED",
        "SNAPSHOT_ONLY",
        "NO_EXTERNAL_EFFECT",
    ]
    if not amount_consistent:
        reason_codes = ["AMOUNT_MISMATCH"]
    policy_review_status = "validation_required" if amount_consistent else "blocked"
    decision: PaymentOptionsPolicyDecision = {
        "decision": policy_review_status,
        "reason_codes": reason_codes,
        "policy_review_status": policy_review_status,
        "amount_consistent": amount_consistent,
        "validation_required": amount_consistent,
        "client_agreement_required": amount_consistent,
        "payment_initiated": False,
        "payment_link_created": False,
        "payment_link_sent": False,
        "schedule_created": False,
        "no_payment_initiated": True,
        "no_payment_link_created": True,
        "no_payment_link_sent": True,
        "no_schedule_created": True,
        "no_external_effect": True,
    }
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.payment_options_safety",
            "rule_id": "PAYMENT_OPTIONS_SAFETY",
            "policy_review_status": decision["policy_review_status"],
            "amount_consistent": amount_consistent,
            "requires_validation": decision["validation_required"],
            "no_payment_initiated": decision["no_payment_initiated"],
            "no_payment_link_created": decision["no_payment_link_created"],
            "no_payment_link_sent": decision["no_payment_link_sent"],
            "no_schedule_created": decision["no_schedule_created"],
            "no_external_effect": decision["no_external_effect"],
        },
        **_event_common(state, node_name="review_payment_options_policy"),
    )
    return {"payment_options_policy": decision}


def build_case_summary_artifact(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Build the drawer-compatible case-summary artifact."""
    case = state["case"]
    policy = state["summary_policy"]
    priority_reasons = [
        f"Retard de {case.days_late} jours",
        case.missed_promise,
        "Dossier déjà dans la file prioritaire Recouvrement",
    ]
    business_factors = [
        f"Montant dû : {case.amount_due_label}",
        f"Canal recommandé : {case.recommended_channel}",
        f"Plage de contact : {case.contact_window_label}",
    ]
    risk_factors = [
        "Engagement de paiement non respecté",
        "Risque de nouvelle absence de réponse",
        "Action à conserver dans un cadre amiable et tracé",
    ]
    allowed_actions = [
        "Rédiger une relance amiable",
        "Vérifier la règle de contact",
        "Préparer un échéancier indicatif soumis à validation",
        "Insérer une note préparée dans le dossier",
    ]
    blocked_or_sensitive_actions = [
        "Ne pas envoyer de message automatiquement",
        "Ne pas créer d'échéancier sans validation",
        "Ne pas exécuter d'écriture définitive dans le dossier",
        "Ne pas contacter hors plage autorisée",
    ]
    recommended_next_action = "Vérifier le canal de contact puis préparer une relance amiable."
    summary = (
        f"{case.case_id} concerne {case.client}, avec {case.amount_due_label} dus, "
        f"{case.days_late} jours de retard et une {case.missed_promise}."
    )
    artifact: RecouvrementArtifact = {
        "id": f"{case.case_id}-summary-v1",
        "type": "case_summary_v1",
        "task": "summary",
        "title": f"Résumé du dossier — {case.case_id}",
        "status": "draft",
        "content": {
            "case_id": case.case_id,
            "client": case.client,
            "amount_due": case.amount_due_label,
            "amount_due_numeric": case.amount_due,
            "days_late": case.days_late,
            "missed_promise": case.missed_promise,
            "contact_window": case.contact_window_label,
            "recommended_channel": case.recommended_channel,
            "alternative_channel": case.alternative_channel,
            "summary": summary,
            "priorityReasons": priority_reasons,
            "businessFactors": business_factors,
            "riskFactors": risk_factors,
            "recommendedNextAction": recommended_next_action,
            "allowedActions": allowed_actions,
            "blockedOrSensitiveActions": blocked_or_sensitive_actions,
            "contextUsed": _context_items(case),
            "policy_review_status": policy["policy_review_status"],
            "message_sent": policy["message_sent"],
            "schedule_created": policy["schedule_created"],
            "no_message_sent": True,
            "no_schedule_created": True,
            "no_external_effect": True,
            "validation_decision": policy["validation_decision"],
            "reason_codes": policy["reason_codes"],
        },
    }
    next_actions = [
        "Rédiger une relance",
        "Vérifier une règle",
        "Proposer un échéancier",
        "Insérer dans le dossier",
    ]
    card_updates = {
        "context": _context_items(case),
        "summary": [
            summary,
            *priority_reasons,
            recommended_next_action,
        ],
        "priorityReasons": priority_reasons,
        "businessFactors": business_factors,
        "riskFactors": risk_factors,
        "allowedActions": allowed_actions,
        "blockedOrSensitiveActions": blocked_or_sensitive_actions,
        "complianceChecks": [
            "Contexte utilisé : snapshot RC-2048 centralisé",
            "Aucune donnée hors dossier ajoutée",
            "Aucun message client généré",
            "Aucune action exécutée",
            "Aucun échéancier créé",
            "Effet externe : aucun",
        ],
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
            "policy_review_status": policy["policy_review_status"],
            "no_message_sent": True,
            "no_schedule_created": True,
            "no_external_effect": True,
        },
        **_event_common(state, node_name="build_case_summary_artifact"),
    )
    return {
        "artifact": artifact,
        "card_updates": card_updates,
        "suggested_actions": next_actions,
    }


def build_payment_options_artifact(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Build the drawer-compatible payment-options artifact."""
    case = state["case"]
    policy = state["payment_options_policy"]
    options = [
        "Paiement total : option à confirmer selon les moyens disponibles dans le dossier.",
        "Paiement partiel : montant et modalités à confirmer avant toute proposition.",
        "Échéancier indicatif : possible uniquement après validation interne et accord client.",
        "Contact conseiller / rappel : préparer un échange pour confirmer la solution adaptée.",
    ]
    eligibility_notes = [
        "Options à confirmer selon les moyens disponibles dans le dossier.",
        "Aucun moyen de paiement spécifique n'est disponible dans le snapshot RC-2048.",
        "Ne pas citer de moyen de paiement spécifique sans donnée confirmée.",
    ]
    required_validation = [
        "Validation interne requise avant toute option d'échéancier",
        "Accord client requis avant mise en place",
    ]
    recommended_next_action = (
        "Confirmer les moyens disponibles dans le dossier, puis préparer un échéancier "
        "indicatif si une validation est obtenue."
    )
    artifact: RecouvrementArtifact = {
        "id": f"{case.case_id}-payment-options-v1",
        "type": "payment_options_v1",
        "task": "explain_payment_options",
        "title": f"Options de paiement — {case.case_id}",
        "status": "draft",
        "content": {
            "case_id": case.case_id,
            "client": case.client,
            "amountDue": case.amount_due_label,
            "amount_due": case.amount_due_label,
            "amount_due_numeric": case.amount_due,
            "options": options,
            "eligibilityNotes": eligibility_notes,
            "requiredValidation": required_validation,
            "required_validation": required_validation,
            "validation_required": policy["validation_required"],
            "clientAgreementRequired": policy["client_agreement_required"],
            "client_agreement_required": policy["client_agreement_required"],
            "recommendedNextAction": recommended_next_action,
            "contextUsed": _context_items(case),
            "no_payment_initiated": policy["no_payment_initiated"],
            "no_payment_link_created": policy["no_payment_link_created"],
            "no_payment_link_sent": policy["no_payment_link_sent"],
            "no_schedule_created": policy["no_schedule_created"],
            "no_external_effect": policy["no_external_effect"],
            "payment_initiated": policy["payment_initiated"],
            "payment_link_created": policy["payment_link_created"],
            "payment_link_sent": policy["payment_link_sent"],
            "schedule_created": policy["schedule_created"],
            "policy_review_status": policy["policy_review_status"],
            "reason_codes": policy["reason_codes"],
        },
    }
    next_actions = [
        "Proposer un échéancier",
        "Préparer le message client",
        "Soumettre à validation",
        "Insérer dans le dossier",
    ]
    card_updates = {
        "context": _context_items(case),
        "summary": [
            f"Montant dû : {case.amount_due_label}",
            "Options de règlement préparées sans initier de paiement",
            "Moyens disponibles à confirmer dans le dossier",
            "Aucun lien de paiement créé ou envoyé",
            "Aucun échéancier créé",
        ],
        "paymentOptions": options,
        "eligibilityNotes": eligibility_notes,
        "requiredValidation": required_validation,
        "complianceChecks": [
            "Aucun paiement initié",
            "Aucun lien de paiement créé",
            "Aucun lien de paiement envoyé",
            "Aucun échéancier créé",
            "Validation requise si une option d'échéancier est retenue",
            "Effet externe : aucun",
        ],
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
            "policy_review_status": policy["policy_review_status"],
            "no_payment_initiated": policy["no_payment_initiated"],
            "no_payment_link_created": policy["no_payment_link_created"],
            "no_payment_link_sent": policy["no_payment_link_sent"],
            "no_schedule_created": policy["no_schedule_created"],
            "no_external_effect": policy["no_external_effect"],
        },
        **_event_common(state, node_name="build_payment_options_artifact"),
    )
    return {
        "artifact": artifact,
        "card_updates": card_updates,
        "suggested_actions": next_actions,
    }


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


def build_schedule_proposal_artifact(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Build the drawer-compatible indicative payment-schedule artifact."""
    case = state["case"]
    policy = state["schedule_policy"]
    requested_months = policy["requested_months"]
    monthly_amount_label = policy["monthly_amount_label"]
    schedule_title = f"Échéancier indicatif — {requested_months} mois"
    client_message = RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1.render({})
    client_message_generation = _template_generation_metadata(RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1)
    artifact: RecouvrementArtifact = {
        "id": f"{case.case_id}-schedule-{requested_months}-months-v2",
        "type": "schedule_proposal_v2",
        "task": "propose_schedule",
        "title": f"Proposition d'échéancier — {case.case_id}",
        "status": "draft",
        "content": {
            "case_id": case.case_id,
            "client": case.client,
            "amount_due": case.amount_due_label,
            "amount_due_numeric": case.amount_due,
            "duration_months": requested_months,
            "monthly_amount": monthly_amount_label,
            "monthly_amount_numeric": policy["monthly_amount"],
            "validation_required": policy["validation_required"],
            "client_agreement_required": policy["client_agreement_required"],
            "created": policy["schedule_created"],
            "schedule_created": policy["schedule_created"],
            "status": "indicatif",
            "reason_codes": policy["reason_codes"],
            "client_message_generation": client_message_generation,
        },
    }
    next_actions = [
        "Ajuster la durée",
        "Comparer les options",
        "Préparer le message client",
        "Soumettre à validation",
    ]
    payment_plan = [
        schedule_title,
        f"Montant dû : {case.amount_due_label}",
        f"Durée demandée : {requested_months} mois",
        f"Mensualité indicative : {monthly_amount_label}",
        "Statut : validation requise avant proposition",
        "Échéancier non créé",
        "Accord client requis",
    ]
    card_updates = {
        "context": _context_items(case),
        "summary": [
            f"Étalement demandé : {requested_months} mois",
            f"Mensualité indicative : {monthly_amount_label}",
            "Validation interne requise avant proposition au client",
            "Échéancier non créé",
            "Accord client requis",
        ],
        "paymentPlan": payment_plan,
        "scheduleItems": [
            f"{requested_months} mensualités indicatives de {monthly_amount_label}",
            f"Total : {case.amount_due_label}",
            "Validation interne requise avant proposition",
            "Aucun échéancier créé",
        ],
        "scheduleVersionLabel": [f"Version indicative — {requested_months} mois"],
        "clientMessage": [client_message],
        "complianceChecks": [
            "Validation requise avant proposition",
            "Accord client nécessaire avant création",
            "Échéancier non créé",
            f"Montant total conservé : {case.amount_due_label}",
        ],
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
            "client_message_generation": client_message_generation,
            "no_schedule_created": True,
        },
        **_event_common(state, node_name="build_schedule_proposal_artifact"),
    )
    record_business_event(
        event_name=BusinessEventName.VALIDATION_REQUESTED,
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=artifact["status"],
        decision=policy["decision"],
        reason_codes=policy["reason_codes"],
        payload={
            "validation_type": "internal_schedule_validation",
            "validation_reason": "Échéancier indicatif à valider avant proposition au client.",
        },
        **_event_common(state, node_name="build_schedule_proposal_artifact"),
    )
    record_business_event(
        event_name=BusinessEventName.ACTION_PREPARED,
        decision="prepared",
        reason_codes=["VALIDATION_REQUIRED"],
        payload={"action_name": "prepare_schedule_proposal"},
        **_event_common(state, node_name="build_schedule_proposal_artifact"),
    )
    return {
        "artifact": artifact,
        "card_updates": card_updates,
        "suggested_actions": next_actions,
    }


def build_reminder_draft_artifact(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Build the drawer-compatible reminder/client-message artifact."""
    case = state["case"]
    slots = state["slots"]
    policy = state["draft_policy"]
    generation = state["draft_generation"]
    current_artifact = _current_artifact(state)
    current_artifact_type = current_artifact["type"] if current_artifact is not None else None
    from_schedule = current_artifact_type == "schedule_proposal_v2"
    artifact_type = "client_message_artifact" if from_schedule else "reminder_draft_v1"
    version_number = (
        "2" if generation["template_id"] == RECOUVREMENT_REMINDER_EMPATHIC_V1.template_id else "1"
    )
    version_label = f"Version {version_number} — {generation['template_label']}"
    title = (
        f"Message client préparé — {case.case_id}"
        if from_schedule
        else f"Brouillon de relance — {case.case_id}"
    )
    artifact: RecouvrementArtifact = {
        "id": (
            f"{case.case_id}-client-message-v1"
            if from_schedule
            else f"{case.case_id}-reminder-v1"
        ),
        "type": artifact_type,
        "task": "draft_reminder",
        "title": title,
        "status": "draft",
        "content": {
            "case_id": case.case_id,
            "client": case.client,
            "message_client": state["draft_message"],
            "tone": policy["tone"],
            "channel": case.alternative_channel,
            "generation_mode": generation["generation_mode"],
            "template_id": generation["template_id"],
            "template_version": generation["template_version"],
            "template_label": generation["template_label"],
            "template_tone": generation["template_tone"],
            "model_id": generation["model_id"],
            "prompt_version": generation["prompt_version"],
            "policy_review_status": policy["policy_review_status"],
            "validation_required": policy["validation_required"],
            "client_agreement_required": policy["client_agreement_required"],
            "schedule_created": policy["schedule_created"],
            "message_sent": policy["message_sent"],
            "no_email_sent": True,
            "no_message_sent": policy["no_message_sent"],
            "no_schedule_created": policy["no_schedule_created"],
            "amount_due": case.amount_due_label,
            "mentions_schedule": policy["mentions_schedule"],
            "reason_codes": policy["reason_codes"],
            "source_artifact_id": current_artifact["id"] if current_artifact is not None else None,
        },
    }
    compliance_checks = [
        f"Ton {policy['tone']}",
        "Aucune menace ni pression injustifiée",
        "Aucun message envoyé",
        f"Montant cohérent : {case.amount_due_label}",
    ]
    if policy["mentions_schedule"]:
        compliance_checks.extend(
            [
                "Validation requise avant proposition d'échéancier",
                "Accord client nécessaire",
                "Aucun échéancier créé",
            ]
        )
    else:
        compliance_checks.append("Aucune validation d'échéancier requise dans ce brouillon")

    next_actions = [
        "Modifier le message",
        "Copier le message",
        "Insérer dans le dossier",
        "Soumettre à validation",
    ]
    card_updates = {
        "context": _context_items(case),
        "summary": [
            f"Dossier : {case.case_id}",
            f"Client : {case.client}",
            f"Montant dû : {case.amount_due_label}",
            f"Retard : {case.days_late} jours",
            "Message préparé sans envoi",
        ],
        "clientMessage": [state["draft_message"]],
        "draftVersionLabel": [version_label],
        "complianceChecks": compliance_checks,
        "nextActions": next_actions,
    }
    if policy["mentions_schedule"]:
        requested_months = slots.get("requested_months")
        monthly_amount_label = slots.get("monthly_amount_label")
        card_updates["paymentPlan"] = [
            "Solution d'échelonnement évoquée uniquement comme option à valider",
            f"Montant dû : {case.amount_due_label}",
            f"Durée indicative : {requested_months} mois"
            if isinstance(requested_months, int)
            else "Durée indicative : à confirmer",
            f"Mensualité indicative : {monthly_amount_label}"
            if isinstance(monthly_amount_label, str)
            else "Mensualité indicative : à confirmer",
            "Échéancier non créé",
        ]
    record_business_event(
        event_name=BusinessEventName.ARTIFACT_CREATED,
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=artifact["status"],
        payload={
            "task": artifact["task"],
            "title": artifact["title"],
            "decision": policy["decision"],
            "generation_mode": generation["generation_mode"],
            "template_id": generation["template_id"],
            "template_version": generation["template_version"],
            "template_label": generation["template_label"],
            "policy_review_status": policy["policy_review_status"],
            "no_message_sent": policy["no_message_sent"],
            "no_schedule_created": policy["no_schedule_created"],
        },
        **_event_common(state, node_name="build_reminder_draft_artifact"),
    )
    if policy["validation_required"]:
        record_business_event(
            event_name=BusinessEventName.VALIDATION_REQUESTED,
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=artifact["status"],
            decision=policy["decision"],
            reason_codes=policy["reason_codes"],
            payload={
                "validation_type": "client_message_schedule_validation",
                "validation_reason": "Message client mentionnant une solution d'échelonnement.",
            },
            **_event_common(state, node_name="build_reminder_draft_artifact"),
        )
    record_business_event(
        event_name=BusinessEventName.ACTION_PREPARED,
        decision="prepared",
        reason_codes=policy["reason_codes"],
        payload={"action_name": "prepare_client_message"},
        **_event_common(state, node_name="build_reminder_draft_artifact"),
    )
    return {
        "artifact": artifact,
        "card_updates": card_updates,
        "suggested_actions": next_actions,
    }


def generate_visible_reply(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Generate the natural-language response visible to Julie."""
    case = state["case"]
    if state.get("intent") == "summarize_case":
        summary_policy = state["summary_policy"]
        artifact = state["artifact"]
        reply = f"Résumé du dossier {case.case_id} mis à jour."
        task = "summary"
        message_payload = {
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": task,
            "generation_mode": "deterministic_builder",
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": summary_policy["policy_review_status"],
            "no_message_sent": True,
            "no_schedule_created": True,
            "no_external_effect": True,
        }
    elif state.get("intent") == "explain_payment_options":
        payment_policy = state["payment_options_policy"]
        artifact = state["artifact"]
        reply = f"Options de paiement du dossier {case.case_id} préparées."
        task = "explain_payment_options"
        message_payload = {
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": task,
            "generation_mode": "deterministic_builder",
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": payment_policy["policy_review_status"],
            "no_payment_initiated": payment_policy["no_payment_initiated"],
            "no_payment_link_created": payment_policy["no_payment_link_created"],
            "no_payment_link_sent": payment_policy["no_payment_link_sent"],
            "no_schedule_created": payment_policy["no_schedule_created"],
            "no_external_effect": payment_policy["no_external_effect"],
        }
    elif state.get("intent") == "propose_schedule":
        schedule_policy = state["schedule_policy"]
        artifact = state["artifact"]
        client_message_generation = artifact["content"].get("client_message_generation")
        reply = (
            f"Pour {case.case_id}, un étalement sur {schedule_policy['requested_months']} mois "
            f"représenterait environ {schedule_policy['monthly_amount_label']} par mois pour "
            f"un montant dû de {case.amount_due_label}. Cette proposition reste indicative, "
            "nécessite une validation interne et l'accord du client. Aucun échéancier n'a "
            "été créé."
        )
        task = "propose_schedule"
        message_payload = {
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": task,
            "generation_mode": "deterministic_builder",
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": schedule_policy["decision"],
            "client_message_generation": client_message_generation,
            "no_schedule_created": True,
        }
    elif state.get("intent") == "draft_reminder":
        draft_policy = state["draft_policy"]
        draft_generation = state["draft_generation"]
        artifact = state["artifact"]
        if draft_policy["validation_required"]:
            reply = (
                f"J'ai préparé un message client prudent pour {case.case_id}. Il mentionne "
                "une solution d'échelonnement uniquement comme option à valider ; aucun "
                "message n'a été envoyé et aucun échéancier n'a été créé."
            )
        else:
            reply = (
                f"J'ai préparé un brouillon de relance amiable pour {case.case_id}. "
                "Aucun message n'a été envoyé."
            )
        task = "draft_reminder"
        message_payload = {
            "message_kind": "client_message",
            "visible_reply": reply,
            "message_text": state["draft_message"],
            "task": task,
            "generation_mode": draft_generation["generation_mode"],
            "template_id": draft_generation["template_id"],
            "template_version": draft_generation["template_version"],
            "template_label": draft_generation["template_label"],
            "template_tone": draft_generation["template_tone"],
            "model_id": draft_generation["model_id"],
            "prompt_version": draft_generation["prompt_version"],
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": draft_policy["policy_review_status"],
            "no_message_sent": draft_policy["no_message_sent"],
            "no_schedule_created": draft_policy["no_schedule_created"],
        }
    else:
        policy = state["contact_policy"]
        artifact = state["artifact"]
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
        task = "check_rule"
        message_payload = {
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": task,
            "generation_mode": "deterministic_builder",
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": policy["decision"],
        }
    event_artifact = state["artifact"]
    record_business_event(
        event_name=BusinessEventName.MESSAGE_GENERATED,
        artifact_id=event_artifact["id"],
        artifact_type=event_artifact["type"],
        artifact_status=event_artifact["status"],
        payload=message_payload,
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
    decisions: dict[str, object] = {
        "intent": state.get("intent"),
        "confidence": state.get("intent_confidence"),
        "slots": state.get("slots", {}),
    }
    if "contact_policy" in state:
        decisions["contactPolicy"] = state["contact_policy"]
    if "schedule_policy" in state:
        decisions["schedulePolicy"] = state["schedule_policy"]
    if "draft_policy" in state:
        decisions["draftPolicy"] = state["draft_policy"]
    if "draft_generation" in state:
        decisions["draftGeneration"] = state["draft_generation"]
    if "summary_policy" in state:
        decisions["summaryPolicy"] = state["summary_policy"]
    if "payment_options_policy" in state:
        decisions["paymentOptionsPolicy"] = state["payment_options_policy"]
    output: RecouvrementOutput = {
        "visibleReply": state["visible_reply"],
        "artifact": state["artifact"],
        "cardUpdates": state["card_updates"],
        "suggestedActions": state["suggested_actions"],
        "businessEvents": events,
        "businessScores": scores,
        "decisions": decisions,
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


def finalize_unauthorized_surface(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Return a controlled refusal without executing the contact business rule."""
    surface = str(state.get("surface", DEFAULT_SURFACE))
    reply = (
        "Cette surface n'est pas autorisée pour l'assistant Recouvrement. "
        "Ouvrez le dossier depuis l'espace Recouvrement ou depuis le cockpit opérateur."
    )
    events = business_events_mod.business_event_rows(
        agent_id=RECOUVREMENT_AGENT_ID,
        conversation_id=state["conversation_id"],
        turn_id=state["turn_id"],
    )
    output: RecouvrementOutput = {
        "visibleReply": reply,
        "artifact": {
            "id": f"{state['case_id']}-authorization-denial-v1",
            "type": "authorization_denial_v1",
            "task": "authorization",
            "title": f"Accès non autorisé — {state['case_id']}",
            "status": "blocked",
            "content": {
                "case_id": state["case_id"],
                "requested_surface": surface,
                "decision": "blocked",
                "reason_codes": ["UNAUTHORIZED_SURFACE"],
            },
        },
        "cardUpdates": {
            "context": [
                f"Dossier : {state['case_id']}",
                f"Surface demandée : {surface}",
                "Accès refusé avant exécution de la règle métier.",
            ],
            "validationItems": [
                "La surface demandée n'est pas autorisée pour le workflow Recouvrement."
            ],
            "nextActions": ["Ouvrir l'espace Recouvrement", "Retourner au cockpit opérateur"],
        },
        "suggestedActions": ["Ouvrir l'espace Recouvrement", "Retourner au cockpit opérateur"],
        "businessEvents": events,
        "businessScores": business_scoring.score_rows(events),
        "decisions": {
            "authorization": {
                "decision": "blocked",
                "reason_codes": ["UNAUTHORIZED_SURFACE"],
                "surface": surface,
            }
        },
    }
    replay.capture_bundle(
        question=state["message"],
        context=f"Surface demandée : {surface}",
        original_answer=reply,
        language=state.get("language", "fr"),
        original_score=1.0,
        original_model=RECOUVREMENT_WORKFLOW_ID,
        conversation_id=state["conversation_id"],
        agent_id=RECOUVREMENT_AGENT_ID,
        turn_id=state["turn_id"],
        business_events=events,
    )
    return {"output": output}


def _canonical_artifact_action(action_name: str) -> str:
    """Return the canonical backend action name from a UI label or API value."""
    normalized = _normalize_message(action_name).replace("_", " ")
    compact = normalized.strip()
    if action_name in {
        "submit_for_validation",
        "insert_artifact_in_case",
        "copy_artifact_text",
        "prepare_reminder_tomorrow",
    }:
        return action_name
    if "soumettre" in compact or "validation" in compact:
        return "submit_for_validation"
    if "inserer" in compact:
        return "insert_artifact_in_case"
    if "copier" in compact or "copy" in compact:
        return "copy_artifact_text"
    if "rappel" in compact and "demain" in compact:
        return "prepare_reminder_tomorrow"
    return compact.replace(" ", "_")


def _artifact_mentions_schedule(artifact: RecouvrementArtifact) -> bool:
    """Whether an artifact carries schedule-sensitive content."""
    content = artifact["content"]
    return (
        artifact["type"] == "schedule_proposal_v2"
        or bool(content.get("mentions_schedule"))
        or bool(content.get("validation_required"))
        or content.get("duration_months") is not None
    )


def _action_payload(decision: ArtifactActionDecision) -> dict[str, object]:
    """Payload shape shared by action lifecycle events."""
    return {
        "artifact_id": decision["artifact_id"],
        "artifact_type": decision["artifact_type"],
        "action_name": decision["action_name"],
        "requested_by": decision["requested_by"],
        "case_id": decision["case_id"],
        "current_status": decision["current_status"],
        "target_status": decision["target_status"],
        "requires_validation": decision["requires_validation"],
        "no_external_effect": decision["no_external_effect"],
    }


def _artifact_action_decision(
    *,
    artifact: RecouvrementArtifact,
    action_name: str,
    requested_by: str,
    case: RecouvrementCaseSnapshot,
) -> ArtifactActionDecision:
    """Evaluate the controlled target status for an artifact action."""
    current_status = artifact["status"]
    mentions_schedule = _artifact_mentions_schedule(artifact)
    if action_name == "submit_for_validation":
        reason_codes = ["VALIDATION_REQUIRED", "NO_EXTERNAL_EFFECT"]
        if mentions_schedule:
            reason_codes.extend(["SCHEDULE_NOT_CREATED", "MESSAGE_NOT_SENT"])
        return {
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "action_name": action_name,
            "requested_by": requested_by,
            "case_id": case.case_id,
            "current_status": current_status,
            "target_status": "pending_validation",
            "requires_validation": True,
            "reason_codes": reason_codes,
            "no_external_effect": True,
            "blocked": False,
        }
    if action_name == "insert_artifact_in_case":
        return {
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "action_name": action_name,
            "requested_by": requested_by,
            "case_id": case.case_id,
            "current_status": current_status,
            "target_status": "insertion_prepared",
            "requires_validation": bool(artifact["content"].get("validation_required")),
            "reason_codes": ["CASE_WRITE_NOT_EXECUTED", "NO_EXTERNAL_EFFECT"],
            "no_external_effect": True,
            "blocked": False,
        }
    if action_name == "prepare_reminder_tomorrow":
        blocked_contact = (
            artifact["type"] == "contact_rule_v1"
            and artifact["content"].get("decision") == "blocked"
        )
        return {
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "action_name": action_name,
            "requested_by": requested_by,
            "case_id": case.case_id,
            "current_status": current_status,
            "target_status": "reminder_prepared" if blocked_contact else current_status,
            "requires_validation": False,
            "reason_codes": (
                ["REMINDER_PREPARED", "CALENDAR_EVENT_NOT_CREATED", "NO_EXTERNAL_EFFECT"]
                if blocked_contact
                else ["ACTION_NOT_APPLICABLE"]
            ),
            "no_external_effect": True,
            "blocked": not blocked_contact,
        }
    if action_name == "copy_artifact_text":
        return {
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "action_name": action_name,
            "requested_by": requested_by,
            "case_id": case.case_id,
            "current_status": current_status,
            "target_status": current_status,
            "requires_validation": False,
            "reason_codes": ["COPY_LOCAL_ONLY", "NO_EXTERNAL_EFFECT"],
            "no_external_effect": True,
            "blocked": False,
        }
    return {
        "artifact_id": artifact["id"],
        "artifact_type": artifact["type"],
        "action_name": action_name,
        "requested_by": requested_by,
        "case_id": case.case_id,
        "current_status": current_status,
        "target_status": current_status,
        "requires_validation": False,
        "reason_codes": ["UNSUPPORTED_ACTION"],
        "no_external_effect": True,
        "blocked": True,
    }


def _updated_artifact_for_action(
    artifact: RecouvrementArtifact,
    decision: ArtifactActionDecision,
) -> RecouvrementArtifact:
    """Return the same artifact with an explicit prepared status and no side effect."""
    content = dict(artifact["content"])
    content.update(
        {
            "last_action_name": decision["action_name"],
            "last_action_requested_by": decision["requested_by"],
            "action_status": decision["target_status"],
            "action_executed": False,
            "no_external_effect": decision["no_external_effect"],
        }
    )
    if decision["action_name"] == "submit_for_validation":
        content.update(
            {
                "validation_status": "pending_validation",
                "validation_required": True,
                "message_sent": False,
                "schedule_created": False,
                "no_message_sent": True,
                "no_schedule_created": True,
            }
        )
    elif decision["action_name"] == "insert_artifact_in_case":
        content.update(
            {
                "insertion_status": "insertion_prepared",
                "insertion_executed": False,
                "case_write_executed": False,
            }
        )
    elif decision["action_name"] == "prepare_reminder_tomorrow":
        content.update(
            {
                "reminder_status": "reminder_prepared",
                "calendar_event_created": False,
            }
        )
    elif decision["action_name"] == "copy_artifact_text":
        content.update({"copy_status": "local_clipboard_only"})
    return {
        **artifact,
        "status": decision["target_status"],
        "content": content,
    }


def _artifact_action_visible_reply(decision: ArtifactActionDecision) -> str:
    """Natural-language confirmation for a governed artifact action."""
    if decision["blocked"]:
        return (
            f"Cette action n'est pas disponible pour {decision['case_id']}. "
            "Aucune action client n'a été exécutée."
        )
    if decision["action_name"] == "submit_for_validation":
        return (
            f"Soumission à validation préparée pour {decision['case_id']}. "
            "Aucune action client n'a été exécutée."
        )
    if decision["action_name"] == "insert_artifact_in_case":
        return (
            f"Insertion préparée dans le dossier {decision['case_id']}. "
            "Aucune écriture définitive n'a encore été exécutée."
        )
    if decision["action_name"] == "prepare_reminder_tomorrow":
        return (
            f"Rappel préparé pour demain pour {decision['case_id']}. "
            "Aucun événement calendrier réel n'a été créé."
        )
    if decision["action_name"] == "copy_artifact_text":
        return (
            f"Copie préparée localement pour {decision['case_id']}. "
            "Aucune action client n'a été exécutée."
        )
    return f"Action préparée pour {decision['case_id']}. Aucune action client n'a été exécutée."


def _artifact_action_cards(
    decision: ArtifactActionDecision,
) -> tuple[dict[str, list[str]], list[str]]:
    """Drawer cards and suggested actions for a governed artifact action."""
    target = decision["target_status"]
    common = [
        f"Artefact ciblé : {decision['artifact_type']}",
        f"Statut : {target}",
        "Effet externe : aucun",
    ]
    if decision["action_name"] == "submit_for_validation":
        actions = ["Voir la demande", "Annuler", "Insérer dans le dossier"]
        return (
            {
                "summary": [
                    *common,
                    "Validation préparée",
                    "Aucun message envoyé",
                    "Aucun échéancier créé",
                ],
                "complianceChecks": [
                    "Validation requise",
                    "Aucun message envoyé",
                    "Aucun échéancier créé",
                    "Aucune action client exécutée",
                    "no_external_effect = true",
                ],
                "nextActions": actions,
            },
            actions,
        )
    if decision["action_name"] == "insert_artifact_in_case":
        actions = ["Confirmer l'insertion", "Annuler", "Voir le dossier"]
        return (
            {
                "summary": [
                    *common,
                    "Insertion préparée",
                    "Écriture définitive : non exécutée",
                ],
                "complianceChecks": [
                    "Artefact courant conservé",
                    "Aucun nouveau brouillon généré",
                    "Aucun message envoyé",
                    "Aucune écriture définitive exécutée",
                    "no_external_effect = true",
                ],
                "nextActions": actions,
            },
            actions,
        )
    if decision["action_name"] == "prepare_reminder_tomorrow":
        actions = ["Voir le rappel préparé", "Rédiger un email", "Annuler"]
        return (
            {
                "summary": [
                    *common,
                    "Rappel demain préparé",
                    "Événement calendrier réel : non créé",
                ],
                "complianceChecks": [
                    "Aucun événement calendrier créé",
                    "Aucun appel préparé hors plage",
                    "Aucune action client exécutée",
                    "no_external_effect = true",
                ],
                "nextActions": actions,
            },
            actions,
        )
    actions = ["Conserver l'artefact", "Retour au dossier"]
    return (
        {
            "summary": common,
            "complianceChecks": [
                "Action locale uniquement",
                "Aucun message envoyé",
                "Aucune action client exécutée",
            ],
            "nextActions": actions,
        },
        actions,
    )


def _finalize_action_output(
    *,
    event_state: RecouvrementWorkflowState,
    artifact: RecouvrementArtifact,
    visible_reply: str,
    card_updates: dict[str, list[str]],
    suggested_actions: list[str],
    decisions: dict[str, object],
) -> RecouvrementOutput:
    """Attach observability and replay to an artifact-action response."""
    events = business_events_mod.business_event_rows(
        agent_id=RECOUVREMENT_AGENT_ID,
        conversation_id=event_state["conversation_id"],
        turn_id=event_state["turn_id"],
    )
    scores = business_scoring.score_rows(events)
    context_case = event_state.get("case", _case_for(event_state["case_id"]))
    replay.capture_bundle(
        question=event_state["message"],
        context="\n".join(_context_items(context_case)),
        original_answer=visible_reply,
        language=event_state.get("language", "fr"),
        original_score=1.0,
        original_model=RECOUVREMENT_WORKFLOW_ID,
        conversation_id=event_state["conversation_id"],
        agent_id=RECOUVREMENT_AGENT_ID,
        turn_id=event_state["turn_id"],
        business_events=events,
    )
    return {
        "visibleReply": visible_reply,
        "artifact": artifact,
        "cardUpdates": card_updates,
        "suggestedActions": suggested_actions,
        "businessEvents": events,
        "businessScores": scores,
        "decisions": decisions,
    }


def run_recouvrement_action_workflow_v1(
    *,
    case_id: str,
    artifact: RecouvrementArtifact,
    action_name: str,
    requested_by: str = "Julie Dubois",
    conversation_id: str | None = None,
    turn_id: str | None = None,
    surface: str = DEFAULT_SURFACE,
    language: str = "fr",
    model: str = RECOUVREMENT_WORKFLOW_ID,
    environment: str = "dev",
) -> RecouvrementOutput:
    """Run a controlled backend cycle for sensitive actions on Recouvrement artifacts."""
    canonical_action = _canonical_artifact_action(action_name)
    event_state: RecouvrementWorkflowState = {
        "conversation_id": conversation_id or uuid.uuid4().hex,
        "turn_id": turn_id or uuid.uuid4().hex,
        "case_id": case_id,
        "message": canonical_action,
        "surface": surface,
        "language": language,
        "model": model,
        "environment": environment,
    }
    if not _surface_allowed(surface):
        record_business_event(
            event_name=BusinessEventName.ACTION_BLOCKED,
            decision="blocked",
            reason_codes=["UNAUTHORIZED_SURFACE"],
            payload={
                "action_name": canonical_action,
                "requested_surface": surface,
                "artifact_id": artifact["id"],
                "artifact_type": artifact["type"],
                "case_id": case_id,
                "current_status": artifact["status"],
                "target_status": artifact["status"],
                "requested_by": requested_by,
                "requires_validation": False,
                "no_external_effect": True,
            },
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=artifact["status"],
            agent_id=RECOUVREMENT_AGENT_ID,
            workflow_id=RECOUVREMENT_WORKFLOW_ID,
            surface=surface,
            conversation_id=event_state["conversation_id"],
            turn_id=event_state["turn_id"],
            case_id=case_id,
            node_name="verify_action_surface_authorization",
            language=language,
            model=model,
            environment=environment,
        )
        denial_artifact: RecouvrementArtifact = {
            "id": f"{case_id}-action-authorization-denial-v1",
            "type": "authorization_denial_v1",
            "task": "artifact_action",
            "title": f"Action non autorisée — {case_id}",
            "status": "blocked",
            "content": {
                "case_id": case_id,
                "requested_surface": surface,
                "action_name": canonical_action,
                "decision": "blocked",
                "reason_codes": ["UNAUTHORIZED_SURFACE"],
                "no_external_effect": True,
            },
        }
        return _finalize_action_output(
            event_state=event_state,
            artifact=denial_artifact,
            visible_reply=(
                "Cette surface n'est pas autorisée pour les actions Recouvrement. "
                "Aucune action client n'a été exécutée."
            ),
            card_updates={
                "summary": [
                    f"Dossier : {case_id}",
                    f"Surface demandée : {surface}",
                    "Action refusée avant tout effet métier.",
                ],
                "complianceChecks": [
                    "UNAUTHORIZED_SURFACE",
                    "Aucune action client exécutée",
                    "Aucun artefact métier modifié",
                ],
                "nextActions": ["Ouvrir l'espace Recouvrement", "Retourner au cockpit opérateur"],
            },
            suggested_actions=["Ouvrir l'espace Recouvrement", "Retourner au cockpit opérateur"],
            decisions={
                "authorization": {
                    "decision": "blocked",
                    "reason_codes": ["UNAUTHORIZED_SURFACE"],
                    "surface": surface,
                }
            },
        )

    case = _case_for(case_id)
    event_state["case"] = case
    record_business_event(
        event_name=BusinessEventName.CASE_CONTEXT_LOADED,
        payload={
            "client": case.client,
            "amount_due": case.amount_due,
            "days_late": case.days_late,
            "contact_window": case.contact_window_label,
        },
        **_event_common(event_state, node_name="load_action_case_context", case=case),
    )
    decision = _artifact_action_decision(
        artifact=artifact,
        action_name=canonical_action,
        requested_by=requested_by,
        case=case,
    )
    action_payload = _action_payload(decision)
    record_business_event(
        event_name=BusinessEventName.ACTION_REQUESTED,
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=artifact["status"],
        reason_codes=decision["reason_codes"],
        payload=action_payload,
        **_event_common(event_state, node_name="route_artifact_action"),
    )
    if decision["blocked"]:
        record_business_event(
            event_name=BusinessEventName.ACTION_BLOCKED,
            decision="blocked",
            reason_codes=decision["reason_codes"],
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=artifact["status"],
            payload=action_payload,
            **_event_common(event_state, node_name="evaluate_artifact_action_policy"),
        )
        visible_reply = _artifact_action_visible_reply(decision)
        card_updates, suggested_actions = _artifact_action_cards(decision)
        record_business_event(
            event_name=BusinessEventName.MESSAGE_GENERATED,
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=artifact["status"],
            payload={
                "message_kind": "internal_confirmation",
                "visible_reply": visible_reply,
                "task": "artifact_action",
                "generation_mode": "deterministic_builder",
                "artifact_id": artifact["id"],
                "artifact_type": artifact["type"],
                "policy_review_status": "blocked",
                "action_name": canonical_action,
                "no_external_effect": True,
            },
            **_event_common(event_state, node_name="generate_action_visible_reply"),
        )
        return _finalize_action_output(
            event_state=event_state,
            artifact=artifact,
            visible_reply=visible_reply,
            card_updates=card_updates,
            suggested_actions=suggested_actions,
            decisions={"artifactAction": decision},
        )

    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision="prepared",
        reason_codes=decision["reason_codes"],
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=artifact["status"],
        payload={
            "policy_rule": "recouvrement.artifact_action_governance",
            "action_name": canonical_action,
            "requires_validation": decision["requires_validation"],
            "no_external_effect": decision["no_external_effect"],
        },
        **_event_common(event_state, node_name="evaluate_artifact_action_policy"),
    )
    updated_artifact = _updated_artifact_for_action(artifact, decision)
    if canonical_action == "submit_for_validation":
        record_business_event(
            event_name=BusinessEventName.VALIDATION_REQUESTED,
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=decision["target_status"],
            decision="pending_validation",
            reason_codes=decision["reason_codes"],
            payload={
                "validation_type": "artifact_validation",
                "validation_reason": "Validation préparée avant toute action client.",
                "action_name": canonical_action,
                "requires_validation": True,
                "no_external_effect": True,
            },
            **_event_common(event_state, node_name="prepare_artifact_action"),
        )
    if decision["target_status"] != decision["current_status"]:
        record_business_event(
            event_name=BusinessEventName.ARTIFACT_STATUS_CHANGED,
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=decision["target_status"],
            decision="prepared",
            reason_codes=decision["reason_codes"],
            payload={
                "previous_status": decision["current_status"],
                "new_status": decision["target_status"],
                "status_reason": canonical_action,
                "action_name": canonical_action,
                "requested_by": requested_by,
                "requires_validation": decision["requires_validation"],
                "no_external_effect": True,
            },
            **_event_common(event_state, node_name="prepare_artifact_action"),
        )
    if canonical_action != "copy_artifact_text":
        record_business_event(
            event_name=BusinessEventName.ACTION_PREPARED,
            decision="prepared",
            reason_codes=decision["reason_codes"],
            artifact_id=artifact["id"],
            artifact_type=artifact["type"],
            artifact_status=decision["target_status"],
            payload=action_payload,
            **_event_common(event_state, node_name="prepare_artifact_action"),
        )
    visible_reply = _artifact_action_visible_reply(decision)
    record_business_event(
        event_name=BusinessEventName.MESSAGE_GENERATED,
        artifact_id=artifact["id"],
        artifact_type=artifact["type"],
        artifact_status=decision["target_status"],
        payload={
            "message_kind": "internal_confirmation",
            "visible_reply": visible_reply,
            "task": "artifact_action",
            "generation_mode": "deterministic_builder",
            "artifact_id": artifact["id"],
            "artifact_type": artifact["type"],
            "policy_review_status": "prepared",
            "action_name": canonical_action,
            "no_external_effect": True,
        },
        **_event_common(event_state, node_name="generate_action_visible_reply"),
    )
    card_updates, suggested_actions = _artifact_action_cards(decision)
    return _finalize_action_output(
        event_state=event_state,
        artifact=updated_artifact,
        visible_reply=visible_reply,
        card_updates=card_updates,
        suggested_actions=suggested_actions,
        decisions={"artifactAction": decision},
    )


def build_recouvrement_graph_v1() -> StateGraph[RecouvrementWorkflowState]:
    """Construct the minimal specialised Recouvrement graph."""
    graph: StateGraph[RecouvrementWorkflowState] = StateGraph(RecouvrementWorkflowState)
    graph.add_node(
        "verify_surface_authorization",
        instrument_node("verify_surface_authorization", verify_surface_authorization),
    )
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
        "evaluate_schedule_policy",
        instrument_node("evaluate_schedule_policy", evaluate_schedule_policy),
    )
    graph.add_node(
        "draft_client_message",
        instrument_node("draft_client_message", draft_client_message),
    )
    graph.add_node(
        "review_client_message_policy",
        instrument_node("review_client_message_policy", review_client_message_policy),
    )
    graph.add_node(
        "review_case_summary_policy",
        instrument_node("review_case_summary_policy", review_case_summary_policy),
    )
    graph.add_node(
        "review_payment_options_policy",
        instrument_node("review_payment_options_policy", review_payment_options_policy),
    )
    graph.add_node(
        "build_case_summary_artifact",
        instrument_node("build_case_summary_artifact", build_case_summary_artifact),
    )
    graph.add_node(
        "build_payment_options_artifact",
        instrument_node("build_payment_options_artifact", build_payment_options_artifact),
    )
    graph.add_node(
        "build_contact_rule_artifact",
        instrument_node("build_contact_rule_artifact", build_contact_rule_artifact),
    )
    graph.add_node(
        "build_schedule_proposal_artifact",
        instrument_node("build_schedule_proposal_artifact", build_schedule_proposal_artifact),
    )
    graph.add_node(
        "build_reminder_draft_artifact",
        instrument_node("build_reminder_draft_artifact", build_reminder_draft_artifact),
    )
    graph.add_node(
        "generate_visible_reply",
        instrument_node("generate_visible_reply", generate_visible_reply),
    )
    graph.add_node(
        "finalize_business_observability",
        instrument_node("finalize_business_observability", finalize_business_observability),
    )
    graph.add_node(
        "finalize_unauthorized_surface",
        instrument_node("finalize_unauthorized_surface", finalize_unauthorized_surface),
    )
    graph.add_edge(START, "verify_surface_authorization")
    graph.add_conditional_edges(
        "verify_surface_authorization",
        _after_surface_authorization,
        {"authorized": "load_case_context", "blocked": "finalize_unauthorized_surface"},
    )
    graph.add_edge("load_case_context", "route_recouvrement_intent")
    graph.add_edge("route_recouvrement_intent", "extract_recouvrement_slots")
    graph.add_conditional_edges(
        "extract_recouvrement_slots",
        _route_after_slot_extraction,
        {
            "contact": "evaluate_contact_policy",
            "schedule": "evaluate_schedule_policy",
            "draft": "draft_client_message",
            "summary": "review_case_summary_policy",
            "payment_options": "review_payment_options_policy",
        },
    )
    graph.add_edge("review_case_summary_policy", "build_case_summary_artifact")
    graph.add_edge("build_case_summary_artifact", "generate_visible_reply")
    graph.add_edge("review_payment_options_policy", "build_payment_options_artifact")
    graph.add_edge("build_payment_options_artifact", "generate_visible_reply")
    graph.add_edge("evaluate_contact_policy", "build_contact_rule_artifact")
    graph.add_edge("build_contact_rule_artifact", "generate_visible_reply")
    graph.add_edge("evaluate_schedule_policy", "build_schedule_proposal_artifact")
    graph.add_edge("build_schedule_proposal_artifact", "generate_visible_reply")
    graph.add_edge("draft_client_message", "review_client_message_policy")
    graph.add_edge("review_client_message_policy", "build_reminder_draft_artifact")
    graph.add_edge("build_reminder_draft_artifact", "generate_visible_reply")
    graph.add_edge("generate_visible_reply", "finalize_business_observability")
    graph.add_edge("finalize_business_observability", END)
    graph.add_edge("finalize_unauthorized_surface", END)
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
