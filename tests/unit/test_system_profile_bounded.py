"""`count_ledger_entries` counts in the database, not in Python — byte-identical, one row (P1).

system_profile's runtime panel shows ``audit_lines`` (the chain's length). It took it by
materialising the entire 38 MB chain just to call ``len()`` — an unbounded whole-ledger read on
every diagnostics load, and the last ``OWED`` entry with a pure-count shape. It now asks the
database for a bounded ``count(*)``. These tests pin, through the real store-read instrumentation
the budget ratchet uses:

* parity — the bounded count equals the OLD ``len(read_ledger_entries())``;
* bound — the read pulls back ONE aggregate row, never the chain;
* the file source (no index) deliberately stays on the materialise-then-``len`` path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.observability import store_spans

if TYPE_CHECKING:
    import pytest


class _FakeCursor:
    """A cursor answering ``count(*)`` and the full ``SELECT payload … ORDER BY seq`` read."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        text = " ".join(sql.split()).lower()
        if "count(*)" in text:
            self._result = [(len(self._rows),)]
        elif "max(seq)" in text:
            self._result = []  # unmodelled → forces the uncached full read (the parity path)
        else:  # SELECT payload ... ORDER BY seq
            self._result = [(r,) for r in self._rows]

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def _seed() -> list[dict[str, Any]]:
    """A chain of guard-audit entries plus non-audit noise — the count includes EVERY row."""
    rows: list[dict[str, Any]] = [
        {"type": "tessera.guard.audit", "occurred_at": f"2026-07-{(i % 27) + 1:02d}T12:00:00+00:00"}
        for i in range(40)
    ]
    rows += [{"type": "tessera.ledger.seal"} for _ in range(5)]
    return rows


def _install_postgres(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows))
    ledger_store.reset_ledger_payloads_cache()


def test_count_is_byte_identical_to_the_materialised_len(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    _install_postgres(monkeypatch, rows)
    old = len(ledger_store.read_ledger_entries())  # the OLD system_profile computation
    assert ledger_store.count_ledger_entries() == old == len(rows)


def test_count_reads_one_row_not_the_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    _install_postgres(monkeypatch, rows)
    with store_spans.recording() as reads:
        ledger_store.count_ledger_entries()
    assert reads, "the count must actually hit the store"
    assert max((r.rows or 0) for r in reads) == 1  # one aggregate row, never the 45 entries


def test_file_source_stays_on_the_python_len_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
    monkeypatch.setattr(ledger_store, "read_ledger_entries", lambda *_a, **_k: [{"x": 1}, {"x": 2}])
    assert ledger_store.count_ledger_entries() == 2  # delegates to len(read_ledger_entries())
