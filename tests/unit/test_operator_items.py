"""Unit tests for the operator work-queue source and the inbox aggregation.

`operator_items.load_items` is exercised with a synthetic eval snapshot + durable
state (no file/DB I/O); `inbox.compute_inbox_overview` is exercised with a
synthetic item list to assert the KPI/by-type/SLA aggregation and the payload
mapping.

The `TestTheNaturePartition` class is the ADR 0038 ratchet: "A faire" serves
ONLY the eval half, "A traiter" ONLY the business half, the two halves are an
exhaustive partition of `load_items()` (nothing lost, nothing duplicated, a
stranger kind refuses loudly), and each compute is exercised through the REAL
filter path — stubbing the SOURCE, never the filter — so removing a page's
filter re-swallows the other half and turns these tests red.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tessera.observability import agent_a_faire, inbox, operator_items as oi
from tessera.observability.eval_data import SessionRow

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


def _item(
    case_id: str,
    priority: str,
    status: str,
    *,
    hours_ago: float,
    kind: str = "eval_failure",
) -> oi.OperatorItem:
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
        source_kind=kind,
    )


def test_inbox_aggregates_real_items(monkeypatch: pytest.MonkeyPatch) -> None:
    # Business-nature items: the only kind this page can see since ADR 0038.
    items = [
        _item("a", "crit", "todo", hours_ago=3, kind="business_event"),  # overdue (crit SLA 1h)
        _item("b", "high", "todo", hours_ago=0.1, kind="business_event"),  # within SLA
        _item("c", "mod", "progress", hours_ago=1, kind="business_event"),  # assigned to Moi
        _item("d", "crit", "done", hours_ago=5, kind="business_event"),  # resolved
    ]
    monkeypatch.setattr(inbox, "load_items_for", lambda *_a, **_k: items)
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
    monkeypatch.setattr(agent_a_faire, "load_items_for", lambda *_a, **_k: items)
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


# --- ADR 0038 — the nature partition ratchet ---------------------------------


def _wire_mixed_backlog(
    monkeypatch: pytest.MonkeyPatch, *, with_evals: bool = True, with_business: bool = True
) -> tuple[set[str], set[str]]:
    """Wire `operator_items` to a synthetic backlog AT THE SOURCE.

    The computes under test then run the REAL partition path (`load_items_for`
    → `partition_items` → `nature_of`); stubbing the filter itself would make
    these tests blind to its removal. Returns (eval item ids, business item ids).
    """
    snap = _Snap(
        [
            _session("01", "pii_leak", passed=False),
            _session("03", "tool_misuse", passed=False),
        ]
    )

    def _snap_loader(_aid: str) -> _Snap:
        if not with_evals:
            raise FileNotFoundError("no eval run")
        return snap

    validation = {
        "event_name": oi.business_events.BusinessEventName.VALIDATION_REQUESTED.value,
        "agent_id": "support-client",
        "conversation_id": "conv-p",
        "turn_id": "turn-v",
        "case_id": "RC-1",
        "artifact_id": "art-1",
        "artifact_type": "schedule_proposal_v2",
        "timestamp": NOW.isoformat(),
        "payload": {},
    }
    blocked = {
        "event_name": oi.business_events.BusinessEventName.ACTION_BLOCKED.value,
        "agent_id": "support-client",
        "conversation_id": "conv-p",
        "turn_id": "turn-b",
        "case_id": "RC-1",
        "timestamp": NOW.isoformat(),
        "payload": {"action_name": "prepare_outbound_call"},
    }
    rows_by_event: dict[str, list[dict[str, object]]] = (
        {
            str(validation["event_name"]): [validation],
            str(blocked["event_name"]): [blocked],
        }
        if with_business
        else {}
    )

    def _rows(
        *, agent_id: str | None = None, event_name: str | None = None, **_kw: object
    ) -> list[dict[str, object]]:
        return list(rows_by_event.get(event_name or "", []))

    monkeypatch.setattr(oi, "_agent_targets", lambda _agent_id=None: ["support-client"])
    monkeypatch.setattr(oi, "load_eval_snapshot", _snap_loader)
    monkeypatch.setattr(oi, "_load_state", dict)
    monkeypatch.setattr(oi.business_events, "business_event_rows", _rows)

    eval_ids = {"support-client.01.fr", "support-client.03.fr"} if with_evals else set()
    business_ids = (
        {
            "support-client.validation.requested.conv-p.turn-v.art-1",
            "support-client.action.blocked.conv-p.turn-b.RC-1",
        }
        if with_business
        else set()
    )
    return eval_ids, business_ids


class TestTheNaturePartition:
    """ADR 0038: one union, two natures, each page serving exactly one of them."""

    def test_the_declared_partition_is_total_and_disjoint(self) -> None:
        """The declaration itself: two natures, disjoint kinds, both emitters owned."""
        assert set(oi._NATURE_KINDS) == {oi.NATURE_A_FAIRE, oi.NATURE_A_TRAITER}
        a_faire_kinds = oi._NATURE_KINDS[oi.NATURE_A_FAIRE]
        a_traiter_kinds = oi._NATURE_KINDS[oi.NATURE_A_TRAITER]
        assert not (a_faire_kinds & a_traiter_kinds)
        # The two kinds the backlog actually emits (the dataclass default and the
        # literal in `_business_event_items`) are both owned by a page.
        assert oi.nature_of("eval_failure") == oi.NATURE_A_FAIRE
        assert oi.nature_of("business_event") == oi.NATURE_A_TRAITER

    def test_the_two_halves_partition_the_union_exactly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Union == load_items() (nothing lost), intersection == ∅ (nothing duplicated)."""
        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)

        union = {i.item_id for i in oi.load_items()}
        a_faire = oi.load_items_for(oi.NATURE_A_FAIRE)
        a_traiter = oi.load_items_for(oi.NATURE_A_TRAITER)
        a_faire_ids = {i.item_id for i in a_faire}
        a_traiter_ids = {i.item_id for i in a_traiter}

        assert a_faire_ids and a_traiter_ids  # a partition test over an empty set proves nothing
        assert a_faire_ids | a_traiter_ids == union
        assert not (a_faire_ids & a_traiter_ids)
        assert a_faire_ids == eval_ids
        assert a_traiter_ids == business_ids
        assert all(i.source_kind == "eval_failure" for i in a_faire)
        assert all(i.source_kind == "business_event" for i in a_traiter)

    def test_a_stranger_kind_refuses_loudly_instead_of_vanishing(self) -> None:
        """A source_kind no page owns is an error, never a silent drop."""
        with pytest.raises(oi.UnknownSourceKindError):
            oi.nature_of("martian")
        stranger = _item("s", "crit", "todo", hours_ago=0.1, kind="martian")
        with pytest.raises(oi.UnknownSourceKindError):
            oi.partition_items([stranger])
        with pytest.raises(ValueError, match="unknown queue nature"):
            oi.load_items_for("nonsense")

    def test_a_faire_serves_only_the_eval_half(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Through the REAL filter path: remove the page's filter and this goes red."""
        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)

        payload = agent_a_faire.compute_agent_a_faire(now=NOW)

        task_ids = {t["key"] for t in payload["table"]["tasks"]}
        assert task_ids == eval_ids
        assert not (task_ids & business_ids)

    def test_inbox_serves_only_the_business_half(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The mirror: the inbox lists the business half and nothing else."""
        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)

        payload = inbox.compute_inbox_overview(now=NOW)

        row_ids = {r["id"] for r in payload["items"]}
        assert row_ids == business_ids
        assert not (row_ids & eval_ids)
        assert all(r["source_kind"] == "business_event" for r in payload["items"])

    def test_a_faire_is_honestly_empty_without_evals_and_never_refills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A backlog with only business events -> "A faire" is LEGITIMATELY empty."""
        _, business_ids = _wire_mixed_backlog(monkeypatch, with_evals=False)
        assert business_ids  # the other half exists — this is what must NOT leak in

        payload = agent_a_faire.compute_agent_a_faire(now=NOW)

        assert payload["table"]["tasks"] == []
        assert payload["detail"] is None
        kpis = {k["key"]: k["value"] for k in payload["kpis"]}
        assert kpis["total"] == "0"

    def test_inbox_is_honestly_empty_without_business_events_and_never_refills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A backlog with only eval failures -> "A traiter" is LEGITIMATELY empty."""
        eval_ids, _ = _wire_mixed_backlog(monkeypatch, with_business=False)
        assert eval_ids  # the eval half exists — and must not be re-swallowed

        payload = inbox.compute_inbox_overview(now=NOW)

        assert payload["items"] == []
        assert payload["total_items"] == 0

    def test_the_chrome_counts_each_half_for_the_page_it_links_to(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Badges and bell rows mirror THEIR page, not the union (chrome doctrine)."""
        from tessera.observability import chrome

        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)

        badges = chrome._queue_badges(NOW)
        assert badges["a_faire"]["count"] == len(eval_ids)
        assert badges["a_traiter"]["count"] == len(business_ids)

        rows = {r["id"]: r for r in chrome._queue_notifications("fr", NOW)}
        pending_business = rows["queue:pending:a_traiter"]
        assert pending_business["href"] == "/a-traiter"
        assert str(len(business_ids)) in str(pending_business["label"])
        pending_eval = rows["queue:pending:a_faire"]
        assert pending_eval["href"] == "/a-faire"
        assert str(len(eval_ids)) in str(pending_eval["label"])


