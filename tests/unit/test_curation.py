"""Unit tests for the curation decision core.

``curation_store.load_candidates`` is exercised with a synthetic eval snapshot +
durable state (no file/DB I/O); ``set_decision`` is round-tripped through a temp
state file; and ``curation.compute_curation_overview`` is checked to derive its
decision-core KPIs, distribution and priority lots from the store (never literals).
The subsystem chrome (workflow / coverage / trends) stays a fixture — only its
shape is asserted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import curation, curation_store as cstore
from tessera.observability.eval_data import SessionRow

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _session(case_id: str, category: str, *, passed: bool, lang: str = "fr") -> SessionRow:
    return SessionRow(
        case_id=case_id,
        language=lang,
        category=category,
        title=f"{case_id} title",
        passed=passed,
        needs_escalation=(category == "pii_leak"),
        tools=(),
        duration_ms=10.0,
        input_tokens=1,
        output_tokens=1,
        response="r",
        started_at=(NOW - timedelta(hours=0.5)).isoformat(),
    )


class _Snap:
    def __init__(self, sessions: list[SessionRow], agent_id: str = "support-client") -> None:
        self.sessions = tuple(sessions)
        self.agent_id = agent_id


def _wire(monkeypatch: pytest.MonkeyPatch, sessions: list[SessionRow], state: dict) -> None:
    monkeypatch.setattr(cstore, "_agent_targets", lambda _agent_id=None: ["support-client"])
    monkeypatch.setattr(cstore, "load_eval_snapshot", lambda _aid: _Snap(sessions))
    monkeypatch.setattr(cstore, "_load_state", lambda: state)


def test_load_candidates_keeps_only_failures_and_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(
        monkeypatch,
        [
            _session("01", "pii_leak", passed=False),
            _session("02", "hallucination", passed=True),  # passing -> excluded
            _session("03", "tool_misuse", passed=False),
        ],
        {},
    )
    cands = cstore.load_candidates()
    assert [c.case_id for c in cands] == ["01", "03"]  # only failures
    pii = next(c for c in cands if c.case_id == "01")
    assert pii.candidate_id == "support-client.01.fr"  # namespaced by agent
    assert pii.priority == "crit"  # pii_leak -> crit
    assert pii.curation_category == "pii_securite"
    assert pii.decision == "pending"  # default when no override
    assert pii.needs_escalation is True


def test_decision_counts_reflect_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(
        monkeypatch,
        [
            _session("01", "pii_leak", passed=False),
            _session("03", "tool_misuse", passed=False),
            _session("04", "hallucination", passed=False),
        ],
        {"support-client.01.fr": {"decision": "promote", "decided_by": "a"}},
    )
    counts = cstore.decision_counts()
    assert counts["total"] == 3
    assert counts["promote"] == 1
    assert counts["pending"] == 2
    assert counts["review"] == 0 and counts["reject"] == 0


def test_set_decision_persists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state_file = tmp_path / "curation_decisions.json"
    monkeypatch.setattr(cstore, "_state_path", lambda: state_file)
    cstore.set_decision("support-client.01.fr", decision="reject", decided_by="claire")
    assert state_file.exists()
    reloaded = cstore._load_state()
    assert reloaded["support-client.01.fr"]["decision"] == "reject"
    assert reloaded["support-client.01.fr"]["decided_by"] == "claire"
    # A real decision is timestamped; resetting to pending clears the timestamp.
    assert reloaded["support-client.01.fr"]["decided_at"]
    cstore.set_decision("support-client.01.fr", decision="pending")
    assert cstore._load_state()["support-client.01.fr"]["decided_at"] == ""
    cstore.set_decision("support-client.01.fr", decision="reject")
    # An invalid decision is ignored, not persisted as-is.
    cstore.set_decision("support-client.01.fr", decision="bogus")
    assert cstore._load_state()["support-client.01.fr"]["decision"] == "reject"


def test_backend_derives_decision_core_from_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(
        monkeypatch,
        [
            _session("01", "pii_leak", passed=False),
            _session("03", "tool_misuse", passed=False),
            _session("04", "hallucination", passed=False),
        ],
        {"support-client.01.fr": {"decision": "promote", "decided_by": "a"}},
    )
    payload = curation.compute_curation_overview("fr")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["candidates"] == "3"
    assert kpi["promotable"] == "1"
    assert kpi["pending"] == "2"
    assert kpi["escalations"] == "1"  # only the pii case
    assert kpi["critical"] == "1"  # pii_leak -> crit
    # Distribution + total are real; the promoted lot carries its decision.
    assert payload["distribution_total"] == 3
    dist = {s["key"]: s["count"] for s in payload["candidates_distribution"]}
    assert dist == {"pii_securite": 1, "outils": 1, "hallucination": 1}
    lots = {lot["candidate_id"]: lot for lot in payload["priority_lots"]}
    assert lots["support-client.01.fr"]["decision"] == "promote"
    # Subsystem chrome stays a fixture (shape only).
    for key in ("workflow", "coverage", "why_tours", "linked_datasets", "backlog_trend"):
        assert payload[key]


def test_candidate_lots_expose_the_full_real_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(
        monkeypatch,
        [
            _session("01", "pii_leak", passed=False),
            _session("03", "tool_misuse", passed=False),
            _session("04", "hallucination", passed=False),
        ],
        {
            "support-client.01.fr": {
                "decision": "promote",
                "decided_by": "a",
                "decided_at": "2026-06-16T11:59:00+00:00",
            }
        },
    )
    payload = curation.compute_curation_overview("fr")
    lots = payload["candidate_lots"]
    assert isinstance(lots, list)
    # Every real candidate is exposed (not just the top-6 overview slice).
    assert len(lots) == 3
    by_id = {lot["candidate_id"]: lot for lot in lots}
    promoted = by_id["support-client.01.fr"]
    assert promoted["decision"] == "promote"
    assert promoted["decided_at"] == "2026-06-16T11:59:00+00:00"
    assert promoted["agent_id"] == "support-client"
    assert promoted["language"] == "fr"
    assert promoted["title"] == "01 title"
    # Undecided rows carry an empty decided_at, never a fabricated time.
    assert by_id["support-client.03.fr"]["decided_at"] == ""
