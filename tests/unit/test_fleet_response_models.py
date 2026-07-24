"""P1.4 — the fleet domain's response models must not change one byte of what it serves.

Audit 2026-07-10, `untyped-api`: 10 `response_model` on ~174 routes. Typing the API is what
unlocks the OpenAPI→zod codegen, closes the front/back validation gap, and makes the read-plane
classification (the open P1 from the security seam) tractable at all. This is the pilot.

**The danger is not a crash — it is silence.** A `response_model` that omits a field does not
fail: FastAPI **strips the field from the response**, and the cockpit simply stops seeing it. So
the models here are derived from **31 real responses**, captured live from the reference agent
across each route's real parameter space, and this file replays every one of them through the
models and asserts the serialization is **byte-identical**.

The second danger is the one the honest-empty doctrine creates. Sixteen of the eighteen fleet
handlers answer `{"available": false}` when their compute raises, so the page degrades instead of
breaking. A naive `response_model` would reject that shape — turning "never break the page" into
"always break the page", a 500 on the exact response that exists to prevent one. Hence the
discriminated union, and hence :class:`TestTheDegradedPathSurvives`, which forces the compute to
raise and asserts the route still answers `200 {"available": false}`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tessera.api.routes.observability import fleet as fleet_routes, router as observability_router
from tessera.api.routes.observability.schemas_fleet import (
    AccessPayload,
    AccessUnavailable,
    AgentEvaluationsPayload,
    AgentEvaluationsUnavailable,
    ChromePayload,
    ChromeUnavailable,
    FleetPayload,
    FleetUnavailable,
    RbacMatrixPayload,
    RbacMatrixUnavailable,
    SandboxConfigPayload,
    SandboxConfigUnavailable,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

_FIXTURE = Path(__file__).parent / "fixtures" / "fleet_real_responses.json"

#: route -> (payload model, unavailable model). The pilot deliberately spans the difficulty
#: range rather than the easy end: `sandbox-config` is the floor (4 fields), `fleet` the
#: flagship (nesting depth 7, 16 optional paths), `agent-evaluations` carries a NESTED
#: honest-empty union, and `access` is the one whose front schema is provably broken today.
PILOT: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "sandbox-config": (SandboxConfigPayload, SandboxConfigUnavailable),
    "chrome": (ChromePayload, ChromeUnavailable),
    "rbac-matrix": (RbacMatrixPayload, RbacMatrixUnavailable),
    "fleet": (FleetPayload, FleetUnavailable),
    "access": (AccessPayload, AccessUnavailable),
    "agent-evaluations": (AgentEvaluationsPayload, AgentEvaluationsUnavailable),
}

REAL: dict[str, list[dict]] = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _cases() -> list[tuple[str, int]]:
    return [(route, i) for route in PILOT for i in range(len(REAL[route]))]


class TestTheModelServesTheSameBytes:
    """The constraint that matters: no behaviour change, and `no change` means byte-for-byte."""

    @pytest.mark.parametrize(("route", "index"), _cases())
    def test_a_real_response_round_trips_unchanged(self, route: str, index: int) -> None:
        """Replay a captured live response through the model. Nothing may move.

        `model_dump(mode="json")` is what FastAPI serialises, so comparing it to the captured
        body is comparing what the cockpit received before to what it will receive after — keys,
        order, values, nulls and all.
        """
        original = REAL[route][index]
        payload_model, _ = PILOT[route]

        served = payload_model.model_validate(original).model_dump(mode="json")

        assert json.dumps(served, ensure_ascii=False) == json.dumps(original, ensure_ascii=False)

    @pytest.mark.parametrize("route", list(PILOT))
    def test_the_model_strips_nothing(self, route: str) -> None:
        """The silent failure mode, asserted directly.

        A missing field in a `response_model` is not an error — FastAPI drops it and the cockpit
        never knows. This compares the KEY SETS, so a dropped field fails here loudly even if the
        remaining bytes happened to line up.
        """
        payload_model, _ = PILOT[route]

        for original in REAL[route]:
            served = payload_model.model_validate(original).model_dump(mode="json")
            assert set(_paths(served)) == set(
                _paths(original)
            ), f"{route}: the response model changes which fields exist"


class TestTheDegradedPathSurvives:
    """Honest-empty must still work. This is the constraint the union exists for.

    Sixteen fleet handlers answer `{"available": false}` when their compute raises. It is the
    one response guaranteed to appear when something is already wrong — so a `response_model`
    that rejected it would turn every outage into a 500 on top of the outage. The degraded path
    was NEVER observed in the 31 live samples (the computes all succeeded), so it is not proven
    by the round-trip above. It is proven here, by forcing it.
    """

    @pytest.mark.parametrize(("route", "models"), list(PILOT.items()))
    def test_the_unavailable_model_accepts_the_degraded_shape(
        self, route: str, models: tuple[type[BaseModel], type[BaseModel]]
    ) -> None:
        _, unavailable = models

        served = unavailable.model_validate({"available": False}).model_dump(mode="json")

        assert served == {"available": False}, route

    def test_a_raising_compute_still_answers_200_and_not_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end, through the real router: break the compute, keep the page.

        This is the test that would have caught a wrong union. With the payload model alone —
        the naive typing — this request answers **500**, and the operator loses the page at the
        exact moment the backend is already failing.
        """

        async def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
            msg = "compute exploded"
            raise RuntimeError(msg)

        monkeypatch.setattr(fleet_routes.fleet_mod, "compute_fleet", _boom)
        app = FastAPI()
        app.include_router(observability_router)

        response = TestClient(app, raise_server_exceptions=False).get("/observability/fleet")

        assert response.status_code == 200, (
            f"the honest-empty degrade became a {response.status_code} — "
            "the response_model broke the one path that exists so the page never breaks"
        )
        assert response.json() == {"available": False}


def test_chrome_response_keeps_the_structured_notification_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FastAPI must not silently strip the count used by the compact action centre."""

    monkeypatch.setattr(
        fleet_routes.chrome_mod,
        "compute_chrome",
        lambda _lang: {
            "badges": {
                "a_traiter": {"count": 3, "tone": "warning"},
                "a_faire": {"count": 0, "tone": "neutral"},
                "incidents": {"count": 0, "tone": "neutral"},
                "curation": {"count": 0, "tone": "neutral"},
                "signal_catalog": {"count": 0, "tone": "neutral"},
            },
            "notifications": {
                "count": 1,
                "items": [
                    {
                        "id": "queue:pending:a_traiter",
                        "label": "3 validations attendent une décision",
                        "count": 3,
                        "href": "/a-traiter",
                        "tone": "warning",
                    }
                ],
            },
        },
    )
    app = FastAPI()
    app.include_router(observability_router)

    response = TestClient(app).get("/observability/chrome")

    assert response.status_code == 200
    assert response.json()["notifications"]["items"][0]["count"] == 3


def _paths(node: object, prefix: str = "$") -> list[str]:
    """Every field path, index-agnostic — so a dropped key is visible wherever it hides."""
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.append(f"{prefix}.{key}")
            out.extend(_paths(value, f"{prefix}.{key}"))
    elif isinstance(node, list) and node:
        out.extend(_paths(node[0], f"{prefix}[]"))
    return out
