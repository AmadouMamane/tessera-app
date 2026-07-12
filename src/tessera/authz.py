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
* ``Actor`` is the third question, and the one the audit trail asks: not *may you*,
  but **who did it**. Same rule, same reason — derived from a verified signal, never
  from the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "SYSTEM_ROLE",
    "Actor",
    "Audience",
    "Auth",
    "AuthState",
    "Surface",
    "auth_satisfies",
]

#: The role an :class:`Actor` carries when no human ordered the act. It is a **value**, not
#: an absence: "nobody passed an actor" and "the retention scheduler did it" must never look
#: the same in the trail, and a ratchet must be able to tell them apart by reading the entry.
SYSTEM_ROLE: Final = "system"


@dataclass(frozen=True, slots=True)
class Actor:
    """WHO performed a governed act — the one field a ledger entry may never omit.

    An act recorded without its author is not evidence; it is a rumour with a timestamp. The
    GDPR asks the controller to *demonstrate* who did what (Art. 5(2) accountability, Art. 30
    records of processing), and a trail that names the data subject but not the operator
    cannot answer the only question a DPO will ever ask about an erasure: **who deleted this
    person's record?** Until 2026-07-12 Tessera could not: ``audit_memory`` had no actor field
    at all, so the most legally consequential act in the system — an irreversible deletion —
    left a subject, an outcome, and nobody to answer for it.

    There are exactly **two** ways to obtain one, and both are explicit at the call site:

    * :func:`tessera.api.security.actor_of` — from a **server-verified** session: the
      principal of the HMAC-signed operator assertion, whose key the browser never holds.
      Never from a request body. A caller who can choose the name in the ledger can frame
      someone else, and the ledger stops being a record of what happened.
    * :meth:`system` — a **named** non-human origin (the guard, the agent's own turn, the
      retention scheduler). The name is the point.

    There is deliberately no third way, and **no default anywhere**. A default on an identity
    field is the whole class of bug this type exists to close: it lets an author omit the one
    thing that makes the record worth keeping, and read green while doing it.
    """

    #: The principal: a person's identifier from a verified assertion, or ``system:<task>``.
    principal: str
    #: The authority the principal held when it acted (its operator role, or ``system``).
    role: str

    def __post_init__(self) -> None:
        """Reject the empty actor at construction — the failure must be loud, and early."""
        if not self.principal or not self.role:
            raise ValueError(
                "an actor with an empty principal or role is not an actor "
                f"(principal={self.principal!r}, role={self.role!r}); "
                "derive it from a verified session, or name the system task that acted"
            )

    @classmethod
    def system(cls, task: str) -> Actor:
        """The actor for an act no human ordered — named, never blank.

        ``task`` is what actually ran: ``guard``, ``agent-turn``, ``retention-purge``. Naming
        it is not decoration; it is what lets a reader distinguish *"the scheduler deleted
        these rows on its TTL"* from *"someone deleted them and the code forgot to say who"*.
        The two must never render the same, and a bare ``"system"`` string makes them.
        """
        if not task:
            raise ValueError("a system actor must name the task that acted")
        return cls(principal=f"system:{task}", role=SYSTEM_ROLE)

    @property
    def is_system(self) -> bool:
        """Whether no human ordered this act (see :meth:`system`)."""
        return self.role == SYSTEM_ROLE


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
