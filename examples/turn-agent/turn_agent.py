"""turn-agent — the ADR 0019 §I3 acceptance test (first invocable external agent).

The counterpart to ``hello-agent``: where hello-agent proves the *publish-only* contract
(pure OTLP, ``binding: none``, honest-empty console), turn-agent proves the *invocable*
contract — it EXPOSES an HTTP turn endpoint speaking the ADR 0018 turn contract, so the
cockpit's :class:`~tessera.api.agent_invoker.HttpTurnInvoker` can send it a turn under the
declared ``binding: http``. Like hello-agent it has a **zero tessera import**: the turn
contract is honoured by shape (the camelCase keys are hard-coded here precisely to prove a
remote agent needs no tessera dependency), and the operator assertion is verified with the
same wire format tessera uses, reimplemented in stdlib.

Run:

    uv run python examples/turn-agent/turn_agent.py           # serves POST /turn on :8500

Env: ``TURN_AGENT_PORT`` (default 8500), ``TURN_AGENT_OPERATOR_KEY`` (optional — when set,
a turn is refused with 401 unless it carries a valid operator assertion, mirroring tessera's
"no anonymous invocation" posture; when unset the check is inert, the safe dev default).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

AGENT_ID = "turn-agent"

#: The ADR 0018 TurnResult camelCase keys (TURN_RESULT_KEYS). Hard-coded, not imported —
#: the whole point is that a remote runtime speaks the contract with no tessera dependency.
_TURN_RESULT_KEYS = (
    "visibleReply",
    "artifact",
    "cardUpdates",
    "suggestedActions",
    "businessEvents",
    "businessScores",
    "decisions",
)

#: The header tessera forwards the signed operator assertion on (mirrors
#: ``tessera.api.operator.OPERATOR_ASSERTION_HEADER``).
_OPERATOR_ASSERTION_HEADER = "x-tessera-operator-assertion"
_ASSERTION_MAX_AGE_S = 5 * 60


def handle_turn(turn_input: dict[str, Any]) -> dict[str, Any]:
    """Process one turn and return a conformant ADR 0018 TurnResult.

    A deliberately trivial agent: it echoes the incoming message into ``visibleReply`` and
    fills every other contract key with its empty default. The value here is not the NLP —
    it is that the *shape* is exactly the turn contract, so the cockpit invoker's conformance
    check (``verify_turn_result``) passes and the http binding is proven end to end.
    """
    message = str(turn_input.get("user_message") or "").strip()
    language = str(turn_input.get("language") or "en")
    reply = f"[{AGENT_ID}] received ({language}): {message}" if message else f"[{AGENT_ID}] ready"
    result: dict[str, Any] = {key: [] for key in _TURN_RESULT_KEYS}
    result["visibleReply"] = reply
    result["artifact"] = None
    result["decisions"] = {"echoed": bool(message), "language": language}
    return result


def _verify_assertion(header_value: str | None, key: bytes) -> bool:
    """Verify a forwarded operator assertion (stdlib reimplementation of tessera's format).

    ``base64url(payload).base64url(HMAC-SHA256(key, payload))`` with a short-lived ``iat``.
    Constant-time MAC check; any malformed / expired / forged token is refused. This is the
    agent's own defence in depth — the cockpit already refuses to send an anonymous turn.
    """
    if not header_value:
        return False
    body, _, signature = header_value.partition(".")
    if not body or not signature:
        return False
    expected = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
    try:
        presented = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    except (ValueError, TypeError):
        return False
    if not hmac.compare_digest(expected, presented):
        return False
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError):
        return False
    issued_at = payload.get("iat") if isinstance(payload, dict) else None
    return isinstance(issued_at, int) and (time.time() - issued_at) <= _ASSERTION_MAX_AGE_S


class _TurnHandler(BaseHTTPRequestHandler):
    """POST /turn → a conformant TurnResult. No other route is served."""

    server_version = f"{AGENT_ID}/1.0"

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802  (http.server dispatch name)
        if self.path.rstrip("/") != "/turn":
            self._send_json(404, {"error": "not found"})
            return
        key = os.environ.get("TURN_AGENT_OPERATOR_KEY")
        if key and not _verify_assertion(
            self.headers.get(_OPERATOR_ASSERTION_HEADER), key.encode("utf-8")
        ):
            # A key is configured but the turn is unauthenticated — refuse (no anonymous turn).
            self._send_json(401, {"error": "missing or invalid operator assertion"})
            return
        try:
            length = int(self.headers.get("content-length") or 0)
            turn_input = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self._send_json(400, {"error": "body was not valid JSON"})
            return
        if not isinstance(turn_input, dict):
            self._send_json(400, {"error": "turn input must be a JSON object"})
            return
        self._send_json(200, handle_turn(turn_input))

    def log_message(self, *_args: Any) -> None:
        return


def main() -> None:
    """Serve POST /turn forever (SIGTERM to stop)."""
    port = int(os.environ.get("TURN_AGENT_PORT", "8500"))
    server = ThreadingHTTPServer(("127.0.0.1", port), _TurnHandler)
    guarded = (
        "on (TURN_AGENT_OPERATOR_KEY set)"
        if os.environ.get("TURN_AGENT_OPERATOR_KEY")
        else "off (dev)"
    )
    print(f"{AGENT_ID}: POST /turn on http://127.0.0.1:{port} — operator-assertion check {guarded}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
