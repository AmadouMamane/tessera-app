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
    tone: str
    mentions_schedule: bool
    validation_required: bool
    client_agreement_required: bool
    schedule_created: bool
    message_sent: bool


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
    authorized: NotRequired[bool]
    authorization_reason: NotRequired[str]
    case: NotRequired[RecouvrementCaseSnapshot]
    intent: NotRequired[str]
    intent_confidence: NotRequired[float]
    slots: NotRequired[dict[str, object]]
    contact_policy: NotRequired[ContactPolicyDecision]
    schedule_policy: NotRequired[SchedulePolicyDecision]
    draft_message: NotRequired[str]
    draft_policy: NotRequired[DraftPolicyDecision]
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
    if _has_draft_intent(normalized) or active_task == "draft_reminder":
        intent = "draft_reminder"
        confidence = 0.93
    elif _has_schedule_intent(normalized):
        intent = "propose_schedule"
        confidence = 0.94
    elif _has_contact_rule_intent(normalized) or active_task in {
        "check_rule",
        "check_contact_rule",
    }:
        intent = "check_contact_rule"
        confidence = 0.96
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


def draft_client_message(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Draft a bounded client message; replaceable by an LLM-only drafting node later."""
    case = state["case"]
    slots = state["slots"]
    current_artifact = _current_artifact(state)
    tone = str(slots.get("tone", "amiable et factuel"))
    mentions_schedule = bool(slots.get("mentions_schedule"))
    requested_months = slots.get("requested_months")
    monthly_amount_label = slots.get("monthly_amount_label")
    is_empathic = "empathique" in tone

    greeting = f"Bonjour {case.client},"
    if is_empathic:
        opening = (
            "Nous comprenons que votre situation puisse nécessiter un échange adapté. "
            f"Nous souhaitons faire le point avec vous concernant le dossier {case.case_id}, "
            f"pour un montant restant dû de {case.amount_due_label}."
        )
    else:
        opening = (
            f"Nous vous contactons au sujet du dossier {case.case_id}. Sauf erreur de notre part, "
            f"le montant restant dû est de {case.amount_due_label}."
        )
    context = (
        "Votre promesse de paiement du 12 juin n'a pas pu être tenue et le dossier présente "
        f"un retard de {case.days_late} jours."
    )
    if mentions_schedule and isinstance(requested_months, int) and isinstance(
        monthly_amount_label, str
    ):
        next_step = (
            "Une solution d'échelonnement peut être étudiée avec vous, par exemple sur "
            f"{requested_months} mois avec une mensualité indicative de {monthly_amount_label}, "
            "sous réserve de validation interne et d'accord sur les modalités."
        )
    elif mentions_schedule:
        next_step = (
            "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
            "validation interne et d'accord sur les modalités."
        )
    else:
        next_step = (
            "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée "
            "à votre situation."
        )
    closing = "Cordialement,\nCrédit Aurore"
    draft = "\n\n".join([greeting, opening, context, next_step, closing])
    if current_artifact is not None and is_empathic:
        draft = draft.replace("Nous vous contactons", "Nous revenons vers vous avec attention")
    return {"draft_message": draft}


def review_client_message_policy(state: RecouvrementWorkflowState) -> dict[str, object]:
    """Review a drafted client message with deterministic Recouvrement safety checks."""
    draft = state["draft_message"]
    slots = state["slots"]
    normalized_draft = _normalize_message(draft)
    forbidden_terms = {
        "mise en demeure",
        "sanction",
        "resiliation",
        "frais d'incident",
        "pression",
        "immediatement obligatoire",
    }
    unsafe = any(term in normalized_draft for term in forbidden_terms)
    mentions_schedule = bool(slots.get("mentions_schedule"))
    validation_required = mentions_schedule
    reason_codes = ["MESSAGE_SAFE", "MESSAGE_NOT_SENT"]
    if validation_required:
        reason_codes = [
            "VALIDATION_REQUIRED",
            "CLIENT_AGREEMENT_REQUIRED",
            "SCHEDULE_NOT_CREATED",
            "MESSAGE_NOT_SENT",
        ]
    if unsafe:
        reason_codes = ["UNSAFE_CLIENT_MESSAGE"]
    policy_decision = (
        "blocked" if unsafe else ("validation_required" if validation_required else "approved")
    )
    decision: DraftPolicyDecision = {
        "decision": policy_decision,
        "reason_codes": reason_codes,
        "tone": str(slots.get("tone", "amiable et factuel")),
        "mentions_schedule": mentions_schedule,
        "validation_required": validation_required,
        "client_agreement_required": validation_required,
        "schedule_created": False,
        "message_sent": False,
    }
    record_business_event(
        event_name=BusinessEventName.POLICY_DECISION_MADE,
        decision=decision["decision"],
        reason_codes=decision["reason_codes"],
        payload={
            "policy_rule": "recouvrement.client_message_safety",
            "rule_id": "CLIENT_MESSAGE_SAFETY",
        },
        **_event_common(state, node_name="review_client_message_policy"),
    )
    return {"draft_policy": decision}


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
        },
    }
    client_message = (
        "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
        "validation et d'accord sur les modalités."
    )
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
    current_artifact = _current_artifact(state)
    current_artifact_type = current_artifact["type"] if current_artifact is not None else None
    from_schedule = current_artifact_type == "schedule_proposal_v2"
    artifact_type = "client_message_artifact" if from_schedule else "reminder_draft_v1"
    version_label = (
        "Version 2 — ton plus empathique"
        if policy["tone"] == "empathique"
        else "Version 1 — relance amiable"
    )
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
            "validation_required": policy["validation_required"],
            "client_agreement_required": policy["client_agreement_required"],
            "schedule_created": policy["schedule_created"],
            "message_sent": policy["message_sent"],
            "no_email_sent": True,
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
    if state.get("intent") == "propose_schedule":
        schedule_policy = state["schedule_policy"]
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
        }
    elif state.get("intent") == "draft_reminder":
        draft_policy = state["draft_policy"]
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
        }
    else:
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
        task = "check_rule"
        message_payload = {
            "message_kind": "assistant_reply",
            "visible_reply": reply,
            "task": task,
        }
    record_business_event(
        event_name=BusinessEventName.MESSAGE_GENERATED,
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
        },
    )
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
