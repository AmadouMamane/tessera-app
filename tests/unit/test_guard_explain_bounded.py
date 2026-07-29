"""`guard_explain` rolls up in the database, not in Python — byte-identical, #groups not the chain.

`compute_guard_explain` materialised every `tessera.guard.audit` entry (94 % of the ledger) and
built a `Counter[(policy_rule, decision)]` in Python. The postgres path now unnests the decisions
and `GROUP BY (rule, kind)` — a few dozen rows. These tests pin the two things that make that safe:

* parity — `_assemble` (which sorts the grouped rows) reproduces `Counter.most_common` EXACTLY,
  including count-tie order (first-seen) and the top-N cut, cross-checked against a verbatim copy of
  the old Python computation;
* bound — the scan reads one row per (rule, kind) group, never the chain (store-read instrumented).

The SQL itself was verified byte-identical against the live 5142-row ledger; the flat-file source
keeps the Python Counter scan (no index), so it stays a `file`-only capability in the ratchet.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.observability import guard_explain, store_spans

if TYPE_CHECKING:
    import pytest

_AUDIT = "tessera.guard.audit"


def _reference(entries: list[dict[str, Any]]) -> tuple[int, int, int, list[tuple[str, str, int]]]:
    """A verbatim copy of the OLD Python computation — the byte-identical oracle."""
    pair: Counter[tuple[str, str]] = Counter()
    n_entries = n_decisions = n_denials = 0
    for obj in entries:
        if obj.get("type") != _AUDIT:
            continue
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            continue
        n_entries += 1
        for d in decisions:
            if not isinstance(d, dict):
                continue
            rule = str(d.get("policy_rule", "unknown"))
            kind = str(d.get("decision", "unknown"))
            pair[(rule, kind)] += 1
            n_decisions += 1
            if kind == "deny":
                n_denials += 1
    rules = [(r, k, c) for (r, k), c in pair.most_common(guard_explain._TOP_LIMIT)]
    return n_entries, n_decisions, n_denials, rules


def _groups_from(entries: list[dict[str, Any]]) -> tuple[int, list[tuple[str, str, int, int]]]:
    """Build the (rule, kind, count, first_seen) rows the SQL GROUP BY would produce.

    first_seen = seq*1_000_000 + ordinality; entries in seq order (index+1), decisions in array
    order (index+1) — the same relative ordering the DB reads, so the tiebreak matches.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    first: dict[tuple[str, str], int] = {}
    n_entries = 0
    for seq, obj in enumerate(entries, start=1):
        if obj.get("type") != _AUDIT:
            continue
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            continue
        n_entries += 1
        for i, d in enumerate(decisions, start=1):
            if not isinstance(d, dict):
                continue
            key = (str(d.get("policy_rule", "unknown")), str(d.get("decision", "unknown")))
            counts[key] += 1
            first.setdefault(key, seq * 1000000 + i)
    groups = [(r, k, counts[(r, k)], first[(r, k)]) for (r, k) in counts]
    return n_entries, groups


def _seed_with_ties_and_overflow() -> list[dict[str, Any]]:
    """Entries exercising: count ties (order by first-seen), >10 pairs (top-N cut), and the
    ignored shapes (non-audit, non-list decisions, non-dict decision, missing policy_rule)."""
    entries: list[dict[str, Any]] = [
        # Two pairs that will TIE at count 2 — 'a'/deny is seen before 'b'/deny.
        {"type": _AUDIT, "decisions": [{"policy_rule": "a", "decision": "deny"}]},
        {"type": _AUDIT, "decisions": [{"policy_rule": "b", "decision": "deny"}]},
        {"type": _AUDIT, "decisions": [{"policy_rule": "a", "decision": "deny"}]},
        {"type": _AUDIT, "decisions": [{"policy_rule": "b", "decision": "deny"}]},
        # Ignored shapes.
        {"type": "other", "decisions": [{"policy_rule": "z", "decision": "deny"}]},
        {"type": _AUDIT, "decisions": "not-a-list"},
        {"type": _AUDIT, "decisions": [123, {"decision": "allow"}]},  # non-dict + missing rule
    ]
    # 12 distinct single-count pairs to push past _TOP_LIMIT (10).
    entries += [
        {"type": _AUDIT, "decisions": [{"policy_rule": f"r{i}", "decision": "allow"}]}
        for i in range(12)
    ]
    return entries


def test_assemble_matches_counter_most_common() -> None:
    entries = _seed_with_ties_and_overflow()
    ref_ne, ref_nd, ref_nden, ref_rules = _reference(entries)
    n_entries, groups = _groups_from(entries)
    report = guard_explain._assemble(n_entries, groups)
    assert report.n_entries == ref_ne
    assert report.n_decisions == ref_nd
    assert report.n_denials == ref_nden
    assert [(r.rule, r.decision, r.count) for r in report.rules] == ref_rules
    # The tie resolves to first-seen: 'a' (seen first) ranks above 'b'.
    assert report.rules[0] == guard_explain.RuleCount("a", "deny", 2)
    assert report.rules[1] == guard_explain.RuleCount("b", "deny", 2)


class _FakeCursor:
    def __init__(self, n_entries: int, groups: list[tuple[str, str, int, int]]) -> None:
        self._n = n_entries
        self._groups = groups
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self._result = list(self._groups) if "group by" in sql.lower() else [(self._n,)]

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


class _FakeConn:
    def __init__(self, n_entries: int, groups: list[tuple[str, str, int, int]]) -> None:
        self._n = n_entries
        self._groups = groups

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._n, self._groups)


def test_scan_is_bounded_and_wires_through(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = [("r1", "deny", 5, 1_000_001), ("r2", "allow", 3, 2_000_001)]
    monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(8, groups))
    with store_spans.recording() as reads:
        report = guard_explain.compute_guard_explain()
    assert report.n_entries == 8
    assert report.n_decisions == 8  # 5 + 3
    assert report.n_denials == 5
    assert report.rules[0] == guard_explain.RuleCount("r1", "deny", 5)
    # The bound: one row per group, never the chain.
    assert reads and max((r.rows or 0) for r in reads) == len(groups)
