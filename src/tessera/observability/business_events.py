"""Business workflow events for specialised agents.

This is the business observability layer, not an audit module. It normalises
workflow events once, then fans them out to OTel span events, the hash-chain
audit sink when opposable, Prometheus counters, and a lightweight projection
store used by replay / Cockpit reads.
"""

from __future__ import annotations

import json
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from tessera.observability import semconv
from tessera.observability._asof import occurred_before
from tessera.observability.logging import get_logger
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
    from collections.abc import Iterable, Iterator, Mapping, Sequence

__all__ = [
    "ACTORS",
    "HUMAN_ACTORS",
    "Actor",
    "AgentBusinessEvent",
    "ArtifactSink",
    "AuditSink",
    "BusinessEvent",
    "BusinessEventClassification",
    "BusinessEventName",
    "BusinessEventSink",
    "BusinessEventStore",
    "BusinessPayloadValidationError",
    "ClickHouseBusinessEventStore",
    "CockpitSignalSink",
    "GRAMMAR_EVENT_NAMES",
    "GRAMMAR_VERSION",
    "InMemoryBusinessEventStore",
    "MetricsSink",
    "ReplaySink",
    "business_event_rows",
    "classify_event",
    "emit_business_event",
    "get_business_event_store",
    "is_synthetic_turn",
    "mark_synthetic_turn",
    "persisted_business_events",
    "record_business_event",
    "recent_business_events",
    "reset_business_event_store",
    "set_business_event_store",
    "synthetic_turn",
    "validate_business_event",
]

_AuditSink = Literal["stdout", "file", "cloud_logging", "postgres"]

# ADR 0019 §4 — the synthetic dimension. A canary/test turn is stamped synthetic so its events
# can NEVER pollute business metrics: the exclusion is by *declaration* (this flag), read once at
# emit and at the read seam, not by every caller remembering to filter. Scope is the current turn
# (the canary invoker enters :func:`synthetic_turn` around one ``graph.ainvoke``), so any business
# event emitted deep inside that turn inherits the mark without threading a parameter through.
_synthetic_turn: ContextVar[bool] = ContextVar("tessera_synthetic_turn", default=False)


@contextmanager
def synthetic_turn() -> Iterator[None]:
    """Mark every business event emitted in this scope synthetic (ADR 0019 §4 · I4 canary).

    The scheduled-canary invoker wraps one turn in this context so the turn's events are excluded
    from business metrics by declaration. Restores the prior value on exit (reentrant-safe).
    """
    token = _synthetic_turn.set(True)
    try:
        yield
    finally:
        _synthetic_turn.reset(token)


def mark_synthetic_turn() -> None:
    """Mark the *current context* synthetic, with no scope to exit (ADR 0019 §4).

    The request-scoped twin of :func:`synthetic_turn`. The SSE turn handler is an async generator
    with no single ``await`` to wrap — its per-turn ContextVars (agent, model, guard overrides) are
    all set this way, and each ASGI request runs in its own copied context, so a mark set here
    reaches the graph beneath it and dies with the request.

    The scope IS the context. Call this only where a request (or a ``copy_context().run(...)``)
    owns the context; called in a *shared* one it never comes back off, and every business event
    emitted afterwards — anywhere — is silently stamped synthetic and excluded from every business
    surface. Prefer :func:`synthetic_turn` wherever a scope exists; it restores the prior value.
    """
    _synthetic_turn.set(True)


def is_synthetic_turn() -> bool:
    """Whether the current turn is a synthetic (canary/test) turn (ADR 0019 §4)."""
    return _synthetic_turn.get()


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
#: ADR 0017 §2 — the workflow grammar is a versioned spec, stamped on every event.
#: It versions independently from the envelope ``schema_version``.
GRAMMAR_VERSION = "workflow_grammar.v1"
#: ADR 0017 §2/§4 — the workflow grammar as a frozen name set: the single source
#: of truth for grammar conformance (signal 104). Never re-list these elsewhere.
GRAMMAR_EVENT_NAMES: frozenset[str] = frozenset(name.value for name in BusinessEventName)


