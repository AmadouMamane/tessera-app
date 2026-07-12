"""The SDK conformance testkit — span-contract (103) + grammar-conformance (104).

Exercises the reusable suites shipped in ``tessera.agent.sdk.testkit`` (ADR 0017
§7, ADR 0018 §D): the L1 span-contract gate and the L3 grammar-conformance gate.
The drift guards tie each suite's contract to its single authoritative source
(``semconv.stamp_turn_dimensions`` / the ``business_events`` grammar), so a change
to the contract that forgets the testkit fails here.
"""

from __future__ import annotations

from tessera.agent.sdk.testkit import (
    REQUIRED_TURN_SPAN_ATTRIBUTES,
    assert_business_event,
    assert_turn_span,
    verify_business_event,
    verify_event_stream,
    verify_turn_span,
)
from tessera.authz import Actor
from tessera.observability import semconv
from tessera.observability.business_events import (
    GRAMMAR_EVENT_NAMES,
    BusinessEvent,
    BusinessEventName,
)


class _RecordingSpan:
    """Minimal span double that records set attributes (offline, no tracer)."""

    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


#: These envelopes are built by a test, not by a turn. Saying so is the honest answer to "who
#: authored this event" — and the envelope now requires an answer, which is the whole point.
_FIXTURE_ACTOR = Actor.system("test-fixture")


