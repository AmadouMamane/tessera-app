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
from typing import TYPE_CHECKING, Literal

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
    from collections.abc import Iterable, Mapping
    from pathlib import Path

__all__ = [
    "AgentBusinessEvent",
    "BusinessEvent",
    "BusinessEventClassification",
    "BusinessEventName",
    "business_event_rows",
    "classify_event",
    "emit_business_event",
    "persisted_business_events",
    "record_business_event",
    "recent_business_events",
    "reset_business_event_store",
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
    ACTION_PREPARED = "action.prepared"
    ACTION_BLOCKED = "action.blocked"
    MESSAGE_GENERATED = "message.generated"


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
        row["version"] = 1
        row["reason_codes"] = list(self.reason_codes)
        row["classification"] = asdict(self.classification)
        return row


AgentBusinessEvent = BusinessEvent

_BUSINESS_EVENTS: deque[BusinessEvent] = deque(maxlen=500)
_WARMED = False


def _business_events_path() -> Path:
    """Durable business-event projection store next to the audit log."""
    from tessera.settings import get_settings

    return get_settings().guard.audit_file.parent / "business_events.jsonl"


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
        )
    except (KeyError, TypeError, ValueError):
        return None


def _persist(event: BusinessEvent) -> None:
    """Append one event to the projection store; best effort."""
    try:
        path = _business_events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(event.to_row(), ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_persisted() -> list[BusinessEvent]:
    events: list[BusinessEvent] = []
    try:
        path = _business_events_path()
        if not path.exists():
            return events
        with path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    event = _row_to_event(obj)
                    if event is not None:
                        events.append(event)
    except OSError:
        return events
    return events


def _warm_live_buffer() -> None:
    global _WARMED
    if _WARMED or _BUSINESS_EVENTS:
        _WARMED = True
        return
    _WARMED = True
    for event in _read_persisted()[-(_BUSINESS_EVENTS.maxlen or 500) :]:
        _BUSINESS_EVENTS.append(event)


def _matches_scope(
    event: BusinessEvent,
    *,
    at: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> bool:
    if not occurred_before(event.timestamp, at):
        return False
    if agent_id is not None and event.agent_id != agent_id:
        return False
    if conversation_id is not None and event.conversation_id != conversation_id:
        return False
    return not (turn_id is not None and event.turn_id != turn_id)


def _filter_events(
    events: Iterable[BusinessEvent],
    *,
    at: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> list[BusinessEvent]:
    return [
        event
        for event in events
        if _matches_scope(
            event,
            at=at,
            agent_id=agent_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
    ]


def persisted_business_events(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> list[BusinessEvent]:
    """Return persisted business events filtered by common dimensions."""
    return _filter_events(
        _read_persisted(),
        at=at,
        agent_id=agent_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )


def recent_business_events(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> list[BusinessEvent]:
    """Return live or as-of-T business events filtered by common dimensions."""
    if at is not None:
        return persisted_business_events(
            at=at,
            agent_id=agent_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
    _warm_live_buffer()
    return _filter_events(
        list(_BUSINESS_EVENTS),
        agent_id=agent_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )


def business_event_rows(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> list[dict[str, object]]:
    """Return serialised business-event rows for replay / Cockpit projection."""
    return [
        event.to_row()
        for event in recent_business_events(
            at=at,
            agent_id=agent_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
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
    safe_payload = _json_safe_payload(payload)
    name = _event_name_value(event_name)
    resolved_classification = classification or classify_event(
        name, decision=decision, payload=safe_payload
    )
    event = BusinessEvent(
        event_name=name,
        timestamp=_now_iso(),
        agent_id=agent_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
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
        reason_codes=tuple(str(code) for code in reason_codes),
        payload=safe_payload,
        actor=actor,
        classification=resolved_classification,
    )
    if event.classification.observable:
        _emit_otel(event)
    _emit_metrics(event)
    _warm_live_buffer()
    _BUSINESS_EVENTS.append(event)
    _persist(event)
    if event.classification.auditable:
        from tessera.guard.audit import emit_business_event_audit

        emit_business_event_audit(event=event.to_row(), sink=audit_sink)
    return event


def emit_business_event(**kwargs: object) -> BusinessEvent:
    """Backward-friendly alias for :func:`record_business_event`."""
    return record_business_event(**kwargs)  # type: ignore[arg-type]


def reset_business_event_store() -> None:
    """Clear the in-process projection buffer; tests use a temp durable path."""
    global _WARMED
    _BUSINESS_EVENTS.clear()
    _WARMED = False
