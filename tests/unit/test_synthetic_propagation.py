"""ADR 0019 §Amendment 1 A1.1 — the synthetic stamp reaches the turn, in-process and on the wire.

§4 promises that test and canary turns never pollute business metrics. Before I5 that promise
rested entirely on `synthetic_turn()`, a ContextVar entered by the scheduled canary and by nobody
else. Two holes followed, and this suite closes both:

* **In-process.** An operator testing an agent from the cockpit Console reaches it through the very
  same `POST /chat` a customer uses. Its business events were indistinguishable from real traffic.
* **Across the wire.** A ContextVar is process-local by construction. An `http`-bound agent emits
  its own telemetry from another process, so the stamp must travel as data: `TurnInput.synthetic`.

The asymmetry that governs every test below: **failing to stamp a test turn inflates business
metrics; stamping a product turn deletes real facts.** The second is worse, so both directions are
pinned, never just the one that motivated the change.
"""

from __future__ import annotations

from contextvars import copy_context
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import SecretStr

from tessera.agent.registry import Surface
from tessera.agent.sdk.testkit import (
    verify_business_event,
    verify_event_stream,
    verify_turn_span,
)
from tessera.api.agent_invoker import HttpTurnInvoker
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.api.routes import chat as chat_route
from tessera.authz import Actor
from tessera.observability import semconv
from tessera.observability.business_events import (
    BusinessEvent,
    BusinessEventName,
    is_synthetic_turn,
    mark_synthetic_turn,
)
from tessera.settings import get_settings

#: Built by a test, not by a turn — and the envelope now insists on an answer to "who".
_FIXTURE_ACTOR = Actor.system("test-fixture")

if TYPE_CHECKING:
    from tessera.agent.turn_contract import TurnInput

_OP_KEY = "operator-assertion-test-key"

#: A conformant TurnResult body, so the invoker's verdict is green and the test is about the
#: request we sent, not the response we got back.
_CONFORMANT_RESULT: dict[str, object] = {
    "visibleReply": "ok",
    "artifact": None,
    "cardUpdates": [],
    "suggestedActions": [],
    "businessEvents": [],
    "businessScores": [],
    "decisions": {},
}


@pytest.fixture
def operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a real operator signing key (mint + verify share it)."""
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr(_OP_KEY))


# --------------------------------------------------------------------------- #
# In-process: the Console's test turn on `POST /chat`
# --------------------------------------------------------------------------- #


class _ProbeGraph:
    """A graph stand-in that records the synthetic mark the turn carried, then stops the turn.

    Reading `is_synthetic_turn()` *inside* `ainvoke` is the whole point: that is where the real
    graph — and every business event emitted beneath it — observes the mark. Raising afterwards
    short-circuits the rest of the SSE handler (reporter, transcript, eval) without an LLM; the
    route catches it and emits `turn.error`, which is a fine outcome for a probe.
    """

    def __init__(self) -> None:
        self.seen: bool | None = None

    async def ainvoke(self, _state: object, config: object = None) -> object:
        self.seen = is_synthetic_turn()
        msg = "probe: the turn stops here"
        raise RuntimeError(msg)


def _drive_chat_turn(monkeypatch: pytest.MonkeyPatch, *, assertion: str | None) -> bool | None:
    """POST one turn through the real ASGI route; return the mark the graph saw."""
    from starlette.testclient import TestClient

    from tessera.api.main import build_app

    probe = _ProbeGraph()
    monkeypatch.setattr(chat_route, "_streaming_graph", lambda: probe)

    # The transcript is Postgres-backed; the unit suite stays offline. Neither read changes what
    # this test measures (the surface → mark decision happens before the graph runs).
    async def _no_prior_agent(_conversation_id: object) -> None:
        return None

    monkeypatch.setattr(chat_route, "last_agent_for", _no_prior_agent)

    headers = {OPERATOR_ASSERTION_HEADER: assertion} if assertion else {}
    client = TestClient(build_app())
    response = client.post("/chat", json={"message": "un tour de test"}, headers=headers)
    assert response.status_code == 200
    # The probe raised, so the stream ends in turn.error — proof the graph really was entered.
    assert "turn.error" in response.text
    return probe.seen


def test_cockpit_console_test_turn_is_synthetic(
    operator_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator testing an agent from the cockpit Console is not a customer (§4)."""
    assertion = issue_operator_assertion("admin", "admin", surface=Surface.COCKPIT_EMBEDDED)
    assert _drive_chat_turn(monkeypatch, assertion=assertion) is True


