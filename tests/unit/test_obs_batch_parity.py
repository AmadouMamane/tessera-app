"""``/observability/batch`` panels are the SAME reads as the standalone routes — parity by wiring.

The multiplex endpoint exists only to save tunnel round-trips; it must never change a value. Two
tests pin that:

* wiring (deterministic): every batch key dispatches to the EXACT handler its individual route
  registers — so a panel is that route's payload by construction, no divergence possible;
* value (tolerant of per-call stamps): a batch panel equals the standalone route's body, ignoring
  the handful of "computed-at" timestamps a read stamps freshly on each call (e.g. firewall
  efficacy's ``observed_at``) — those reflect WHEN the read ran, not WHAT it read.

Plus: unknown keys are ignored, an empty set yields empty panels, and a handler that cannot run in
a unit sweep (no live stack/DB) 500s individually AND is omitted from ``panels`` — the value test
asserts that consistency rather than a fabricated value.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from tessera.api.routes.observability.batch import _BATCH_KEYS

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI

# Fields a read stamps with the current instant on every call — identical data, different clock
# (e.g. a live "last 7 days" window's bounds, or a "computed at" marker). Batching recomputes them
# at its own instant; the DATA is unchanged, so parity comparison ignores them.
_VOLATILE = {"observed_at", "window_start", "window_end"}


def _strip(obj: Any) -> Any:
    """Drop per-call timestamp fields recursively so two calls of the same read compare equal."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in _VOLATILE}
    if isinstance(obj, list):
        return [_strip(x) for x in obj]
    return obj


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from tessera.api.main import build_app

    return build_app()


@pytest.fixture
def no_external(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Refuse outbound sockets so handlers that dial Ollama/Langfuse take their documented degrade
    path deterministically (as in CI) rather than hanging or leaking sockets."""

    def _refused(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no external stack in a unit sweep")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    yield


def test_batch_dispatches_to_each_routes_own_handler(app: FastAPI) -> None:
    # The strong, deterministic guarantee: same handler object as the standalone route registers.
    endpoints = {getattr(r, "path", None): getattr(r, "endpoint", None) for r in app.routes}
    for key, (handler, _kwargs) in _BATCH_KEYS.items():
        assert endpoints.get(f"/observability/{key}") is handler, key


@pytest.mark.usefixtures("no_external")
def test_every_panel_equals_its_standalone_route(app: FastAPI) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    keys = sorted(_BATCH_KEYS)
    batch = client.get(f"/observability/batch?keys={','.join(keys)}")
    assert batch.status_code == 200
    panels = batch.json()["panels"]
    compared = 0
    for key in keys:
        individual = client.get(f"/observability/{key}")
        if individual.status_code != 200:
            # Cannot run here (no live stack/DB) → the batch must OMIT it too.
            assert key not in panels, f"{key}: 500 individually but present in batch"
            continue
        assert _strip(panels.get(key)) == _strip(individual.json()), key
        compared += 1
    assert compared >= 5  # guard against a vacuous pass


@pytest.mark.usefixtures("no_external")
def test_unknown_keys_are_ignored(app: FastAPI) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/observability/batch?keys=firewall-efficacy,not-a-real-key")
    assert resp.status_code == 200
    assert set(resp.json()["panels"]) <= {"firewall-efficacy"}
    assert "not-a-real-key" not in resp.json()["panels"]


def test_empty_key_set_returns_empty_panels(app: FastAPI) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/observability/batch?keys=")
    assert resp.status_code == 200
    assert resp.json()["panels"] == {}
