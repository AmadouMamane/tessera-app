"""Grammar-conformance suite — signal 104, the ADR 0017 §4 L3 gate.

An agent is **L3 (Business)** iff its business events conform to the versioned
workflow grammar (ADR 0017 §2): event names ∈ the grammar, the stamped
grammar/schema versions match this build, and payloads are strict + PII-free (the
``extra="forbid"`` payload models). Reusable checker (ADR 0017 §7 testkit); the
authoritative grammar + validator live in
:mod:`tessera.observability.business_events`, never re-implemented here (0015
one-canonical-source).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.business_events import (
    GRAMMAR_EVENT_NAMES,
    BusinessPayloadValidationError,
    validate_business_event,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tessera.observability.business_events import BusinessEvent

__all__ = [
    "GRAMMAR_EVENT_NAMES",
    "assert_business_event",
    "verify_business_event",
    "verify_event_stream",
]


def verify_business_event(event: BusinessEvent, *, synthetic: bool) -> list[str]:
    """Return the L3 grammar-conformance violations for one event (empty ⇒ conforming).

    ``synthetic`` is the posture the platform declared for the turn that produced this event
    (``TurnInput.synthetic``), and it has no default — see
    :func:`tessera.agent.sdk.testkit.span_contract.verify_turn_span` for why stating it is the
    point. An event's ``synthetic`` field must equal the turn's posture: a test turn whose
    events claim to be product traffic moves business counters (ADR 0019 §4), and a product
    turn whose events claim to be synthetic deletes real facts from every business surface —
    both are caught here, at the agent's boundary, not after the numbers are wrong.
    """
    try:
        validate_business_event(event)
    except BusinessPayloadValidationError as exc:
        return [str(exc)]
    if event.synthetic is not synthetic:
        turn = "synthetic" if synthetic else "product"
        return [
            f"{turn} turn emitted an event with synthetic={event.synthetic!r} "
            f"(ADR 0019 §4: the turn's posture must reach every event it emits)"
        ]
    return []


def verify_event_stream(events: Iterable[BusinessEvent], *, synthetic: bool) -> list[str]:
    """Return all grammar-conformance violations across an event stream, labelled by index."""
    violations: list[str] = []
    for index, event in enumerate(events):
        violations.extend(
            f"[event {index} {event.event_name}] {message}"
            for message in verify_business_event(event, synthetic=synthetic)
        )
    return violations


def assert_business_event(event: BusinessEvent, *, synthetic: bool) -> None:
    """Raise ``AssertionError`` if the event fails the L3 grammar contract (signal 104)."""
    violations = verify_business_event(event, synthetic=synthetic)
    assert not violations, "grammar-conformance (signal 104) violations: " + "; ".join(violations)