def test_recouvrement_business_console_turn_is_not_synthetic(
    operator_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dedicated-ui` is an operator doing REAL work — its events must count.

    This is the expensive mistake in the other direction: stamping every operator surface
    synthetic would silently erase recouvrement's entire business record.
    """
    assertion = issue_operator_assertion("collections", "collections", surface=Surface.DEDICATED_UI)
    assert _drive_chat_turn(monkeypatch, assertion=assertion) is False


def test_customer_widget_turn_is_not_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """No assertion → the customer widget. Product traffic is never stamped."""
    assert _drive_chat_turn(monkeypatch, assertion=None) is False


def test_only_the_cockpit_surface_is_a_test_bench() -> None:
    """Pin the exact set: a new Surface must force a decision, never inherit one."""
    benches = {surface for surface in Surface if chat_route.is_test_turn(surface)}
    assert benches == {Surface.COCKPIT_EMBEDDED}


def test_mark_synthetic_turn_is_visible_beneath_it_and_dies_with_its_context() -> None:
    """The mark has no scope to exit — its scope IS the context it was set in.

    That is exactly the ASGI guarantee it relies on: every request runs in its own copied
    context, so the mark reaches the graph beneath it and cannot reach the next request. Setting
    it in a *shared* context would leak — this test learned that the hard way, by poisoning the
    business-counter assertions of every module that ran after it.
    """

    def _inside_one_request() -> bool:
        mark_synthetic_turn()
        return is_synthetic_turn()

    assert is_synthetic_turn() is False
    assert copy_context().run(_inside_one_request) is True
    assert is_synthetic_turn() is False


# --------------------------------------------------------------------------- #
# Across the wire: HttpTurnInvoker writes the posture onto the request body
# --------------------------------------------------------------------------- #


def _capturing_factory(sent: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    def factory(_timeout_s: float) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            sent.append(json.loads(request.content))
            return httpx.Response(200, json=_CONFORMANT_RESULT)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return factory


async def _invoke_capturing(*, synthetic: bool) -> dict[str, Any]:
    sent: list[dict[str, Any]] = []
    invoker = HttpTurnInvoker(client_factory=_capturing_factory(sent))
    turn_input: TurnInput = {"user_message": "probe", "language": "en"}
    outcome = await invoker.invoke(
        "turn-agent",
        turn_input,
        operator_assertion="assertion",
        actor=Actor(principal="op@bank.eu", role="admin"),
        conversation_id="c",
        turn_id="t",
        synthetic=synthetic,
    )
    assert outcome.verdict == "green", outcome.error
    assert len(sent) == 1
    return sent[0]


async def test_a_synthetic_invocation_says_so_on_the_wire() -> None:
    body = await _invoke_capturing(synthetic=True)
    assert body["synthetic"] is True


async def test_a_product_invocation_says_so_on_the_wire() -> None:
    # No consumer drives product traffic through the binding today, but the wire must be able to
    # say so: `synthetic` is a declaration, not a synonym for "someone used the invoker".
    body = await _invoke_capturing(synthetic=False)
    assert body["synthetic"] is False


async def test_the_callers_posture_overrides_whatever_the_turn_input_carried() -> None:
    """The platform, not its input, is the authority on whether it is testing the agent."""
    sent: list[dict[str, Any]] = []
    invoker = HttpTurnInvoker(client_factory=_capturing_factory(sent))
    # A stale/hostile TurnInput claiming to be product traffic must not win.
    turn_input: TurnInput = {"user_message": "probe", "synthetic": False}
    await invoker.invoke(
        "turn-agent",
        turn_input,
        operator_assertion="assertion",
        actor=Actor(principal="op@bank.eu", role="admin"),
        conversation_id="c",
        turn_id="t",
        synthetic=True,
    )
    assert sent[0]["synthetic"] is True


def test_the_invoker_refuses_to_guess_the_posture() -> None:
    """No default: a caller must state whether it is testing the agent (the lot-B lesson)."""
    import inspect

    parameter = inspect.signature(HttpTurnInvoker.invoke).parameters["synthetic"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


# --------------------------------------------------------------------------- #
# The conformance gate: the propagation duty is checked, not merely written down
# --------------------------------------------------------------------------- #
#
# ADR 0019 §A1.1 makes propagation "a conformance requirement checked by the SDK testkit —
# mandatory, not advisory". An `http` agent emits its own telemetry from its own process, so
# these two suites are the only place the platform can hold it to the duty.


class _RecordingSpan:
    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attrs[key] = value


def _stamped_span(*, synthetic: bool) -> dict[str, object]:
    span = _RecordingSpan()
    semconv.stamp_turn_dimensions(
        span,  # type: ignore[arg-type]
        agent_id="duplex-agent",
        language="fr",
        model=None,
        conversation_id="c",
        turn_id="t",
        environment="ci",
        synthetic=synthetic,
    )
    return span.attrs


def _grammar_event(*, synthetic: bool) -> BusinessEvent:
    return BusinessEvent(
        event_name=BusinessEventName.INTENT_ROUTED.value,
        timestamp="2026-01-01T00:00:00+00:00",
        agent_id="duplex-agent",
        conversation_id="c",
        turn_id="t",
        author_principal=_FIXTURE_ACTOR.principal,
        author_role=_FIXTURE_ACTOR.role,
        synthetic=synthetic,
    )


class TestSpanContractSyntheticCase:
    def test_a_propagating_agent_conforms(self) -> None:
        assert verify_turn_span(_stamped_span(synthetic=True), synthetic=True) == []
        assert verify_turn_span(_stamped_span(synthetic=False), synthetic=False) == []

    def test_a_synthetic_turn_left_unstamped_is_flagged(self) -> None:
        """The failure A1.1 exists to catch: test traffic entering business metrics."""
        violations = verify_turn_span(_stamped_span(synthetic=False), synthetic=True)
        assert any("did not propagate" in v for v in violations)

    def test_a_product_turn_stamped_synthetic_is_flagged(self) -> None:
        """The worse failure: real turns silently excluded from business reasoning."""
        violations = verify_turn_span(_stamped_span(synthetic=True), synthetic=False)
        assert any("excluded from business reasoning" in v for v in violations)

    def test_absent_means_product_so_an_agent_predating_the_field_still_conforms(self) -> None:
        attrs = _stamped_span(synthetic=False)
        assert semconv.TESSERA_SYNTHETIC not in attrs
        assert verify_turn_span(attrs, synthetic=False) == []


class TestGrammarConformanceSyntheticCase:
    def test_a_propagating_agent_conforms(self) -> None:
        assert verify_business_event(_grammar_event(synthetic=True), synthetic=True) == []
        assert verify_business_event(_grammar_event(synthetic=False), synthetic=False) == []

    def test_a_synthetic_turns_event_claiming_to_be_product_is_flagged(self) -> None:
        violations = verify_business_event(_grammar_event(synthetic=False), synthetic=True)
        assert any("must reach every event it emits" in v for v in violations)

    def test_a_product_turns_event_claiming_to_be_synthetic_is_flagged(self) -> None:
        violations = verify_business_event(_grammar_event(synthetic=True), synthetic=False)
        assert any("must reach every event it emits" in v for v in violations)

    def test_the_stream_checker_carries_the_posture_through(self) -> None:
        stream = [_grammar_event(synthetic=True), _grammar_event(synthetic=False)]
        violations = verify_event_stream(stream, synthetic=True)
        assert all("[event 1 intent.routed]" in v for v in violations)
