"""The leader-computed shared read-snapshot (ADR 0046).

Pins the cache's contract: a fresh entry is served, a stale/missing/absent one is a MISS (the
caller then computes — the fallback that makes the snapshot purely additive), the reset hook clears
it (test isolation), and the leader's entry composition is best-effort (a failing compute omits
only its own entry). The file lives in the shared state dir; conftest resets it between tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.api.routes.observability.schemas_fleet import FleetUnavailable
from tessera.observability import read_snapshot as rs

if TYPE_CHECKING:
    import pytest


def test_write_then_read_within_ttl_returns_the_payload() -> None:
    rs.reset_read_snapshot()
    payload = {"badges": {}, "notifications": {"count": 0, "items": []}}
    rs.write_snapshot({"chrome:fr": payload})
    assert rs.read_snapshot("chrome:fr", rs.SNAPSHOT_TTL_S) == payload


def test_a_zero_ttl_is_always_stale() -> None:
    rs.reset_read_snapshot()
    rs.write_snapshot({"chrome:fr": {"x": 1}})
    assert rs.read_snapshot("chrome:fr", 0.0) is None


def test_a_missing_key_is_a_miss() -> None:
    rs.reset_read_snapshot()
    rs.write_snapshot({"chrome:fr": {"x": 1}})
    assert rs.read_snapshot("chrome:de", rs.SNAPSHOT_TTL_S) is None


def test_an_absent_file_is_a_miss() -> None:
    rs.reset_read_snapshot()
    assert rs.read_snapshot("chrome:fr", rs.SNAPSHOT_TTL_S) is None


def test_reset_removes_the_file() -> None:
    rs.write_snapshot({"k": {"x": 1}})
    rs.reset_read_snapshot()
    assert rs.read_snapshot("k", rs.SNAPSHOT_TTL_S) is None


def test_snapshot_keys() -> None:
    assert rs.chrome_snapshot_key("fr") == "chrome:fr"
    assert rs.fleet_snapshot_key("fr", "d7") == "fleet:fr:d7"
    assert rs.fleet_snapshot_key("fr", None) == "fleet:fr:all"


async def test_compute_entries_composes_chrome_and_fleet(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_fleet(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        return FleetUnavailable(available=False)

    monkeypatch.setattr(
        "tessera.observability.chrome._compute_chrome_uncached", lambda lang: {"lang": lang}
    )
    monkeypatch.setattr("tessera.api.routes.observability.fleet._compute_fleet", _fake_fleet)
    entries = await rs.compute_snapshot_entries()
    assert entries["chrome:fr"] == {"lang": "fr"}
    assert entries["chrome:de"] == {"lang": "de"}
    assert entries["chrome:en"] == {"lang": "en"}
    assert entries["fleet:fr:all"] == {"available": False}
    assert entries["fleet:fr:d7"] == {"available": False}


async def test_compute_entries_omits_a_failing_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(lang: str) -> dict[str, object]:
        raise RuntimeError("postgres down")

    async def _fake_fleet(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        return FleetUnavailable(available=False)

    monkeypatch.setattr("tessera.observability.chrome._compute_chrome_uncached", _boom)
    monkeypatch.setattr("tessera.api.routes.observability.fleet._compute_fleet", _fake_fleet)
    entries = await rs.compute_snapshot_entries()
    assert not any(k.startswith("chrome:") for k in entries)  # every chrome entry omitted
    assert entries["fleet:fr:all"] == {"available": False}  # fleet still published
