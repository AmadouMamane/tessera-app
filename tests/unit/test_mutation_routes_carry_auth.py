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
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import SecretStr
from starlette.requests import Request

from tessera.api.security import (
    require_collections_operator,
    require_operator,
    require_subject_reader,
    require_superadmin,
)
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: The service bearer, as the BFF would present it. Any value: what matters is that the
#: caller presents the *correct* one — the frontend does, for every visitor it proxies.
_SERVICE_BEARER = "the-frontend-service-token"

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

#: Every dependency this repo uses as an IDENTITY gate, on ANY plane — the mutation guards
#: above plus the read plane's ``require_subject_reader`` (F-4). The behavioural definition
#: below is asserted over all of them: the doctrine "a guard is what refuses a stranger" is
#: not a property of the write plane, it is a property of a guard. A read guard that
#: degraded to provenance would hand a transcript to the same stranger.
IDENTITY_GUARDS: frozenset[Callable[..., object]] = KNOWN_AUTH_GUARDS | {require_subject_reader}

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


# ─────────────────────────────────────────────────────────────────────────────────────
# THE DEFINITION. A guard is what refuses a stranger.
#
# A bearer says WHERE a call comes from, never WHO makes it.
#
# Everything above this line is a LIST, and a list can be wrong. F-5 is what a wrong list
# costs: `require_bearer` sat in KNOWN_AUTH_GUARDS, so the ratchet built to forbid the
# anonymous writer *certified* `DELETE /memory/{conversation_id}` — the erasure of any
# subject's memory — as guarded. Measured on `main` before this branch: an anonymous
# caller received **204 No Content**. The guard-rail was blind to its own class, because
# membership of the list was asserted by NOBODY.
#
# So the list stops being a claim and becomes a test. Below, every member of
# IDENTITY_GUARDS — the mutation plane's guards AND the read plane's — is CALLED with the
# request a stranger actually sends, and must refuse it. Adding a provenance guard back to
# either set does not "pass review": it fails here, on the spot, today and in ten years.
# ─────────────────────────────────────────────────────────────────────────────────────


def _a_stranger_behind_the_frontend(*, present_bearer: bool) -> Request:
    """The request a stranger's browser actually produces, once the BFF has proxied it.

    This is the whole subtlety, and getting it wrong would make this test a rubber stamp.
    "Anonymous" does NOT mean "carries nothing": the front's BFF attaches the **service
    bearer on the caller's behalf**, so a stranger's request reaches the agent carrying a
    perfectly valid one. A test that sent *no* bearer would let `require_bearer` answer 401
    and look like a guard — proving only that the stranger did not paste a secret they were
    never asked for.

    So the request carries the correct bearer and no identity: no operator assertion, no
    session cookie. Anything that refuses THIS is a guard. Anything that admits it is
    provenance, whatever its name.
    """
    headers: list[tuple[bytes, bytes]] = []
    if present_bearer:
        headers.append((b"authorization", f"Bearer {_SERVICE_BEARER}".encode()))
    return Request(
        {
            "type": "http",
            "method": "DELETE",
            "path": "/memory/00000000-0000-0000-0000-000000000000",
            "raw_path": b"/memory/00000000-0000-0000-0000-000000000000",
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "http_version": "1.1",
            "headers": headers,
            "client": ("203.0.113.7", 51234),
            "server": ("testserver", 80),
        }
    )


@pytest.fixture
def _service_bearer_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The PRODUCTION posture: a bearer is configured, and the caller presents the right one."""
    monkeypatch.setattr(get_settings().api, "bearer_token", SecretStr(_SERVICE_BEARER))


@pytest.fixture
def _no_bearer_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CI/dev posture — the one `make gate` runs in, where `require_bearer` is a no-op."""
    monkeypatch.setattr(get_settings().api, "bearer_token", None)


@pytest.mark.usefixtures("_service_bearer_configured")
@pytest.mark.parametrize("guard", sorted(IDENTITY_GUARDS, key=lambda g: g.__name__))
def test_every_known_guard_refuses_a_stranger_who_carries_a_valid_bearer(
    guard: Callable[..., object],
) -> None:
    """THE ratchet on the ratchet: membership of KNOWN_AUTH_GUARDS is now earned, not claimed.

    The caller presents everything the frontend legitimately attaches — a **valid** service
    bearer — and nothing that says who they are. A guard must answer 401.

    `require_bearer` fails this test, and that is precisely why the test exists: it admits
    this caller (the bearer is correct), so it is provenance, not identity, and it can never
    return to the set above. The check is behavioural, so no future edit can smuggle a
    provenance dependency back in by simply adding a name to a frozenset.
    """
    with pytest.raises(HTTPException) as raised:
        guard(_a_stranger_behind_the_frontend(present_bearer=True))

    assert raised.value.status_code == 401, (
        f"{guard.__name__} answered {raised.value.status_code} to a caller carrying a valid "
        "service bearer and NO identity — a guard must refuse a stranger with 401"
    )


@pytest.mark.usefixtures("_no_bearer_configured")
@pytest.mark.parametrize("guard", sorted(IDENTITY_GUARDS, key=lambda g: g.__name__))
def test_every_known_guard_refuses_a_stranger_in_the_ci_posture_too(
    guard: Callable[..., object],
) -> None:
    """The same demand in the posture the gate itself runs in — where a no-op is invisible.

    With no token configured, `require_bearer` returns `None` without looking at anything.
    That is the posture of every `make gate` and every CI run, so a guard that degrades to a
    no-op here would be *certified green by the very suite meant to catch it*. Asserting both
    postures is what makes the ratchet independent of how the environment happens to be set.
    """
    with pytest.raises(HTTPException) as raised:
        guard(_a_stranger_behind_the_frontend(present_bearer=False))

    assert raised.value.status_code == 401, (
        f"{guard.__name__} answered {raised.value.status_code} to an unidentified caller in "
        "the CI posture — a guard that is a no-op without configuration is not a guard"
    )


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
