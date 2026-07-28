"""Per-agent detail reads are bounded in SQL — byte-identical to the full scan, but fast.

Two agent-detail builders walked the WHOLE ledger and filtered in Python, once per page:

* ``source_state_traces`` (Connaissances) kept only ``target``-prefixed knowledge acts;
* ``_scan_journal`` (Synthèse) kept one agent's handoff / routing / guard-audit slices, of
  which only the last ``_JOURNAL_EVENT_CAP`` guard events reach a capped deque.

Both now push their predicate into SQL (``read_ledger_entries_by_target_prefix`` /
``read_agent_journal_entries``), so only the relevant rows materialise. These tests pin the
property that makes that safe: the bounded output equals the full-scan output. The reference
is the FILE source (which returns the whole read, so the caller's belt filter reproduces the
old behaviour exactly); the subject under test is the POSTGRES source (bounded in SQL).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tessera.guard import ledger_store
from tessera.guard.ledger_store import (
    read_agent_journal_entries,
    read_ledger_entries_by_target_prefix,
)
from tessera.observability.agent_synthese import _JOURNAL_EVENT_CAP, _scan_journal
from tessera.observability.knowledge import _TRACE_TARGET_PREFIX, source_state_traces

if TYPE_CHECKING:
    import pytest


class _FakeCursor:
    """A cursor over an in-memory ``(seq, payload)`` chain that models the bounded queries."""

    def __init__(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        self._rows = rows
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        text = " ".join(sql.split()).lower()
        p = list(params or [])
        if "payload->>'target' like" in text:
            prefix = str(p[0]).rstrip("%")
            self._result = [
                (pl,) for _, pl in self._rows if str(pl.get("target", "")).startswith(prefix)
            ]
        elif "'tessera.agent.handoff'" in text:
            agent = p[0]
            self._result = [
                (s, pl)
                for s, pl in self._rows
                if pl.get("type") == "tessera.agent.handoff"
                and (pl.get("to_agent") == agent or pl.get("from_agent") == agent)
            ]
        elif "'tessera.agent.routing'" in text:
            agent = p[0]
            self._result = [
                (s, pl)
                for s, pl in self._rows
                if pl.get("type") == "tessera.agent.routing" and pl.get("agent_id") == agent
            ]
        elif "'tessera.guard.audit'" in text:  # ORDER BY seq DESC LIMIT
            agent, limit = p[0], int(p[-1])
            hits = [
                (s, pl)
                for s, pl in self._rows
                if pl.get("type") == "tessera.guard.audit" and pl.get("agent_id") == agent
            ]
            self._result = sorted(hits, key=lambda r: r[0], reverse=True)[:limit]
        else:  # a plain full read
            self._result = [(pl,) for _, pl in self._rows]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None


class _FakeConn:
    def __init__(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def _postgres(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[int, dict[str, Any]]]) -> None:
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "postgres")
    monkeypatch.setattr(ledger_store, "_connect_sync", lambda: _FakeConn(rows))


def _file_full(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[int, dict[str, Any]]]) -> None:
    """The reference source: the whole read, so each builder's belt filter is the old scan."""
    monkeypatch.setattr(ledger_store, "ledger_source", lambda: "file")
    monkeypatch.setattr(
        ledger_store, "read_ledger_entries", lambda **_: [pl for _, pl in rows], raising=True
    )


def _at(day: int) -> str:
    return f"2026-07-{day:02d}T12:00:00+00:00"


