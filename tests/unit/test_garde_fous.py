"""Unit tests for the Garde-fous payload assembly (no file, no audit I/O).

Exercise :func:`tessera.observability.agent_garde_fous._assemble` and its
helpers with a synthetic compiled policy, a synthetic audit scan and a chain
status: localization (fr/de/en), real firing stats, decisions-desc sort, the
durable enable/disable state, derived KPIs/coverage and the chain watch item.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from tessera.guard.audit import ChainStatus
from tessera.guard.decisions import ArgumentRule, Policy, ToolPolicy
from tessera.observability import agent_garde_fous as g

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _policy() -> Policy:
    return Policy(
        version=1,
        tools={
            "card_block": ToolPolicy(
                name="card_block",
                allow=True,
                requires_confirmation=True,
                max_calls_per_turn=1,
                arguments={
                    "customer_id": ArgumentRule(pattern=re.compile("x"), redact_in_audit=True),
                    "reason": ArgumentRule(pattern=re.compile("y"), redact_in_audit=False),
                },
            ),
            "account_balance": ToolPolicy(
                name="account_balance", allow=True, max_calls_per_turn=2, arguments={}
            ),
        },
        prompt_injection_deny=tuple(re.compile(p) for p in ("a", "b", "c", "d")),
        prompt_injection_transforms=(),
        pii_patterns=tuple(re.compile(p) for p in ("x", "y")),
    )


def _scan() -> g._AuditScan:
    scan = g._AuditScan(total=100, denials=80, total_24h=12, denials_24h=10)
    scan.per_rule["prompt_injection.deny_patterns"] = g._RuleStat(
        decisions=80, denials=80, last_fired=NOW - timedelta(hours=2), c24=10, cprev=5
    )
    scan.per_rule["tool.account_balance.allow"] = g._RuleStat(
        decisions=20, denials=0, last_fired=NOW - timedelta(hours=3), c24=2
    )
    return scan


def _chain(*, verified: bool = True, broken_at: int | None = None) -> ChainStatus:
    return ChainStatus(verified=verified, length=100, broken_at=broken_at)


def _assemble(state: dict | None = None, lang: str = "fr") -> dict:
    return g._assemble(
        _policy(),
        _scan(),
        _chain(),
        state or {},
        NOW - timedelta(days=2),
        lang,
        now=NOW,
    )


def test_fmt_int_groups_thousands_with_ascii_space() -> None:
    assert g._fmt_int(15484) == "15 484"
    assert g._fmt_int(80) == "80"


def test_fmt_pct_uses_comma() -> None:
    assert g._fmt_pct(80.0) == "80,0 %"


def test_t_fallback_to_french() -> None:
    assert g._t(g._CATEGORY["securite"], "fr") == "Sécurité"
    assert g._t(g._CATEGORY["securite"], "de") == "Sicherheit"
    assert g._t(g._CATEGORY["securite"], "xx") == "Sécurité"  # unknown -> fr


def test_rows_count_and_sorted_by_decisions_desc() -> None:
    payload = _assemble()
    rows = payload["table"]["rows"]
    assert len(rows) == len(g._RULES) == 9
    decisions = [r["decisions"] for r in rows]
    assert decisions == sorted(decisions, reverse=True)
    assert rows[0]["key"] == "prompt_injection.deny_patterns"
    assert rows[0]["decisions"] == 80


def test_kpis_are_derived_from_the_scan() -> None:
    kpis = {k["key"]: k for k in _assemble()["kpis"]}
    assert kpis["rules"]["value"] == "9"
    assert kpis["categories"]["value"] == "4 / 4"
    assert kpis["block"]["value"] == "80,0 %"  # 80/100
    assert kpis["incidents"]["value"] == "80"
    assert kpis["falsepos"]["value"] == "-"  # unsourced -> dash
    assert kpis["decisions"]["value"] == "100"


def test_activity_share_is_real_fraction_of_total() -> None:
    rows = {r["key"]: r for r in _assemble()["table"]["rows"]}
    assert rows["prompt_injection.deny_patterns"]["coverage"] == 80  # 80/100
    assert rows["tool.account_balance.allow"]["coverage"] == 20  # 20/100


def test_never_fired_rule_marked_off_tone() -> None:
    rows = {r["key"]: r for r in _assemble()["table"]["rows"]}
    pii = rows["pii.redact_patterns"]
    assert pii["decisions"] == 0
    assert pii["test_tone"] == "off"


def test_disabled_rule_drops_active_count_and_coverage() -> None:
    state = {"tool.account_balance.allow": {"enabled": False}}
    payload = _assemble(state)
    rows = {r["key"]: r for r in payload["table"]["rows"]}
    assert rows["tool.account_balance.allow"]["status_tone"] == "off"
    kpis = {k["key"]: k for k in payload["kpis"]}
    assert kpis["rules"]["value"] == "8"  # 9 - 1 disabled
    cov = {c["label"]: c for c in payload["coverage"]["items"]}
    # Tools has 5 rules; one disabled -> 80%.
    assert cov["Outils"]["pct"] == 80


def test_tool_config_reads_real_policy() -> None:
    details = {d["key"]: d for d in _assemble()["details"]}
    cfg = {c["label"]: c["value"] for c in details["tool.card_block.allow"]["config"]}
    assert cfg["Confirmation requise"] == "Oui"
    assert cfg["Appels max / tour"] == "1"
    assert cfg["Arguments valides"] == "2"
    assert cfg["Arguments masques (audit)"] == "1"  # only customer_id redacts


def test_injection_config_counts_real_patterns() -> None:
    details = {d["key"]: d for d in _assemble()["details"]}
    cfg = {c["label"]: c["value"] for c in details["prompt_injection.deny_patterns"]["config"]}
    assert cfg["Motifs de refus"] == "4"
    assert cfg["Transformations"] == "0"


def test_broken_chain_surfaces_a_critical_watch_item() -> None:
    payload = g._assemble(
        _policy(),
        _scan(),
        _chain(verified=False, broken_at=42),
        {},
        NOW - timedelta(days=2),
        "fr",
        now=NOW,
    )
    tones = [it["tone"] for it in payload["watch"]["items"]]
    assert "crit" in tones


def test_localization_de_labels() -> None:
    payload = _assemble(lang="de")
    assert payload["kpis"][0]["label"] == "Aktive Regeln"
    assert payload["table"]["rows"][0]["name"] == "Prompt-Injection - Blockieren"


def test_details_tabs_have_three_sections() -> None:
    detail = _assemble()["details"][0]
    assert len(detail["tabs"]) == 3
    assert detail["enabled"] is True
