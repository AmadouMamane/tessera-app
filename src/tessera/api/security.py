"""HTTP security primitives: security-headers middleware and route-level authz.

These complement, rather than replace, the existing :class:`AuthMiddleware`.
The header set is hand-rolled (≈ one dict) instead of pulling a dependency so
it stays auditable and deployment-aware (ADR 0020): HSTS is emitted only when
TLS is actually terminated for this deployment.

The route-level authorization dependency is defence in depth for the read
surfaces (``/audit``, ``/memory``): when a bearer token is configured these
routes require it even if the global middleware were ever bypassed.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from tessera.api.operator import (
    COLLECTIONS_MUTATION_ROLES,
    MUTATION_ROLES,
    SUBJECT_READ_ROLES,
    SUPERADMIN_ROLES,
    resolve_request_context,
)
from tessera.authz import Actor, AuthState
from tessera.settings import Environment, get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response

    from tessera.api.session import SessionContext

__all__ = [
    "SecurityHeadersMiddleware",
    "actor_of",
    "require_bearer",
    "require_collections_operator",
    "require_operator",
    "require_subject_reader",
    "require_superadmin",
    "validate_bearer_token",
]


# A conservative, framework-agnostic header set. CSP is intentionally strict:
# the API serves JSON and (in non-prod) the Swagger UI at /docs, which needs a
# small allowance handled by FastAPI's own assets; we keep a default-deny base.
_STATIC_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}

# RFC 6797: two years, include subdomains, eligible for preload.
_HSTS_VALUE = "max-age=63072000; includeSubDomains; preload"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response (ADR 0020).

    HSTS is conditional on ``settings.hsts_enabled`` so an on-prem deployment
    that terminates TLS at a separate proxy (or runs plain HTTP internally) does
    not advertise a policy it cannot honour.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Run the handler, then stamp the response with security headers."""
        response = await call_next(request)
        settings = get_settings()
        if not settings.api.security_headers_enabled:
            return response
        for key, value in _STATIC_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.hsts_enabled:
            response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)
        return response


#: The postures that must configure the service bearer, i.e. the ones that are *reachable
#: from outside*. Staging joined production on the operator's call (2026-07-12): a staging
#: agent is routinely internet-reachable, and an unset bearer there publishes exactly the
#: same audit ledger, memory (GDPR) surface and runtime settings as it would in production.
#:
#: ``is_production()`` was the wrong question. It asks *"is this the prod project?"* when what
#: the bearer guards against is *"can a stranger reach this?"* — and for staging the honest
#: answer is yes. Dev and CI are the only postures that are genuinely not exposed.
_BEARER_REQUIRED_ENVIRONMENTS: frozenset[Environment] = frozenset(
    {Environment.STAGING, Environment.PRODUCTION}
)


def _missing_bearer_message(environment: Environment) -> str:
    """The boot-refusal text — one function, so the test asserts what the operator reads."""
    return (
        f"TESSERA_API__BEARER_TOKEN is unset in a {environment.value} deployment. The bearer "
        "is not optional there: require_bearer and AuthMiddleware both no-op when it is None, "
        "which would silently publish the audit ledger, the memory (GDPR) surface and the "
        "runtime settings. Refusing to start rather than booting wide open."
    )


def validate_bearer_token() -> None:
    """Fail-closed startup check: a deployed agent must configure the service bearer.

    Audit 2026-07-10, **P0 `auth-fail-open`** — security.py:80 · middleware.py:68 · main.py:265.

    The session signing key and the operator assertion key each already refuse to boot when
    absent in production. The bearer did not: left unset, ``require_bearer`` returned early
    (security.py:80) and ``AuthMiddleware`` became a no-op — so the audit ledger, the memory
    surface (GDPR data) and the runtime settings endpoints served themselves to anyone. The
    failure mode was *silent* and pointed the wrong way: a missing secret opened the doors
    instead of closing them.

    Applies to **staging and production** (:data:`_BEARER_REQUIRED_ENVIRONMENTS`). Dev/CI stay
    reachable without secret material — that is the documented posture, and the tests and the
    local loop depend on it. That pressure is precisely what re-loosens such checks later, so
    the exemption is drawn as narrowly as it can be: not-exposed, rather than not-production.
    """
    settings = get_settings()
    if settings.api.bearer_token is None and settings.environment in _BEARER_REQUIRED_ENVIRONMENTS:
        raise RuntimeError(_missing_bearer_message(settings.environment))


