"""Business workflow events for specialised agents.

This is the business observability layer, not an audit module. It normalises
workflow events once, then fans them out to OTel span events, the hash-chain
audit sink when opposable, Prometheus counters, and a lightweight projection
store used by replay / Cockpit reads.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from tessera.observability import semconv
from tessera.observability._asof import occurred_before
from tessera.observability.metrics import (
    ACTION_BLOCKED_TOTAL,
    ACTION_PREPARED_TOTAL,
    ARTIFACT_CREATED_TOTAL,
    ARTIFACT_STATUS_CHANGED_TOTAL,
    BUSINESS_EVENTS_TOTAL,
    BUSINESS_RULE_CHECKED_TOTAL,
    POLICY_DECISION_TOTAL,
    VALIDATION_REQUESTED_TOTAL,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

__all__ = [
    "AgentBusinessEvent",
    "ArtifactSink",
    "AuditSink",
    "BusinessEvent",
    "BusinessEventClassification",
    "BusinessEventName",
    "BusinessEventSink",
    "BusinessEventStore",
    "BusinessPayloadValidationError",
    "CockpitSignalSink",
    "InMemoryBusinessEventStore",
    "MetricsSink",
    "ReplaySink",
    "business_event_rows",
    "classify_event",
    "emit_business_event",
    "get_business_event_store",
    "persisted_business_events",
    "record_business_event",
    "recent_business_events",
    "reset_business_event_store",
    "set_business_event_store",
]

_AuditSink = Literal["stdout", "file", "cloud_logging", "postgres"]


class BusinessEventName(StrEnum):
    """Known workflow event names for specialised agents."""

    CASE_CONTEXT_LOADED = "case.context_loaded"
    INTENT_ROUTED = "intent.routed"
    SLOTS_EXTRACTED = "slots.extracted"
    BUSINESS_RULE_CHECKED = "business_rule.checked"
    POLICY_DECISION_MADE = "policy.decision_made"
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_UPDATED = "artifact.updated"
    ARTIFACT_STATUS_CHANGED = "artifact.status_changed"
    VALIDATION_REQUESTED = "validation.requested"
    ACTION_REQUESTED = "action.requested"
    ACTION_PREPARED = "action.prepared"
    ACTION_BLOCKED = "action.blocked"
    MESSAGE_GENERATED = "message.generated"


EVENT_SCHEMA_VERSION = "business_event.v1"
EVENT_VERSION = 1


class BusinessPayloadValidationError(ValueError):
    """A critical business event did not satisfy its strict payload contract."""


class BusinessEventSink(Protocol):
    """A sink that receives the normalised business-event envelope."""

    def emit(self, event: BusinessEvent) -> None:
        """Emit one event to the sink."""
        ...


class BusinessEventStore(Protocol):
    """Read-model projection for business events, never the audit proof store."""

    def append(self, event: BusinessEvent) -> None:
        """Append one event to the projection."""
        ...

    def list(
        self,
        *,
        at: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
        case_id: str | None = None,
        event_name: str | None = None,
        artifact_type: str | None = None,
        decision: str | None = None,
    ) -> list[BusinessEvent]:
        """Return events filtered by common cockpit/spine dimensions."""
        ...

    def clear(self) -> None:
        """Clear the projection, for tests and local reset only."""
        ...


class AuditSink(Protocol):
    """Opposable-event sink, backed by the hash-chained audit ledger."""

    def emit_audit_event(self, event: BusinessEvent) -> None:
        """Append one auditable business event."""
        ...


class ReplaySink(Protocol):
    """Replay sink that can embed business events in captured turn bundles."""

    def attach_events(self, events: Sequence[dict[str, object]]) -> None:
        """Attach serialised events to a replayable turn."""
        ...


class CockpitSignalSink(Protocol):
    """Cockpit read-model sink used behind spine signals."""

    def project(self, event: BusinessEvent) -> None:
        """Project one event for cockpit reads."""
        ...


class MetricsSink(Protocol):
    """Metrics sink for low-cardinality Prometheus aggregates."""

    def increment(self, event: BusinessEvent) -> None:
        """Increment counters derived from an event."""
        ...


class ArtifactSink(Protocol):
    """Sink for typed business artifacts produced by specialised workflows."""

    def publish_artifact_event(self, event: BusinessEvent) -> None:
        """Publish an artifact-related business event."""
        ...


@dataclass(frozen=True, slots=True)
class BusinessEventClassification:
    """Routing flags for a business event's observability fan-out."""

    observable: bool = True
    auditable: bool = False
    scoring_input: bool = False
    metric_input: bool = False
    cockpit_signal: bool = False


