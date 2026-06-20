"""Unit tests for the Integrations overview (configurer/integrations).

Assert the payload is built from the real agent tools crossed with the guard
policy and the audit log — not a fabricated SaaS catalogue. Audit folding is
tested on a synthetic scan so it needs no real log file.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.guard.decisions import load_policy
from tessera.observability import integrations as ig

NOW = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)


def test_rows_mirror_the_real_tools() -> None:
    payload = ig.compute_integrations_overview()
    ids = [r["id"] for r in payload["integrations"]]
    assert ids == [t["id"] for t in ig._TOOLS]
    assert payload["total_integrations"] == len(ig._TOOLS)
    # No invented SaaS connectors.
    names = " ".join(str(r["name"]) for r in payload["integrations"]).lower()
    assert "salesforce" not in names
    assert "snowflake" not in names


def test_policy_drives_status_and_config() -> None:
    policy = load_policy()
    by_id = {r["id"]: r for r in ig.compute_integrations_overview()["integrations"]}
    for tool_id, row in by_id.items():
        tp = policy.tool(tool_id)
        if not tp.allow:
            assert row["status"] == "error"
        elif tp.requires_confirmation:
            assert row["status"] == "warning"
        # the guard contract is surfaced in the detail config rows
        labels = {r["label"]: r["value"] for r in row["detail"]["config_rows"]}
        assert labels["Appels max / tour"] == str(tp.max_calls_per_turn)
        assert labels["Confirmation requise"] == ("Oui" if tp.requires_confirmation else "Non")


def test_audit_scan_folds_only_tool_allow_rules() -> None:
    scan = ig._Scan()
    decisions = [
        {
            "policy_rule": "tool.account_balance.allow",
            "decision": "allow",
            "occurred_at": NOW.isoformat(),
        },
        {
            "policy_rule": "tool.account_balance.allow",
            "decision": "deny",
            "occurred_at": NOW.isoformat(),
        },
        {"policy_rule": "prompt_injection.deny_patterns", "decision": "deny"},  # ignored
    ]
    for d in decisions:
        ig._record(scan, d, NOW)
    stat = scan.stat("account_balance")
    assert stat.decisions == 2
    assert stat.denials == 1
    assert scan.stat("prompt_injection").decisions == 0  # non-tool rule skipped


def test_kpis_count_real_tool_facts() -> None:
    policy = load_policy()
    kpis = {k["key"]: k["value"] for k in ig.compute_integrations_overview()["kpis"]}
    assert kpis["tools"] == str(len(ig._TOOLS))
    assert kpis["allowed"] == str(sum(1 for t in ig._TOOLS if policy.tool(t["id"]).allow))


def test_distributions_are_real() -> None:
    payload = ig.compute_integrations_overview()
    # category donut sums to the tool count
    assert sum(s["count"] for s in payload["by_type"]) == len(ig._TOOLS)
    # per-tool call panel carries a human label and is sorted desc by calls
    pcts = [e["pct"] for e in payload["by_env"]]
    assert pcts == sorted(pcts, reverse=True)
    assert all(e["label"] for e in payload["by_env"])
