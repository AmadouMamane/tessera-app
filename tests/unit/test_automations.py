"""Unit tests for the Automations real core (rules + journal + approvals).

The rules must evaluate REAL conditions (wired stores are monkeypatched to
synthetic values here), the journal must persist executed evaluations, the
approval queue must hold exactly the requests opened by fired approb-mode
rules, and the overview must derive its catalogue/KPIs/funnel from the store —
with honest dashes for the storeless figures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.observability import automation_store as astore, automations

if TYPE_CHECKING:
    from pathlib import Path


def _wire_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(astore, "_rules_path", lambda: tmp_path / "automation_rules.json")
    monkeypatch.setattr(astore, "_runs_path", lambda: tmp_path / "automation_runs.json")
    monkeypatch.setattr(astore, "_approvals_path", lambda: tmp_path / "automation_approvals.json")


def _stub_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic check outcomes without touching the real stores."""
    outcomes = {
        "gate_freeze": (True, "gate FAIL: onboarding"),
        "chain_alert": (False, "chain OK (100)"),
        "low_faith_review": (True, "4 turns < 0.8"),
        "deny_spike": (False, "12 denies / 24h"),
        "curation_backlog": (True, "42 pending"),
    }
    patched = tuple(
        astore.AutomationRule(
            id=rule.id,
            type=rule.type,
            mode=rule.mode,
            role=rule.role,
            severity=rule.severity,
            check=(lambda rid=rule.id: outcomes[rid]),
        )
        for rule in astore.RULES
    )
    monkeypatch.setattr(astore, "RULES", patched)
    monkeypatch.setattr(automations, "RULES", patched)


def test_rule_toggle_is_durable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wire_paths(monkeypatch, tmp_path)
    assert astore.list_rule_states()["gate_freeze"] is True  # default enabled
    astore.set_rule_enabled("gate_freeze", enabled=False)
    assert astore.list_rule_states()["gate_freeze"] is False
    astore.set_rule_enabled("bogus", enabled=False)  # unknown ids ignored
    assert "bogus" not in astore.list_rule_states()


def test_evaluate_rules_journals_real_outcomes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire_paths(monkeypatch, tmp_path)
    _stub_checks(monkeypatch)
    astore.set_rule_enabled("deny_spike", enabled=False)
    entries = astore.evaluate_rules()
    # Only the 4 enabled rules ran; each entry carries the observed real value.
    assert len(entries) == 4
    by_rule = {e["rule_id"]: e for e in entries}
    assert "deny_spike" not in by_rule
    assert by_rule["gate_freeze"]["fired"] is True
    assert by_rule["gate_freeze"]["observed"] == "gate FAIL: onboarding"
    assert by_rule["chain_alert"]["fired"] is False
    # Journal is durable: a reload sees the same entries.
    assert len(astore.load_runs()) == 4


def test_overview_derives_from_the_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _wire_paths(monkeypatch, tmp_path)
    _stub_checks(monkeypatch)
    monkeypatch.setattr(automations, "_guardrail_counts", list)
    monkeypatch.setattr(automations, "list_rule_states", astore.list_rule_states)
    monkeypatch.setattr(automations, "load_runs", astore.load_runs)
    astore.evaluate_rules()

    payload = automations.compute_automations_overview("fr")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["active"] == "5"
    assert kpi["executions"] == "5"  # journalled this run
    assert kpi["success_rate"] == "100.0%"
    for storeless in ("blocked", "mttr"):
        assert kpi[storeless] == "—"
    # Catalogue: real ids, durable status, journalled fired/checked ratio.
    rows = {r["id"]: r for r in payload["catalogue"]}
    assert rows["gate_freeze"]["success"] == "1/1"
    assert rows["gate_freeze"]["status"] == "active"
    assert rows["chain_alert"]["success"] == "0/1"
    # Journal rows reflect the real observed values.
    assert any("42 pending" in str(j["trigger"]) for j in payload["journal"])
    # The two fired approb-mode rules opened REAL pending approval requests,
    # and the approvals KPI counts them (never the static rule-mode count).
    appr = {a["rule_id"]: a for a in payload["approvals"]}
    assert set(appr) == {"low_faith_review", "curation_backlog"}
    assert appr["curation_backlog"]["observed"] == "42 pending"
    assert kpi["approvals"] == "2"
    savings = {s["key"]: s["value"] for s in payload["savings"]}
    assert savings["tickets"] == "—"  # flagged demo, never invented


def test_fired_approb_rules_open_one_pending_request_each_idempotently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fired approb rule asks a human ONCE: re-evaluating an unresolved
    condition refreshes nothing; auto-mode rules never ask."""
    _wire_paths(monkeypatch, tmp_path)
    _stub_checks(monkeypatch)
    astore.evaluate_rules()
    first = astore.pending_approvals()
    # gate_freeze fired too, but it is mode=auto — it never opens a request.
    assert {a["rule_id"] for a in first} == {"low_faith_review", "curation_backlog"}
    astore.evaluate_rules()
    assert astore.pending_approvals() == first  # idempotent while unresolved


def test_decide_approval_is_attributed_and_single_shot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire_paths(monkeypatch, tmp_path)
    _stub_checks(monkeypatch)
    astore.evaluate_rules()
    target = next(a for a in astore.pending_approvals() if a["rule_id"] == "low_faith_review")
    decided = astore.decide_approval(str(target["id"]), approved=True, decided_by="bob@bank.eu")
    assert decided["status"] == "approved"
    assert decided["decided_by"] == "bob@bank.eu"
    # The queue no longer lists it; the decision is durable.
    assert all(a["id"] != target["id"] for a in astore.pending_approvals())
    stored = {a["id"]: a for a in astore.load_approvals()}
    assert stored[target["id"]]["decided_by"] == "bob@bank.eu"
    # A second decision must never silently overwrite the first author.
    with pytest.raises(astore.ApprovalNotPendingError):
        astore.decide_approval(str(target["id"]), approved=False, decided_by="eve@bank.eu")
    with pytest.raises(astore.ApprovalNotPendingError):
        astore.decide_approval("ghost-id", approved=True, decided_by="bob@bank.eu")
    # A rejected request leaves the queue the same way.
    other = next(a for a in astore.pending_approvals())
    rejected = astore.decide_approval(str(other["id"]), approved=False, decided_by="bob@bank.eu")
    assert rejected["status"] == "rejected"
    assert astore.pending_approvals() == []
    # Once resolved, a re-fire may open a NEW request (the condition persists).
    astore.evaluate_rules()
    assert {a["rule_id"] for a in astore.pending_approvals()} == {
        "low_faith_review",
        "curation_backlog",
    }


def test_overview_without_any_run_is_honest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _wire_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(automations, "_guardrail_counts", list)
    monkeypatch.setattr(automations, "list_rule_states", astore.list_rule_states)
    monkeypatch.setattr(automations, "load_runs", astore.load_runs)
    payload = automations.compute_automations_overview("en")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["executions"] == "0"
    assert kpi["success_rate"] == "—"
    assert payload["completion"] == "—"
    rows = {r["id"]: r for r in payload["catalogue"]}
    assert all(r["last_run"] == "—" for r in rows.values())
