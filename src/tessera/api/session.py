"""Signed customer session — the server-side source of ``auth_state`` (ADR 0008/0009).

ADR 0008 mandates that the agent's ``auth_state`` be **derived server-side from a
verified session, never asserted by the request body**. This module is that single
source of truth.

What is real (architecturally):

* A tamper-evident session **cookie**: ``base64url(payload) "." base64url(HMAC-
  SHA256(key, payload))``, signed with a key that comes from settings / GCP Secret
  Manager and is **never committed** (``TESSERA_API_SESSION_SIGNING_KEY``). A
  forged or edited cookie fails the constant-time signature check and is ignored.
* The cookie is ``httpOnly`` (JS cannot read it), ``SameSite=Lax``, and ``Secure``
  when TLS is terminated. It carries an issued-at stamp and expires.
* ``auth_state`` is read from the *verified* payload only — body tampering cannot
  change it.

What is demo-assumed (banque fictive, day-twenty): "logging in" establishes a
session for a single **seeded** customer identity (:data:`DEMO_CUSTOMER_ID`),
labelled as a demo. There is no password, no KYC, no production IdP, no signup.
The operator (``operator-rbac``) tier is intentionally out of scope.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.authz import AuthState
from tessera.settings import get_settings

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

__all__ = [
    "DEMO_CUSTOMER_ID",
    "DEMO_CUSTOMER_LABEL",
    "SESSION_COOKIE",
    "SessionContext",
    "clear_session_cookie",
    "issue_session_token",
    "resolve_session",
    "set_session_cookie",
    "validate_session_signing_key",
    "verify_session_token",
]

#: Cookie name carrying the signed session token.
SESSION_COOKIE = "tessera_session"

#: The single seeded customer identity a demo login authenticates as. It matches
#: the account-tools demo dataset (``account_balance._DEMO_ACCOUNTS``) so that
#: memory, account tools, and recouvrement all resolve to one coherent customer.
DEMO_CUSTOMER_ID = "demo-customer-001"
DEMO_CUSTOMER_LABEL = "Client démo · demo-customer-001"

#: Session lifetime. Short, since it is a demo session, not a real SSO session.
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60

# Process-ephemeral fallback key, used only when no signing key is configured
# (local dev / CI). Sessions then survive within a process but not across a
# restart — honest for a demo, and never a committed secret. Production MUST set
# TESSERA_API_SESSION_SIGNING_KEY (resolved from GCP Secret Manager).
_EPHEMERAL_KEY = secrets.token_bytes(32)
_warned_ephemeral = False


_MISSING_KEY_IN_PROD = (
    "TESSERA_API_SESSION_SIGNING_KEY is required in production (resolve it from "
    "GCP Secret Manager). Refusing to use a process-ephemeral session key, which "
    "is non-persistent and inconsistent across replicas."
)


def validate_session_signing_key() -> None:
    """Fail-closed startup check: a production process must have a real signing key.

    Called once at app startup (``build_app``) so a misconfiguration **refuses to
    boot** rather than silently degrading to an ephemeral key at the first request
    (ADR 0008/0009). No-op in non-production (dev/CI keep the ephemeral fallback).
    """
    settings = get_settings()
    if settings.is_production() and settings.api.session_signing_key is None:
        raise RuntimeError(_MISSING_KEY_IN_PROD)


def _signing_key() -> bytes:
    """Return the HMAC signing key: configured secret, else a process-ephemeral key.

    In production a missing key raises (defence in depth behind the startup check
    in :func:`validate_session_signing_key`); in dev/CI it falls back to a
    process-ephemeral key with a one-time warning.
    """
    settings = get_settings()
    configured = settings.api.session_signing_key
    if configured is not None:
        return configured.get_secret_value().encode("utf-8")
    if settings.is_production():
        raise RuntimeError(_MISSING_KEY_IN_PROD)
    global _warned_ephemeral
    if not _warned_ephemeral:
        sys.stderr.write(
            "tessera.api.session: TESSERA_API_SESSION_SIGNING_KEY unset — using a "
            "process-ephemeral signing key (sessions will not survive a restart). "
            "Set it from Secret Manager in any shared/production deployment.\n"
        )
        _warned_ephemeral = True
    return _EPHEMERAL_KEY


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


@dataclass(frozen=True, slots=True)
class SessionContext:
    """The resolved session — what the rest of the server reads (never the body)."""

    auth_state: AuthState
    subject_id: str | None
    authenticated: bool
    label: str | None
    demo: bool


def issue_session_token(subject_id: str, auth_state: AuthState) -> str:
    """Sign a session token binding ``subject_id`` to ``auth_state`` with an iat stamp."""
    payload = {"sub": subject_id, "auth": auth_state.value, "iat": int(time.time())}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_session_token(token: str) -> SessionContext | None:  # noqa: PLR0911  fail-closed: each invalid shape returns None explicitly
    """Verify signature + freshness; return the session, or ``None`` if invalid.

    Any failure — bad shape, forged/edited signature, expired stamp, unknown
    auth value — yields ``None`` (treated as anonymous). The signature check is
    constant-time.
    """
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    expected = hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest()
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
    if not isinstance(issued_at, int) or time.time() - issued_at > SESSION_MAX_AGE_SECONDS:
        return None
    try:
        auth_state = AuthState(str(payload.get("auth")))
    except ValueError:
        return None
    subject_id = payload.get("sub")
    if not isinstance(subject_id, str) or not subject_id:
        return None
    return SessionContext(
        auth_state=auth_state,
        subject_id=subject_id,
        authenticated=auth_state is not AuthState.ANONYMOUS,
        label=DEMO_CUSTOMER_LABEL if subject_id == DEMO_CUSTOMER_ID else subject_id,
        demo=True,
    )


_ANONYMOUS = SessionContext(
    auth_state=AuthState.ANONYMOUS,
    subject_id=None,
    authenticated=False,
    label=None,
    demo=False,
)


def resolve_session(request: Request) -> SessionContext:
    """Resolve the request's session from its signed cookie (anonymous if none/invalid).

    This is the *single place* ADR 0008 refers to: ``auth_state`` is produced here
    from the verified cookie, and never from the request body.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return _ANONYMOUS
    return verify_session_token(token) or _ANONYMOUS


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the signed session cookie: httpOnly, SameSite=Lax, Secure under TLS."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=get_settings().api.tls_terminated,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie (logout → anonymous)."""
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_settings().api.tls_terminated,
    )
