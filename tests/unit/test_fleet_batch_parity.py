"""``/observability/fleet-batch`` is the SAME two reads, in one round-trip — parity, at the wire.

A GOUVERNER domain page awaited the fleet rollup and then the per-agent snapshot fan-out: two
INDEPENDENT reads, two serial tunnel round-trips. ``/observability/fleet-batch`` returns both at
once. It exists only to save a round-trip; it may never change a value.

Three tests pin that, and one pins the shared clock:

* wiring (deterministic): the endpoint calls the very handler objects ``/observability/fleet`` and
  ``/observability/fleet-snapshot`` register — so each half is that route's payload by
  construction, no divergence possible;
* value (at the wire): each half of the combined body equals the standalone route's JSON body —
  the serialization path too, not just the handler return, since the frontend consumes the wire.
  The SNAPSHOT half is checked here, because it is registry-driven and therefore populated
  anywhere. The FLEET half needs a database to have a populated arm at all, so its value parity
  lives in ``tests/integration/test_fleet_batch_parity_populated.py`` (2026-08-04);
* independence: the two halves are passed through untouched, so each still degrades on its own
  terms (an unavailable fleet does not empty the snapshot);
* ``?period=``/``?at=`` reach EVERY half. Until 2026-08-26 the snapshot fan-out deliberately
  stayed live and all-history while the rollup obeyed the rail — two clocks inside the one
  « Vue par agent » card. Decided on its own merits (operator, 2026-08-26): one card, one clock;
  a caller that sends no window keeps the all-history contract unchanged.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI

# A domain lens' real signal set (the compliance / proof pages' `DOMAIN_SIGNALS`), so parity is
# exercised on the shape the cockpit actually asks for.
_SIGNALS = "governance,audit_count"
_ASOF = "2026-06-13T00:00:00Z"

#: The snapshot envelope's per-REQUEST overlay (``spine/snapshot.py``): whether THIS call hit the
#: read-through cache, how long THIS call took, and when the value was computed. They describe the
#: call, not the data — the second of two identical calls is a "hit" by construction. Stripped
#: exactly where the code writes them (``snapshot.meta``), never by key name across the whole tree:
#: a signal's own ``latency_ms`` is data, and a blanket strip would quietly stop comparing it.
_PER_CALL_META = ("cache", "latency_ms", "computed_at")


def _without_call_meta_one(envelope: Any) -> Any:
    """One snapshot envelope with its per-request meta removed."""
    meta = {k: v for k, v in envelope["meta"].items() if k not in _PER_CALL_META}
    return {**envelope, "meta": meta}


def _without_call_meta(fleet_snapshot: Any) -> Any:
    """The bulk snapshot body with each agent envelope's per-request meta removed."""
    agents = [
        {**entry, "snapshot": _without_call_meta_one(entry["snapshot"])}
        for entry in fleet_snapshot["agents"]
    ]
    return {**fleet_snapshot, "agents": agents}


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from tessera.api.main import build_app

    return build_app()


