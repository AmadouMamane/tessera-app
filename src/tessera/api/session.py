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
    "CONFIRMATION_TOKEN_MAX_AGE_SECONDS",
    "DEMO_CUSTOMER_ID",
    "DEMO_CUSTOMER_LABEL",
    "RESUME_TOKEN_HEADER",
    "RESUME_TOKEN_MAX_AGE_SECONDS",
    "SESSION_COOKIE",
    "SessionContext",
    "clear_session_cookie",
    "issue_confirmation_token",
    "issue_resume_token",
    "issue_session_token",
    "resolve_session",
    "set_session_cookie",
    "validate_session_signing_key",
    "verify_confirmation_token",
    "verify_resume_token",
    "verify_session_token",
]

#: Header the product widget presents its conversation-resume capability in.
RESUME_TOKEN_HEADER = "x-tessera-resume-token"  # noqa: S105  a header NAME, not a secret

#: Domain separator for the resume MAC. Both token families are HMAC-SHA256 under the same
#: key, so without this a session token and a resume token could in principle be made to
#: verify for one another. They are different grants and must never be interchangeable.
_RESUME_DOMAIN = "tessera.resume.v1"

#: How long a browser may resume its own conversation. Deliberately longer than the 8-hour
#: session (a customer returning next week still expects their chat) and deliberately NOT
#: unbounded: this is a bearer capability sitting in ``localStorage``, so it must age out
#: rather than grant a read forever. On expiry the widget starts a fresh conversation —
#: exactly what it already does when the transcript comes back empty.
RESUME_TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

#: Domain separator for the irreversible-action confirmation MAC. Third family under the
#: same key, and the one it would be worst to confuse: a session token replayed as a
#: confirmation would turn "this caller is logged in" into "a human approved blocking this
#: card", which are not remotely the same statement.
_CONFIRMATION_DOMAIN = "tessera.confirm.v1"

#: How long a human has to act on a confirmation prompt. Short on purpose: the token stands
#: for a click that is about to happen, not for a standing authorisation. Long enough to read
#: the card's last four digits and decide; too short to be worth stockpiling.
CONFIRMATION_TOKEN_MAX_AGE_SECONDS = 10 * 60

#: Cookie name carrying the signed session token.
SESSION_COOKIE = "tessera_session"

#: The single seeded customer identity a demo login authenticates as. It matches
#: the account-tools demo dataset (``account_balance._DEMO_ACCOUNTS``) so that
#: memory and the account tools resolve to one coherent customer.
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
    #: The RBAC role (ADR 0009) when the session came from a verified operator assertion:
    #: ``admin`` / ``superadmin`` / ``auditor`` / ``collections``. ``None`` on the customer
    #: path, which has no role.
    #:
    #: ``AuthState`` answers *"is this an operator?"* and stops there — so before this
    #: field existed, the agent could not tell an **auditor** from an **admin** and let
    #: both promote an agent to production. The role was already on the wire (the signed
    #: assertion carries it and the verifier checks it against ``OPERATOR_ROLES``); it was
    #: simply dropped into a display label and never read again. Least privilege needs it.
    role: str | None = None


def issue_session_token(subject_id: str, auth_state: AuthState) -> str:
    """Sign a session token binding ``subject_id`` to ``auth_state`` with an iat stamp."""
    payload = {"sub": subject_id, "auth": auth_state.value, "iat": int(time.time())}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def issue_resume_token(conversation_id: str) -> str:
    """Sign the capability that lets a browser re-read the conversation it just held.

    Audit 2026-07-12, **P1 F-4**. The product widget resumes the customer's own chat after
    a reload, and until now it did so by asking ``GET /observability/conversation-messages``
    for a raw ``conversation_id`` — an endpoint that answered *anyone*, for *any* id. Its
    code carried the defence in a comment: *"It is a capability the customer's browser
    already holds … so there is no cross-customer exposure"*. That was an argument about
    what the widget asks for, not about what the server grants — and the capability did not
    hold anyway, because ``GET /observability/conversations`` published the ids next to the
    ``title``, which is the conversation's opening user message. A directory defeats a
    secret url.

    So the transcript read moved behind an operator guard, and the customer keeps its own
    resume through this token: the server mints it at ``turn.start`` for the browser it is
    streaming to, and demands it back. Possession of the id is no longer enough; possession
    of a **signed** statement that this browser was told that id, is.

    This does NOT authenticate a person — the customer plane has no per-person identity
    (the session cookie is minted only at ``/session/login``, and every demo customer shares
    one :data:`DEMO_CUSTOMER_ID`). It is a bearer capability over one conversation, which is
    the honest name for what the widget always relied on. Giving customers a real identity
    is an ADR, not a night's work.

    Domain-separated (:data:`_RESUME_DOMAIN`) so a resume token can never be confused with,
    or substituted for, a session token — both are HMACs under the same key.
    """
    payload = {"cid": conversation_id, "iat": int(time.time())}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(_resume_mac(body))
    return f"{body}.{signature}"


