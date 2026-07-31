"""``/observability/fleet-batch`` is the SAME two reads, in one round-trip — parity, at the wire.

A GOUVERNER domain page awaited the fleet rollup and then the per-agent snapshot fan-out: two
INDEPENDENT reads, two serial tunnel round-trips. ``/observability/fleet-batch`` returns both at
once. It exists only to save a round-trip; it may never change a value.

Three tests pin that, and one pins a deliberate NON-forward:

* wiring (deterministic): the endpoint calls the very handler objects ``/observability/fleet`` and
  ``/observability/fleet-snapshot`` register — so each half is that route's payload by
  construction, no divergence possible;
* value (at the wire): each half of the combined body equals the standalone route's JSON body —
  the serialization path too, not just the handler return, since the frontend consumes the wire;
* independence: the two halves are passed through untouched, so each still degrades on its own
  terms (an unavailable fleet does not empty the snapshot);
* ``?at=`` scopes the FLEET half only. The breakdown's snapshot fan-out has never carried an
  as-of bound, and a round-trip collapse is not the place to give it one — that asymmetry is
  preserved deliberately, so it is asserted rather than left to be "fixed" by accident.
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
    """Refuse outbound sockets so handlers that dial an external stack take their documented
    degrade path deterministically (as in CI) rather than hanging or leaking sockets."""

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
def test_both_halves_equal_their_standalone_route(app: FastAPI) -> None:
    """Each half of the combined body is the standalone route's body, byte for byte."""
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

    # Anti-vacuity: both halves are registry-driven and non-empty even with no live stack, so an
    # all-empty pass cannot be mistaken for parity — and the fleet half, being a response_model
    # union, is compared on its POPULATED arm, which is the serialization that could have drifted.
    assert body["fleet"]["available"] is True, "the fleet half degraded — vacuous parity"
    assert body["fleet"]["agents"], "the fleet half came back with no agent — vacuous parity"
    assert body["fleet_snapshot"]["agents"], "the snapshot half came back empty — vacuous parity"


@pytest.mark.usefixtures("no_external")
def test_the_org_half_equals_the_org_snapshot_route(app: FastAPI) -> None:
    """``?org_signals=`` is the quality page's org read — the same route, same body."""
    client = TestClient(app, raise_server_exceptions=False)

    combined = client.get("/observability/fleet-batch?lang=fr&period=d7&org_signals=slo")
    assert combined.status_code == 200
    body = combined.json()

    org = client.get("/observability/snapshot?signals=slo")
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
def test_as_of_scopes_the_fleet_half_only(app: FastAPI) -> None:
    """``?at=`` bounds the rollup; the snapshot fan-out stays live, exactly as the front asks it.

    Not an oversight: the breakdown has never sent an as-of bound to the per-agent snapshot, and
    forwarding this one would silently change the rendered columns. Asserted so the asymmetry is
    a decision on the record rather than a detail somebody "tidies up" into a behaviour change.
    """
    client = TestClient(app, raise_server_exceptions=False)
    body = client.get(
        f"/observability/fleet-batch?lang=fr&period=d7&at={_ASOF}&signals={_SIGNALS}"
    ).json()

    assert body["fleet"] == client.get(f"/observability/fleet?lang=fr&period=d7&at={_ASOF}").json()
    live = client.get(f"/observability/fleet-snapshot?signals={_SIGNALS}").json()
    assert _without_call_meta(body["fleet_snapshot"]) == _without_call_meta(live)
    # And it really is the LIVE fan-out: no as-of bound reached the snapshot half.
    assert all(e["snapshot"]["scope"]["at"] is None for e in body["fleet_snapshot"]["agents"])
