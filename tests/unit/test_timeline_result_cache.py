"""The live-timeline result memo: single-flight + short TTL (ADR 0044 follow-up).

The audit half of the time rail is memoised by ledger head, but the score walk recomputed on
every fetch. The whole LIVE result is now memoised so a burst of /timeline fetches — navigation,
poll, several operators — shares ONE compute; an as-of read (``at`` set) always recomputes.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from tessera.api.routes.observability import console

if TYPE_CHECKING:
    import pytest

_RESULT: dict[str, object] = {"n_events": 0, "events": []}


def test_live_second_call_within_ttl_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []
    monkeypatch.setattr(console, "_compute_timeline", lambda at: (calls.append(at), _RESULT)[1])
    console.reset_timeline_audit_cache()
    first = console.observability_timeline(None)
    second = console.observability_timeline(None)
    assert first is second is _RESULT
    assert calls == [None], "the live read must compute once and serve the memo"


def test_asof_read_always_recomputes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []
    monkeypatch.setattr(console, "_compute_timeline", lambda at: (calls.append(at), _RESULT)[1])
    console.reset_timeline_audit_cache()
    at = "2026-07-10T12:00:00+00:00"
    console.observability_timeline(at)
    console.observability_timeline(at)
    assert calls == [at, at], "an as-of read is never served from the live memo"


def test_reset_forces_recompute(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []
    monkeypatch.setattr(console, "_compute_timeline", lambda at: (calls.append(at), _RESULT)[1])
    console.reset_timeline_audit_cache()
    console.observability_timeline(None)
    console.reset_timeline_audit_cache()
    console.observability_timeline(None)
    assert calls == [None, None], "reset must drop the memo so the next live read recomputes"


def test_concurrent_live_callers_share_one_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-flight: eight threads on a cold memo yield exactly one score walk."""
    calls: list[str | None] = []

    def slow(at: str | None) -> dict[str, object]:
        calls.append(at)
        time.sleep(0.15)
        return _RESULT

    monkeypatch.setattr(console, "_compute_timeline", slow)
    console.reset_timeline_audit_cache()

    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        console.observability_timeline(None)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == [None], f"single-flight failed: {len(calls)} computes, expected 1"
