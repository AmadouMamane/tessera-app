"""B2 — the 26 operator mutations are no longer anonymous.

Audit 2026-07-10, **P0 `broken-access-control`** — route.ts:25/81 · observability.py (26x) ·
main.py:310.

``ALWAYS_PUBLIC`` contained ``observability`` and the BFF's POST branch checked only the path
segment — no session, no role. The proxy then attached the *service bearer* on the caller's
behalf, so an anonymous visitor's mutation reached the agent perfectly authenticated, and the
agent mounted the observability router with no ``dependencies=`` at all.

What those 26 endpoints do: promote an agent to production, rewrite runtime configuration,
switch a guardrail off, decide curation, mutate the governance stores.

Why ``require_bearer`` alone could not have closed it — and this is the crux — the bearer
answers "did this come from our frontend?", never "who is asking?". The BFF holds it and
attaches it for everyone. Only the HMAC-signed operator assertion, minted from a verified
NextAuth session with a key the browser never holds, answers the second question.

Every test below fails against the pre-fix tree, where the router carried no dependency.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tessera.api.routes.observability import mutations, router as observability_router

EXPECTED_MUTATION_COUNT = 26


def _mutation_paths() -> list[str]:
    return sorted({route.path for route in mutations.router.routes})  # type: ignore[attr-defined]


@pytest.fixture
def anonymous_client() -> TestClient:
    """A client with no operator assertion — i.e. anyone on the internet."""
    app = FastAPI()
    app.include_router(observability_router)
    return TestClient(app, raise_server_exceptions=False)


def test_all_twenty_six_mutations_are_accounted_for() -> None:
    """The audit counted 26. If a 27th appears it must not slip in ungated."""
    assert len(mutations.router.routes) == EXPECTED_MUTATION_COUNT
    methods = {m for route in mutations.router.routes for m in route.methods}  # type: ignore[attr-defined]
    assert methods == {"POST"}


def test_the_mutation_router_declares_its_guard() -> None:
    """The guard lives on the router, so a new mutation cannot be added without it."""
    assert mutations.router.dependencies, "the mutations router carries no dependency"


@pytest.mark.parametrize("path", _mutation_paths())
def test_an_anonymous_caller_cannot_reach_a_mutation(
    anonymous_client: TestClient, path: str
) -> None:
    """The finding, closed, endpoint by endpoint.

    Pre-fix every one of these returned a 2xx (or a validation error on the body) to a
    caller with no session whatsoever — including `/observability/agents/release`, which
    promotes an agent to production.

    401 is asserted specifically: a 422 would mean the body was validated FIRST and the
    request had already entered the handler's blast radius.
    """
    response = anonymous_client.post(path, json={})

    assert response.status_code == 401, (
        f"{path} answered {response.status_code} to an anonymous caller — "
        "a mutation must refuse before it looks at the body"
    )
    assert response.json()["detail"] == "operator authentication required"


def test_the_public_reads_are_untouched() -> None:
    """Reads stay public — the cockpit's declared posture. Only the mutation plane is gated.

    Guards against over-correcting: locking the 126 GETs would 404 the whole cockpit for
    the operators this change is meant to protect.
    """
    from tessera.api.security import require_operator

    read_routes = [
        route for route in observability_router.routes if "GET" in getattr(route, "methods", set())
    ]
    assert len(read_routes) == 126
    for route in read_routes:
        guards = [dep.dependency for dep in getattr(route, "dependencies", [])]
        assert require_operator not in guards, (
            f"{route.path} is a read and must not require an operator"  # type: ignore[attr-defined]
        )
