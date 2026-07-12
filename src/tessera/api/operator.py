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
from tessera.observability.logging import get_logger
from tessera.settings import get_settings

if TYPE_CHECKING:
    from starlette.requests import Request

_LOG = get_logger("tessera.api.operator")

__all__ = [
    "MUTATION_ROLES",
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
#: ``collections`` is the business-plane role for recouvrement's dedicated console
#: (ADR 0010 Phase C / 0013), distinct from the platform roles (admin/auditor/
#: superadmin). All map to ``AuthState.OPERATOR`` on the agent — the role string is
#: carried for the audit label, the auth floor it satisfies is operator-rbac.
OPERATOR_ROLES: frozenset[str] = frozenset({"admin", "auditor", "superadmin", "collections"})

#: The roles that may MUTATE state from the cockpit control plane — promote an agent to
#: production, rewrite runtime configuration, switch a guardrail off, mutate the governance
#: stores. Strictly narrower than :data:`OPERATOR_ROLES`, and that gap is the point:
#:
#: * ``auditor`` reads and does not write. ADR 0009 already said so — *"auditor (audit +
#:   budget + eval detail, **not settings**)"* — but only the front ever enforced it, and
#:   only on which pages it rendered. The agent gated on ``AuthState.OPERATOR``, which an
#:   auditor satisfies, so an auditor could reach every one of the 26 mutations. An audit
#:   role that can change what it audits is not an audit role.
#: * ``collections`` is the *business*-plane role (recouvrement's dedicated console, ADR
#:   0010 Phase C). It never had cockpit authority — ``hasCockpitAccess`` in the front says
#:   so — but its assertion verifies as OPERATOR all the same, so the agent was laxer than
#:   its own edge. It is not a platform operator and does not administer the platform.
#:
#: Mirrors ``canMutateCockpit`` in ``webapp/frontend/lib/auth/roles.ts``. The front's copy is
#: the friendly refusal; THIS one is the authority (the browser never holds the signing key).
MUTATION_ROLES: frozenset[str] = frozenset({"admin", "superadmin"})

#: Assertion lifetime. Short — it is minted per turn from a live session, not stored.
OPERATOR_ASSERTION_MAX_AGE_SECONDS = 5 * 60

#: The operator surfaces an assertion may carry: the cockpit console (Phase B) and
#: recouvrement's dedicated business console (Phase C). The agent honours the
#: surface *carried by the verified assertion* — never a single hard-coded value,
#: and never the customer widget (an assertion can never claim it).
_OPERATOR_SURFACES: frozenset[Surface] = frozenset({Surface.COCKPIT_EMBEDDED, Surface.DEDICATED_UI})
_OPERATOR_SURFACE_VALUES: frozenset[str] = frozenset(s.value for s in _OPERATOR_SURFACES)


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
    if settings.api.operator_assertion_signing_key is None:
        if settings.is_production():
            raise RuntimeError(_MISSING_KEY_IN_PROD)
        # Dev/CI: the operator path is simply inert (safe), but that fails SILENTLY —
        # the recouvrement console then mis-attributes to support-client. Surface it
        # ONCE at boot so it is visible without waiting for a mis-routed turn.
        _LOG.warning(
            "operator_assertion_key_absent",
            effect="operator surfaces inert — recouvrement console falls back to support-client",
            remedy=(
                "set the SAME secret in TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY (agent "
                ".env.local) and TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY (front .env.local); "
                "`make dev-secrets` generates a matched pair"
            ),
        )


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


def issue_operator_assertion(
    principal: str, role: str, surface: Surface = Surface.COCKPIT_EMBEDDED
) -> str:
    """Sign an operator assertion binding ``principal``/``role`` to an operator surface.

    This is the Python reference for the token the Next BFF mints (the BFF mirrors
    the exact wire format). Used by the agent's tests; in production the BFF is the
    real minter. ``surface`` must be an operator surface (cockpit-embedded for the
    Phase B console, dedicated-ui for the Phase C business console). Raises if no
    key is available (cannot sign without one) or the surface is not an operator one.
    """
    key = _operator_key()
    if key is None:
        raise RuntimeError("no operator assertion signing key configured")
    if surface not in _OPERATOR_SURFACES:
        raise ValueError(f"not an operator surface: {surface!r}")
    payload = {
        "principal": principal,
        "role": role,
        "surface": surface.value,
        "iat": int(time.time()),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64e(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_operator_assertion(token: str) -> tuple[SessionContext, Surface] | None:  # noqa: PLR0911  fail-closed: each invalid shape returns None explicitly
    """Verify a signed operator assertion; return ``(session, surface)`` else ``None``.

    The returned surface is the one *carried by the verified assertion* (cockpit-
    embedded or dedicated-ui) — never assumed. Any failure — no key configured, bad
    shape, forged/edited signature, expired stamp, a non-operator surface, or a
    non-operator role — yields ``None`` (the turn is not operator). The signature
    check is constant-time.
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
    # The assertion may only ever carry an operator surface and an operator role —
    # a valid signature over any other value is still refused (defence in depth).
    surface_value = payload.get("surface")
    if not isinstance(surface_value, str) or surface_value not in _OPERATOR_SURFACE_VALUES:
        return None
    role = payload.get("role")
    if not isinstance(role, str) or role not in OPERATOR_ROLES:
        return None
    principal = payload.get("principal")
    if not isinstance(principal, str) or not principal:
        return None
    session = SessionContext(
        auth_state=AuthState.OPERATOR,
        subject_id=principal,
        authenticated=True,
        label=f"Opérateur · {principal} ({role})",
        demo=True,
        # Carried, not just displayed. AuthState says "an operator"; the role says *which*,
        # and least privilege is decided on the second question (see MUTATION_ROLES).
        role=role,
    )
    return session, Surface(surface_value)


def resolve_request_context(request: Request) -> tuple[SessionContext, Surface]:
    """Resolve the turn's ``(session, surface)`` from trusted, server-verified signals.

    Operator path (ADR 0010 Phase B/C): a valid signed operator assertion header →
    ``(OPERATOR, <surface carried by the assertion>)`` — cockpit-embedded for the
    operator console, dedicated-ui for recouvrement's business console. Otherwise
    the existing customer path (ADR 0008/0009) is untouched: the signed cookie
    resolves to ``CUSTOMER``/``ANONYMOUS`` on the ``shared-customer-widget``. The
    operator branch is strictly additive — a forged assertion falls through to the
    cookie path (never an error, never an escalation).
    """
    raw = request.headers.get(OPERATOR_ASSERTION_HEADER)
    if raw:
        verified = verify_operator_assertion(raw)
        if verified is not None:
            return verified
        # An assertion was forwarded but did NOT verify. This fails silently — the
        # turn drops to the customer widget, so an operator surface (e.g. the
        # recouvrement console) is mis-routed to support-client with no error. The
        # overwhelmingly common cause in dev is a missing/mismatched signing key.
        # Warn loudly so it is never diagnosed as a routing bug. (A genuinely forged
        # token from a visitor also lands here — the safe outcome — but that is rare
        # enough that warning on every unverified assertion is the right tradeoff.)
        key_absent = get_settings().api.operator_assertion_signing_key is None
        _LOG.warning(
            "operator_assertion_unverified",
            reason="agent_signing_key_unset" if key_absent else "bad_signature_expired_or_forged",
            fallback="customer-widget (turn routed to the default support agent)",
            remedy=(
                "set the SAME secret in TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY (agent "
                ".env.local, double underscore) and TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY "
                "(front .env.local, single underscore)"
            ),
        )
    return resolve_session(request), Surface.SHARED_CUSTOMER_WIDGET
