"""Unit tests for the operator work-queue source and the inbox aggregation.

`operator_items.load_items` is exercised with a synthetic eval snapshot + durable
state (no file/DB I/O); `inbox.compute_inbox_overview` is exercised with a
synthetic item list to assert the KPI/by-type/SLA aggregation and the payload
mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import inbox, operator_items as oi
from tessera.observability.eval_data import SessionRow

if TYPE_CHECKING:
    import pytest

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _session(
    case_id: str, category: str, *, passed: bool, lang: str = "fr", hours_ago: float = 0.5
) -> SessionRow:
    started = (NOW - timedelta(hours=hours_ago)).isoformat()
    return SessionRow(
        case_id=case_id,
        language=lang,
        category=category,
        title=f"{case_id} title",
        passed=passed,
        needs_escalation=False,
        tools=(),
        duration_ms=10.0,
        input_tokens=1,
        output_tokens=1,
        response="r",
        started_at=started,
    )


class _Snap:
    def __init__(self, sessions: list[SessionRow]) -> None:
        self.sessions = tuple(sessions)


def test_load_items_keeps_only_failures_and_maps_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _Snap(
        [
            _session("01", "pii_leak", passed=False),
            _session("02", "hallucination", passed=True),  # passing -> excluded
            _session("03", "tool_misuse", passed=False),
        ]
    )
    monkeypatch.setattr(oi, "load_eval_snapshot", lambda: snap)
    monkeypatch.setattr(oi, "_load_state", dict)
    items = oi.load_items()
    assert [i.case_id for i in items] == ["01", "03"]  # only failures
    pii = next(i for i in items if i.case_id == "01")
    assert pii.priority == "crit"  # pii_leak -> crit
    assert pii.source == "Confidentialite"
    assert pii.status == "todo"  # default when no override


def test_load_items_merges_durable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _Snap([_session("01", "pii_leak", passed=False)])
    monkeypatch.setattr(oi, "load_eval_snapshot", lambda: snap)
    monkeypatch.setattr(oi, "_load_state", lambda: {"01.fr": {"status": "done", "assignee": "Moi"}})
    item = oi.load_items()[0]
    assert item.status == "done"
    assert item.assignee == "Moi"


def test_sla_tone_reflects_remaining_time() -> None:
    crit_overdue = oi.OperatorItem(
        item_id="x",
        case_id="x",
        category="pii_leak",
        type_label="",
        title="",
        language="fr",
        source="",
        priority="crit",
        created_at=NOW - timedelta(hours=3),
        needs_escalation=False,
        status="todo",
        assignee="",
    )
    assert crit_overdue.overdue(NOW) is True
    assert crit_overdue.sla_tone(NOW) == "crit"
    fresh_low = oi.OperatorItem(
        item_id="y",
        case_id="y",
        category="overconfidence",
        type_label="",
        title="",
        language="fr",
        source="",
        priority="low",
        created_at=NOW,
        needs_escalation=False,
        status="todo",
        assignee="",
    )
    assert fresh_low.sla_tone(NOW) == "ok"
    done = oi.OperatorItem(
        item_id="z",
        case_id="z",
        category="pii_leak",
        type_label="",
        title="",
        language="fr",
        source="",
        priority="crit",
        created_at=NOW - timedelta(hours=9),
        needs_escalation=False,
        status="done",
        assignee="",
    )
    assert done.sla_tone(NOW) == "ok"  # resolved is never crit


def _item(case_id: str, priority: str, status: str, *, hours_ago: float) -> oi.OperatorItem:
    return oi.OperatorItem(
        item_id=f"{case_id}.fr",
        case_id=case_id,
        category="pii_leak",
        type_label="t",
        title=f"{case_id} t",
        language="fr",
        source="Confidentialite",
        priority=priority,
        created_at=NOW - timedelta(hours=hours_ago),
        needs_escalation=False,
        status=status,
        assignee="Moi" if status == "progress" else "",
    )


def test_inbox_aggregates_real_items(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _item("a", "crit", "todo", hours_ago=3),  # overdue (crit SLA 1h)
        _item("b", "high", "todo", hours_ago=0.1),  # within SLA
        _item("c", "mod", "progress", hours_ago=1),  # assigned to Moi
        _item("d", "crit", "done", hours_ago=5),  # resolved
    ]
    monkeypatch.setattr(inbox, "load_items", lambda: items)
    payload = inbox.compute_inbox_overview()
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpis["total"] == "3"  # 3 open
    assert kpis["resolved"] == "1"
    assert kpis["urgent"] == "1"  # one open crit
    assert kpis["overdue"] == "1"  # the crit todo 3h old
    assert kpis["assigned"] == "1"  # c assigned to Moi
    assert payload["total_items"] == 4
    row_a = next(r for r in payload["items"] if r["id"] == "a.fr")
    assert row_a["priority"] == "urgent"  # crit -> urgent
    assert row_a["sla"] == "En retard"
    row_d = next(r for r in payload["items"] if r["id"] == "d.fr")
    assert row_d["status"] == "resolved"  # done -> resolved
