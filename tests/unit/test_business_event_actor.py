"""The typed envelope ``actor`` — a closed vocabulary of KINDS, enforced at emit (§A2.1).

It is a *kind*, never a name: ``operator`` is an authority, ``internal_collaborator`` is a
relationship. WHO acted lives in ``author_principal`` (see ``test_governed_acts_name_their_author``
and ADR 0024) — the two were one field until 2026-07-13, which is how a named collections officer's
action was exported to the SOC as having been performed by "system".
"""

from __future__ import annotations

import pytest

from tessera.authz import Actor
from tessera.observability.business_events import (
    ACTORS,
    HUMAN_ACTORS,
    ActorKind,
    BusinessEventName,
    BusinessPayloadValidationError,
    record_business_event,
)


def _emit(actor: str):
    # The author must AGREE with the kind — a human kind needs a human author, a system kind a
    # system one. record_business_event refuses the contradiction, which is the invariant the
    # single-field design could not even express.
    author = (
        Actor.system("test-fixture")
        if actor == ActorKind.SYSTEM.value
        else Actor(principal="julie@bank.eu", role="collections")
    )
    return record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="conv-actor",
        turn_id="turn-actor",
        author=author,
        actor_kind=actor,
    )


def test_vocabulary_is_the_closed_set() -> None:
    assert {"system", "external_customer", "internal_collaborator", "operator"} == ACTORS
    assert {a.value for a in ActorKind} == ACTORS


def test_human_actors_exclude_system() -> None:
    # A ``human_action``-level fact (§A2.2) is exactly an event whose actor is human.
    assert "system" not in HUMAN_ACTORS
    assert {"external_customer", "internal_collaborator", "operator"} == HUMAN_ACTORS


def test_the_kind_may_default_but_the_author_may_not() -> None:
    """The asymmetry IS the doctrine: a classification may default; an identity may never.

    ``actor`` (the kind) keeps its default because "which category of party" has a safe,
    honest answer when nobody says — ``system`` — and getting it wrong mislabels a row.
    ``author`` (the person) has none, because there is no safe answer to "who did this": every
    candidate default is a plausible constant, and a plausible constant in the author column is
    worse than a gap. A gap gets found. ``"Julie Dubois"`` did not, for two months.
    """
    event = record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="conv-actor",
        turn_id="turn-actor",
        author=Actor.system("test-fixture"),
    )
    assert event.actor_kind == "system", "the KIND defaults"
    assert event.author_principal == "system:test-fixture", "the AUTHOR was named, not defaulted"

    with pytest.raises(TypeError, match="author"):
        record_business_event(  # type: ignore[call-arg]
            event_name=BusinessEventName.INTENT_ROUTED,
            agent_id="recouvrement",
            conversation_id="conv-actor",
            turn_id="turn-actor",
        )


@pytest.mark.parametrize("actor", sorted(ACTORS))
def test_each_vocabulary_actor_is_accepted(actor: str) -> None:
    assert _emit(actor).actor_kind == actor


def test_unknown_actor_is_rejected() -> None:
    with pytest.raises(BusinessPayloadValidationError, match="unknown actor"):
        _emit("robot")
