"""``app.routes`` still yields the routes, so the ratchets that walk it still SEE something.

Five test files iterate ``build_app().routes`` to assert a property of every endpoint. Three of
them are security ratchets:

* ``test_subject_reads_carry_auth.py`` — every subject-scoped read is authenticated;
* ``test_mutation_routes_carry_auth.py`` — every mutation is authenticated;
* ``test_governed_acts_name_their_author.py`` — ADR 0024, every governed act names its author.

All three are of the form "for every route, assert P". **An empty iteration satisfies all of
them.** From FastAPI 0.137.2, ``include_router`` stops flattening its routes into ``app.routes``
and keeps a nested ``_IncludedRouter`` instead — measured 2026-08-04: under 0.141.1,
``build_app().routes`` returns thirteen entries, of which ten are opaque routers and only three
are real paths (FastAPI's own ``/docs``, ``/openapi.json``, ``/docs/oauth2-redirect``). Every one
of those ratchets would have gone quietly, permanently green.

`pyproject.toml` therefore caps ``fastapi<0.137``. A cap is a promise about a file nobody reads
during a routine dependency bump, so this is the witness that makes it loud: if the shape ever
changes — by a lifted cap, a transitive resolution, anything — this goes red *here*, naming the
cause, instead of three security ratchets going vacuously green somewhere else.

ADR 0026: a witness that cannot see may not report "ok". This one checks that it can see.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi import FastAPI

#: Measured on 2026-08-04 with fastapi 0.136.3: 300+ path-bearing routes. The floor is set far
#: below that — this guards against COLLAPSE (three, under the nested shape), not against the
#: ordinary churn of adding and removing endpoints.
_MINIMUM_VISIBLE_ROUTES = 50

#: Routes FastAPI registers itself. A tree that contains only these is the collapse signature.
_FRAMEWORK_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from tessera.api.main import build_app

    return build_app()


def _paths(app: FastAPI) -> list[str]:
    return [p for r in app.routes if isinstance(p := getattr(r, "path", None), str)]


class TestTheRouteWalkIsNotVacuous:
    def test_app_routes_yields_our_own_paths_not_only_the_frameworks(self, app: FastAPI) -> None:
        ours = sorted(set(_paths(app)) - _FRAMEWORK_PATHS)
        assert ours, (
            "app.routes carries no path of ours — include_router is no longer flattening. "
            "Every 'for route in app.routes: assert ...' ratchet is now vacuous. See the "
            "fastapi cap in pyproject.toml."
        )

    def test_the_count_has_not_collapsed(self, app: FastAPI) -> None:
        paths = _paths(app)
        assert len(paths) >= _MINIMUM_VISIBLE_ROUTES, (
            f"only {len(paths)} path-bearing routes are visible from app.routes "
            f"(floor {_MINIMUM_VISIBLE_ROUTES}); the walks the security ratchets depend on "
            "are seeing almost nothing"
        )

    def test_a_known_governed_route_is_reachable_by_walking(self, app: FastAPI) -> None:
        """Name one, so the count above cannot be satisfied by an unrelated family of routes."""
        assert "/chat" in _paths(app), "the chat route is not visible from app.routes"