def _event(name: BusinessEventName, **overrides: object) -> BusinessEvent:
    """A minimally-populated envelope; ``overrides`` set the per-event fields."""
    base: dict[str, object] = {
        "event_name": name.value,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "agent_id": "recouvrement",
        "conversation_id": "conv-1",
        "turn_id": "turn-1",
        "author_principal": _FIXTURE_ACTOR.principal,
        "author_role": _FIXTURE_ACTOR.role,
    }
    base.update(overrides)
    return BusinessEvent(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Span-contract (signal 103, L1)
# --------------------------------------------------------------------------- #


class TestSpanContract:
    def test_stamped_turn_span_conforms(self) -> None:
        """A span stamped by the authoritative helper satisfies the L1 contract."""
        span = _RecordingSpan()
        semconv.stamp_turn_dimensions(
            span,  # type: ignore[arg-type]
            agent_id="recouvrement",
            language="fr",
            model="llama3.2:3b",
            conversation_id="conv-1",
            turn_id="turn-1",
            environment="local",
            synthetic=False,
        )
        assert verify_turn_span(span.attrs, synthetic=False) == []
        assert_turn_span(span.attrs, synthetic=False)

    def test_required_list_matches_the_authoritative_stamper(self) -> None:
        """Drift guard: every required attribute is actually stamped (no model)."""
        span = _RecordingSpan()
        semconv.stamp_turn_dimensions(
            span,  # type: ignore[arg-type]
            agent_id="a",
            language="en",
            model=None,  # model legitimately absent
            conversation_id="c",
            turn_id="t",
            environment="ci",
            synthetic=False,
        )
        # Model omitted → still conforming (it is conditional, not required).
        assert verify_turn_span(span.attrs, synthetic=False) == []
        for key in REQUIRED_TURN_SPAN_ATTRIBUTES:
            assert key in span.attrs, f"stamper no longer stamps required key {key!r}"

    def test_missing_required_attribute_is_flagged(self) -> None:
        span = _RecordingSpan()
        semconv.stamp_turn_dimensions(
            span,  # type: ignore[arg-type]
            agent_id="a",
            language="fr",
            model=None,
            conversation_id="c",
            turn_id="t",
            environment="local",
            synthetic=False,
        )
        del span.attrs[semconv.TESSERA_TURN_ID]
        violations = verify_turn_span(span.attrs, synthetic=False)
        assert any(semconv.TESSERA_TURN_ID in v for v in violations)

    def test_empty_required_attribute_is_flagged(self) -> None:
        attrs = {
            semconv.TESSERA_AGENT_ID: "",  # empty
            semconv.TESSERA_LANGUAGE: "fr",
            semconv.GEN_AI_CONVERSATION_ID: "c",
            semconv.TESSERA_TURN_ID: "t",
            semconv.DEPLOYMENT_ENVIRONMENT: "local",
        }
        violations = verify_turn_span(attrs, synthetic=False)
        assert any(semconv.TESSERA_AGENT_ID in v and "empty" in v for v in violations)

    def test_present_but_empty_model_is_flagged(self) -> None:
        attrs = {
            semconv.TESSERA_AGENT_ID: "a",
            semconv.TESSERA_LANGUAGE: "fr",
            semconv.GEN_AI_CONVERSATION_ID: "c",
            semconv.TESSERA_TURN_ID: "t",
            semconv.DEPLOYMENT_ENVIRONMENT: "local",
            semconv.GEN_AI_REQUEST_MODEL: "",  # present but empty
        }
        violations = verify_turn_span(attrs, synthetic=False)
        assert any(semconv.GEN_AI_REQUEST_MODEL in v for v in violations)


# --------------------------------------------------------------------------- #
# Grammar-conformance (signal 104, L3)
# --------------------------------------------------------------------------- #


class TestGrammarConformance:
    def test_grammar_names_are_the_thirteen(self) -> None:
        assert {name.value for name in BusinessEventName} == GRAMMAR_EVENT_NAMES
        assert len(GRAMMAR_EVENT_NAMES) == 13

    def test_valid_non_critical_event_conforms(self) -> None:
        # intent.routed has no payload model and no required envelope fields.
        assert verify_business_event(_event(BusinessEventName.INTENT_ROUTED), synthetic=False) == []

    def test_valid_critical_event_conforms(self) -> None:
        event = _event(
            BusinessEventName.POLICY_DECISION_MADE,
            decision="allowed",
            payload={"policy_rule": "contact_window_policy"},
        )
        assert verify_business_event(event, synthetic=False) == []
        assert_business_event(event, synthetic=False)

    def test_event_name_outside_grammar_is_flagged(self) -> None:
        rogue = BusinessEvent(
            event_name="fraud.detected",  # not in the grammar
            timestamp="2026-01-01T00:00:00+00:00",
            agent_id="x",
            conversation_id="c",
            turn_id="t",
            author_principal=_FIXTURE_ACTOR.principal,
            author_role=_FIXTURE_ACTOR.role,
        )
        violations = verify_business_event(rogue, synthetic=False)
        assert any("workflow grammar" in v for v in violations)

    def test_unexpected_payload_key_is_rejected(self) -> None:
        # extra="forbid" is what makes payloads PII-free by construction: an
        # un-whitelisted key (here a stray free-text field) is a hard violation.
        event = _event(
            BusinessEventName.POLICY_DECISION_MADE,
            decision="allowed",
            payload={"policy_rule": "x", "customer_email": "jean@example.com"},
        )
        violations = verify_business_event(event, synthetic=False)
        assert any("invalid payload" in v for v in violations)

    def test_missing_required_envelope_field_is_flagged(self) -> None:
        # artifact.created requires artifact_id/type/status/case_id/node_name.
        event = _event(
            BusinessEventName.ARTIFACT_CREATED,
            payload={"title": "Brouillon"},
        )
        violations = verify_business_event(event, synthetic=False)
        assert any("missing" in v for v in violations)

    def test_wrong_grammar_version_is_flagged(self) -> None:
        event = _event(
            BusinessEventName.INTENT_ROUTED,
            grammar_version="workflow_grammar.v2",
        )
        violations = verify_business_event(event, synthetic=False)
        assert any("grammar_version" in v for v in violations)

    def test_event_stream_labels_violations_by_index(self) -> None:
        stream = [
            _event(BusinessEventName.INTENT_ROUTED),  # ok
            _event(BusinessEventName.ARTIFACT_CREATED),  # missing envelope fields
        ]
        violations = verify_event_stream(stream, synthetic=False)
        assert violations
        assert all("[event 1 artifact.created]" in v for v in violations)
