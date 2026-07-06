"""The typed envelope ``actor`` — a closed vocabulary, enforced at emit (ADR 0017 §A2.1)."""

from __future__ import annotations

import pytest

from tessera.observability.business_events import (
    ACTORS,
    HUMAN_ACTORS,
    Actor,
    BusinessEventName,
    BusinessPayloadValidationError,
    record_business_event,
)


def _emit(actor: str):
    return record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="conv-actor",
        turn_id="turn-actor",
        actor=actor,
    )


def test_vocabulary_is_the_closed_set() -> None:
    assert {"system", "external_customer", "internal_collaborator", "operator"} == ACTORS
    assert {a.value for a in Actor} == ACTORS


def test_human_actors_exclude_system() -> None:
    # A ``human_action``-level fact (§A2.2) is exactly an event whose actor is human.
    assert "system" not in HUMAN_ACTORS
    assert {"external_customer", "internal_collaborator", "operator"} == HUMAN_ACTORS


def test_default_actor_is_system() -> None:
    event = record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="conv-actor",
        turn_id="turn-actor",
    )
    assert event.actor == "system"


@pytest.mark.parametrize("actor", sorted(ACTORS))
def test_each_vocabulary_actor_is_accepted(actor: str) -> None:
    assert _emit(actor).actor == actor


def test_unknown_actor_is_rejected() -> None:
    with pytest.raises(BusinessPayloadValidationError, match="unknown actor"):
        _emit("robot")