def _journal_seed() -> list[tuple[int, dict[str, Any]]]:
    """Handoffs, routing and guard-audit for two agents, plus noise the scan must ignore."""
    rows: list[tuple[int, dict[str, Any]]] = []
    seq = 0

    def add(payload: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        rows.append((seq, payload))

    # 12 guard-audit for support-client (only the last _JOURNAL_EVENT_CAP feed the deque).
    for i in range(12):
        add(
            {
                "type": "tessera.guard.audit",
                "agent_id": "support-client",
                "outcome": "denied" if i % 3 == 0 else "allowed",
                "target": f"tool.{i}",
                "occurred_at": _at((i % 27) + 1),
            }
        )
    add({"type": "tessera.guard.audit", "agent_id": "recouvrement", "occurred_at": _at(4)})
    add(
        {
            "type": "tessera.agent.routing",
            "agent_id": "support-client",
            "reason": "solde -> lookup",
            "occurred_at": _at(5),
        }
    )
    add(
        {
            "type": "tessera.agent.routing",
            "agent_id": "support-client",
            "reason": "carte",
            "occurred_at": _at(6),
        }
    )
    add(
        {
            "type": "tessera.agent.routing",
            "agent_id": "recouvrement",
            "reason": "x",
            "occurred_at": _at(7),
        }
    )
    add(
        {
            "type": "tessera.agent.handoff",
            "to_agent": "support-client",
            "from_agent": "recouvrement",
            "occurred_at": _at(8),
        }
    )
    add(
        {
            "type": "tessera.agent.handoff",
            "to_agent": "recouvrement",
            "from_agent": "support-client",
            "occurred_at": _at(9),
        }
    )
    add(
        {
            "type": "tessera.agent.handoff",
            "to_agent": "duplex",
            "from_agent": "duplex",
            "occurred_at": _at(10),
        }
    )
    add({"type": "tessera.ledger.seal", "occurred_at": _at(11)})  # pure noise
    return rows


def test_scan_journal_bounded_equals_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SQL-bounded journal scan is byte-identical to the whole-window scan, per agent."""
    rows = _journal_seed()
    for agent in ("support-client", "recouvrement"):
        _file_full(monkeypatch, rows)
        reference = _scan_journal(agent, None, None)
        _postgres(monkeypatch, rows)
        actual = _scan_journal(agent, None, None)
        assert actual == reference, agent


def test_agent_journal_read_returns_only_the_three_slices(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader returns the agent's handoffs + routing + a guard tail — nothing else."""
    rows = _journal_seed()
    _postgres(monkeypatch, rows)
    got = read_agent_journal_entries(
        "support-client", since=None, until=None, guard_tail=_JOURNAL_EVENT_CAP
    )
    kinds = [e["type"] for e in got]
    # Guard-audit is capped to the tail; handoffs (party) and routing come in full.
    assert kinds.count("tessera.guard.audit") == _JOURNAL_EVENT_CAP
    assert kinds.count("tessera.agent.routing") == 2  # only support-client's
    assert kinds.count("tessera.agent.handoff") == 2  # the two support-client is a party to
    assert "tessera.ledger.seal" not in kinds  # noise excluded
    # Oldest→newest by seq (the scan depends on it for the deque tail).
    seqs = [r[0] for r in rows]
    assert seqs == sorted(seqs)


def _trace_seed() -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    seq = 0

    def add(payload: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        rows.append((seq, payload))

    add(
        {
            "target": f"{_TRACE_TARGET_PREFIX}dora",
            "actor": "amadou",
            "occurred_at": _at(2),
            "arguments": {"attached": True},
        }
    )
    add(
        {
            "target": f"{_TRACE_TARGET_PREFIX}gdpr",
            "actor": "ops",
            "occurred_at": _at(3),
            "arguments": {"active": False},
        }
    )
    add(
        {
            "target": f"{_TRACE_TARGET_PREFIX}dora",
            "actor": "amadou",
            "occurred_at": _at(5),
            "arguments": {"active": True},
        }
    )
    for _ in range(20):  # noise with other targets the fold must ignore
        add({"target": "incident.open", "occurred_at": _at(4)})
        add({"type": "tessera.guard.audit", "agent_id": "support-client", "occurred_at": _at(4)})
    return rows


def test_source_state_traces_bounded_equals_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """The knowledge-source fold is identical whether read whole (file) or prefix-bounded (pg)."""
    rows = _trace_seed()
    _file_full(monkeypatch, rows)
    reference = source_state_traces()
    _postgres(monkeypatch, rows)
    actual = source_state_traces()
    assert actual == reference
    assert set(actual) == {"dora", "gdpr"}  # the two real sources, noise excluded


def test_target_prefix_read_selects_only_the_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bounded reader returns every prefixed row and nothing else."""
    rows = _trace_seed()
    _postgres(monkeypatch, rows)
    got = read_ledger_entries_by_target_prefix(_TRACE_TARGET_PREFIX)
    assert len(got) == 3
    assert all(str(e["target"]).startswith(_TRACE_TARGET_PREFIX) for e in got)
