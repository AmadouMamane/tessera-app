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

from tessera.api.operator import MUTATION_ROLES, resolve_request_context
from tessera.authz import AuthState
from tessera.settings import Environment, get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response

__all__ = [
    "SecurityHeadersMiddleware",
    "require_bearer",
    "require_operator",
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


def require_operator(request: Request) -> None:
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
