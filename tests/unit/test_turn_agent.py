"""turn-agent (ADR 0019 §I3) speaks the turn contract — the SDK testkit http gate.

The invocable counterpart of ``test_hello_agent``: where hello-agent proves the L1 span
contract, turn-agent proves the ADR 0019 §I3 promise — *"an agent declaring ``http`` must
speak the turn contract"*. Its ``handle_turn`` output must satisfy ``verify_turn_result``
(the reusable conformance suite the cockpit invoker also runs before trusting a response).
It also carries the operator-assertion verifier (the agent's own "no anonymous turn"
posture), pinned here for accept / reject.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import time
from pathlib import Path

from tessera.agent.sdk.testkit.turn_contract_conformance import (
    assert_turn_result,
    verify_turn_result,
)

_TURN_PATH = Path(__file__).resolve().parents[2] / "examples" / "turn-agent" / "turn_agent.py"


def _turn_agent() -> object:
    spec = importlib.util.spec_from_file_location("turn_agent", _TURN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sign(key: bytes, *, iat: int) -> str:
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"principal": "op", "role": "admin", "iat": iat}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = (
        base64.urlsafe_b64encode(hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest())
        .rstrip(b"=")
        .decode()
    )
    return f"{payload}.{sig}"


# ── the http contract: handle_turn returns a conformant TurnResult ────────────────


def test_handle_turn_output_is_a_conformant_turn_result() -> None:
    mod = _turn_agent()
    result = mod.handle_turn({"user_message": "bonjour", "language": "fr"})
    assert verify_turn_result(result) == []
    assert_turn_result(result)  # raises on any violation
    # It actually processed the turn (echo), not a canned empty.
    assert "bonjour" in result["visibleReply"]
    assert result["decisions"] == {"echoed": True, "language": "fr"}


def test_handle_turn_conforms_even_on_empty_input() -> None:
    # A turn with no message is still a conformant TurnResult (all keys present, empty defaults).
    result = _turn_agent().handle_turn({})
    assert verify_turn_result(result) == []
    assert result["artifact"] is None
    assert result["businessEvents"] == []


def test_conformance_gate_has_teeth() -> None:
    # Drift guard: a foreign shape (missing the contract keys) is flagged — the gate is real.
    assert verify_turn_result({"reply": "wrong shape"})  # non-empty violations
    assert verify_turn_result("not even an object")


# ── the agent's own "no anonymous turn" posture (operator-assertion verify) ───────


def test_verify_assertion_accepts_a_fresh_valid_token() -> None:
    mod = _turn_agent()
    key = b"shared-secret"
    assert mod._verify_assertion(_sign(key, iat=int(time.time())), key) is True


def test_verify_assertion_rejects_missing_forged_and_expired() -> None:
    mod = _turn_agent()
    key = b"shared-secret"
    assert mod._verify_assertion(None, key) is False
    assert mod._verify_assertion("garbage", key) is False
    assert mod._verify_assertion(_sign(b"other-key", iat=int(time.time())), key) is False
    assert mod._verify_assertion(_sign(key, iat=int(time.time()) - 10_000), key) is False
