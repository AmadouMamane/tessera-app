"""Unit tests for the Policies & guardrails real core.

``compute_policies_overview`` must derive its active policies from the compiled
guard policy (one row per enforced rule, keyed by the emitted ``policy_rule``
id), its posture KPIs and runtime gauges from the audit ledger, and the footer
chain from the live verification — never from literals. The impact simulator
stays a flagged fixture (shape only).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.guard.audit import ChainStatus
from tessera.guard.decisions import Policy, ToolPolicy
from tessera.observability import policies as pol

if TYPE_CHECKING:
    import pytest


def _policy() -> Policy:
    return Policy(
        version=7,
        tools={
            "account_balance": ToolPolicy(name="account_balance", allow=True),
            "card_block": ToolPolicy(name="card_block", allow=True, requires_confirmation=True),
            "wire_transfer": ToolPolicy(name="wire_transfer", allow=False),
        },
        prompt_injection_deny=["a", "b", "c"],
        prompt_injection_transforms=["strip"],
        pii_patterns=["iban", "email"],
    )


def _entries(now: datetime) -> list[dict[str, object]]:
    def dec(kind: str, rule: str, hours_ago: float) -> dict[str, object]:
        return {
            "decision": kind,
            "policy_rule": rule,
            "occurred_at": (now - timedelta(hours=hours_ago)).isoformat(),
        }

    return [
        {
            "type": "tessera.guard.audit",
            "occurred_at": now.isoformat(),
            "decisions": [
                dec("deny", "prompt_injection.deny_patterns", 1),
                dec("deny", "prompt_injection.deny_patterns", 2),
                dec("deny", "tool.wire_transfer.allow", 3),
                dec("transform", "pii.patterns", 4),
                dec("allow", "memory.read.governance", 5),
                dec("allow", "memory.write.governance", 30),  # outside 24h
                dec("deny", "prompt_injection.deny_patterns", 30),  # outside 24h
            ],
        },
        {"type": "something.else", "decisions": [dec("deny", "x", 1)]},
    ]


def _wire(monkeypatch: pytest.MonkeyPatch, *, verified: bool = True) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(pol, "load_policy", _policy)
    monkeypatch.setattr(pol, "read_ledger_entries", lambda: _entries(now))
    monkeypatch.setattr(
        pol,
        "verify_active_ledger",
        lambda: ChainStatus(verified=verified, length=42, broken_at=None if verified else 3),
    )


def test_active_policies_come_from_the_compiled_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch)
    payload = pol.compute_policies_overview("fr")
    rows = {str(p["id"]): p for p in payload["active_policies"]}
    # One row per enforced rule family + one per tool, real emitted rule ids.
    assert "prompt_injection.deny_patterns" in rows
    assert "pii.patterns" in rows
    assert "memory.write.governance" in rows
    assert "tool.account_balance.allow" in rows
    assert "tool.card_block.allow" in rows
    assert "tool.wire_transfer.allow" in rows
    assert len(rows) == 4 + 3
    # Actions derive from the real tool policy flags.
    assert rows["tool.account_balance.allow"]["action"] == "allow"
    assert rows["tool.card_block.allow"]["action"] == "warn"  # requires_confirmation
    assert rows["tool.wire_transfer.allow"]["action"] == "deny"  # not allowed
    # The real single version stamps every row.
    assert payload["active_version"] == "v7"
    assert all(p["version"] == "v7" for p in payload["active_policies"])


def test_kpis_and_guardrails_derive_from_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch)
    payload = pol.compute_policies_overview("fr")
    kpi = {k["key"]: k for k in payload["kpis"]}
    assert kpi["active_policies"]["value"] == "7"
    # deny-mode rules: injection + wire_transfer tool + memory write governance.
    assert kpi["blocking_guardrails"]["value"] == "3"
    # denies in the last 24h: 2 injection + 1 tool (the 30h-old ones excluded).
    assert kpi["violations_blocked"]["value"] == "3"
    # Metrics with no real source stay honest dashes, never invented numbers.
    assert kpi["false_positives"]["value"] == "—"
    assert kpi["pending_versions"]["value"] == "0"
    gr = {g["key"]: g for g in payload["guardrails"]}
    # 4 denies / 7 decisions on real entries; the non-guard entry is ignored.
    assert gr["deny_policies"]["value"] == "57.1%"
    assert gr["attacks_blocked"]["value"] == "3"
    assert gr["tool_denials"]["value"] == "1"
    assert gr["pii_blocked"]["value"] == "1"
    assert gr["memory_approved"]["value"] == "100%"


def test_chain_footer_is_live_and_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, verified=True)
    ok = pol.compute_policies_overview("fr")
    assert "42" in str(ok["footer"]["chain"])
    _wire(monkeypatch, verified=False)
    broken = pol.compute_policies_overview("fr")
    assert "3" in str(broken["footer"]["chain"])
    assert str(ok["footer"]["source"]).startswith("guard/policy.yaml")


def test_single_real_version_rail_and_diff_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch)
    payload = pol.compute_policies_overview("en")
    timeline = payload["version_timeline"]
    assert len(timeline) == 1
    assert timeline[0]["version"] == "v7"
    assert timeline[0]["status"] == "active"
    # The diff slot carries a context-only summary of the REAL active content.
    diff = payload["diff"]
    assert all(line["type"] == "context" for line in diff["lines"])
    texts = " ".join(line["text"] for line in diff["lines"])
    assert "deny_patterns: 3" in texts
    assert "pii_patterns: 2" in texts
    assert "tools: 3 (allow 2, confirm 1, deny 1)" in texts
    # Impact simulator stays a fixture (shape only).
    assert len(payload["impact"]) == 5
