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


def verify_business_event(event: BusinessEvent) -> list[str]:
    """Return the L3 grammar-conformance violations for one event (empty ⇒ conforming)."""
    try:
        validate_business_event(event)
    except BusinessPayloadValidationError as exc:
        return [str(exc)]
    return []


def verify_event_stream(events: Iterable[BusinessEvent]) -> list[str]:
    """Return all grammar-conformance violations across an event stream, labelled by index."""
    violations: list[str] = []
    for index, event in enumerate(events):
        violations.extend(
            f"[event {index} {event.event_name}] {message}"
            for message in verify_business_event(event)
        )
    return violations


def assert_business_event(event: BusinessEvent) -> None:
    """Raise ``AssertionError`` if the event fails the L3 grammar contract (signal 104)."""
    violations = verify_business_event(event)
    assert not violations, "grammar-conformance (signal 104) violations: " + "; ".join(violations)