@dataclass(frozen=True, slots=True)
class BusinessEvent:
    """A normalised business event emitted by a specialised workflow."""

    event_name: str
    timestamp: str
    agent_id: str
    conversation_id: str
    turn_id: str
    schema_version: str = EVENT_SCHEMA_VERSION
    event_version: int = EVENT_VERSION
    workflow_id: str | None = None
    surface: str | None = None
    language: str | None = None
    model: str | None = None
    environment: str | None = None
    case_id: str | None = None
    node_name: str | None = None
    artifact_id: str | None = None
    artifact_type: str | None = None
    artifact_status: str | None = None
    decision: str | None = None
    reason_codes: tuple[str, ...] = ()
    payload: dict[str, object] = field(default_factory=dict)
    actor: str = "system"
    classification: BusinessEventClassification = field(default_factory=BusinessEventClassification)

    def to_row(self) -> dict[str, object]:
        """Serialise the event for projection, replay, and audit sinks."""
        row = asdict(self)
        row["version"] = self.event_version
        row["reason_codes"] = list(self.reason_codes)
        row["classification"] = asdict(self.classification)
        return row


AgentBusinessEvent = BusinessEvent


class _StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BusinessRuleCheckedPayload(_StrictPayload):
    """Payload contract for ``business_rule.checked``."""

    rule_id: str = Field(min_length=1)
    result: str | None = None
    decision: str | None = None
    requested_time: str | None = None
    allowed_window: str | None = None
    recommended_channel: str | None = None


class PolicyDecisionMadePayload(_StrictPayload):
    """Payload contract for ``policy.decision_made``."""

    policy_rule: str = Field(min_length=1)
    rule_id: str | None = None
    action_name: str | None = None
    generation_mode: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    template_label: str | None = None
    policy_review_status: str | None = None
    amount_consistent: bool | None = None
    requires_validation: bool | None = None
    no_payment_initiated: bool | None = None
    no_payment_link_created: bool | None = None
    no_payment_link_sent: bool | None = None
    no_schedule_created: bool | None = None
    no_external_effect: bool | None = None


class ArtifactCreatedPayload(_StrictPayload):
    """Payload contract for ``artifact.created``."""

    task: str | None = None
    title: str | None = None
    decision: str | None = None
    generation_mode: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    template_label: str | None = None
    policy_review_status: str | None = None
    client_message_generation: dict[str, object] | None = None
    no_message_sent: bool | None = None
    no_payment_initiated: bool | None = None
    no_payment_link_created: bool | None = None
    no_payment_link_sent: bool | None = None
    no_schedule_created: bool | None = None
    no_external_effect: bool | None = None


class ArtifactStatusChangedPayload(_StrictPayload):
    """Payload contract for ``artifact.status_changed``."""

    previous_status: str | None = None
    new_status: str | None = None
    status_reason: str | None = None
    action_name: str | None = None
    requested_by: str | None = None
    requires_validation: bool | None = None
    no_external_effect: bool | None = None


class ValidationRequestedPayload(_StrictPayload):
    """Payload contract for ``validation.requested``."""

    validation_type: str = Field(min_length=1)
    validation_reason: str | None = None
    action_name: str | None = None
    requires_validation: bool | None = None
    no_external_effect: bool | None = None