class Actor(StrEnum):
    """Closed vocabulary for the party a business event is attributed to (ADR 0017 §A2.1).

    ``actor`` was a free string defaulting to ``system``; this narrows it to a closed
    set. The narrowing is additive — every event emitted before this amendment is
    ``system``, so the envelope stays ``business_event.v1``.
    """

    SYSTEM = "system"
    EXTERNAL_CUSTOMER = "external_customer"
    INTERNAL_COLLABORATOR = "internal_collaborator"
    OPERATOR = "operator"


#: The closed ``actor`` vocabulary (§A2.1) — validated at emit time.
ACTORS: frozenset[str] = frozenset(a.value for a in Actor)
#: The human actors: a ``human_action``-level business fact (§A2.2) is exactly an event
#: whose actor is one of these — the distinction the 3-level ladder is built on.
HUMAN_ACTORS: frozenset[str] = frozenset(ACTORS - {Actor.SYSTEM.value})


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
        capability_id: str | None = None,
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
    grammar_version: str = GRAMMAR_VERSION
    workflow_id: str | None = None
    # ADR 0017 §A1.2 — optional; additive/optional keeps the envelope ``business_event.v1``
    # (events emitted before the amendment read honestly as ``capability_id IS NULL``). It is
    # step 4's per-capability join key; domain emitters stamp it when the capability is known.
    capability_id: str | None = None
    surface: str | None = None
    language: str | None = None
    model: str | None = None
    environment: str | None = None
    # ADR 0019 §4 — a synthetic (canary/test) turn's event. Excluded from every business-metric
    # surface by declaration (the emit-time counter guard + the read seam); still observable in
    # the trace, so the canary's own telemetry stays inspectable.
    synthetic: bool = False
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
        capability_id: str | None = None,
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
            capability_id=capability_id,
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


_LOG = get_logger("tessera.observability.business_events")


class ClickHouseBusinessEventStore:
    """Read-only ``BusinessEventStore`` backed by the owned ClickHouse table (ADR 0017 §5).

    The active read model once business-event reads flip to ``spine``. Reads rebuild
    :class:`BusinessEvent` s via :func:`_row_to_event`; ``append`` / ``clear`` are no-ops —
    writes reach the table through the best-effort dual-write
    (:mod:`tessera.observability.clickhouse_business_events`), and a read path must never
    truncate the owned store. An unreachable ClickHouse yields an honest-empty read.
    """

    def append(self, event: BusinessEvent) -> None:
        """No-op: writes reach the owned table via the dual-write, not this read store."""

    def list(
        self,
        *,
        at: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
        case_id: str | None = None,
        capability_id: str | None = None,
        event_name: str | None = None,
        artifact_type: str | None = None,
        decision: str | None = None,
    ) -> list[BusinessEvent]:
        """Read + rebuild business events from the owned table (honest-empty if unreachable)."""
        from tessera.observability.spine.adapters.base import SpineUnavailableError
        from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

        try:
            rows = ClickHouseAdapter().business_events(
                at=at,
                agent_id=agent_id,
                workflow_id=workflow_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                case_id=case_id,
                capability_id=capability_id,
                event_name=event_name,
                artifact_type=artifact_type,
                decision=decision,
            )
        except SpineUnavailableError as exc:
            _LOG.warning("owned business-event read unavailable: %s", exc)
            return []
        return [event for event in (_row_to_event(row) for row in rows) if event is not None]

    def clear(self) -> None:
        """No-op: a read path never truncates the owned store."""


class _ShadowBusinessEventStore:
    """Serve the in-process store, read the owned store, record divergence (§5 shadow parity).

    The safety net before the flip bakes: the primary (in-process) result is what callers
    get; the owned-store result is read and any count divergence is logged — a lagging owned
    store is surfaced, never silently served (ADR 0015 shadow discipline, per-fact).
    """

    def __init__(self, primary: BusinessEventStore, owned: BusinessEventStore) -> None:
        self._primary = primary
        self._owned = owned

    def append(self, event: BusinessEvent) -> None:
        """Append to the primary in-process store (the owned table is fed by the dual-write)."""
        self._primary.append(event)

    def list(
        self,
        *,
        at: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
        case_id: str | None = None,
        capability_id: str | None = None,
        event_name: str | None = None,
        artifact_type: str | None = None,
        decision: str | None = None,
    ) -> list[BusinessEvent]:
        """Serve the primary result; compare the owned store; log any divergence."""
        filters = {
            "at": at,
            "agent_id": agent_id,
            "workflow_id": workflow_id,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "case_id": case_id,
            "capability_id": capability_id,
            "event_name": event_name,
            "artifact_type": artifact_type,
            "decision": decision,
        }
        primary = self._primary.list(**filters)
        owned = self._owned.list(**filters)
        if len(primary) != len(owned):
            _LOG.warning(
                "business-event shadow divergence: primary=%d owned=%d filters=%s",
                len(primary),
                len(owned),
                {key: value for key, value in filters.items() if value is not None},
            )
        return primary

    def clear(self) -> None:
        """Clear the primary in-process store (never truncates the owned table)."""
        self._primary.clear()


