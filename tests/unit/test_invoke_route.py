"""The declared cockpit→agent invocation route (ADR 0019 §I3 + §3 + §4).

The route is the Console consumer's server seam; these pins hold its governance gates:
operator-only (no anonymous invocation), plane-scoped (``routable``), http-binding-only,
and it returns the invoker's honest outcome. The invoker itself is faked here — its own
behaviour is covered by ``test_agent_invoker`` — so the route's *gating* is what is tested.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tessera.api.agent_invoker import InvocationOutcome
from tessera.api.main import build_app
from tessera.api.ratelimit import InvokeLimiter, InvokeThrottledError, reset_invoke_limiter
from tessera.api.routes import invoke as invoke_routes
from tessera.api.session import SessionContext
from tessera.authz import AuthState, Surface

_client = TestClient(build_app())


@pytest.fixture(autouse=True)
def _fresh_invoke_limiter() -> None:
    """Isolate the process-wide invocation limiter between tests (rate/concurrency state)."""
    reset_invoke_limiter()


def _as_operator(monkeypatch, *, surface: Surface = Surface.COCKPIT_EMBEDDED) -> None:
    session = SessionContext(
        auth_state=AuthState.OPERATOR,
        subject_id="op-jules",
        authenticated=True,
        label="Opérateur · op-jules (admin)",
        demo=True,
    )
    monkeypatch.setattr(invoke_routes, "resolve_request_context", lambda _req: (session, surface))


class _FakeInvoker:
    def __init__(self, *_a, **_k) -> None: ...

    async def invoke(self, agent_id: str, turn_input, **_kw) -> InvocationOutcome:
        return InvocationOutcome(
            ok=True,
            verdict="green",
            duration_ms=1.0,
            result={"visibleReply": f"echo:{turn_input.get('user_message')}"},
            status_code=200,
        )


def test_non_operator_is_refused() -> None:
    # No operator assertion → resolve_request_context yields the customer widget → 401.
    resp = _client.post("/agents/turn-agent/invoke", json={"message": "hi"})
    assert resp.status_code == 401


def test_operator_invokes_http_agent_and_gets_the_outcome(monkeypatch) -> None:
    _as_operator(monkeypatch)
    monkeypatch.setattr(invoke_routes, "HttpTurnInvoker", _FakeInvoker)
    resp = _client.post("/agents/turn-agent/invoke", json={"message": "ping"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "green"
    assert body["result"]["visibleReply"] == "echo:ping"
    assert body["conversation_id"] and body["turn_id"]


def test_unknown_agent_is_404(monkeypatch) -> None:
    _as_operator(monkeypatch)
    resp = _client.post("/agents/no-such-agent/invoke", json={"message": "x"})
    assert resp.status_code == 404


def test_non_http_binding_is_400(monkeypatch) -> None:
    # recouvrement is reachable by a cockpit operator but declares in_process_chat — it is
    # tested through /chat, not this route (a 400, never a mis-dispatched POST).
    _as_operator(monkeypatch)
    resp = _client.post("/agents/recouvrement/invoke", json={"message": "x"})
    assert resp.status_code == 400


def test_unreachable_agent_is_403(monkeypatch) -> None:
    # support-client lives on the customer widget; a cockpit operator does not reach it (ADR
    # 0013 plane rules) — refused before any invocation.
    _as_operator(monkeypatch)
    resp = _client.post("/agents/support-client/invoke", json={"message": "x"})
    assert resp.status_code == 403


def test_invoke_rate_limit_returns_honest_429(monkeypatch: pytest.MonkeyPatch) -> None:
    # A purpose-built limit bounds the seam (ADR 0019 §Open questions): the turn past a 2/min
    # budget is a 429 carrying a Retry-After and an honest reason, never a silent drop.
    _as_operator(monkeypatch)
    monkeypatch.setattr(invoke_routes, "HttpTurnInvoker", _FakeInvoker)
    tiny = InvokeLimiter(rate="2/minute", max_concurrent=10, storage_uri="memory://", enabled=True)
    monkeypatch.setattr(invoke_routes, "get_invoke_limiter", lambda: tiny)
    assert _client.post("/agents/turn-agent/invoke", json={"message": "1"}).status_code == 200
    assert _client.post("/agents/turn-agent/invoke", json={"message": "2"}).status_code == 200
    resp = _client.post("/agents/turn-agent/invoke", json={"message": "3"})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After")
    assert "rate limit" in resp.json()["detail"]


def test_invoke_limiter_rate_is_per_subject() -> None:
    lim = InvokeLimiter(rate="2/minute", max_concurrent=10, storage_uri="memory://", enabled=True)
    lim.check_rate(agent_id="turn-agent", role="cockpit-embedded", subject="op-a")
    lim.check_rate(agent_id="turn-agent", role="cockpit-embedded", subject="op-a")
    with pytest.raises(InvokeThrottledError) as excinfo:
        lim.check_rate(agent_id="turn-agent", role="cockpit-embedded", subject="op-a")
    assert excinfo.value.retry_after >= 0
    assert "rate" in excinfo.value.reason
    # A different operator has its own budget — one caller cannot exhaust another's.
    lim.check_rate(agent_id="turn-agent", role="cockpit-embedded", subject="op-b")


def test_invoke_limiter_concurrency_cap() -> None:
    lim = InvokeLimiter(rate="100/minute", max_concurrent=2, storage_uri="memory://", enabled=True)
    held = [lim.concurrency_slot(agent_id="turn-agent", role="r") for _ in range(2)]
    for slot in held:
        slot.__enter__()
    with pytest.raises(InvokeThrottledError) as excinfo:
        lim.concurrency_slot(agent_id="turn-agent", role="r").__enter__()
    assert "concurrency" in excinfo.value.reason
    held[0].__exit__(None, None, None)  # free one slot → capacity available again
    freed = lim.concurrency_slot(agent_id="turn-agent", role="r")
    freed.__enter__()
    freed.__exit__(None, None, None)
    held[1].__exit__(None, None, None)


def test_invoke_limiter_disabled_is_noop() -> None:
    lim = InvokeLimiter(rate="1/minute", max_concurrent=1, storage_uri="memory://", enabled=False)
    for _ in range(5):
        lim.check_rate(agent_id="a", role="r", subject="s")  # never raises when disabled
    slots = [lim.concurrency_slot(agent_id="a", role="r") for _ in range(3)]
    for slot in slots:  # 3 > cap of 1, but disabled → no raise
        slot.__enter__()
    for slot in slots:
        slot.__exit__(None, None, None)
