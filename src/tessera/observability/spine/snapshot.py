"""Batched, cached snapshot compute — the anti-fan-out read model (ADR 0015 §Performance).

``compute_snapshot(scope)`` returns **all** hot-path signals for a scope in one backend pass
that shares the underlying reads (via :class:`SnapshotContext`), served through a
read-through cache with single-flight. The frontend fires **one** query and each card
``select`` s its slice, collapsing 24-37 per-page requests into one round-trip.

Cache discipline:
- key = ``(scope, signal set)``; TTL = the live poll cadence (~10 s) for a live read.
- an as-of-T read of a *past* instant can never change → cached indefinitely (the temporal
  super-power: scrubbing back to a visited instant is a cache hit).
- concurrent requests for one key coalesce onto a single in-flight compute (single-flight),
  so N viewers of one scope cost one upstream pass per TTL.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.metrics import (
    SPINE_CACHE_HIT_RATIO,
    SPINE_SNAPSHOT_LATENCY,
    SPINE_SNAPSHOT_UPSTREAM_READS,
)
from tessera.observability.spine.capabilities import snapshot_signal_ids
from tessera.observability.spine.context import SnapshotContext, bind_context, reset_context
from tessera.observability.spine.registry import get_registry

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = ["SnapshotCache", "compute_snapshot", "reset_snapshot_cache"]

_LIVE_TTL_S = 10.0
_Compute = Callable[[], Awaitable[dict[str, object]]]


class SnapshotCache:
    """Read-through cache with per-key single-flight and immutable-past caching."""

    def __init__(self, live_ttl: float = _LIVE_TTL_S) -> None:
        self._live_ttl = live_ttl
        self._entries: dict[str, tuple[dict[str, object], float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _fresh(self, key: str, *, immutable: bool) -> dict[str, object] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if immutable or (time.monotonic() - stored_at) < self._live_ttl:
            return value
        return None

    async def get_or_compute(
        self, key: str, *, immutable: bool, compute: _Compute
    ) -> tuple[dict[str, object], str]:
        """Serve a fresh cached value, or compute once under single-flight.

        Returns the value and the cache outcome (``"hit"`` / ``"miss"``).
        """
        cached = self._fresh(key, immutable=immutable)
        if cached is not None:
            return cached, "hit"
        async with self._lock(key):
            # Another coroutine may have filled the entry while we waited on the lock.
            cached = self._fresh(key, immutable=immutable)
            if cached is not None:
                return cached, "hit"
            value = await compute()
            self._entries[key] = (value, time.monotonic())
            return value, "miss"

    def reset(self) -> None:
        """Drop all cached entries and their single-flight locks."""
        self._entries.clear()
        self._locks.clear()


_default_cache: SnapshotCache | None = None
_hits = 0
_total = 0


def _cache() -> SnapshotCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = SnapshotCache()
    return _default_cache


def reset_snapshot_cache() -> None:
    """Clear the process snapshot cache + hit-ratio counters (tests / erasure)."""
    global _hits, _total
    if _default_cache is not None:
        _default_cache.reset()
    _hits = 0
    _total = 0


def _record_outcome(outcome: str) -> None:
    global _hits, _total
    _total += 1
    if outcome == "hit":
        _hits += 1
    SPINE_CACHE_HIT_RATIO.set(_hits / _total if _total else 0.0)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def _compute(scope: Scope, ids: tuple[str, ...]) -> dict[str, object]:
    ctx = SnapshotContext()
    token = bind_context(ctx)
    try:
        registry = get_registry()
        signals: dict[str, object] = {}
        for signal_id in ids:
            result = await registry.read(signal_id, scope)
            signals[signal_id] = result.as_dict()
    finally:
        reset_context(token)
    SPINE_SNAPSHOT_UPSTREAM_READS.observe(ctx.upstream_reads)
    return {
        "scope": {
            "at": scope.at,
            "agent": scope.agent_param,
            "language": scope.language,
            "model": scope.model,
            "environment": scope.environment,
            # The window LENGTH the envelope was computed under (None = all history) — the
            # payload names what was applied, so a reader never has to infer it from the URL.
            "days": scope.period_days,
        },
        "signals": signals,
        "meta": {
            "upstream_reads": ctx.upstream_reads,
            "n_signals": len(signals),
            "computed_at": _now_iso(),
        },
    }


async def compute_snapshot(
    scope: Scope, signal_ids: Sequence[str] | None = None
) -> dict[str, object]:
    """All hot-path signals for ``scope`` in one cached, single-flight backend pass.

    Args:
        scope: the dimension filters to read under.
        signal_ids: an optional subset of signal ids; defaults to every hot-path signal.

    Returns:
        ``{"scope", "signals": {id: {"data", "report"}}, "meta"}`` where ``meta`` carries the
        cache outcome, this request's latency, and the compute's shared-read count.
    """
    ids = tuple(signal_ids) if signal_ids is not None else snapshot_signal_ids()
    key = f"{scope.key()}::{','.join(ids)}"
    immutable = scope.at is not None
    started = time.perf_counter()
    value, outcome = await _cache().get_or_compute(
        key, immutable=immutable, compute=lambda: _compute(scope, ids)
    )
    elapsed = time.perf_counter() - started
    SPINE_SNAPSHOT_LATENCY.labels(cache=outcome).observe(elapsed)
    _record_outcome(outcome)
    # Overlay this request's cache outcome + latency without mutating the cached payload.
    envelope = dict(value)
    raw_meta = envelope.get("meta", {})
    meta: dict[str, object] = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    meta["cache"] = outcome
    meta["latency_ms"] = round(elapsed * 1000, 3)
    envelope["meta"] = meta
    return envelope
