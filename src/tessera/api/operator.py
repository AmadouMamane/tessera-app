"""Signed operator assertion — the server-verified source of ``AuthState.OPERATOR``.

ADR 0010 Phase B forwards the operator identity that ADR 0009 keeps in the Next.js
front (next-auth) through to the agent, so the agent can derive
``AuthState.OPERATOR`` from a **trusted, server-verified signal — never a
client-asserted field**. The chosen mechanism mirrors the customer-session cookie
(``tessera.api.session``):

* The **Next BFF** (``app/api/chat/route.ts``) calls ``auth()``. When a request
  comes from the cockpit console *and* carries a valid operator next-auth session,
  the BFF mints a signed assertion ``base64url(payload) "." base64url(HMAC-
  SHA256(key, payload))`` with ``payload = {principal, role, surface, iat}`` and
  forwards it to the agent as the ``X-Tessera-Operator-Assertion`` header. Without
  an operator session, nothing is minted — the turn stays customer/widget.
* The **agent** verifies that assertion here. A forged or edited token fails the
  constant-time MAC check and yields ``None`` (no operator). The browser cannot
  forge a valid assertion: it never holds the signing key (server-only env /
  Secret Manager). The raw "client surface" hint is consumed by the BFF only and
  is **never** honoured by the agent on its own — the agent trusts the signature,
  not a header value.

Unlike the customer cookie, mint (front) and verify (agent) run in **different
processes**, so there is no process-ephemeral fallback: both sides must share the
exact key. In production a missing key is fail-closed (refuse to boot); in dev/CI
an unset key simply makes the operator path inert (no assertion ever verifies),
which is the safe direction — it can never *grant* operator by accident.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING

from tessera.api.session import SessionContext, resolve_session
from tessera.authz import AuthState, Surface
from tessera.settings import get_settings

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = [
    "OPERATOR_ASSERTION_HEADER",
    "OPERATOR_ROLES",
    "issue_operator_assertion",
    "resolve_request_context",
    "validate_operator_assertion_key",
    "verify_operator_assertion",
]

#: Header the Next BFF uses to forward the signed operator assertion to the agent.
OPERATOR_ASSERTION_HEADER = "x-tessera-operator-assertion"

#: The next-auth roles that count as an operator (mirrors lib/auth/accounts.ts).
OPERATOR_ROLES: frozenset[str] = frozenset({"admin", "auditor", "superadmin"})

#: Assertion lifetime. Short — it is minted per turn from a live session, not stored.
OPERATOR_ASSERTION_MAX_AGE_SECONDS = 5 * 60

#: The only surface an operator assertion may carry (ADR 0010 Phase B). The agent
#: refuses any other value so a console assertion can never claim the widget.
_OPERATOR_SURFACE_VALUE = Surface.COCKPIT_EMBEDDED.value


_MISSING_KEY_IN_PROD = (
    "TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is required in production (resolve "
    "it from GCP Secret Manager). The operator assertion is minted by the Next BFF "
    "and verified by the agent; both must share this key. Refusing to boot without it."
)


def validate_operator_assertion_key() -> None:
    """Fail-closed startup check: production must configure the operator key.

    Called once at app startup (``build_app``) alongside the customer-session
    check, so a misconfigured production process refuses to boot rather than
    silently leaving the operator path unverifiable. No-op in dev/CI (the path is
    simply inert there).
    """
    settings = get_settings()
    if settings.is_production() and settings.api.operator_assertion_signing_key is None:
        raise RuntimeError(_MISSING_KEY_IN_PROD)


def _operator_key() -> bytes | None:
    """Return the operator assertion HMAC key, or ``None`` when the path is inert.

    Configured secret → its bytes. Production + unset → raise (defence in depth
    behind :func:`validate_operator_assertion_key`). Dev/CI + unset → ``None``,
    meaning no assertion can verify (the operator path is disabled, never granted).
    """
    settings = get_settings()
    configured = settings.api.operator_assertion_signing_key
    if configured is not None:
        return configured.get_secret_value().encode("utf-8")
    if settings.is_production():
        raise RuntimeError(_MISSING_KEY_IN_PROD)
    return None


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_operator_assertion(principal: str, role: str) -> str:
    """Sign an operator assertion binding ``principal``/``role`` to the cockpit surface.

    This is the Python reference for the token the Next BFF mints (the BFF mirrors
    the exact wire format). Used by the agent's tests; in production the BFF is the
    real minter. Raises if no key is available (cannot sign without one).
    """
    key = _operator_key()
    if key is None:
        raise RuntimeError("no operator assertion signing key configured")
    payload = {
        "principal": principal,
        "role": role,
        "surface": _OPERATOR_SURFACE_VALUE,
        "iat": int(time.time()),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_operator_assertion(token: str) -> SessionContext | None:  # noqa: PLR0911  fail-closed: each invalid shape returns None explicitly
    """Verify a signed operator assertion; return an OPERATOR session, else ``None``.

    Any failure — no key configured, bad shape, forged/edited signature, expired
    stamp, wrong surface, or a non-operator role — yields ``None`` (the turn is not
    operator). The signature check is constant-time.
    """
    key = _operator_key()
    if key is None:
        return None
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    expected = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
    try:
        presented = _b64d(signature)
    except ValueError:  # binascii.Error subclasses ValueError
        return None
    if not hmac.compare_digest(expected, presented):
        return None
    try:
        payload = json.loads(_b64d(body))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    issued_at = payload.get("iat")
    if (
        not isinstance(issued_at, int)
        or time.time() - issued_at > OPERATOR_ASSERTION_MAX_AGE_SECONDS
    ):
        return None
    # The assertion may only ever carry the cockpit surface and an operator role —
    # a valid signature over any other value is still refused (defence in depth).
    if payload.get("surface") != _OPERATOR_SURFACE_VALUE:
        return None
    role = payload.get("role")
    if not isinstance(role, str) or role not in OPERATOR_ROLES:
        return None
    principal = payload.get("principal")
    if not isinstance(principal, str) or not principal:
        return None
    return SessionContext(
        auth_state=AuthState.OPERATOR,
        subject_id=principal,
        authenticated=True,
        label=f"Opérateur · {principal} ({role})",
        demo=True,
    )


def resolve_request_context(request: Request) -> tuple[SessionContext, Surface]:
    """Resolve the turn's ``(session, surface)`` from trusted, server-verified signals.

    Operator path (ADR 0010 Phase B): a valid signed operator assertion header →
    ``(OPERATOR, cockpit-embedded)``. Otherwise the existing customer path (ADR
    0008/0009) is untouched: the signed cookie resolves to ``CUSTOMER``/``ANONYMOUS``
    on the ``shared-customer-widget``. The operator branch is strictly additive —
    a forged assertion falls through to the cookie path (never an error, never an
    escalation).
    """
    raw = request.headers.get(OPERATOR_ASSERTION_HEADER)
    if raw:
        operator = verify_operator_assertion(raw)
        if operator is not None:
            return operator, Surface.COCKPIT_EMBEDDED
    return resolve_session(request), Surface.SHARED_CUSTOMER_WIDGET