class ActionPayload(_StrictPayload):
    """Payload contract for action lifecycle events."""

    action_name: str = Field(min_length=1)
    action_label: str | None = None
    artifact_id: str | None = None
    artifact_type: str | None = None
    case_id: str | None = None
    current_status: str | None = None
    target_status: str | None = None
    requested_by: str | None = None
    requires_validation: bool | None = None
    no_external_effect: bool | None = None
    requested_time: str | None = None
    requested_surface: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_action_name(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "action_name" in data:
            return data
        action = data.get("action") or data.get("action_id")
        if action is None:
            return data
        normalised = dict(data)
        normalised["action_name"] = action
        normalised.pop("action", None)
        normalised.pop("action_id", None)
        return normalised


class MessageGeneratedPayload(_StrictPayload):
    """Payload contract for sensitive generated messages."""

    message_kind: str = Field(min_length=1)
    visible_reply: str | None = None
    message_text: str | None = None
    task: str | None = None
    generation_mode: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    template_label: str | None = None
    template_tone: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    artifact_id: str | None = None
    artifact_type: str | None = None
    policy_review_status: str | None = None
    client_message_generation: dict[str, object] | None = None
    action_name: str | None = None
    no_message_sent: bool | None = None
    no_payment_initiated: bool | None = None
    no_payment_link_created: bool | None = None
    no_payment_link_sent: bool | None = None
    no_schedule_created: bool | None = None
    no_external_effect: bool | None = None

    @field_validator("message_kind")
    @classmethod
    def _known_message_kind(cls, value: str) -> str:
        allowed = {"assistant_reply", "client_message", "internal_confirmation"}
        if value not in allowed:
            msg = f"unknown message_kind {value!r}"
            raise ValueError(msg)
        return value


_CRITICAL_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    BusinessEventName.BUSINESS_RULE_CHECKED.value: BusinessRuleCheckedPayload,
    BusinessEventName.POLICY_DECISION_MADE.value: PolicyDecisionMadePayload,
    BusinessEventName.ARTIFACT_CREATED.value: ArtifactCreatedPayload,
    BusinessEventName.ARTIFACT_STATUS_CHANGED.value: ArtifactStatusChangedPayload,
    BusinessEventName.VALIDATION_REQUESTED.value: ValidationRequestedPayload,
    BusinessEventName.ACTION_REQUESTED.value: ActionPayload,
    BusinessEventName.ACTION_PREPARED.value: ActionPayload,
    BusinessEventName.ACTION_BLOCKED.value: ActionPayload,
    BusinessEventName.MESSAGE_GENERATED.value: MessageGeneratedPayload,
}


class InMemoryBusinessEventStore:
    """Bounded in-process business-event read model for local/test cockpit reads.

    The durable sinks remain the ADR 15 homes: OTel for traces, Prometheus for aggregates,
    the hash-chained ledger for opposable events, and replay bundles for replay payloads.
    This store is deliberately not a JSONL substitute or a proof store.
    """

    def __init__(self, *, maxlen: int = 500) -> None:
        self._events: deque[BusinessEvent] = deque(maxlen=maxlen)

    def append(self, event: BusinessEvent) -> None:
        """Append one event to the bounded projection."""
        self._events.append(event)

    def list(
        self,
        *,
        at: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
        case_id: str | None = None,
        event_name: str | None = None,
        artifact_type: str | None = None,
        decision: str | None = None,
    ) -> list[BusinessEvent]:
        """Return filtered events, oldest to newest."""
        return _filter_events(
            list(self._events),
            at=at,
            agent_id=agent_id,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            case_id=case_id,
            event_name=event_name,
            artifact_type=artifact_type,
            decision=decision,
        )

    def clear(self) -> None:
        """Remove every event from the projection."""
        self._events.clear()


_BUSINESS_EVENT_STORE: BusinessEventStore = InMemoryBusinessEventStore()