def _operator_client(monkeypatch: pytest.MonkeyPatch) -> object:
    """A TestClient over the observability router, authenticated as a real admin.

    The assertion is minted with the real HMAC — what is under test is the
    partition decision taken AFTER authentication succeeds.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
    from tessera.api.routes.observability import router as observability_router
    from tessera.settings import get_settings

    monkeypatch.setattr(get_settings().api, "operator_assertion_signing_key", SecretStr("test-key"))
    app = FastAPI()
    app.include_router(observability_router)
    token = issue_operator_assertion(principal="admin", role="admin")
    return TestClient(
        app, headers={OPERATOR_ASSERTION_HEADER: token}, raise_server_exceptions=False
    )


class TestTheItemStateEndpointsHonourThePartition:
    """ADR 0038 on the mutation plane: each endpoint acts on ITS half only."""

    def test_a_business_item_is_refused_by_a_faire_and_served_by_the_inbox(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)
        writes: list[dict[str, dict[str, str]]] = []
        monkeypatch.setattr(oi, "_save_state", writes.append)
        client = _operator_client(monkeypatch)
        business_id = "support-client.action.blocked.conv-p.turn-b.RC-1"
        assert business_id in business_ids

        refused = client.post(  # type: ignore[attr-defined]
            "/observability/agent-a-faire/item-state",
            json={"item_id": business_id, "status": "progress"},
        )
        assert refused.status_code == 404
        assert not writes  # refused BEFORE the durable write, not after

        served = client.post(  # type: ignore[attr-defined]
            "/observability/inbox/item-state",
            json={"item_id": business_id, "status": "progress"},
        )
        assert served.status_code == 200
        assert writes  # the owning page's endpoint DID persist
        # The returned view is the FILTERED one: no eval item re-appears.
        ids = {r["id"] for r in served.json()["items"]}
        assert ids == business_ids
        assert not (ids & eval_ids)

    def test_an_eval_item_is_refused_by_the_inbox_and_served_by_a_faire(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eval_ids, business_ids = _wire_mixed_backlog(monkeypatch)
        monkeypatch.setattr(oi, "_save_state", lambda _state: None)
        client = _operator_client(monkeypatch)
        eval_id = "support-client.01.fr"
        assert eval_id in eval_ids

        refused = client.post(  # type: ignore[attr-defined]
            "/observability/inbox/item-state", json={"item_id": eval_id, "status": "progress"}
        )
        assert refused.status_code == 404

        served = client.post(  # type: ignore[attr-defined]
            "/observability/agent-a-faire/item-state",
            json={"item_id": eval_id, "status": "progress"},
        )
        assert served.status_code == 200
        task_ids = {t["key"] for t in served.json()["table"]["tasks"]}
        assert task_ids == eval_ids
        assert not (task_ids & business_ids)
