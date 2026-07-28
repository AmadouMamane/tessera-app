"""`audit_count` counts in the database, not in Python — byte-identical, one row not the chain.

`_read_audit_count` used to materialise every ``tessera.guard.audit`` entry (94 % of the ledger)
and take its ``len``, once per snapshot context — six times per fleet snapshot, ~1.6 s each. A
live read needs only the COUNT, so it now asks the database for a bounded ``count(*)``. These
tests pin the two properties that make that safe AND fast, through the real store-read
instrumentation the budget ratchet uses:

* parity — the bounded live count equals the OLD materialise-and-filter length, for the org view
  and for individual agents;
* bound — the live read pulls back ONE aggregate row, never the chain;

and that the two paths where the fail-open ``occurred_before`` semantics matter — an as-of read
and the flat-file source — deliberately stay on the Python materialise path.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tessera.guard import ledger_store
from tessera.observability import store_spans
from tessera.observability._asof import occurred_before
from tessera.observability.spine.adapters import ledger, set_reader
from tessera.observability.spine.adapters.current import CurrentStoresReader
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.signals import _read_audit_count
from tessera.observability.spine.snapshot import reset_snapshot_cache

if TYPE_CHECKING:
    from collections.abc import Iterator

_AUDIT = "tessera.guard.audit"


@pytest.fixture(autouse=True)
def _reset_reader() -> Iterator[None]:
    """The process reader is a cached global — reset it (and the snapshot cache) per test."""
    yield
    set_reader(None)
    reset_snapshot_cache()


class _FakeCursor:
    """A cursor over an in-memory ledger that answers both `count(*)` and `SELECT payload`."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        text = " ".join(sql.split()).lower()
        params = params or []
        matched = [r for r in self._rows if r.get("type") == params[0]]
        if "payload->>'agent_id' = %s" in text:
            matched = [r for r in matched if r.get("agent_id") == params[1]]
        if "count(*)" in text:
            self._result = [(len(matched),)]
        else:  # SELECT payload ... ORDER BY seq
            self._result = [(r,) for r in matched]

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
    """A ledger with guard-audit entries across two agents + org, plus non-audit noise."""
    rows: list[dict[str, Any]] = []
    for i in range(40):
        rows.append(
            {
                "type": _AUDIT,
                "agent_id": "support-client" if i % 2 == 0 else "recouvrement",
                "occurred_at": f"2026-07-{(i % 27) + 1:02d}T12:00:00+00:00",
            }
        )
    # org-scoped audit entries (no agent_id) and non-audit noise the count must ignore.
    rows.append({"type": _AUDIT, "occurred_at": "2026-07-10T00:00:00+00:00"})
    for _ in range(5):
        rows.append({"type": "tessera.ledger.seal", "occurred_at": "2026-07-05T00:00:00+00:00"})
    return rows


def _install_postgres(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows))
    # Pin the reader so the as-of fallback materialises through the same fake connection.
    set_reader(CurrentStoresReader())


def _old_count(scope: Scope) -> int:
    """The OLD computation: materialise the guard-audit entries, filter in Python, len()."""
    return len(ledger.events_for_scope(CurrentStoresReader().audit_entries(scope), scope))


def _new_count(scope: Scope) -> int:
    return int(asyncio.run(_read_audit_count(scope))["entry_count"])


def test_live_count_is_byte_identical_to_the_materialised_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _seed()
    _install_postgres(monkeypatch, rows)
    for agent in (None, "support-client", "recouvrement"):
        scope = Scope.from_query({"agent": agent})
        assert scope.at is None  # a live read — the bounded path
        assert _new_count(scope) == _old_count(scope), agent


def test_live_count_reads_one_row_not_the_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    _install_postgres(monkeypatch, rows)
    scope = Scope.from_query({"agent": None})
    with store_spans.recording() as reads:
        _new_count(scope)
    # The bound: the whole read is a single aggregate row, never the 41 audit entries.
    assert reads, "the count must actually hit the store"
    assert max((r.rows or 0) for r in reads) == 1


def test_asof_read_falls_back_and_matches_occurred_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _seed()
    _install_postgres(monkeypatch, rows)
    at = "2026-07-15T00:00:00+00:00"
    scope = Scope.from_query({"agent": "support-client", "at": at})
    # An as-of read is NOT bounded here — it keeps occurred_before's fail-open semantics.
    assert ledger.count_for_scope(scope) is None
    expected = sum(
        1
        for r in rows
        if r.get("type") == _AUDIT
        and r.get("agent_id") == "support-client"
        and occurred_before(r.get("occurred_at"), at)
    )
    assert _new_count(scope) == expected
    assert _new_count(scope) == _old_count(scope)


def test_file_source_stays_on_the_python_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
    # The flat-file source has no SQL count: the bridge declines so the caller materialises.
    assert ledger.count_for_scope(Scope.from_query({"agent": None})) is None
