"""The live-payloads cache reads the chain once, then only the delta.

`load_ledger_payloads_sync()` drove every SURVEILLER page's O(ledger) scan. The ledger is
strictly append-only (a BEFORE UPDATE OR DELETE trigger + a monotonic `seq`), so `max(seq)` is
a complete cache key. These tests pin the three properties that make the cache correct AND fast,
measured through the real store-read instrumentation the budget ratchet uses:

* cold — the first read materialises the whole chain (nothing to reuse);
* hit — an unchanged head reads ZERO rows and returns the identical payloads;
* delta — an advanced head reads ONLY the appended rows, and the result is still complete.

A truncation (a smaller head than cached) discards the cache rather than trusting a stale prefix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.guard.ledger_store import load_ledger_payloads_sync, reset_ledger_payloads_cache
from tessera.observability import store_spans

if TYPE_CHECKING:
    import pytest


class _FakeCursor:
    """A cursor over an in-memory append-only chain of ``(seq, payload)`` rows."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        text = " ".join(sql.split()).lower()
        if "max(seq)" in text:
            seqs = [seq for seq, _ in self._conn.rows]
            self._result = [(max(seqs) if seqs else None,)]
        elif "where seq >" in text:
            anchor = int(params[0]) if params else 0
            self._result = [(p,) for seq, p in self._conn.rows if seq > anchor]
        else:  # the full unbounded read (the no-max(seq) fallback path)
            self._result = [(p,) for _, p in self._conn.rows]

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    """A ``_connect_sync`` double whose chain can grow between calls."""

    def __init__(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        self.rows = rows

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)


def _install(monkeypatch: pytest.MonkeyPatch, conn: _FakeConn) -> None:
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: conn)
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    reset_ledger_payloads_cache()


def _rows(seqs: range) -> list[tuple[int, dict[str, Any]]]:
    return [(s, {"seq": s}) for s in seqs]


def _seqs(payloads: list[dict[str, Any]]) -> list[int]:
    return [int(p["seq"]) for p in payloads]


def test_cold_read_materialises_the_whole_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first read has nothing cached — it walks the chain, once."""
    _install(monkeypatch, _FakeConn(_rows(range(1, 6))))
    with store_spans.recording() as reads:
        payloads = load_ledger_payloads_sync()
    assert _seqs(payloads) == [1, 2, 3, 4, 5]
    assert [r.rows for r in reads] == [5]


def test_unchanged_head_is_a_zero_row_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same head ⇒ the payloads come from memory and NO payload row is re-read."""
    _install(monkeypatch, _FakeConn(_rows(range(1, 6))))
    first = load_ledger_payloads_sync()
    with store_spans.recording() as reads:
        again = load_ledger_payloads_sync()
    assert again == first
    assert [r.rows for r in reads] == [0]


def test_advanced_head_reads_only_the_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    """An append reads ONLY the new rows, and the returned chain is still complete."""
    conn = _FakeConn(_rows(range(1, 6)))
    _install(monkeypatch, conn)
    load_ledger_payloads_sync()  # warm the cache at head 5
    conn.rows.extend(_rows(range(6, 8)))  # two new entries appended
    with store_spans.recording() as reads:
        payloads = load_ledger_payloads_sync()
    assert _seqs(payloads) == [1, 2, 3, 4, 5, 6, 7]
    assert [r.rows for r in reads] == [2]  # only seq 6 and 7 were fetched


def test_a_smaller_head_discards_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """A head below the cached one (a test truncation) must not serve a stale prefix."""
    conn = _FakeConn(_rows(range(1, 6)))
    _install(monkeypatch, conn)
    load_ledger_payloads_sync()  # cache head 5
    conn.rows[:] = _rows(range(1, 3))  # chain reset to seq 1..2
    with store_spans.recording() as reads:
        payloads = load_ledger_payloads_sync()
    assert _seqs(payloads) == [1, 2]
    assert [r.rows for r in reads] == [2]  # a full re-read from anchor 0, not a stale hit


def test_as_of_read_bypasses_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """An as-of-T read never touches the live cache — it carries its own upper bound."""
    conn = _FakeConn(_rows(range(1, 6)))
    _install(monkeypatch, conn)
    with store_spans.recording() as reads:
        load_ledger_payloads_sync(at="2026-07-27T00:00:00+00:00")
    # The as-of path issues a single windowed read; it must not have primed the live cache,
    # so a subsequent live read is still a cold full walk.
    with store_spans.recording() as live:
        load_ledger_payloads_sync()
    assert [r.rows for r in live] == [5]
    assert reads  # the as-of read was recorded (it happened, uncached)