def get_business_event_store() -> BusinessEventStore:
    """Return the active business-event read-model store."""
    return _BUSINESS_EVENT_STORE


def set_business_event_store(store: BusinessEventStore) -> None:
    """Replace the active business-event store, used by tests and future adapters."""
    global _BUSINESS_EVENT_STORE
    _BUSINESS_EVENT_STORE = store


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _event_name_value(event_name: BusinessEventName | str) -> str:
    return event_name.value if isinstance(event_name, BusinessEventName) else str(event_name)


def _json_safe_payload(payload: Mapping[str, object] | None) -> dict[str, object]:
    """Return a JSON-safe payload with defensive coercion."""
    if payload is None:
        return {}
    try:
        loaded: object = json.loads(json.dumps(dict(payload), ensure_ascii=False, default=repr))
        if isinstance(loaded, dict):
            return {str(key): value for key, value in loaded.items()}
        return {}
    except (TypeError, ValueError):
        return {key: repr(value) for key, value in payload.items()}


def _validate_event_payload(
    *,
    event_name: str,
    payload: Mapping[str, object],
    decision: str | None,
    reason_codes: tuple[str, ...],
    case_id: str | None,
    node_name: str | None,
    artifact_id: str | None,
    artifact_type: str | None,
    artifact_status: str | None,
) -> dict[str, object]:
    """Validate critical event payloads and required envelope fields."""
    model = _CRITICAL_PAYLOAD_MODELS.get(event_name)
    if model is not None:
        try:
            validated = model.model_validate(dict(payload))
        except ValidationError as exc:
            msg = f"invalid payload for {event_name}: {exc}"
            raise BusinessPayloadValidationError(msg) from exc
        payload = validated.model_dump(exclude_none=True)
    missing: list[str] = []
    if event_name in {
        BusinessEventName.BUSINESS_RULE_CHECKED.value,
        BusinessEventName.POLICY_DECISION_MADE.value,
        BusinessEventName.ACTION_BLOCKED.value,
    }:
        if not decision:
            missing.append("decision")
        if decision in {"blocked", "denied", "failed"} and not reason_codes:
            missing.append("reason_codes")
    if event_name in {
        BusinessEventName.ARTIFACT_CREATED.value,
        BusinessEventName.ARTIFACT_STATUS_CHANGED.value,
    }:
        for field_name, value in (
            ("artifact_id", artifact_id),
            ("artifact_type", artifact_type),
            ("artifact_status", artifact_status),
            ("case_id", case_id),
            ("node_name", node_name),
        ):
            if not value:
                missing.append(field_name)
    if event_name == BusinessEventName.VALIDATION_REQUESTED.value:
        if not artifact_id:
            missing.append("artifact_id")
        if not case_id:
            missing.append("case_id")
    if missing:
        msg = f"invalid envelope for {event_name}: missing {', '.join(sorted(set(missing)))}"
        raise BusinessPayloadValidationError(msg)
    return dict(payload)


