"""Unit tests for the Incidents & playbooks real core.

The incident feed must derive from the guard ledger (one cluster per rule
family with denies in the window, real counts/times/series) plus the
low-faithfulness replay cluster; lifecycle metrics with no store render "—".
The playbook/journal/postmortem subsystem stays a fixture (shape only).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import incidents as inc

if TYPE_CHECKING:
    import pytest

NOW = datetime.now(UTC)


def _entries() -> list[dict[str, object]]:
    def dec(rule: str, hours_ago: float) -> dict[str, object]:
        return {
            "decision": "deny",
            "policy_rule": rule,
            "occurred_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
        }

    return [
        {
            "type": "tessera.guard.audit",
            "occurred_at": NOW.isoformat(),
            "decisions": [
                dec("prompt_injection.deny_patterns", 1),
                dec("prompt_injection.deny_patterns", 2),
                dec("prompt_injection.deny_patterns", 26),
                dec("tool.wire_transfer.allow", 3),
                dec("pii.patterns", 4),
                dec("prompt_injection.deny_patterns", 24 * 10),  # outside 7d window
            ],
        },
    ]


def _wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inc, "read_ledger_entries", lambda **_kw: _entries())
    monkeypatch.setattr(inc, "_scan_low_score", lambda *_a, **_kw: (2, NOW - timedelta(hours=5)))


def test_incident_clusters_derive_from_the_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    payload = inc.compute_incidents_overview("fr")
    rows = payload["priority_incidents"]
    # 3 rule clusters + the low-faithfulness cluster.
    assert len(rows) == 4
    top = rows[0]
    # Injection dominates (3 denies in-window), marked critical / security.
    assert "Prompt injection" in str(top["trigger"])
    assert "(3)" in str(top["trigger"])
    assert top["severity"] == "critique"
    assert top["domain"] == "securite"
    # No lifecycle store: owner and SLA are honest dashes, status is open.
    assert top["owner"] == "—"
    assert top["sla"] == "—"
    assert all(r["status"] == "ouvert" for r in rows)
    # The low-score cluster carries the real bundle count.
    low = rows[-1]
    assert "2" in str(low["trigger"])
    assert low["domain"] == "qualite_rag"


def test_kpis_are_real_or_honest_dashes(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    payload = inc.compute_incidents_overview("fr")
    kpi = {k["key"]: k["value"] for k in payload["kpis"]}
    assert kpi["open"] == "4"
    assert kpi["critical"] == "2"  # injection + pii clusters
    for storeless in ("mtta", "mttr", "playbooks", "autoresolve", "sla_risk", "evidence"):
        assert kpi[storeless] == "—"
    # Real per-domain donut (only non-empty domains, real total).
    dist = {d["key"]: d["count"] for d in payload["domain_distribution"]}
    assert dist == {"securite": 2, "privacy": 1, "qualite_rag": 1}
    assert payload["donut_total"] == 4


def test_recent_feed_and_footer_are_live(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    payload = inc.compute_incidents_overview("en")
    recent = payload["recent_incidents"]
    # 5 in-window deny EVENTS collapse to one row per INCIDENT (rule cluster): the feed
    # lists incidents and its id is the row's identity. Found live: the four latest events
    # were one injection burst and the feed read INC-449 four times — React reported the
    # duplicate key to the operator as the dev-overlay "1 error" badge.
    ids = [r["id"] for r in recent]
    assert len(ids) == len(set(ids)), f"an id that names two rows names neither: {ids}"
    assert len(recent) == 3  # injection, wire-transfer, pii — one row each
    assert recent[0]["label"] == "Prompt injection"
    # The burst's single row is stamped with its LATEST event, not an older one.
    assert recent[0]["time"] == (NOW - timedelta(hours=1)).strftime("%H:%M")
    # What the dedup did not list is still counted, never silently dropped.
    assert payload["recent_more"] == 2
    footer = payload["footer"]
    assert footer["critical"] == 2
    assert footer["proofs"] == 5  # real in-window deny events
    # Subsystem chrome stays a fixture (shape only).
    for key in ("running_playbook", "response_journal", "automations", "postmortems"):
        assert payload[key]


class TestAsOfBounds:
    """The as-of reading ends the deny window at T — later events do not exist."""

    @staticmethod
    def _audit_entry(when: datetime) -> dict[str, object]:
        return {
            "type": "tessera.guard.audit",
            "occurred_at": when.isoformat(),
            "decisions": [
                {
                    "decision": "deny",
                    "policy_rule": "prompt_injection.deny",
                    "occurred_at": when.isoformat(),
                }
            ],
        }

    def test_the_deny_window_ends_at_t(self, monkeypatch: pytest.MonkeyPatch) -> None:
        base = datetime(2026, 7, 22, 0, 0, tzinfo=UTC)
        entries = [
            self._audit_entry(base + timedelta(hours=10)),
            self._audit_entry(base + timedelta(hours=14)),
        ]
        monkeypatch.setattr(inc, "read_ledger_entries", lambda **_kw: list(entries))
        monkeypatch.setattr(inc, "_scan_low_score", lambda *_a, **_kw: (0, None))

        live = inc._RealIncidents(base + timedelta(hours=15))
        assert live.n_events == 2

        at_noon = inc._RealIncidents(base + timedelta(hours=12))
        assert at_noon.n_events == 1  # the 14h deny does not exist at T

    def test_a_malformed_instant_reads_live_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(inc, "read_ledger_entries", lambda **_kw: [])
        monkeypatch.setattr(inc, "_scan_low_score", lambda *_a, **_kw: (0, None))
        payload = inc.compute_incidents_overview("fr", at="not-a-date")
        assert isinstance(payload, dict) and "kpis" in payload
