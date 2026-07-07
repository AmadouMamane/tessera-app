"""The optional ``capability_id`` on the business-event envelope (ADR 0017 §A1.2).

Additive + optional → the envelope stays ``business_event.v1``: a pre-amendment event reads
honestly as ``capability_id`` absent/None, and a stamped one carries it through ``to_row``
and the rebuild. Emitter stamping itself rides step 4; this pins the envelope surface.
"""

from __future__ import annotations

from tessera.observability.business_events import (
    BusinessEvent,
    BusinessEventName,
    _row_to_event,
    record_business_event,
    reset_business_event_store,
)


def test_capability_id_defaults_to_none_and_serialises() -> None:
    event = BusinessEvent(
        event_name="intent.routed",
        timestamp="2026-07-07T00:00:00+00:00",
        agent_id="recouvrement",
        conversation_id="c1",
        turn_id="t1",
    )
    assert event.capability_id is None
    row = event.to_row()
    assert "capability_id" in row  # the field is always present on the envelope row
    assert row["capability_id"] is None


def test_record_business_event_stamps_capability_id_into_to_row() -> None:
    reset_business_event_store()
    event = record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="c1",
        turn_id="t1",
        capability_id="draft_reminder",
    )
    assert event.capability_id == "draft_reminder"
    assert event.to_row()["capability_id"] == "draft_reminder"


def test_capability_id_round_trips_through_rebuild() -> None:
    original = record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="c1",
        turn_id="t1",
        capability_id="propose_schedule",
    )
    rebuilt = _row_to_event(original.to_row())
    assert rebuilt is not None
    assert rebuilt.capability_id == "propose_schedule"