def classify_event(
    event_name: BusinessEventName | str,
    *,
    decision: str | None = None,
    payload: Mapping[str, object] | None = None,
) -> BusinessEventClassification:
    """Classify one event for fan-out severity."""
    name = _event_name_value(event_name)
    safe_payload = payload or {}
    if name == BusinessEventName.BUSINESS_RULE_CHECKED.value:
        return BusinessEventClassification(
            observable=True,
            auditable=decision is not None,
            scoring_input=True,
            metric_input=True,
            cockpit_signal=True,
        )
    if name in {
        BusinessEventName.ARTIFACT_CREATED.value,
        BusinessEventName.ARTIFACT_UPDATED.value,
        BusinessEventName.ARTIFACT_STATUS_CHANGED.value,
        BusinessEventName.VALIDATION_REQUESTED.value,
        BusinessEventName.ACTION_BLOCKED.value,
        BusinessEventName.ACTION_PREPARED.value,
        BusinessEventName.POLICY_DECISION_MADE.value,
    }:
        return BusinessEventClassification(
            observable=True,
            auditable=True,
            scoring_input=True,
            metric_input=True,
            cockpit_signal=True,
        )
    if name == BusinessEventName.ACTION_REQUESTED.value:
        return BusinessEventClassification(
            observable=True,
            auditable=False,
            scoring_input=True,
            metric_input=True,
            cockpit_signal=True,
        )
    if name == BusinessEventName.MESSAGE_GENERATED.value:
        is_client_message = safe_payload.get("message_kind") == "client_message"
        return BusinessEventClassification(
            observable=True,
            auditable=is_client_message,
            scoring_input=True,
            metric_input=True,
            cockpit_signal=is_client_message,
        )
    if name == BusinessEventName.SLOTS_EXTRACTED.value:
        return BusinessEventClassification(
            observable=True,
            auditable=False,
            scoring_input=bool(safe_payload.get("rule_impacting")),
            metric_input=True,
            cockpit_signal=True,
        )
    return BusinessEventClassification(
        observable=True,
        auditable=False,
        scoring_input=True,
        metric_input=True,
        cockpit_signal=True,
    )