_CLICKHOUSE_STORE: ClickHouseBusinessEventStore | None = None


def _clickhouse_store() -> ClickHouseBusinessEventStore:
    """The process-wide owned-store read adapter (stateless; built once)."""
    global _CLICKHOUSE_STORE
    if _CLICKHOUSE_STORE is None:
        _CLICKHOUSE_STORE = ClickHouseBusinessEventStore()
    return _CLICKHOUSE_STORE


def _read_store() -> BusinessEventStore:
    """The store business-event READS resolve to, per the ``business_events`` fact flip (§5).

    ``local`` → the in-process store; ``spine`` (default after the step-4 bake) → the
    owned ClickHouse table; ``shadow`` → serve in-process, compare owned, record divergence.
    Writes always append to the in-process store; the owned table is fed by the dual-write.
    """
    from tessera.observability.spine.adapters import fact_source

    source = fact_source("business_events")
    if source == "spine":
        return _clickhouse_store()
    if source == "shadow":
        return _ShadowBusinessEventStore(get_business_event_store(), _clickhouse_store())
    return get_business_event_store()


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


def validate_business_event(event: BusinessEvent) -> None:
    """Validate one event against the versioned workflow grammar (ADR 0017 §2, §4 L3).

    The single authoritative grammar check (signal 104): raises
    :class:`BusinessPayloadValidationError` if the event name is outside the
    grammar, its stamped grammar/schema versions disagree with this build, or its
    payload fails the strict (``extra="forbid"``, PII-free) contract for its name.
    The SDK testkit (:mod:`tessera.agent.sdk.testkit.grammar_conformance`) wraps
    this into the reusable CI conformance gate.
    """
    if event.event_name not in GRAMMAR_EVENT_NAMES:
        msg = f"event_name {event.event_name!r} is not in the workflow grammar"
        raise BusinessPayloadValidationError(msg)
    if event.grammar_version != GRAMMAR_VERSION:
        msg = f"grammar_version {event.grammar_version!r} != {GRAMMAR_VERSION!r}"
        raise BusinessPayloadValidationError(msg)
    if event.schema_version != EVENT_SCHEMA_VERSION:
        msg = f"schema_version {event.schema_version!r} != {EVENT_SCHEMA_VERSION!r}"
        raise BusinessPayloadValidationError(msg)
    _validate_event_payload(
        event_name=event.event_name,
        payload=event.payload,
        decision=event.decision,
        reason_codes=event.reason_codes,
        case_id=event.case_id,
        node_name=event.node_name,
        artifact_id=event.artifact_id,
        artifact_type=event.artifact_type,
        artifact_status=event.artifact_status,
    )


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
            capability_id=(
                str(row["capability_id"]) if row.get("capability_id") is not None else None
            ),
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
            # ADR 0019 §4 — carried through every medium that stores it. A row without the
            # key (a bundle or a pre-column ClickHouse row) is real, never assumed synthetic.
            synthetic=bool(row.get("synthetic", False)),
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
    capability_id: str | None = None,
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
        and (capability_id is None or event.capability_id == capability_id)
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
    capability_id: str | None = None,
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
            capability_id=capability_id,
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
    capability_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
    include_synthetic: bool = False,
) -> list[BusinessEvent]:
    """Return projected business events filtered by common dimensions.

    Reads resolve through the ``business_events`` fact flip (§5): the in-process store by
    default, the owned ClickHouse table once flipped, or a shadow comparison of both.

    Synthetic (canary/test) events are excluded **by default** (ADR 0019 §4): this is the one
    read seam every business surface (Métier tables, scores, signals, coverage, À traiter,
    replay) flows through, so excluding them here excludes them everywhere — by declaration, not
    by each caller filtering. The canary descriptor's own freshness read never comes here; it
    reads the durable S1 canary entry, so it is unaffected.

    Medium note: the filter reads ``event.synthetic``, and **every** read medium now round-trips
    it — the in-process store natively, and the owned ClickHouse table through its ``synthetic``
    ``UInt8`` column (added 2026-07-10). This matters because ``business_events`` defaults to
    ``spine``: ClickHouse *is* the default read medium, not the in-process store. Between the
    flip and that column, a canary row was written without the mark and rebuilt as a real event,
    so the exclusion silently failed on the very path it guards. Combined with the emit-time
    Prometheus guard, it is airtight on both media.
    """
    events = _read_store().list(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        capability_id=capability_id,
        event_name=event_name,
        artifact_type=artifact_type,
        decision=decision,
    )
    if include_synthetic:
        return events
    return [event for event in events if not event.synthetic]


