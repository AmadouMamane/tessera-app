"""Unit tests for the operator work-queue source and the inbox aggregation.

`operator_items.load_items` is exercised with a synthetic eval snapshot + durable
state (no file/DB I/O); `inbox.compute_inbox_overview` is exercised with a
synthetic item list to assert the KPI/by-type/SLA aggregation and the payload
mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import agent_a_faire, inbox, operator_items as oi
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
    def __init__(self, sessions: list[SessionRow], agent_id: str = "support-client") -> None:
        self.sessions = tuple(sessions)
        self.agent_id = agent_id


def test_load_items_keeps_only_failures_and_maps_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _Snap(
        [
            _session("01", "pii_leak", passed=False),
            _session("02", "hallucination", passed=True),  # passing -> excluded
            _session("03", "tool_misuse", passed=False),
        ]
    )
    # One-agent fleet; the snapshot loader is called with that agent id.
    monkeypatch.setattr(oi, "_agent_targets", lambda _agent_id=None: ["support-client"])
    monkeypatch.setattr(oi, "load_eval_snapshot", lambda _aid: snap)
    monkeypatch.setattr(oi, "_load_state", dict)
    items = oi.load_items()
    assert [i.case_id for i in items] == ["01", "03"]  # only failures
    pii = next(i for i in items if i.case_id == "01")
    assert pii.agent_id == "support-client"  # real per-agent attribution
    assert pii.item_id == "support-client.01.fr"  # id namespaced by agent
    assert pii.priority == "crit"  # pii_leak -> crit
    assert pii.source == "Confidentialite"
    assert pii.status == "todo"  # default when no override


def test_load_items_ventilates_by_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    snaps = {
        "support-client": _Snap([_session("01", "pii_leak", passed=False)], "support-client"),
        "recouvrement": _Snap([_session("07", "tool_misuse", passed=False)], "recouvrement"),
    }
    monkeypatch.setattr(
        oi,
        "_agent_targets",
        lambda agent_id=None: ([agent_id] if agent_id else ["support-client", "recouvrement"]),
    )
    monkeypatch.setattr(oi, "load_eval_snapshot", lambda aid: snaps[aid])
    monkeypatch.setattr(oi, "_load_state", dict)
    # The whole-fleet queue carries both agents' failures, each attributed.
    everyone = oi.load_items()
    assert {i.agent_id for i in everyone} == {"support-client", "recouvrement"}
    # Filtering to one agent returns only that agent's items — the ventilation.
    only_reco = oi.load_items("recouvrement")
    assert [i.agent_id for i in only_reco] == ["recouvrement"]
    assert only_reco[0].case_id == "07"


def test_load_items_includes_business_event_operator_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_eval_run(_aid: str) -> None:
        raise FileNotFoundError("no eval run")

    validation = {
        "event_name": oi.business_events.BusinessEventName.VALIDATION_REQUESTED.value,
        "agent_id": "recouvrement",
        "conversation_id": "conv-lot2",
        "turn_id": "turn-validation",
        "case_id": "RC-2048",
        "capability_id": "propose_schedule",
        "artifact_id": "artifact-schedule",
        "artifact_type": "schedule_proposal_v2",
        "timestamp": NOW.isoformat(),
        "payload": {"action_name": "prepare_schedule_proposal"},
    }
    blocked = {
        "event_name": oi.business_events.BusinessEventName.ACTION_BLOCKED.value,
        "agent_id": "recouvrement",
        "conversation_id": "conv-lot2",
        "turn_id": "turn-blocked",
        "case_id": "RC-2048",
        "capability_id": "check_contact_rule",
        "timestamp": (NOW - timedelta(minutes=10)).isoformat(),
        "payload": {"action_name": "prepare_outbound_call"},
    }
    rows_by_event = {
        validation["event_name"]: [validation, dict(validation)],
        blocked["event_name"]: [blocked],
    }

    def _business_rows(
        *, agent_id: str | None = None, event_name: str | None = None, **_kwargs: object
    ) -> list[dict[str, object]]:
        assert agent_id == "recouvrement"
        return rows_by_event.get(event_name or "", [])

    monkeypatch.setattr(oi, "load_eval_snapshot", _no_eval_run)
    monkeypatch.setattr(oi.business_events, "business_event_rows", _business_rows)
    monkeypatch.setattr(
        oi,
        "_load_state",
        lambda: {
            "recouvrement.action.blocked.conv-lot2.turn-blocked.RC-2048": {
                "status": "progress",
                "assignee": "Amadou",
            }
        },
    )

    items = oi.load_items("recouvrement")

    assert len(items) == 2
    assert {item.category for item in items} == {"validation_requested", "action_blocked"}
    assert all(item.source == "Métier" for item in items)
    assert all(item.source_kind == "business_event" for item in items)
    assert items[0].category == "action_blocked"  # critical before high
    assert items[0].status == "progress"
    assert items[0].assignee == "Amadou"
    validation_item = next(item for item in items if item.category == "validation_requested")
    assert validation_item.priority == "high"
    assert validation_item.detail_href.startswith("/agents/recouvrement/metier?")
    assert "turn_id=turn-validation" in validation_item.detail_href
    assert "capability_id=propose_schedule" in validation_item.detail_href


def test_load_items_skips_agents_without_a_real_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def _loader(aid: str) -> _Snap:
        if aid == "ghost":
            raise FileNotFoundError("no run for ghost")
        return _Snap([_session("01", "pii_leak", passed=False)], aid)

    monkeypatch.setattr(oi, "_agent_targets", lambda _agent_id=None: ["support-client", "ghost"])
    monkeypatch.setattr(oi, "load_eval_snapshot", _loader)
    monkeypatch.setattr(oi, "_load_state", dict)
    items = oi.load_items()
    # 'ghost' has no run → contributes nothing (never a fabricated attribution).
    assert {i.agent_id for i in items} == {"support-client"}


def test_load_items_merges_durable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _Snap([_session("01", "pii_leak", passed=False)])
    monkeypatch.setattr(oi, "_agent_targets", lambda _agent_id=None: ["support-client"])
    monkeypatch.setattr(oi, "load_eval_snapshot", lambda _aid: snap)
    monkeypatch.setattr(
        oi, "_load_state", lambda: {"support-client.01.fr": {"status": "done", "assignee": "Moi"}}
    )
    item = oi.load_items()[0]
    assert item.status == "done"
    assert item.assignee == "Moi"


def test_sla_tone_reflects_remaining_time() -> None:
    crit_overdue = oi.OperatorItem(
        item_id="x",
        agent_id="support-client",
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
        agent_id="support-client",
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
        agent_id="support-client",
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
        agent_id="support-client",
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
    monkeypatch.setattr(inbox, "load_items", lambda *_a, **_k: items)
    payload = inbox.compute_inbox_overview(now=NOW)
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


def test_a_faire_aggregates_and_exposes_details(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _item("a", "crit", "todo", hours_ago=3),  # overdue
        _item("b", "mod", "progress", hours_ago=1),  # in progress, assigned Moi
        _item("c", "crit", "done", hours_ago=5),  # resolved
    ]
    monkeypatch.setattr(agent_a_faire, "load_items", lambda *_a, **_k: items)
    payload = agent_a_faire.compute_agent_a_faire(now=NOW)
    kpis = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpis["total"] == "2"  # 2 open (a, b)
    assert kpis["late"] == "1"  # a overdue
    assert kpis["mine"] == "1"  # b assigned Moi
    assert kpis["resolved"] == "1"
    # one detail per item, keyed; workflow status is independent of SLA breach.
    assert len(payload["details"]) == 3
    det_a = next(d for d in payload["details"] if d["key"] == "a.fr")
    assert det_a["current_status"] == "A traiter"  # overdue does NOT mask workflow status
    task_a = next(t for t in payload["table"]["tasks"] if t["key"] == "a.fr")
    assert task_a["sla"] == "En retard"  # breach shown in the SLA cell
    assert task_a["status"] == "A traiter"
    det_b = next(d for d in payload["details"] if d["key"] == "b.fr")
    assert det_b["current_status"] == "En cours"
