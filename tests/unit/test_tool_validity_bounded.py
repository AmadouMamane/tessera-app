"""`tool_validity.compute_tool_validity` tallies outcomes in SQL — #outcomes rows, not the chain.

``compute_tool_validity`` materialised every ``tessera.guard.audit`` entry (94 % of the chain) and
folded outcome tallies in Python. The postgres path now ``GROUP BY`` the ``outcome`` — one row per
outcome. These tests pin the assembly (grouped rows → report, ``arg_failures`` read only from the
denied group, a null-outcome group ignored), the one-row-per-outcome bound, and the WHERE the caller
hands the query (``target`` exclusion always; the as-of cutoff parsed to a datetime and the agent id
only when set).

The SQL itself was verified BYTE-IDENTICAL against the live ledger and, since the demo carries no
tool decisions, on the real Postgres engine over a synthetic ``VALUES`` CTE across every as-of/agent
scenario (outcomes, arg-failure discrimination, target exclusion, null-target kept, the Z vs +00:00
boundary, null occurred_at, malformed cutoff fail-open). The flat-file source keeps the Python fold
(no index), so it stays a ``file``-only ratchet capability.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.observability import store_spans
from tessera.observability.tool_validity import compute_tool_validity

if TYPE_CHECKING:
    import pytest


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]], sink: dict[str, Any]) -> None:
        self._rows = rows
        self._sink = sink
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self._sink["sql"] = sql
        self._sink["params"] = list(params) if params is not None else None
        self._result = list(self._rows)  # the sole query is the GROUP BY

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    def __init__(self, rows: list[tuple[Any, ...]], sink: dict[str, Any]) -> None:
        self._rows = rows
        self._sink = sink

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows, self._sink)


def _wire(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    sink: dict[str, Any] = {}
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows, sink))
    return sink


def test_report_from_grouped_rows_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        ("allowed", 4, 0),
        ("denied", 2, 1),  # 1 of the 2 denials is an argument failure
        ("error", 1, 0),
        (None, 3, 0),  # a null-outcome group is counted by neither branch
    ]
    sink = _wire(monkeypatch, rows)

    with store_spans.recording() as reads:
        report = compute_tool_validity(at="2026-07-29T12:00:00Z", agent_id="recouvrement")

    assert (report.total, report.allowed, report.denied, report.errored) == (7, 4, 2, 1)
    assert report.arg_failures == 1  # read from the denied group only
    assert report.validity_rate == 4 / 7

    # The WHERE the caller assembled: target excluded, as-of parsed to a datetime, agent last.
    assert "IS DISTINCT FROM 'user_input'" in sink["sql"]
    assert sink["params"] == [datetime.fromisoformat("2026-07-29T12:00:00Z"), "recouvrement"]

    # The bound: one row per outcome group, never the chain.
    assert reads and max((r.rows or 0) for r in reads) == len(rows)


def test_live_read_adds_no_cutoff_clause(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [("denied", 1, 1)]
    sink = _wire(monkeypatch, rows)
    report = compute_tool_validity()  # at=None, agent_id=None
    assert (report.total, report.denied, report.arg_failures) == (1, 1, 1)
    assert report.validity_rate == 0.0  # 0 allowed / 1
    assert sink["params"] == []  # no as-of, no agent → no bound params
    assert "occurred_at" not in sink["sql"] and "agent_id" not in sink["sql"]
