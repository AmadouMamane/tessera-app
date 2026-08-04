"""``/observability/fleet-batch``'s FLEET half equals its standalone route — on the POPULATED arm.

This assertion used to live in ``tests/unit/test_fleet_batch_parity.py`` and was green on every
developer's machine for weeks. The first CI runner to see it went red, and it was right: the
fleet rollup is a Postgres aggregate over ``conversation_messages``, so without a database the
route degrades — honestly — to ``FleetUnavailable``, whose whole body is ``{"available": false}``.
Comparing that to itself is the vacuous parity the unit file explicitly refuses, so the unit test
refused it, loudly, instead of passing over the hole.

Two things had hidden that for weeks:

* the unit file's ``no_external`` fixture claims to force the offline degrade path by refusing
  ``socket.socket.connect``; psycopg's pool does not dial through that attribute, so on a machine
  where ``tessera_test`` is up the "isolated" test quietly used the real database;
* ``tessera_test`` is always up on a developer's machine and never up in the hermetic gate.

So the assertion is not weakened, it is **rehoused**: here, where a database is a declared
service (``.github/workflows/integration.yml``), the populated arm is exercised for real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from fastapi import FastAPI

pytestmark = pytest.mark.integration

_SIGNALS = "governance,audit_count"

#: Per-REQUEST overlay of the snapshot envelope (``spine/snapshot.py``): whether THIS call hit the
#: cache, how long THIS call took, when the value was computed. Stripped exactly where the code
#: writes them — a signal's own ``latency_ms`` is data, and a blanket strip would stop comparing it.
_PER_CALL_META = ("cache", "latency_ms", "computed_at")


def _without_call_meta_one(envelope: Any) -> Any:
    meta = {k: v for k, v in envelope["meta"].items() if k not in _PER_CALL_META}
    return {**envelope, "meta": meta}


def _without_call_meta(fleet_snapshot: Any) -> Any:
    agents = [
        {**entry, "snapshot": _without_call_meta_one(entry["snapshot"])}
        for entry in fleet_snapshot["agents"]
    ]
    return {**fleet_snapshot, "agents": agents}


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from tessera.api.main import build_app

    return build_app()


def test_the_fleet_half_equals_its_standalone_route_populated(app: FastAPI) -> None:
    """Byte for byte, on the arm that carries data — the serialization that could have drifted."""
    client = TestClient(app, raise_server_exceptions=False)

    combined = client.get(f"/observability/fleet-batch?lang=fr&period=d7&signals={_SIGNALS}")
    assert combined.status_code == 200
    body = combined.json()

    fleet = client.get("/observability/fleet?lang=fr&period=d7")
    assert fleet.status_code == 200
    assert body["fleet"] == fleet.json()

    snapshot = client.get(f"/observability/fleet-snapshot?signals={_SIGNALS}")
    assert snapshot.status_code == 200
    assert _without_call_meta(body["fleet_snapshot"]) == _without_call_meta(snapshot.json())

    # The whole reason this file exists: assert the arm, do not hope for it. A degraded fleet
    # half here means the declared Postgres service is not actually reachable, and the comparison
    # above compared `{"available": false}` with itself — a pass that proves nothing.
    assert body["fleet"]["available"] is True, (
        "the fleet half degraded — this suite declares a Postgres service, so a degrade here is "
        "an infrastructure failure, not a tolerable environment"
    )
    assert body["fleet"]["agents"], "the fleet half came back with no agent — vacuous parity"
    assert body["fleet_snapshot"]["agents"], "the snapshot half came back empty — vacuous parity"


def test_as_of_scopes_the_fleet_half_only_populated(app: FastAPI) -> None:
    """``?at=`` bounds the rollup and never reaches the snapshot fan-out — checked with data.

    The unit file asserts the second half of this (no as-of bound reaches the snapshot), which
    needs no database. The first half — that the batch's fleet body IS the as-of route's body —
    only says something once the arm is populated.
    """
    asof = "2026-06-13T00:00:00Z"
    client = TestClient(app, raise_server_exceptions=False)
    body = client.get(
        f"/observability/fleet-batch?lang=fr&period=d7&at={asof}&signals={_SIGNALS}"
    ).json()

    assert body["fleet"] == client.get(f"/observability/fleet?lang=fr&period=d7&at={asof}").json()
    assert body["fleet"]["available"] is True, "as-of fleet half degraded — vacuous comparison"
    live = client.get(f"/observability/fleet-snapshot?signals={_SIGNALS}").json()
    assert _without_call_meta(body["fleet_snapshot"]) == _without_call_meta(live)
    assert all(e["snapshot"]["scope"]["at"] is None for e in body["fleet_snapshot"]["agents"])
