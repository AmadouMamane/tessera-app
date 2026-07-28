"""The time-rail endpoints answer from bounded aggregates, not a 64k-row walk — byte-identical.

`data-range`, `least-privilege` and `timeline` each materialised the whole guard-audit chain (94 %
of the ledger, ~1.2 s) on every client fetch — and the time rail fires `data-range` + `timeline`
on EVERY cockpit page. These tests pin that the bounded replacements return exactly what the walk
did:

* `audit_type_min_occurred_and_count` — the DB's `min(occurred_at)` + `count(*)` equals the Python
  `_data_availability_start` min and the `len`, over the same non-blank stamps;
* `audit_target_call_counts` — the DB's `GROUP BY target` equals the Python `usage[target] += 1`;
* the timeline's audit events are memoised by ledger head — cold walks once, an unchanged head is a
  zero-walk hit, an advanced head re-walks — and the memoised list equals the inline walk exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.api.routes.observability import console
from tessera.api.routes.observability.console import (
    _audit_timeline_events,
    _compute_audit_timeline_events,
    reset_timeline_audit_cache,
)
from tessera.guard import ledger_store
from tessera.guard.ledger_store import (
    audit_target_call_counts,
    audit_type_min_occurred_and_count,
)

if TYPE_CHECKING:
    import pytest

_AUDIT = "tessera.guard.audit"


class _FakeCursor:
    """A cursor answering the time-rail aggregates over in-memory ``(seq, payload)`` rows."""

    def __init__(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        self._rows = rows
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        text = " ".join(sql.split()).lower()
        params = params or []
        if "max(seq)" in text:
            seqs = [seq for seq, _ in self._rows]
            self._result = [(max(seqs) if seqs else None,)]
            return
        typed = [p for _, p in self._rows if p.get("type") == (params[0] if params else None)]
        if "min(payload->>'occurred_at')" in text:
            stamps = [str(p.get("occurred_at", "")) for p in typed]
            stamps = [s for s in stamps if s]
            self._result = [(min(stamps) if stamps else None, len(typed))]
        elif "group by payload->>'target'" in text:
            counts: dict[str, int] = {}
            for p in typed:
                target = p.get("target")
                if isinstance(target, str):  # payload->>'target' IS NOT NULL
                    counts[target] = counts.get(target, 0) + 1
            self._result = list(counts.items())
        else:  # SELECT payload ... WHERE type (load_ledger_payloads_of_type)
            self._result = [(p,) for p in typed]

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    def __init__(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        self.rows = rows

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.rows)


def _install(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[int, dict[str, Any]]]) -> _FakeConn:
    conn = _FakeConn(rows)
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: conn)
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    return conn


def _seed() -> list[tuple[int, dict[str, Any]]]:
    """Guard-audit rows (denials, allows, a model change, blanks) + non-audit noise."""
    rows: list[tuple[int, dict[str, Any]]] = []
    seq = 0

    def add(**payload: Any) -> None:
        nonlocal seq
        seq += 1
        rows.append((seq, {"type": _AUDIT, **payload}))

    add(
        occurred_at="2026-07-10T09:00:00+00:00",
        outcome="allow",
        target="account_balance",
        model="m1",
    )
    add(occurred_at="2026-07-10T09:30:00+00:00", outcome="block", target="card_block", model="m1")
    add(occurred_at="2026-07-10T09:45:00+00:00", outcome="block", target="card_block", model="m2")
    add(occurred_at="2026-07-11T14:00:00+00:00", outcome="allow", target="user_input", model="m2")
    add(occurred_at="2026-07-11T14:05:00+00:00", outcome="allow", target="memory.write", model="m2")
    add(occurred_at="", outcome="allow", target="account_balance")  # blank stamp — excluded
    # non-audit noise the type filter must ignore
    seq += 1
    rows.append((seq, {"type": "tessera.ledger.seal", "occurred_at": "2026-07-01T00:00:00+00:00"}))
    return rows


def _entries(rows: list[tuple[int, dict[str, Any]]]) -> list[dict[str, object]]:
    return [p for _, p in rows if p.get("type") == _AUDIT]


def test_data_range_min_and_count_match_the_python_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    _install(monkeypatch, rows)
    entries = _entries(rows)
    stamps = [str(e.get("occurred_at", "")) for e in entries]
    expected_min = min(s for s in stamps if s)
    start, count = audit_type_min_occurred_and_count(_AUDIT)
    assert start == expected_min
    assert count == len(entries)  # the blank-stamp row still counts toward n


def test_least_privilege_group_by_matches_the_usage_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    _install(monkeypatch, rows)
    non_tools = {"user_input"}
    expected: dict[str, int] = {}
    for e in _entries(rows):
        target = e.get("target")
        if isinstance(target, str) and target not in non_tools and not target.startswith("memory."):
            expected[target] = expected.get(target, 0) + 1
    counts = audit_target_call_counts(_AUDIT)
    got = {t: c for t, c in counts.items() if t not in non_tools and not t.startswith("memory.")}
    assert got == expected  # account_balance:1, card_block:2 — user_input + memory.* excluded


def test_timeline_audit_events_equal_the_inline_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    monkeypatch.setattr(console, "_read_audit_entries", lambda: _entries(rows))
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(ledger_store, "ledger_head_seq", lambda: 42)
    reset_timeline_audit_cache()
    assert _audit_timeline_events(None) == _compute_audit_timeline_events(None)


def test_timeline_cache_walks_once_then_serves_the_head(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    calls = {"n": 0}

    def _spy() -> list[dict[str, object]]:
        calls["n"] += 1
        return _entries(rows)

    monkeypatch.setattr(console, "_read_audit_entries", _spy)
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    head = {"seq": 10}
    monkeypatch.setattr(ledger_store, "ledger_head_seq", lambda: head["seq"])
    reset_timeline_audit_cache()

    first = _audit_timeline_events(None)
    assert calls["n"] == 1
    again = _audit_timeline_events(None)  # unchanged head → cache hit, no re-walk
    assert calls["n"] == 1
    assert again == first
    head["seq"] = 11  # an append advances the head → re-walk
    _audit_timeline_events(None)
    assert calls["n"] == 2


def test_timeline_asof_bypasses_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _seed()
    calls = {"n": 0}

    def _spy() -> list[dict[str, object]]:
        calls["n"] += 1
        return _entries(rows)

    monkeypatch.setattr(console, "_read_audit_entries", _spy)
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(ledger_store, "ledger_head_seq", lambda: 10)
    reset_timeline_audit_cache()
    # An as-of read carries its own bound — it must never touch or prime the live cache.
    _audit_timeline_events("2026-07-10T12:00:00+00:00")
    _audit_timeline_events("2026-07-10T12:00:00+00:00")
    assert calls["n"] == 2