def _resume_mac(body: str) -> bytes:
    """MAC over the domain-separated body, so the two token families cannot cross."""
    message = f"{_RESUME_DOMAIN}.{body}".encode("ascii")
    return hmac.new(_signing_key(), message, hashlib.sha256).digest()


def issue_confirmation_token(*, conversation_id: str, tool: str, card_last_four: str) -> str:
    """Mint the server's statement that THIS action was offered to a human for approval.

    **A confirmation the caller can assert is not a confirmation.** ``requires_confirmation``
    in ``guard/policy.yaml`` is the last thing standing between a model's suggestion and an
    irreversible act on a customer's card, and it was enforced by reading ``confirmed_tools``
    straight off the request body. The guard's own docstring defended that channel as separate
    from model-generated text — which it is, and which is beside the point: the model cannot
    forge it, but the **caller** can, and ADR 0024 is explicit that a value the caller chooses
    can never carry a fact about who did what. A first request could therefore block a card
    with no prompt ever displayed, and the ledger would seal ``allowed`` under a rule whose
    entire meaning is "a person said yes".

    The token binds the three things that make the approval specific — which conversation,
    which tool, which card — so it cannot be replayed onto a different action, a different
    thread, or a different card. It is minted only when the guard has actually refused the
    call and asked for confirmation, so the server issues it exactly when a prompt is shown.
    """
    payload = {
        "cid": conversation_id,
        "tool": tool,
        "l4": card_last_four,
        "iat": int(time.time()),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_b64e(_confirmation_mac(body))}"


def _confirmation_mac(body: str) -> bytes:
    """MAC over the domain-separated body, so the three token families cannot cross."""
    message = f"{_CONFIRMATION_DOMAIN}.{body}".encode("ascii")
    return hmac.new(_signing_key(), message, hashlib.sha256).digest()


def verify_confirmation_token(  # noqa: PLR0911  fail-closed: each invalid shape refuses explicitly
    token: str, *, conversation_id: str, tool: str
) -> str | None:
    """Return the confirmed ``card_last_four``, or ``None`` if this is not a valid approval.

    Fails closed on every invalid shape: malformed, forged, expired, minted for another
    conversation, or minted for another tool. Returning the bound card digits rather than a
    bare boolean lets the caller check that the act it is about to perform is the act that
    was approved — a token is permission for *one* card, not for the next one the model names.
    """
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    try:
        presented = _b64d(signature)
    except ValueError:  # binascii.Error subclasses ValueError
        return None
    if not hmac.compare_digest(_confirmation_mac(body), presented):
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
        or time.time() - issued_at > CONFIRMATION_TOKEN_MAX_AGE_SECONDS
    ):
        return None
    claimed_cid = payload.get("cid")
    claimed_tool = payload.get("tool")
    if not isinstance(claimed_cid, str) or not hmac.compare_digest(claimed_cid, conversation_id):
        return None
    if not isinstance(claimed_tool, str) or not hmac.compare_digest(claimed_tool, tool):
        return None
    last_four = payload.get("l4")
    return last_four if isinstance(last_four, str) else None


def verify_resume_token(token: str, conversation_id: str) -> bool:  # noqa: PLR0911  fail-closed: each invalid shape refuses explicitly
    """True only if ``token`` is this server's signed capability for ``conversation_id``.

    Fails closed on every invalid shape: bad form, forged/edited signature, expired stamp,
    or — the one that matters — a **valid token for a different conversation**. A caller
    cannot present the token of a conversation it legitimately holds and swap the id.
    The MAC check is constant-time.
    """
    body, _, signature = token.partition(".")
    if not body or not signature:
        return False
    try:
        presented = _b64d(signature)
    except ValueError:  # binascii.Error subclasses ValueError
        return False
    if not hmac.compare_digest(_resume_mac(body), presented):
        return False
    try:
        payload = json.loads(_b64d(body))
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    issued_at = payload.get("iat")
    if not isinstance(issued_at, int) or time.time() - issued_at > RESUME_TOKEN_MAX_AGE_SECONDS:
        return False
    claimed = payload.get("cid")
    return isinstance(claimed, str) and hmac.compare_digest(claimed, conversation_id)


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
