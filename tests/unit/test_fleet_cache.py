"""The fleet-rollup memo: async single-flight + short TTL (ADR 0044 follow-up).

`compute_fleet` is the ~0.64s read both the overview and every domain breakdown pay, and the
agent-scope toggle re-requests the SAME rollup on a fresh URL. The live read is memoised so a
burst shares one compute; an as-of read always recomputes.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.api.routes.observability import fleet
from tessera.api.routes.observability.schemas_fleet import FleetUnavailable

if TYPE_CHECKING:
    import pytest

_RESULT = FleetUnavailable(available=False)


async def test_live_second_call_within_ttl_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None, str | None]] = []

    async def fake(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        calls.append((lang, period, at))
        return _RESULT

    monkeypatch.setattr(fleet, "_compute_fleet", fake)
    fleet.reset_fleet_cache()
    first = await fleet.observability_fleet(lang="fr", period="d7")
    second = await fleet.observability_fleet(lang="fr", period="d7")
    assert first is second is _RESULT
    assert calls == [("fr", "d7", None)], "the live read computes once and serves the memo"


async def test_period_and_lang_are_keyed_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str | None]] = []

    async def fake(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        seen.append((lang, period))
        return _RESULT

    monkeypatch.setattr(fleet, "_compute_fleet", fake)
    fleet.reset_fleet_cache()
    await fleet.observability_fleet(lang="fr", period="d7")
    await fleet.observability_fleet(lang="de", period="d7")
    await fleet.observability_fleet(lang="fr", period="d30")
    await fleet.observability_fleet(lang="fr", period="d7")  # first key still cached
    assert seen == [("fr", "d7"), ("de", "d7"), ("fr", "d30")]


async def test_asof_read_always_recomputes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    async def fake(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        calls.append(at)
        return _RESULT

    monkeypatch.setattr(fleet, "_compute_fleet", fake)
    fleet.reset_fleet_cache()
    at = "2026-07-10T12:00:00+00:00"
    await fleet.observability_fleet(lang="fr", at=at)
    await fleet.observability_fleet(lang="fr", at=at)
    assert calls == [at, at], "an as-of read is never served from the live memo"


async def test_reset_forces_recompute(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def fake(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        calls.append(1)
        return _RESULT

    monkeypatch.setattr(fleet, "_compute_fleet", fake)
    fleet.reset_fleet_cache()
    await fleet.observability_fleet(lang="fr")
    fleet.reset_fleet_cache()
    await fleet.observability_fleet(lang="fr")
    assert calls == [1, 1], "reset drops the memo so the next live read recomputes"


async def test_concurrent_live_callers_share_one_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-flight: many coroutines on a cold memo yield exactly one compute."""
    calls: list[int] = []

    async def slow(lang: str, period: str | None, at: str | None) -> FleetUnavailable:
        calls.append(1)
        await asyncio.sleep(0.05)
        return _RESULT

    monkeypatch.setattr(fleet, "_compute_fleet", slow)
    fleet.reset_fleet_cache()
    await asyncio.gather(*(fleet.observability_fleet(lang="fr", period="d7") for _ in range(8)))
    assert calls == [1], f"single-flight failed: {len(calls)} computes, expected 1"
