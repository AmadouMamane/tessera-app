"""Ratchet — no mutating route ships without an auth story. Exceptions frozen at zero.

Audit 2026-07-12, **P0 F-1**, the structural lesson: the 26 cockpit mutations were closed
on 2026-07-11 by hardening ONE router — and two POSTs outside that router stayed anonymous,
because nothing in the codebase said "every mutation must be behind auth" in a way a test
could enforce. Guarding routers one by one closes findings; it does not close the *class*.
This file closes the class.

The rule: every route that can change state (POST/PUT/PATCH/DELETE) on the real, fully
assembled app must either

* carry a recognised auth dependency — one that establishes **who** is asking:
  ``require_operator`` (cockpit control plane), ``require_collections_operator``
  (recouvrement business plane) or ``require_superadmin`` (the synthesis grant) — or
* appear in :data:`SELF_AUTHENTICATING` — routes whose handler resolves and refuses
  callers itself, each for a documented reason. That set is asserted with ``==``, so it
  can neither grow nor go stale silently: adding a self-authenticating mutation means
  editing this file, in review, with the reason on the record.

There is no third bucket. :data:`UNGATED_EXCEPTIONS` — mutations with no auth story at
all — is the empty set, asserted empty, and must stay empty forever. That emptiness IS
the finding's closure: F-1 existed because this set was silently ``{4 routes}``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.routing import APIRoute

from tessera.api.security import (
    require_collections_operator,
    require_operator,
    require_superadmin,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: The dependencies this repo recognises as an auth gate at the routing layer.
#:
#: ``require_bearer`` is deliberately NOT here (audit 2026-07-12, **P1 F-5**). It was, until
#: this file's own premise was turned on itself: **the bearer says WHERE a call comes from,
#: never WHO makes it — so it cannot gate a mutation.** The repo proves this in its own
#: source (``security.py``, :func:`~tessera.api.security.require_operator`): the BFF attaches
#: the service bearer on the caller's behalf, so an anonymous visitor's request reaches the
#: agent carrying a perfectly valid one. Recognising it here made the ratchet built to close
#: the "anonymous writer" class *certify* the GDPR mutations (``/memory/*``) and the runtime
#: settings (``/settings/*``) as safe, because they were mounted behind
#: ``dependencies=[Depends(require_bearer)]`` (``main.py``). The guard-rail embodied the very
#: confusion it existed to forbid.
#:
#: Removing it turned this ratchet red on exactly those routes. That red WAS F-5, and the
#: only admissible way to make it green again is the one taken here: give those routes an
#: identity guard. Not an entry in :data:`SELF_AUTHENTICATING`, and never one in
#: :data:`UNGATED_EXCEPTIONS`.
KNOWN_AUTH_GUARDS: frozenset[Callable[..., object]] = frozenset(
    {require_operator, require_collections_operator, require_superadmin}
)

#: Mutating routes whose AUTH LIVES IN THE HANDLER, each with its reason. Frozen by an
#: equality assertion below — an entry that gains a routing-layer guard must be removed,
#: and a new naked mutation cannot hide here without a reviewed edit to this file.
#:
#: * ``/chat`` — the customer widget. ANONYMOUS is a legitimate auth state there (the
#:   public demo surface, ADR 0008/0009); the handler resolves the turn's real state via
#:   ``resolve_request_context`` and the graph enforces per-state authority.
#: * ``/agents/{agent_id}/invoke`` — resolves the operator assertion in-handler and
#:   refuses non-operators with 401 (ADR 0019 §I3; its own tests prove the refusal).
#: * ``/session/login`` + ``/session/logout`` — the session bootstrap itself: login is
#:   what CREATES the credential (demanding one first is a paradox), logout only clears
#:   the caller's own signed cookie.
SELF_AUTHENTICATING: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/chat"),
        ("POST", "/agents/{agent_id}/invoke"),
        ("POST", "/session/login"),
        ("POST", "/session/logout"),
    }
)

#: Mutations with NO auth story: neither a recognised guard nor a documented
#: self-authenticating handler. This is the set F-1 lived in. It is frozen at zero —
#: never add an entry; give the route a guard instead.
UNGATED_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset()


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The real assembly — ``build_app()`` — because the finding lived at the mount site.

    A unit app that re-mounts one router cannot see a router mounted bare in
    ``main.py``; only the full assembly can.
    """
    from tessera.api.main import build_app

    return build_app()


def _flat_dependency_calls(route: APIRoute) -> set[Callable[..., object]]:
    """Every dependency callable reachable from the route, router and mount included.

    FastAPI folds router-level and mount-level ``dependencies=`` into each route's
    dependant at include time, so walking the dependant tree sees the guard wherever it
    was declared — which is exactly what "behind an auth-bearing router" means on the wire.
    """
    calls: set[Callable[..., object]] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependant = stack.pop()
        if dependant.call is not None:
            calls.add(dependant.call)
        stack.extend(dependant.dependencies)
    return calls


def _mutating_routes(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    return {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods & MUTATING_METHODS)
    }


def test_every_mutating_route_has_an_auth_story(app: FastAPI) -> None:
    """The ratchet. A mutating route is guarded, or declared self-authenticating — never neither.

    This test fails against the pre-fix tree with exactly the four F-1 routes in the
    naked set, which is the honest way to state what it protects against.
    """
    naked = {
        key
        for key, route in _mutating_routes(app).items()
        if not (_flat_dependency_calls(route) & KNOWN_AUTH_GUARDS)
    }

    undeclared = naked - SELF_AUTHENTICATING - UNGATED_EXCEPTIONS
    assert not undeclared, (
        "mutating routes with NO auth story (no recognised guard, not declared "
        f"self-authenticating): {sorted(undeclared)} — give the route a guard on its "
        "router; do not add it to any list in this file"
    )


def test_the_self_authenticating_set_is_exact(app: FastAPI) -> None:
    """Frozen both directions: nothing new hides in it, nothing stale lingers in it.

    ``==`` and not ``<=``: if a listed route gains a routing-layer guard (good), it must
    leave the list; if it disappears from the app, the entry is stale. Either way the
    author passes through review with this file in the diff.
    """
    naked = {
        key
        for key, route in _mutating_routes(app).items()
        if not (_flat_dependency_calls(route) & KNOWN_AUTH_GUARDS)
    }

    assert naked == SELF_AUTHENTICATING


def test_the_exception_list_is_frozen_at_zero() -> None:
    """The audit's own words: *la liste des exceptions gelée à zéro*.

    Structurally redundant with the two tests above — and stated on its own because THIS
    is the invariant that closes the finding's class. If this line ever needs to change,
    the change under review is "we are shipping a mutation with no auth", said out loud.
    """
    assert not UNGATED_EXCEPTIONS


def test_the_recouvrement_routes_carry_the_business_plane_guard(app: FastAPI) -> None:
    """F-1's four routes, by name — the concrete instance the class-test abstracts over.

    Belt and braces with `test_recouvrement_assistant_auth_closed.py` (which proves the
    guard's *behaviour*); this one proves the guard is present ON THE REAL ASSEMBLY, so a
    refactor that re-mounted the router bare — the original sin at `main.py:351` — fails
    here even if the router's own tests still pass.
    """
    routes = _mutating_routes(app)
    for path in (
        "/recouvrement-assistant/message",
        "/api/recouvrement-assistant/message",
        "/recouvrement-assistant/action",
        "/api/recouvrement-assistant/action",
    ):
        route = routes[("POST", path)]
        assert require_collections_operator in _flat_dependency_calls(
            route
        ), f"{path} lost require_collections_operator"