def _row_to_event(row: dict[str, object]) -> BusinessEvent | None:
    """Rebuild a stored row into a :class:`BusinessEvent`."""
    try:
        classification_raw = row.get("classification")
        payload_raw = row.get("payload")
        payload_mapping: Mapping[str, object] | None = (
            payload_raw if isinstance(payload_raw, dict) else None
        )
        classification = (
            BusinessEventClassification(**classification_raw)
            if isinstance(classification_raw, dict)
            else classify_event(
                str(row["event_name"]),
                decision=str(row["decision"]) if row.get("decision") is not None else None,
                payload=payload_mapping,
            )
        )
        reason_codes = row.get("reason_codes")
        raw_event_version = row.get("event_version", row.get("version", EVENT_VERSION))
        event_version = (
            int(raw_event_version) if isinstance(raw_event_version, str | int) else EVENT_VERSION
        )
        return BusinessEvent(
            event_name=str(row["event_name"]),
            timestamp=str(row.get("timestamp") or row.get("occurred_at") or ""),
            agent_id=str(row["agent_id"]),
            conversation_id=str(row["conversation_id"]),
            turn_id=str(row["turn_id"]),
            workflow_id=str(row["workflow_id"]) if row.get("workflow_id") is not None else None,
            surface=str(row["surface"]) if row.get("surface") is not None else None,
            language=str(row["language"]) if row.get("language") is not None else None,
            model=str(row["model"]) if row.get("model") is not None else None,
            environment=(str(row["environment"]) if row.get("environment") is not None else None),
            case_id=str(row["case_id"]) if row.get("case_id") is not None else None,
            node_name=str(row["node_name"]) if row.get("node_name") is not None else None,
            artifact_id=(str(row["artifact_id"]) if row.get("artifact_id") is not None else None),
            artifact_type=(
                str(row["artifact_type"]) if row.get("artifact_type") is not None else None
            ),
            artifact_status=(
                str(row["artifact_status"]) if row.get("artifact_status") is not None else None
            ),
            decision=str(row["decision"]) if row.get("decision") is not None else None,
            reason_codes=(
                tuple(str(code) for code in reason_codes) if isinstance(reason_codes, list) else ()
            ),
            payload=dict(payload_mapping) if payload_mapping is not None else {},
            actor=str(row.get("actor", "system")),
            classification=classification,
            schema_version=str(row.get("schema_version", EVENT_SCHEMA_VERSION)),
            event_version=event_version,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _matches_scope(
    event: BusinessEvent,
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> bool:
    return (
        occurred_before(event.timestamp, at)
        and (agent_id is None or event.agent_id == agent_id)
        and (workflow_id is None or event.workflow_id == workflow_id)
        and (conversation_id is None or event.conversation_id == conversation_id)
        and (turn_id is None or event.turn_id == turn_id)
        and (case_id is None or event.case_id == case_id)
        and (event_name is None or event.event_name == event_name)
        and (artifact_type is None or event.artifact_type == artifact_type)
        and (decision is None or event.decision == decision)
    )


def _filter_events(
    events: Iterable[BusinessEvent],
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> list[BusinessEvent]:
    return [
        event
        for event in events
        if _matches_scope(
            event,
            at=at,
            agent_id=agent_id,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            case_id=case_id,
            event_name=event_name,
            artifact_type=artifact_type,
            decision=decision,
        )
    ]


def persisted_business_events(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> list[BusinessEvent]:
    """Return projected business events filtered by common dimensions."""
    return get_business_event_store().list(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        event_name=event_name,
        artifact_type=artifact_type,
        decision=decision,
    )


def recent_business_events(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> list[BusinessEvent]:
    """Return live or as-of-T business events filtered by common dimensions."""
    return persisted_business_events(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        event_name=event_name,
        artifact_type=artifact_type,
        decision=decision,
    )


def business_event_rows(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
) -> list[dict[str, object]]:
    """Return serialised business-event rows for replay / Cockpit projection."""
    return [
        event.to_row()
        for event in recent_business_events(
            at=at,
            agent_id=agent_id,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            case_id=case_id,
            event_name=event_name,
            artifact_type=artifact_type,
            decision=decision,
        )
    ]


def _label(value: str | None) -> str:
    return value if value else "none"


def _reason_labels(reason_codes: tuple[str, ...]) -> tuple[str, ...]:
    return reason_codes or ("none",)


def _emit_otel(event: BusinessEvent) -> None:
    """Attach the event to the current OTel span when tracing is active."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        attrs: dict[str, str] = {
            semconv.TESSERA_AGENT_ID: event.agent_id,
            semconv.TESSERA_TURN_ID: event.turn_id,
        }
        optional_attrs = {
            semconv.TESSERA_WORKFLOW_ID: event.workflow_id,
            "tessera.surface": event.surface,
            semconv.TESSERA_CASE_ID: event.case_id,
            "tessera.node_name": event.node_name,
            semconv.TESSERA_ARTIFACT_ID: event.artifact_id,
            semconv.TESSERA_ARTIFACT_TYPE: event.artifact_type,
            semconv.TESSERA_ARTIFACT_STATUS: event.artifact_status,
            "tessera.business.decision": event.decision,
        }
        attrs.update({key: value for key, value in optional_attrs.items() if value})
        if event.reason_codes:
            attrs["tessera.business.reason_codes"] = ",".join(event.reason_codes)
        span.add_event(f"tessera.business.{event.event_name}", attributes=attrs)
    except Exception:
        return


def _emit_metrics(event: BusinessEvent) -> None:
    """Increment low-cardinality business counters."""
    if not event.classification.metric_input:
        return
    agent = _label(event.agent_id)
    workflow = _label(event.workflow_id)
    surface = _label(event.surface)
    decision = _label(event.decision)
    artifact_type = _label(event.artifact_type)
    artifact_status = _label(event.artifact_status)
    BUSINESS_EVENTS_TOTAL.labels(
        agent_id=agent,
        workflow_id=workflow,
        surface=surface,
        event_name=event.event_name,
        decision=decision,
    ).inc()
    for reason_code in _reason_labels(event.reason_codes):
        if event.event_name == BusinessEventName.BUSINESS_RULE_CHECKED.value:
            BUSINESS_RULE_CHECKED_TOTAL.labels(
                agent_id=agent,
                workflow_id=workflow,
                surface=surface,
                decision=decision,
                reason_code=reason_code,
            ).inc()
        elif event.event_name == BusinessEventName.POLICY_DECISION_MADE.value:
            POLICY_DECISION_TOTAL.labels(
                agent_id=agent,
                workflow_id=workflow,
                surface=surface,
                decision=decision,
                reason_code=reason_code,
            ).inc()
        elif event.event_name == BusinessEventName.ACTION_PREPARED.value:
            ACTION_PREPARED_TOTAL.labels(
                agent_id=agent,
                workflow_id=workflow,
                surface=surface,
                decision=decision,
                reason_code=reason_code,
            ).inc()
        elif event.event_name == BusinessEventName.ACTION_BLOCKED.value:
            ACTION_BLOCKED_TOTAL.labels(
                agent_id=agent,
                workflow_id=workflow,
                surface=surface,
                decision=decision,
                reason_code=reason_code,
            ).inc()
    if event.event_name == BusinessEventName.ARTIFACT_CREATED.value:
        ARTIFACT_CREATED_TOTAL.labels(
            agent_id=agent,
            workflow_id=workflow,
            surface=surface,
            artifact_type=artifact_type,
            artifact_status=artifact_status,
        ).inc()
    elif event.event_name == BusinessEventName.ARTIFACT_STATUS_CHANGED.value:
        ARTIFACT_STATUS_CHANGED_TOTAL.labels(
            agent_id=agent,
            workflow_id=workflow,
            surface=surface,
            artifact_type=artifact_type,
            artifact_status=artifact_status,
        ).inc()
    elif event.event_name == BusinessEventName.VALIDATION_REQUESTED.value:
        VALIDATION_REQUESTED_TOTAL.labels(
            agent_id=agent,
            workflow_id=workflow,
            surface=surface,
            artifact_type=artifact_type,
            artifact_status=artifact_status,
        ).inc()


def record_business_event(
    *,
    event_name: BusinessEventName | str,
    agent_id: str,
    conversation_id: str,
    turn_id: str,
    workflow_id: str | None = None,
    surface: str | None = None,
    language: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    case_id: str | None = None,
    node_name: str | None = None,
    artifact_id: str | None = None,
    artifact_type: str | None = None,
    artifact_status: str | None = None,
    decision: str | None = None,
    reason_codes: Iterable[str] = (),
    payload: Mapping[str, object] | None = None,
    actor: str = "system",
    classification: BusinessEventClassification | None = None,
    audit_sink: _AuditSink | None = None,
) -> BusinessEvent:
    """Normalise and fan out one business event to the existing sinks."""
    raw_payload = _json_safe_payload(payload)
    name = _event_name_value(event_name)
    reasons = tuple(str(code) for code in reason_codes)
    safe_payload = _validate_event_payload(
        event_name=name,
        payload=raw_payload,
        decision=decision,
        reason_codes=reasons,
        case_id=case_id,
        node_name=node_name,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_status=artifact_status,
    )
    resolved_classification = classification or classify_event(
        name, decision=decision, payload=safe_payload
    )
    event = BusinessEvent(
        event_name=name,
        timestamp=_now_iso(),
        agent_id=agent_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        schema_version=EVENT_SCHEMA_VERSION,
        event_version=EVENT_VERSION,
        workflow_id=workflow_id,
        surface=surface,
        language=language,
        model=model,
        environment=environment,
        case_id=case_id,
        node_name=node_name,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_status=artifact_status,
        decision=decision,
        reason_codes=reasons,
        payload=safe_payload,
        actor=actor,
        classification=resolved_classification,
    )
    if event.classification.observable:
        _emit_otel(event)
    _emit_metrics(event)
    get_business_event_store().append(event)
    if event.classification.auditable:
        from tessera.guard.audit import emit_business_event_audit

        emit_business_event_audit(event=event.to_row(), sink=audit_sink)
    return event


def emit_business_event(**kwargs: object) -> BusinessEvent:
    """Backward-friendly alias for :func:`record_business_event`."""
    return record_business_event(**kwargs)  # type: ignore[arg-type]


def reset_business_event_store() -> None:
    """Clear the in-process projection buffer."""
    get_business_event_store().clear()
