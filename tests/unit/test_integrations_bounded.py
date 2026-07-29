"""`integrations._scan_audit` folds per-tool stats in the database — #tools rows, not the chain.

The per-tool stats (decisions / denials / 24h calls / last-seen) came from materialising every
`tessera.guard.audit` entry and folding a `_ToolStat` in Python. The postgres path now unnests the
`tool.<name>.allow` decisions and `GROUP BY` the tool name — one row per tool. These tests pin the
assembly (grouped rows → `_Scan`, empty stat for an unseen tool) and the one-row-per-group bound.

The SQL itself was verified BYTE-IDENTICAL against the real Postgres engine over synthetic edge
cases (c24 strict boundary, the `tool.allow` empty-name overlap, denials, ignored shapes) — the live
demo ledger carries no tool decisions to validate against, so the engine check used a CTE fixture.
The flat-file source keeps the Python fold (no index), so it stays a `file`-only ratchet capability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.observability import integrations, store_spans

if TYPE_CHECKING:
    import pytest


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self._result = list(self._rows)  # the sole query is the GROUP BY

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def test_scan_builds_per_tool_and_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    rows = [
        ("account_balance", 3, 1, 2, "2026-07-29T11:00:00+00:00"),
        ("card_block", 2, 0, 1, "2026-07-28T12:00:00.500000+00:00"),
    ]
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows))

    with store_spans.recording() as reads:
        scan = integrations._scan_audit(Path("ignored-in-postgres-mode"), now)

    ab = scan.stat("account_balance")
    assert (ab.decisions, ab.denials, ab.c24) == (3, 1, 2)
    assert ab.last == datetime.fromisoformat("2026-07-29T11:00:00+00:00")
    cb = scan.stat("card_block")
    assert (cb.decisions, cb.denials, cb.c24) == (2, 0, 1)
    # An unseen tool folds to an empty stat (setdefault), exactly as the Python loop did.
    assert scan.stat("loan_simulate").decisions == 0
    assert scan.stat("loan_simulate").last is None
    # The bound: one row per tool group, never the chain.
    assert reads and max((r.rows or 0) for r in reads) == len(rows)


def test_null_last_parses_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    rows = [("ticket_escalate", 1, 0, 0, None)]  # a tool whose only occ was null/invalid
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows))
    scan = integrations._scan_audit(Path("x"), now)
    assert scan.stat("ticket_escalate").last is None