def require_bearer(request: Request) -> None:
    """FastAPI dependency: enforce the bearer token at the route level.

    Defence in depth for the read surfaces. A no-op when no token is configured
    (the documented CI posture), so health and local development stay reachable
    without secret material — mirroring :class:`AuthMiddleware`.

    In production this can no longer be reached with no token: :func:`validate_bearer_token`
    refuses to boot. The early return below is therefore a dev/CI affordance, not a
    production hole.
    """
    token = get_settings().api.bearer_token
    if token is None:
        return
    expected = token.get_secret_value()
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = header[len("bearer ") :].strip()
    if not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def actor_of(session: SessionContext) -> Actor:
    """The one sanctioned way to turn a verified session into a ledger actor.

    A single function, so there is a single place to be right — and a single place a reviewer
    has to read to know that no governed act in this system can be attributed to a name the
    caller chose. The value comes from ``verify_operator_assertion``: the ``principal`` claim of
    an HMAC-SHA256 assertion whose key lives server-side (``api/operator.py``). The browser
    never holds it, so the name in the trail is the one thing in the request a caller cannot
    pick for themselves.

    Everything else on the request is a *worse* answer, and each was tried somewhere in this
    codebase before it was taken out:

    * the **body** — F-1's ``requested_by``, a caller-chosen string that went straight into the
      ledger, so a visitor could pin a governed action on a colleague;
    * the **bearer** — F-5's ``require_bearer``, which names the frontend *service* the BFF
      attaches for every visitor, and so names nobody;
    * a **literal** — ``actor="operator"``, ``"Julie Dubois"``: plausible, constant, false.

    Raises:
        RuntimeError: if the session is not a verified operator. Defence in depth, and it
            should be unreachable: an identity guard runs first and refuses with 401/403. If it
            ever *is* reached, an unattributable act is in flight, and the honest outcome is a
            500 the operator investigates — never a governed write with an invented author.
    """
    if session.auth_state is not AuthState.OPERATOR or not session.subject_id or not session.role:
        raise RuntimeError(
            "actor_of() was called on a session that is not a verified operator "
            f"(auth_state={session.auth_state}, role={session.role!r}) — the route's identity "
            "guard should have refused this caller. Refusing to attribute a governed act to a "
            "principal the server has not verified."
        )
    return Actor(principal=session.subject_id, role=session.role)


def require_operator(request: Request) -> SessionContext:
    """FastAPI dependency: this route mutates state, so a real operator must be behind it.

    Audit 2026-07-10, **P0 `broken-access-control`** — 26 operator mutation endpoints were
    reachable anonymously: promote an agent to production, rewrite runtime configuration,
    switch a guardrail off, mutate the governance stores.

    ``require_bearer`` alone CANNOT close that hole, and it is important to say why. The
    bearer authenticates the *frontend service*, and the BFF attaches it on the caller's
    behalf — so an anonymous visitor's request arrives at the agent carrying a perfectly
    valid bearer. The bearer answers "did this come from our frontend?", never "who is
    asking?". Only the signed operator assertion answers the second question: the BFF mints
    it from a verified NextAuth session, HMAC-signed with a key the browser never holds, and
    the agent verifies it here.

    Fails CLOSED: no assertion, an expired one, or a forged one → 401. ``resolve_request_context``
    deliberately *falls through* to the customer path for an unverified assertion (never an
    escalation, correct for a chat turn); a mutation must not accept that fallthrough, so the
    auth state is checked explicitly rather than inferred.

    **Being an operator is not enough — the role must carry write authority** (operator
    decision, 2026-07-12; :data:`~tessera.api.operator.MUTATION_ROLES`). ``AuthState.OPERATOR``
    is one bit: it says *an* operator is asking, never *which*. An ``auditor`` satisfies it, and
    ADR 0009 has said since day one that the auditor reads and does not write — so gating on the
    bit alone would have let the audit role promote an agent to production, rewrite runtime
    config and switch a guardrail off. The two refusals are deliberately different codes:

    * **401** — we do not know who you are (no valid assertion). *Authenticate.*
    * **403** — we know exactly who you are, and you may not do this. *Nothing to retry.*

    Collapsing them into one status would tell an auditor to go and log in again, which they
    already have.

    **Returns the verified session**, like :func:`require_collections_operator` already did, so
    a handler that must NAME the actor can depend on this same callable and read the principal
    the server verified (FastAPI caches the call per request — the guard still runs once). That
    is the whole seam: the guard decides *may you*, and hands back the *who* — so the two can
    never disagree, and a handler cannot obtain a name by any route that bypasses the check.
    """
    session, _surface = resolve_request_context(request)
    if session.auth_state is not AuthState.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="operator authentication required",
        )
    if session.role not in MUTATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this role is read-only on the cockpit control plane",
        )
    return session


