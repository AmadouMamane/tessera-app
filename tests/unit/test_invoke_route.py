"""The declared cockpit→agent invocation route (ADR 0019 §I3 + §3 + §4).

The route is the Console consumer's server seam; these pins hold its governance gates:
operator-only (no anonymous invocation), plane-scoped (``routable``), http-binding-only,
and it returns the invoker's honest outcome. The invoker itself is faked here — its own
behaviour is covered by ``test_agent_invoker`` — so the route's *gating* is what is tested.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tessera.api.agent_invoker import InvocationOutcome
from tessera.api.main import build_app
from tessera.api.routes import invoke as invoke_routes
from tessera.api.session import SessionContext
from tessera.authz import AuthState, Surface

_client = TestClient(build_app())


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
