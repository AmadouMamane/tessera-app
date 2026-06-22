"""Authorization vocabulary — audience, surface, auth floor, and session state.

This is a **leaf** module (standard library only) on purpose. The agent registry
(ADR 0008) governs three first-class agent properties — ``audience``, ``surface``,
``auth`` — and routing compares them against the authorization a live session
actually carries (``AuthState``). Both the *agent* layer (registry, supervisor)
and the *guard* layer (tool allowlist) need this vocabulary, but the guard must
never import ``tessera.agent`` at module load (it would pull the LangGraph and
create an import cycle). Keeping the enums and the satisfaction ladder here lets
both sides share one source of truth without coupling.

* ``audience`` / ``surface`` are bindings on the agent (who it serves, through
  which channel).
* ``auth`` is the *minimum* identity floor a session must clear to reach the agent
  (or a sensitive tool).
* ``AuthState`` is the distinct, **server-derived** thing: the authorization a
  session has been proven to hold. It is never asserted by the client.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "Audience",
    "Auth",
    "AuthState",
    "Surface",
    "auth_satisfies",
]


class Audience(StrEnum):
    """The primary human an agent converses with."""

    CUSTOMER = "customer"
    OPERATOR = "operator"


class Surface(StrEnum):
    """The delivery channel an agent is exposed through."""

    SHARED_CUSTOMER_WIDGET = "shared-customer-widget"
    DEDICATED_UI = "dedicated-ui"
    COCKPIT_EMBEDDED = "cockpit-embedded"
    API_ONLY = "api-only"


class Auth(StrEnum):
    """The minimum identity/authorization a session must satisfy to reach a resource."""

    ANONYMOUS_OK = "anonymous-ok"
    CUSTOMER_AUTH = "customer-auth"
    OPERATOR_RBAC = "operator-rbac"


class AuthState(StrEnum):
    """The authorization a *session* actually carries.

    Derived server-side from a verified session, never from the request body, and
    compared against an :class:`Auth` floor via :func:`auth_satisfies`.
    """

    ANONYMOUS = "anonymous"
    CUSTOMER = "customer"
    OPERATOR = "operator"


# Monotone ladder: a session of rank N satisfies any floor of rank <= N.
# anonymous (0) < customer (1) < operator (2).
_AUTH_FLOOR_RANK: dict[Auth, int] = {
    Auth.ANONYMOUS_OK: 0,
    Auth.CUSTOMER_AUTH: 1,
    Auth.OPERATOR_RBAC: 2,
}
_AUTH_STATE_RANK: dict[AuthState, int] = {
    AuthState.ANONYMOUS: 0,
    AuthState.CUSTOMER: 1,
    AuthState.OPERATOR: 2,
}


def auth_satisfies(auth_state: AuthState, floor: Auth) -> bool:
    """Whether a session's ``auth_state`` meets an ``auth`` floor (auth_state ⊇ floor)."""
    return _AUTH_STATE_RANK[auth_state] >= _AUTH_FLOOR_RANK[floor]