def recent_business_events(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    capability_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
    include_synthetic: bool = False,
) -> list[BusinessEvent]:
    """Return live or as-of-T business events filtered by common dimensions.

    Synthetic (canary) events are excluded by default (ADR 0019 §4) — see
    :func:`persisted_business_events`.
    """
    return persisted_business_events(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        capability_id=capability_id,
        event_name=event_name,
        artifact_type=artifact_type,
        decision=decision,
        include_synthetic=include_synthetic,
    )


def business_event_rows(
    *,
    at: str | None = None,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    case_id: str | None = None,
    capability_id: str | None = None,
    event_name: str | None = None,
    artifact_type: str | None = None,
    decision: str | None = None,
    include_synthetic: bool = False,
) -> list[dict[str, object]]:
    """Return serialised business-event rows for replay / Cockpit projection.

    Synthetic (canary) events are excluded by default (ADR 0019 §4) — see
    :func:`persisted_business_events`.
    """
    return [
        event.to_row()
        for event in recent_business_events(
            at=at,
            agent_id=agent_id,
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            case_id=case_id,
            capability_id=capability_id,
            event_name=event_name,
            artifact_type=artifact_type,
            decision=decision,
            include_synthetic=include_synthetic,
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
            "tessera.business.capability_id": event.capability_id,
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
    if event.synthetic:
        # ADR 0019 §4 — a synthetic canary turn must NEVER move a business counter. The guard is
        # at emit (the counter fires here, not through a read), the twin of the read-seam filter.
        return
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


def _dual_write_owned(event: BusinessEvent) -> None:
    """Best-effort dual-write to the owned ClickHouse read model (ADR 0017 §5 / Phase D).

    Non-blocking and gated (``TESSERA_CLICKHOUSE_BUSINESS_EVENTS``): a down store is skipped,
    never raised into the hot path. The in-process store + replay bundles stay the read
    substrate until the flip bakes. Lazily imported to avoid an import cycle.
    """
    from tessera.observability.clickhouse_business_events import record_business_event_row

    record_business_event_row(event.to_row())


def record_business_event(
    *,
    event_name: BusinessEventName | str,
    agent_id: str,
    conversation_id: str,
    turn_id: str,
    workflow_id: str | None = None,
    capability_id: str | None = None,
    surface: str | None = None,
    language: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    synthetic: bool | None = None,
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
    """Normalise and fan out one business event to the existing sinks.

    ``synthetic`` defaults to the current turn's synthetic mark (ADR 0019 §4): a business event
    emitted inside a canary turn inherits it without the emitter having to pass it explicitly.
    """
    raw_payload = _json_safe_payload(payload)
    name = _event_name_value(event_name)
    if actor not in ACTORS:
        msg = f"unknown actor {actor!r}: expected one of {sorted(ACTORS)}"
        raise BusinessPayloadValidationError(msg)
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
        capability_id=capability_id,
        surface=surface,
        language=language,
        model=model,
        environment=environment,
        synthetic=_synthetic_turn.get() if synthetic is None else synthetic,
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
    _dual_write_owned(event)
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