@pytest.fixture
def no_external(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Refuse plain outbound sockets, so a handler that dials an external stack degrades here
    rather than hanging or leaking a socket.

    It does **not** cut the database. Measured 2026-08-04: psycopg's pool does not dial through
    ``socket.socket.connect``, so on a developer's machine — where ``tessera_test`` is up — the
    fleet rollup silently ran its real Postgres aggregate while this docstring claimed the
    offline path was forced. That is why the value-parity of the fleet half moved to
    ``tests/integration/``: what a fixture *claims* to isolate and what it isolates were two
    different things, and the difference was invisible until a runner without a database
    disagreed with the local gate (ADR 0026).
    """

    def _refused(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no external stack in a unit sweep")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    yield


def test_fleet_batch_calls_each_routes_own_handler(app: FastAPI) -> None:
    """The strong, deterministic guarantee: the same handler objects, not a re-implementation."""
    from tessera.api.routes.observability import batch as batch_mod

    endpoints = {getattr(r, "path", None): getattr(r, "endpoint", None) for r in app.routes}
    assert endpoints["/observability/fleet"] is batch_mod.observability_fleet
    assert endpoints["/observability/fleet-snapshot"] is batch_mod.observability_fleet_snapshot


@pytest.mark.usefixtures("no_external")
def test_the_snapshot_half_equals_its_standalone_route(app: FastAPI) -> None:
    """The registry-driven half is compared at the wire, on any machine, with real content.

    The FLEET half's value parity is deliberately NOT asserted here. Its populated arm is a
    Postgres aggregate over ``conversation_messages``; with no database the route honestly
    degrades to ``FleetUnavailable``, whose entire body is ``{"available": false}`` — and
    comparing that to itself is exactly the vacuous pass this file exists to refuse. It is
    asserted where the data lives: ``tests/integration/test_fleet_batch_parity_populated.py``.

    Nothing is lost in the meantime, because the STRONG guarantee needs no data at all:
    ``test_fleet_batch_calls_each_routes_own_handler`` pins that both routes are the same
    handler object, so a divergence is not merely absent but impossible to construct.
    """
    client = TestClient(app, raise_server_exceptions=False)

    combined = client.get(f"/observability/fleet-batch?lang=fr&period=d7&signals={_SIGNALS}")
    assert combined.status_code == 200
    body = combined.json()

    # The batch forwards its `period` as the fan-out's window, so the standalone comparison
    # must ask for the same one — parity is only meaningful between two reads of one clock.
    snapshot = client.get(f"/observability/fleet-snapshot?signals={_SIGNALS}&days=d7")
    assert snapshot.status_code == 200
    assert _without_call_meta(body["fleet_snapshot"]) == _without_call_meta(snapshot.json())

    # Anti-vacuity, and it bites here: the snapshot half is registry-driven, so it is populated
    # with or without a live stack. An all-empty pass can never be mistaken for parity.
    assert body["fleet_snapshot"]["agents"], "the snapshot half came back empty — vacuous parity"


@pytest.mark.usefixtures("no_external")
def test_the_org_half_equals_the_org_snapshot_route(app: FastAPI) -> None:
    """``?org_signals=`` is the quality page's org read — the same route, same body."""
    client = TestClient(app, raise_server_exceptions=False)

    combined = client.get("/observability/fleet-batch?lang=fr&period=d7&org_signals=slo")
    assert combined.status_code == 200
    body = combined.json()

    org = client.get("/observability/snapshot?signals=slo&days=d7")
    assert org.status_code == 200
    assert _without_call_meta_one(body["snapshot"]) == _without_call_meta_one(org.json())
    assert body["snapshot"]["signals"]["slo"], "the org half came back empty — vacuous parity"
    # It is the ORG read: agent-scoped would answer a different question on the same shape.
    assert body["snapshot"]["scope"]["agent"] == "all"


@pytest.mark.usefixtures("no_external")
def test_a_half_is_computed_only_when_it_is_asked_for(app: FastAPI) -> None:
    """No caller pays for a read it will not render — an absent parameter omits its half.

    Deliberately NOT the standalone route's default: there, no ``?signals=`` means every hot-path
    signal. Here it means no fan-out at all, because the caller that omits it (the quality page's
    first read) does not yet know which signals its plan will ask for.
    """
    client = TestClient(app, raise_server_exceptions=False)

    only_fleet = client.get("/observability/fleet-batch?lang=fr").json()
    assert set(only_fleet) == {"fleet"}

    with_fanout = client.get(f"/observability/fleet-batch?lang=fr&signals={_SIGNALS}").json()
    assert set(with_fanout) == {"fleet", "fleet_snapshot"}

    with_org = client.get("/observability/fleet-batch?lang=fr&org_signals=slo").json()
    assert set(with_org) == {"fleet", "snapshot"}

    both = client.get(
        f"/observability/fleet-batch?lang=fr&signals={_SIGNALS}&org_signals=slo"
    ).json()
    assert set(both) == {"fleet", "fleet_snapshot", "snapshot"}


@pytest.mark.usefixtures("no_external")
def test_the_halves_are_independent(app: FastAPI) -> None:
    """One half's honest-empty never empties the other — the degradations stay separate."""
    client = TestClient(app, raise_server_exceptions=False)
    body = client.get(f"/observability/fleet-batch?lang=fr&signals={_SIGNALS}").json()

    assert set(body) == {"fleet", "fleet_snapshot"}
    assert isinstance(body["fleet"], dict) and "available" in body["fleet"]
    # Whatever the fleet half says, every registered agent whose compute succeeded is still there.
    assert body["fleet_snapshot"]["agents"]


@pytest.mark.usefixtures("no_external")
def test_the_window_and_anchor_reach_every_half(app: FastAPI) -> None:
    """``?period=``/``?at=`` bound the rollup AND the snapshot halves — one card, one clock.

    This test used to assert the exact opposite (the fan-out deliberately stayed live and
    all-history), so the asymmetry was a decision on the record. It has now been decided the
    other way on its own merits (operator, 2026-08-26): the per-agent rows and the fleet total
    render inside one card under one period control, and the old asymmetry showed lifetime
    values beside a windowed total. Asserted the same way, so the NEW behaviour is equally on
    the record — and each envelope names the scope it was computed under, so the claim is read
    off the payload, not inferred from the call.
    """
    client = TestClient(app, raise_server_exceptions=False)
    body = client.get(
        f"/observability/fleet-batch?lang=fr&period=d7&at={_ASOF}&signals={_SIGNALS}"
    ).json()

    assert body["fleet"] == client.get(f"/observability/fleet?lang=fr&period=d7&at={_ASOF}").json()
    windowed = client.get(f"/observability/fleet-snapshot?signals={_SIGNALS}&days=d7&at={_ASOF}")
    assert _without_call_meta(body["fleet_snapshot"]) == _without_call_meta(windowed.json())
    # The window and the anchor really reached the fan-out: every envelope says so itself.
    for entry in body["fleet_snapshot"]["agents"]:
        assert entry["snapshot"]["scope"]["at"] == _ASOF
        assert entry["snapshot"]["scope"]["days"] == 7
    assert body["fleet_snapshot"]["window"] == {"period_days": 7}
