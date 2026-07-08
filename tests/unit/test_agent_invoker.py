"""HTTP turn invoker (ADR 0019 §I3) — assertion forwarding, timeout, audit, honest red.

Hermetic — no live server. The invoker is driven over an ``httpx.MockTransport`` (the same
fake-seam discipline as the canary's ``InProcessChatInvoker`` double), so the transport
behaviour, the conformance gate, the "no anonymous invocation" refusal and the one-S1-per-call
audit are exercised in isolation. The load-bearing properties:

* a conformant response is green; a timeout / refused connection / non-2xx / non-conformant
  body is **red**, never a fabricated green;
* the verified operator assertion is forwarded on every call, and an empty one is refused
  **before the network is touched** (no anonymous invocation, §4);
* exactly one S1 event is emitted per invocation, green or red (a governed act lives in the
  ledger either way).
"""

from __future__ import annotations

import httpx

from tessera.agent.turn_contract import TURN_RESULT_KEYS
from tessera.api.agent_invoker import HttpTurnInvoker, InvocationOutcome
from tessera.guard import audit

_ASSERTION = "signed.operator-assertion-token"


def _conformant_body() -> dict[str, object]:
    body: dict[str, object] = {key: [] for key in TURN_RESULT_KEYS}
    body["visibleReply"] = "ok"
    body["artifact"] = None
    body["decisions"] = {}
    return body


def _invoker_over(handler) -> tuple[HttpTurnInvoker, list[httpx.Request]]:
    """An invoker whose client is backed by a MockTransport; records the requests it saw."""
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(timeout_s: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(_record), timeout=timeout_s)

    return HttpTurnInvoker(client_factory=factory), seen


async def _invoke(invoker: HttpTurnInvoker, *, assertion: str = _ASSERTION) -> InvocationOutcome:
    return await invoker.invoke(
        "turn-agent",
        {"user_message": "probe", "language": "en"},
        operator_assertion=assertion,
        actor="op-principal",
        conversation_id="conv-1",
        turn_id="turn-1",
    )


# ── green path + assertion forwarding + one S1 ────────────────────────────────────


async def test_conformant_response_is_green_and_forwards_the_assertion(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **kw: captured.append(kw))
    invoker, seen = _invoker_over(lambda _req: httpx.Response(200, json=_conformant_body()))

    outcome = await _invoke(invoker)

    assert outcome.ok is True
    assert outcome.verdict == "green"
    assert outcome.status_code == 200
    assert outcome.result is not None and outcome.result["visibleReply"] == "ok"
    # The verified operator assertion is forwarded verbatim (0010 Phase B).
    assert seen[0].headers["x-tessera-operator-assertion"] == _ASSERTION
    # Exactly one S1 event, green, attributed to the operator principal.
    assert len(captured) == 1
    assert captured[0]["verdict"] == "green"
    assert captured[0]["actor"] == "op-principal"
    assert captured[0]["binding"] == "http"


# ── red paths: never a fabricated green ───────────────────────────────────────────


async def test_non_conformant_response_is_red_with_violations(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **kw: captured.append(kw))
    # Reachable, 200, but the body breaks the turn contract (missing keys).
    invoker, _ = _invoker_over(lambda _req: httpx.Response(200, json={"reply": "wrong"}))

    outcome = await _invoke(invoker)

    assert outcome.verdict == "red"
    assert outcome.conformance  # the violations say WHY it is red
    assert captured[0]["verdict"] == "red"


async def test_http_error_status_is_red(monkeypatch) -> None:
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **_kw: None)
    invoker, _ = _invoker_over(lambda _req: httpx.Response(500, text="boom"))
    outcome = await _invoke(invoker)
    assert outcome.verdict == "red"
    assert outcome.status_code == 500


async def test_timeout_is_red_not_a_raise(monkeypatch) -> None:
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **_kw: None)

    def _timeout(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    invoker, _ = _invoker_over(_timeout)
    outcome = await _invoke(invoker)
    assert outcome.verdict == "red"
    assert outcome.error is not None and "timeout" in outcome.error


async def test_connect_error_is_red(monkeypatch) -> None:
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **_kw: None)

    def _boom(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    invoker, _ = _invoker_over(_boom)
    outcome = await _invoke(invoker)
    assert outcome.verdict == "red"


# ── governance: no anonymous invocation, refused before the network ───────────────


async def test_missing_assertion_is_refused_without_touching_the_network(monkeypatch) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **kw: captured.append(kw))
    invoker, seen = _invoker_over(lambda _req: httpx.Response(200, json=_conformant_body()))

    outcome = await _invoke(invoker, assertion="")

    assert outcome.verdict == "red"
    assert outcome.error is not None and "anonymous" in outcome.error
    assert seen == []  # the network was never touched
    assert len(captured) == 1  # the refused governed act is still audited


async def test_non_http_agent_is_refused(monkeypatch) -> None:
    # support-client declares in_process_chat, not http — the http invoker refuses it (red),
    # rather than POSTing to a non-existent endpoint.
    monkeypatch.setattr(audit, "emit_agent_invocation", lambda **_kw: None)
    invoker, seen = _invoker_over(lambda _req: httpx.Response(200, json=_conformant_body()))
    outcome = await invoker.invoke(
        "support-client",
        {"user_message": "x"},
        operator_assertion=_ASSERTION,
        actor="op",
        conversation_id="c",
        turn_id="t",
    )
    assert outcome.verdict == "red"
    assert outcome.error is not None and "http" in outcome.error
    assert seen == []
