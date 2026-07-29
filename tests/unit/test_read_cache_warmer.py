"""The per-worker read-cache warmer (ADR 0044 follow-up).

The heaviest cockpit reads build an in-process, head-invalidated cache on first touch; with N
workers each holding its own, a user scatters across cold workers until all N are warm. The warmer
pays that once per worker at boot, off the request path. These tests pin the three properties the
warmer must have: it is a no-op where there is no such cache (file mode), it warms BOTH persistent
caches in postgres mode (in order), and a warm-up failure never propagates — a request re-earns it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.api import main

if TYPE_CHECKING:
    import pytest


async def test_warmer_is_a_noop_in_file_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """File mode has no incremental cache (the journal is re-walked per read) — nothing to warm."""
    monkeypatch.setattr("tessera.guard.ledger_store.ledger_source", lambda: "file")
    assert await main._start_read_cache_warmer() is None


async def test_warmer_warms_both_persistent_caches_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres mode warms the whole-ledger read (ai-act/guard-audit) then the timeline rail."""
    called: list[str] = []
    monkeypatch.setattr("tessera.guard.ledger_store.ledger_source", lambda: "postgres")
    monkeypatch.setattr(
        "tessera.guard.ledger_store.load_ledger_payloads_sync",
        lambda: (called.append("ledger"), [])[1],
    )
    monkeypatch.setattr(
        "tessera.api.routes.observability.console.observability_timeline",
        lambda: (called.append("timeline"), {})[1],
    )
    task = await main._start_read_cache_warmer()
    assert task is not None
    await task
    assert called == ["ledger", "timeline"]


async def test_a_warmup_failure_never_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cold read that raises (e.g. Postgres blip) is swallowed; the other cache still warms."""
    called: list[str] = []

    def _boom() -> list[object]:
        raise RuntimeError("postgres unreachable at boot")

    monkeypatch.setattr("tessera.guard.ledger_store.ledger_source", lambda: "postgres")
    monkeypatch.setattr("tessera.guard.ledger_store.load_ledger_payloads_sync", _boom)
    monkeypatch.setattr(
        "tessera.api.routes.observability.console.observability_timeline",
        lambda: (called.append("timeline"), {})[1],
    )
    task = await main._start_read_cache_warmer()
    assert task is not None
    await task  # must not raise despite the first warm-up blowing up
    assert called == ["timeline"]
