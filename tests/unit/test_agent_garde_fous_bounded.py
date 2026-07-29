"""`agent_garde_fous._scan_audit` folds per-rule + whole-log stats in SQL — #rules rows, not chain.

The Garde-fous panel materialised every ``tessera.guard.audit`` entry (94 % of the chain) and
folded a per-rule ``_RuleStat`` plus four whole-log totals (decisions, denials, 24h, prior-24h) in
Python. The postgres path now unnests the decisions and ``GROUP BY`` the ``policy_rule`` — one row
per rule. These tests pin the assembly (grouped rows → ``_AuditScan``: per-rule stats + the four
totals as the column sums, an empty stat for an unseen rule, null last → None), the
one-row-per-group bound, and the cutoffs the caller hands the query (``now - 1d`` for c24/den_c24,
``now - 2d`` for the cprev floor).

The SQL itself was verified BYTE-IDENTICAL against the live ledger (5142 ``injection.limes.*``
decisions, all within 24h → exercises c24) and, for the boundaries the live data does not carry
(cprev window, exact DAY/2DAY boundaries, deny-in-24h, null occ, absent/null policy_rule), on the
real Postgres engine over a synthetic ``VALUES`` CTE. The flat-file source keeps the Python fold
(no index), so it stays a ``file``-only ratchet capability.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.observability import agent_garde_fous, store_spans

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


def test_scan_builds_per_rule_and_totals_and_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 29, 22, 0, 0, tzinfo=UTC)
    # each row groups one policy_rule: rule, decisions, denials, den_c24, c24, cprev, last
    rows = [
        ("injection.limes.allow", 3904, 0, 0, 3904, 0, "2026-07-29T15:23:16.196044+00:00"),
        ("injection.limes.deny", 1238, 1238, 1238, 1238, 0, "2026-07-29T15:23:16.186936+00:00"),
    ]
    sink = _wire(monkeypatch, rows)

    with store_spans.recording() as reads:
        scan = agent_garde_fous._scan_audit(Path("ignored-in-postgres-mode"), now)

    # Whole-log totals are the column sums; denials_24h uses the den_c24 subset, not denials.
    assert (scan.total, scan.denials) == (5142, 1238)
    assert (scan.total_24h, scan.denials_24h) == (5142, 1238)

    allow = scan.per_rule["injection.limes.allow"]
    assert (allow.decisions, allow.denials, allow.c24, allow.cprev) == (3904, 0, 3904, 0)
    assert allow.last_fired == datetime.fromisoformat("2026-07-29T15:23:16.196044+00:00")
    deny = scan.per_rule["injection.limes.deny"]
    assert (deny.decisions, deny.denials, deny.c24, deny.cprev) == (1238, 1238, 1238, 0)

    # An unseen rule folds to an empty stat, exactly as the Python defaultdict path did.
    assert scan.per_rule.get("tool.card_block.allow", agent_garde_fous._RuleStat()).decisions == 0

    # The cutoffs are the caller's clock: c24/den_c24 at now-1d, the cprev floor at now-2d.
    assert sink["params"] == [
        now - timedelta(days=1),
        now - timedelta(days=1),
        now - timedelta(days=2),
        now - timedelta(days=1),
    ]

    # The bound: one row per rule group, never the chain.
    assert reads and max((r.rows or 0) for r in reads) == len(rows)


def test_null_last_parses_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 29, 22, 0, 0, tzinfo=UTC)
    rows = [("r.nullocc", 1, 1, 0, 0, 0, None)]  # a rule whose only occ was null/invalid
    _wire(monkeypatch, rows)
    scan = agent_garde_fous._scan_audit(Path("x"), now)
    assert scan.per_rule["r.nullocc"].last_fired is None
    assert (scan.total, scan.denials, scan.total_24h, scan.denials_24h) == (1, 1, 0, 0)
