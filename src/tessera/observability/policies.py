"""Policies & guardrails cockpit overview (page #16-policies).

Composes the "Policies & garde-fous" overview: the version timeline, the policy
posture (active policies, blocking guardrails, blocked violations, false
positives, pending versions, exceptions), the critical active policies, the
version history, the YAML diff, the runtime guardrails, the impact simulator and
the sensitive governance actions.

The dataset is a deterministic reference fixture (policies ship as governance
artifacts in this build); values are stable across calls so the page never
"dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability.knowledge import _LANG_IDX, _norm_lang

__all__ = ["compute_policies_overview"]

# Localized free-text (fr, de, en). Versions/dates/authors/YAML/enum keys verbatim.
_POL_NAME: dict[str, tuple[str, str, str]] = {
    "POL-PII-001": ("Blocage PII strict", "Strikte PII-Sperre", "Strict PII block"),
    "POL-INJ-002": ("Anti prompt-injection", "Anti-Prompt-Injection", "Anti prompt-injection"),
    "POL-TOOL-002": ("Gouvernance outils", "Tool-Governance", "Tool governance"),
    "POL-MEM-001": ("TTL mémoire & purge", "Speicher-TTL & Purge", "Memory TTL & purge"),
    "POL-REG-001": ("Allégations régulées", "Regulierte Aussagen", "Regulated claims"),
    "POL-LOC-001": ("Localisation contenu", "Inhaltslokalisierung", "Content localization"),
}
_IMPACT_METRIC: dict[str, tuple[str, str, str]] = {
    "violations": ("Violations", "Verstoesse", "Violations"),
    "false_positives": ("Faux positifs", "Falsch-Positive", "False positives"),
    "injection": ("Injection coverage", "Injection-Abdeckung", "Injection coverage"),
    "pii": ("PII blocked", "PII blockiert", "PII blocked"),
    "tool": ("Tool denials", "Tool-Ablehnungen", "Tool denials"),
}
_CHAIN_INTACT = ("Chaîne d'audit intacte", "Audit-Kette intakt", "Audit chain intact")


def _idx(lang: str) -> int:
    return _LANG_IDX.get(lang, 0)


def _kpi(
    key: str, value: str, delta_label: str, good_is_up: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "delta_label": delta_label,
        "good_is_up": good_is_up,
        "series": series,
    }


def compute_policies_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Policies & guardrails overview payload.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the version timeline, posture KPIs,
        critical active policies, version history, YAML diff, runtime guardrails,
        impact simulator and sensitive actions.
    """
    lang = _norm_lang(lang)
    li = _idx(lang)
    now = datetime.now(UTC)

    version_timeline = [
        {"version": "v1.9", "status": "draft", "date": "01/06 09:12"},
        {"version": "v2.0-rc1", "status": "approved", "date": "03/06 16:30"},
        {"version": "v2.0", "status": "approved", "date": "05/06 11:05"},
        {"version": "v2.1-rc1", "status": "approved", "date": "07/06 14:20"},
        {"version": "v2.1", "status": "active", "date": "10/06 14:20"},
        {"version": "v2.2-draft", "status": "canary", "date": "11/06 09:50"},
    ]

    kpis = [
        _kpi("active_policies", "42", "+3", True, [38, 39, 40, 40, 41, 42, 42]),
        _kpi("blocking_guardrails", "18", "+1", True, [15, 16, 16, 17, 17, 18, 18]),
        _kpi(
            "violations_blocked", "1 284", "+14%", True, [980, 1040, 1100, 1150, 1200, 1240, 1284]
        ),
        _kpi("false_positives", "2,3%", "+0.4 pt", False, [18, 19, 20, 21, 21, 22, 23]),
        _kpi("pending_versions", "2", "0", True, [2, 2, 1, 2, 2, 2, 2]),
        _kpi("exceptions", "7", "-1", False, [9, 9, 8, 8, 7, 8, 7]),
    ]

    active_policies = [
        {
            "id": "POL-PII-001",
            "name": "Blocage PII strict",
            "type": "pii",
            "action": "deny",
            "scope": "Prod",
            "version": "v2.1",
            "changed_by": "Amadou D.",
            "approved_by": "Sophie L.",
            "status": "active",
        },
        {
            "id": "POL-INJ-002",
            "name": "Anti prompt-injection",
            "type": "injection",
            "action": "deny",
            "scope": "Prod",
            "version": "v2.1",
            "changed_by": "Sophie L.",
            "approved_by": "Admin",
            "status": "active",
        },
        {
            "id": "POL-TOOL-002",
            "name": "Gouvernance outils",
            "type": "tool",
            "action": "allow",
            "scope": "Prod",
            "version": "v2.1",
            "changed_by": "Marc T.",
            "approved_by": "Sophie L.",
            "status": "active",
        },
        {
            "id": "POL-MEM-001",
            "name": "TTL mémoire & purge",
            "type": "memory",
            "action": "warn",
            "scope": "Prod",
            "version": "v2.0",
            "changed_by": "A. Privacy",
            "approved_by": "Sophie L.",
            "status": "active",
        },
        {
            "id": "POL-REG-001",
            "name": "Allégations régulées",
            "type": "regulatory",
            "action": "warn",
            "scope": "FR",
            "version": "v2.1",
            "changed_by": "Julie M.",
            "approved_by": "Compliance",
            "status": "active",
        },
        {
            "id": "POL-LOC-001",
            "name": "Localisation contenu",
            "type": "regulatory",
            "action": "deny",
            "scope": "EU",
            "version": "v2.1",
            "changed_by": "Julie M.",
            "approved_by": "Marc T.",
            "status": "active",
        },
    ]

    version_history = [
        {
            "version": "v2.2-draft",
            "datetime": "11/06 09:50",
            "author": "Sophie L.",
            "approver": "—",
            "status": "canary",
        },
        {
            "version": "v2.1",
            "datetime": "10/06 14:20",
            "author": "Amadou D.",
            "approver": "Sophie L.",
            "status": "active",
        },
        {
            "version": "v2.1-rc1",
            "datetime": "07/06 14:20",
            "author": "Amadou D.",
            "approver": "Sophie L.",
            "status": "approved",
        },
        {
            "version": "v2.0",
            "datetime": "05/06 11:05",
            "author": "Sophie L.",
            "approver": "Admin",
            "status": "archived",
        },
        {
            "version": "v2.0-rc1",
            "datetime": "03/06 16:30",
            "author": "Marc T.",
            "approver": "Sophie L.",
            "status": "archived",
        },
    ]

    diff = {
        "title": "v2.1 vs v2.0",
        "lines": [
            {"type": "context", "text": "pii_detection:"},
            {"type": "removed", "text": "  threshold: 0.90"},
            {"type": "added", "text": "  threshold: 0.97"},
            {"type": "context", "text": "  mode: deny"},
            {"type": "context", "text": "injection:"},
            {"type": "removed", "text": "  patterns: [v2.0_set]"},
            {"type": "added", "text": "  patterns: [v2.1_set, jailbreak_rag]"},
            {"type": "context", "text": "memory_write:"},
            {"type": "added", "text": "  ttl_days: 30"},
        ],
    }

    guardrails = [
        {"key": "deny_policies", "value": "97.1%", "pct": 97},
        {"key": "pii_detection", "value": "2.4%", "pct": 24},
        {"key": "attacks_blocked", "value": "1 284", "pct": 88},
        {"key": "tool_denials", "value": "347", "pct": 42},
        {"key": "pii_blocked", "value": "862", "pct": 64},
        {"key": "memory_approved", "value": "73%", "pct": 73},
    ]

    impact = [
        {
            "metric": "Violations",
            "baseline": "1 284",
            "candidate": "1 296",
            "delta": "+12 (+0,9%)",
            "tone": "warn",
        },
        {
            "metric": "Faux positifs",
            "baseline": "2,3%",
            "candidate": "3,8%",
            "delta": "+1,3 pt",
            "tone": "bad",
        },
        {
            "metric": "Injection coverage",
            "baseline": "4,1%",
            "candidate": "3,7%",
            "delta": "-0,4 pt",
            "tone": "ok",
        },
        {
            "metric": "PII blocked",
            "baseline": "95%",
            "candidate": "95%",
            "delta": "0",
            "tone": "neutral",
        },
        {
            "metric": "Tool denials",
            "baseline": "862",
            "candidate": "921",
            "delta": "+59 (+6,9%)",
            "tone": "warn",
        },
    ]

    version_detail = {
        "version": "v2.1",
        "effective_from": "10/06/2026 14:20",
        "commit": "7f3a9c2",
        "author": "Amadou D.",
        "approver": "Sophie L. (Compliance+)",
        "scope": "Prod · Crédit Aurore",
    }

    sensitive_actions = [
        {"key": "rollback", "role": "Admin+"},
        {"key": "force_activation", "role": "Admin+"},
        {"key": "disable", "role": "Admin+"},
        {"key": "delete_draft", "role": "Admin+"},
    ]

    quick_links = ["audit_journal", "export_siem", "evidence_pack", "release_control"]

    # Localize the free-text labels (names + impact metrics) by stable key.
    for pol in active_policies:
        name = _POL_NAME.get(str(pol["id"]))
        if name:
            pol["name"] = name[li]
    for key, row in zip(
        ("violations", "false_positives", "injection", "pii", "tool"), impact, strict=False
    ):
        row["metric"] = _IMPACT_METRIC[key][li]

    return {
        "generated_at": now.isoformat(),
        "active_version": "v2.1",
        "compare_to": "v2.0",
        "version_timeline": version_timeline,
        "version_detail": version_detail,
        "kpis": kpis,
        "active_policies": active_policies,
        "version_history": version_history,
        "diff": diff,
        "guardrails": guardrails,
        "impact": impact,
        "sensitive_actions": sensitive_actions,
        "quick_links": quick_links,
        "footer": {"source": "YAML · Git", "chain": _CHAIN_INTACT[li]},
    }
