"""The per-worker read-cache warmer (ADR 0044 follow-up).

The heaviest cockpit reads build an in-process, head-invalidated cache on first touch; with N
workers each holding its own, a user scatters across cold workers until all N are warm. The warmer
pays that once per worker at boot, off the request path. These tests pin the three properties the
warmer must have: it is a no-op where there is no such cache (file mode), it warms BOTH persistent
caches in postgres mode (in order), and a warm-up failure never propagates — a request re-earns it.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from tessera.api import main

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    import pytest


async def test_warmer_is_a_noop_in_file_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """File mode has no incremental cache (the journal is re-walked per read) — nothing to warm."""
    monkeypatch.setattr("tessera.guard.ledger_store.ledger_source", lambda: "file")
    assert await main._start_read_cache_warmer() is None


async def test_warmer_warms_all_persistent_caches_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres mode warms the whole-ledger read, the timeline rail, then the audit chain."""
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
    monkeypatch.setattr(
        "tessera.api.routes.audit._read_entries_full_cached",
        lambda: (called.append("audit_entries"), [])[1],
    )
    task = await main._start_read_cache_warmer()
    assert task is not None
    await task
    assert called == ["ledger", "timeline", "audit_entries"]


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


def _record_boot(
    monkeypatch: pytest.MonkeyPatch,
    order: list[str],
    warm_body: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Stub the warmer + singleton so the boot helper's ORDER of side effects is observable."""

    async def _fake_warmer() -> asyncio.Task[None]:
        return asyncio.create_task(warm_body())

    async def _fake_singleton() -> list[asyncio.Task[None]]:
        order.append("singleton")
        return []

    monkeypatch.setattr(main, "_start_read_cache_warmer", _fake_warmer)
    monkeypatch.setattr(main, "_start_singleton_work", _fake_singleton)


async def test_leader_finishes_warming_before_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """On the leader the warm-up completes BEFORE the contended snapshot writer is started."""
    order: list[str] = []

    async def _warm() -> None:
        order.append("warm")

    _record_boot(monkeypatch, order, _warm)
    warm_task, leader_tasks = await main._start_boot_background_work(is_leader=True)
    assert order == ["warm", "singleton"]
    assert leader_tasks == []
    assert warm_task is not None and warm_task.done()


async def test_follower_fires_warm_and_never_starts_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A follower warms fire-and-forget (not awaited) and starts no singleton work."""
    order: list[str] = []
    blocked = asyncio.Event()

    async def _warm() -> None:
        await blocked.wait()  # would hang the helper if a follower ever awaited it
        order.append("warm")

    _record_boot(monkeypatch, order, _warm)
    warm_task, leader_tasks = await main._start_boot_background_work(is_leader=False)
    assert leader_tasks == []
    assert order == []  # singleton not started; warm not awaited (still blocked)
    assert warm_task is not None and not warm_task.done()
    warm_task.cancel()
    with suppress(asyncio.CancelledError):
        await warm_task


async def test_leader_warm_overrun_does_not_block_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """A warm-up over the budget is left running (shielded); boot proceeds to singleton work."""
    order: list[str] = []
    release = asyncio.Event()

    async def _warm() -> None:
        await release.wait()
        order.append("warm")

    _record_boot(monkeypatch, order, _warm)
    monkeypatch.setattr(main, "_LEADER_WARM_BUDGET_S", 0.05)
    warm_task, leader_tasks = await main._start_boot_background_work(is_leader=True)
    assert order == ["singleton"]  # boot did not wait for the overrunning warm-up
    assert warm_task is not None and not warm_task.done()  # shielded — still warming
    release.set()
    await warm_task
    assert order == ["singleton", "warm"]  # the warm-up still completed, in the background