def require_collections_operator(request: Request) -> SessionContext:
    """FastAPI dependency: recouvrement's business-plane writes need a verified operator.

    Audit 2026-07-12, **P0 F-1** — ``POST /recouvrement-assistant/{message,action}`` were
    mounted with no dependency at all (`main.py:351`), while their BFF proxied anonymous
    visitors through with the service bearer attached. Same class as the 26 cockpit
    mutations closed on 2026-07-11; these two POSTs sat outside the hardened router. The
    bearer answers "did this come from our frontend?", never "who is asking?" — only the
    signed operator assertion answers the second question (see :func:`require_operator`,
    which documents the full argument; it applies here unchanged).

    Differs from :func:`require_operator` in exactly one way: the role set is the business
    plane's (:data:`~tessera.api.operator.COLLECTIONS_MUTATION_ROLES`), so ``collections`` —
    the role these routes exist FOR — is admitted, and the ``auditor`` is still refused
    (reads and does not write, on every plane). Same two refusals, same meanings:

    * **401** — no verified assertion. We do not know who is asking. *Authenticate.*
    * **403** — a verified operator whose role has no write authority here. *Nothing to retry.*

    Returns the verified :class:`~tessera.api.session.SessionContext`, so a route that
    needs the identity — the action route stamps ``requested_by`` into the ledger — can
    depend on this same callable and read the *verified* principal (FastAPI caches the
    call per-request; the guard runs once). Attribution derives from the assertion the
    browser cannot forge, never from a body field.
    """
    session, _surface = resolve_request_context(request)
    if session.auth_state is not AuthState.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="operator authentication required",
        )
    if session.role not in COLLECTIONS_MUTATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this role is read-only on the recouvrement business plane",
        )
    return session


def require_subject_reader(request: Request) -> SessionContext:
    """FastAPI dependency: this route returns SUBJECT-SCOPED data, so prove who is asking.

    Audit 2026-07-12, **P1 F-4** — ``GET /observability/conversation-messages?conversation_id=…``
    returned the complete transcript of *any* conversation to *anyone*. The observability
    router was mounted with no route-level auth (``main.py``, under a comment reading
    "public surface"), and the front's BFF proxy listed ``observability`` in ``ALWAYS_PUBLIC``
    — so an anonymous visitor of the public demo reached it through the front, with the
    service bearer attached on their behalf.

    The uuid4 conversation id was the de-facto capability, and it did not hold: the same
    router published ``/observability/conversations``, whose rows carry the id **and** the
    ``title`` — which ``memory/transcript.py`` defines as *"the conversation's opening user
    message"*. List, then read. The directory defeated the capability.

    Distinct from the mutation guards on purpose. The cockpit plane narrows to writers
    (:data:`~tessera.api.operator.MUTATION_ROLES`); this one admits **every operator role**
    (:data:`~tessera.api.operator.SUBJECT_READ_ROLES`) — the ``auditor`` because reading is
    its trade, ``collections`` because these endpoints ARE its console. The bit that matters
    here is the one the surface never checked at all: *is a verified operator asking?*

    * **401** — no verified assertion. Anonymous, or a customer. *Authenticate.*
    * **403** — a verified operator whose role may not read here (unreachable today by
      construction, since the set equals ``OPERATOR_ROLES``; kept explicit so that
      narrowing the set is a one-line policy edit and not a rewrite of this guard).

    Returns the verified session so a handler can scope its read to the caller when that
    becomes possible. It is NOT possible today: the customer plane has no per-person
    identity (the session cookie is minted only at ``/session/login``, and every demo
    customer shares one ``DEMO_CUSTOMER_ID``), which is why the customer's own transcript
    resume goes through a signed capability instead — see
    :func:`~tessera.api.session.issue_resume_token`.
    """
    session, _surface = resolve_request_context(request)
    if session.auth_state is not AuthState.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="operator authentication required",
        )
    if session.role not in SUBJECT_READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this role may not read subject-scoped data",
        )
    return session


def require_superadmin(request: Request) -> SessionContext:
    """FastAPI dependency: only the superadmin may grant "an admin may see the synthesis".

    Audit 2026-07-12, **P1 F-5** — ``PUT /settings/synthesis-admin`` sat behind
    ``require_bearer`` alone, and the front's BFF said the quiet part out loud: *"The
    enforcement lives here (the front holds the identity); the agent persists the flag
    without its own role check."* A rule enforced only in the browser's own BFF is not
    enforced: the bearer authenticates the frontend *service*, so any caller the BFF proxies
    — and, with the bearer in hand, any caller at all — could flip the grant.

    Why not :func:`require_operator`? Because ``MUTATION_ROLES`` admits ``admin``, and the
    whole point of this flag is that an **admin must not grant it to itself**. The operator
    assertion is not path-bound (it carries principal/role/surface/iat, no audience), so an
    admin holding one minted for any cockpit mutation could otherwise replay it here.
    """
    session, _surface = resolve_request_context(request)
    if session.auth_state is not AuthState.OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="operator authentication required",
        )
    if session.role not in SUPERADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the superadmin may grant synthesis access",
        )
    return session
