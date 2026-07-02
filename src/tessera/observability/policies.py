"""Policies & guardrails cockpit overview (page #16-policies).

Composes the "Policies & garde-fous" overview. The page has a REAL governance
core and a demonstration subsystem:

* **REAL:** the active policies table is the compiled guard policy
  (``guard/policy.yaml`` via :func:`tessera.guard.decisions.load_policy`) — one
  row per enforced rule family / tool, keyed by the **policy_rule id the guard
  actually emits** so rows join to logged decisions; the posture KPIs and the
  runtime-guardrail gauges are derived from the audit **ledger** (the real
  allow / deny / transform decisions through the read-seam); the version rail
  carries the real policy version + ``policy.yaml`` mtime; the footer chain
  status is a live :func:`verify_active_ledger`.
* **DEMONSTRATION (``policy_versioning`` synthetic signal):** the impact
  simulator and the multi-actor approval workflow describe a policy-versioning
  subsystem this build does not implement (``policy.yaml`` is a single
  Git-managed file). Their zones stay a deterministic fixture, flagged in the
  frontend. Metrics with no real source (false positives) render ``—``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tessera.guard.decisions import load_policy
from tessera.guard.ledger_store import read_ledger_entries, verify_active_ledger
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import get_settings

__all__ = ["compute_policies_overview"]

# Localized free-text (fr, de, en). Versions/dates/ids/enum keys verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "pol_injection": ("Anti prompt-injection", "Anti-Prompt-Injection", "Anti prompt-injection"),
    "pol_pii": (
        "Rédaction PII (transformation)",
        "PII-Redaktion (Transformation)",
        "PII redaction (transform)",
    ),
    "pol_mem_write": (
        "Gouvernance écriture mémoire",
        "Governance Speicher-Schreiben",
        "Memory write governance",
    ),
    "pol_mem_read": (
        "Gouvernance lecture mémoire",
        "Governance Speicher-Lesen",
        "Memory read governance",
    ),
    "pol_tool": ("Outil", "Tool", "Tool"),
    "author_git": ("policy.yaml (Git)", "policy.yaml (Git)", "policy.yaml (Git)"),
    "diff_title": (
        "contenu actif (aucune version antérieure)",
        "aktiver Inhalt (keine Vorversion)",
        "active content (no prior version)",
    ),
    "chain_intact": ("Chaîne d'audit intacte", "Audit-Kette intakt", "Audit chain intact"),
    "chain_broken": (
        "Chaîne d'audit rompue à l'entrée {n}",
        "Audit-Kette gebrochen bei Eintrag {n}",
        "Audit chain broken at entry {n}",
    ),
    "chain_entries": ("{n} entrées vérifiées", "{n} Eintraege verifiziert", "{n} entries verified"),
}
_IMPACT_METRIC: dict[str, tuple[str, str, str]] = {
    "violations": ("Violations", "Verstoesse", "Violations"),
    "false_positives": ("Faux positifs", "Falsch-Positive", "False positives"),
    "injection": ("Injection coverage", "Injection-Abdeckung", "Injection coverage"),
    "pii": ("PII blocked", "PII blockiert", "PII blocked"),
    "tool": ("Tool denials", "Tool-Ablehnungen", "Tool denials"),
}


def _idx(lang: str) -> int:
    return _LANG_IDX.get(lang, 0)


def _t(key: str, lang: str) -> str:
    return _TR[key][_idx(lang)]


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


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


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class _LedgerScan:
    """One pass over the real guard ledger: decision tallies + per-day denies."""

    __slots__ = ("day_denies", "denies_24h", "per_rule", "totals")

    def __init__(self, entries: list[dict[str, Any]], now: datetime) -> None:
        self.totals: dict[str, int] = {"allow": 0, "deny": 0, "transform": 0}
        self.per_rule: dict[str, dict[str, int]] = {}
        day_keys = [(now - timedelta(days=d)).date().isoformat() for d in range(6, -1, -1)]
        self.day_denies: dict[str, int] = dict.fromkeys(day_keys, 0)
        self.denies_24h = 0
        cutoff_24h = now - timedelta(hours=24)
        for entry in entries:
            if entry.get("type") != "tessera.guard.audit":
                continue
            decisions = entry.get("decisions")
            if not isinstance(decisions, list):
                continue
            for dec in decisions:
                if not isinstance(dec, dict):
                    continue
                kind = str(dec.get("decision", ""))
                if kind not in self.totals:
                    continue
                self.totals[kind] += 1
                rule = str(dec.get("policy_rule", "") or "")
                tally = self.per_rule.setdefault(rule, {"allow": 0, "deny": 0, "transform": 0})
                tally[kind] += 1
                if kind != "deny":
                    continue
                when = _parse_dt(dec.get("occurred_at")) or _parse_dt(entry.get("occurred_at"))
                if when is None:
                    continue
                if when >= cutoff_24h:
                    self.denies_24h += 1
                key = when.date().isoformat()
                if key in self.day_denies:
                    self.day_denies[key] += 1

    def rule_count(self, prefix: str, kind: str) -> int:
        return sum(
            tally.get(kind, 0) for rule, tally in self.per_rule.items() if rule.startswith(prefix)
        )


def compute_policies_overview(lang: str = "fr") -> dict[str, object]:
    """Return the Policies & guardrails overview payload (real core + flagged demo).

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the real version rail, posture KPIs,
        active policies (from the compiled guard policy), the active-content
        summary, the runtime guardrails (from the ledger) — plus the flagged
        impact-simulator fixture and the sensitive governance actions.
    """
    lang = _norm_lang(lang)
    li = _idx(lang)
    now = datetime.now(UTC)
    settings = get_settings()

    policy = load_policy()
    scan = _LedgerScan(read_ledger_entries(), now)
    chain = verify_active_ledger()

    version = f"v{policy.version}"
    try:
        mtime = datetime.fromtimestamp(settings.guard.policy_path.stat().st_mtime, tz=UTC)
        mtime_label = mtime.strftime("%d/%m/%Y %H:%M")
    except OSError:
        mtime_label = "—"

    env_label = settings.environment

    # ── REAL version rail: the single Git-managed policy version ────────────
    version_timeline = [{"version": version, "status": "active", "date": mtime_label}]
    version_history = [
        {
            "version": version,
            "datetime": mtime_label,
            "author": _t("author_git", lang),
            "approver": "—",
            "status": "active",
        }
    ]
    version_detail = {
        "version": version,
        "effective_from": mtime_label,
        "commit": "—",
        "author": _t("author_git", lang),
        "approver": "—",
        "scope": f"{env_label} · Crédit Aurore",
    }

    # ── REAL active policies: one row per enforced rule, keyed by the real
    # policy_rule id the guard emits (joins to the logged decisions) ─────────
    tool_label = _t("pol_tool", lang)
    active_policies: list[dict[str, object]] = [
        {
            "id": "prompt_injection.deny_patterns",
            "name": _t("pol_injection", lang),
            "type": "injection",
            "action": "deny",
            "scope": env_label,
            "version": version,
            "changed_by": mtime_label,
            "approved_by": "—",
            "status": "active",
        },
        {
            "id": "pii.patterns",
            "name": _t("pol_pii", lang),
            "type": "pii",
            "action": "warn",
            "scope": env_label,
            "version": version,
            "changed_by": mtime_label,
            "approved_by": "—",
            "status": "active",
        },
        {
            "id": "memory.write.governance",
            "name": _t("pol_mem_write", lang),
            "type": "memory",
            "action": "deny",
            "scope": env_label,
            "version": version,
            "changed_by": mtime_label,
            "approved_by": "—",
            "status": "active",
        },
        {
            "id": "memory.read.governance",
            "name": _t("pol_mem_read", lang),
            "type": "memory",
            "action": "allow",
            "scope": env_label,
            "version": version,
            "changed_by": mtime_label,
            "approved_by": "—",
            "status": "active",
        },
    ]
    for name in sorted(policy.tools):
        tool = policy.tools[name]
        action = "deny" if not tool.allow else ("warn" if tool.requires_confirmation else "allow")
        active_policies.append(
            {
                "id": f"tool.{name}.allow",
                "name": f"{tool_label} · {name}",
                "type": "tool",
                "action": action,
                "scope": env_label,
                "version": version,
                "changed_by": mtime_label,
                "approved_by": "—",
                "status": "active",
            }
        )

    n_rules = len(active_policies)
    n_blocking = sum(1 for p in active_policies if p["action"] == "deny")

    # ── REAL posture KPIs (ledger-derived where a source exists, else "—") ───
    min_series_for_delta = 2
    deny_series = list(scan.day_denies.values())
    delta_24h = deny_series[-1] - deny_series[-2] if len(deny_series) >= min_series_for_delta else 0
    kpis = [
        _kpi("active_policies", str(n_rules), "0", True, [n_rules] * 7),
        _kpi("blocking_guardrails", str(n_blocking), "0", True, [n_blocking] * 7),
        _kpi(
            "violations_blocked",
            _fmt_int(scan.denies_24h),
            f"{delta_24h:+d}" if delta_24h else "0",
            True,
            deny_series,
        ),
        _kpi("false_positives", "—", "—", False, [0] * 7),
        _kpi("pending_versions", "0", "0", True, [0] * 7),
        _kpi("exceptions", "—", "—", False, [0] * 7),
    ]

    # ── REAL active-content summary in the diff slot (no prior version) ─────
    comp_tools_allowed = sum(1 for t in policy.tools.values() if t.allow)
    comp_confirm = sum(1 for t in policy.tools.values() if t.requires_confirmation)
    comp_denied = sum(1 for t in policy.tools.values() if not t.allow)
    diff = {
        "title": f"{version} — {_t('diff_title', lang)}",
        "lines": [
            {"type": "context", "text": f"version: {policy.version}"},
            {"type": "context", "text": "prompt_injection:"},
            {"type": "context", "text": f"  deny_patterns: {len(policy.prompt_injection_deny)}"},
            {
                "type": "context",
                "text": f"  transforms: {len(policy.prompt_injection_transforms)}",
            },
            {"type": "context", "text": f"pii_patterns: {len(policy.pii_patterns)}"},
            {
                "type": "context",
                "text": (
                    f"tools: {len(policy.tools)} "
                    f"(allow {comp_tools_allowed}, confirm {comp_confirm}, deny {comp_denied})"
                ),
            },
            {"type": "context", "text": "memory: {read, write} governance"},
        ],
    }

    # ── REAL runtime guardrails from the ledger decision tallies ────────────
    n_total = sum(scan.totals.values()) or 1
    deny_share = scan.totals["deny"] / n_total
    transform_share = scan.totals["transform"] / n_total
    injection_denies = scan.rule_count("prompt_injection", "deny")
    tool_denies = scan.rule_count("tool.", "deny")
    mem_allow = scan.rule_count("memory.", "allow")
    mem_total = sum(
        sum(tally.values()) for rule, tally in scan.per_rule.items() if rule.startswith("memory.")
    )
    mem_share = mem_allow / mem_total if mem_total else 1.0
    guardrails = [
        {
            "key": "deny_policies",
            "value": f"{deny_share * 100:.1f}%",
            "pct": round(deny_share * 100),
        },
        {
            "key": "pii_detection",
            "value": f"{transform_share * 100:.1f}%",
            "pct": round(transform_share * 100),
        },
        {
            "key": "attacks_blocked",
            "value": _fmt_int(injection_denies),
            "pct": round(injection_denies / (scan.totals["deny"] or 1) * 100),
        },
        {
            "key": "tool_denials",
            "value": _fmt_int(tool_denies),
            "pct": round(tool_denies / (scan.totals["deny"] or 1) * 100),
        },
        {
            "key": "pii_blocked",
            "value": _fmt_int(scan.totals["transform"]),
            "pct": round(min(transform_share * 100, 100)),
        },
        {
            "key": "memory_approved",
            "value": f"{mem_share * 100:.0f}%",
            "pct": round(mem_share * 100),
        },
    ]

    # ── DEMONSTRATION: impact simulator (policy_versioning subsystem) ───────
    impact = [
        {
            "metric": _IMPACT_METRIC["violations"][li],
            "baseline": "1 284",
            "candidate": "1 296",
            "delta": "+12 (+0,9%)",
            "tone": "warn",
        },
        {
            "metric": _IMPACT_METRIC["false_positives"][li],
            "baseline": "2,3%",
            "candidate": "3,8%",
            "delta": "+1,3 pt",
            "tone": "bad",
        },
        {
            "metric": _IMPACT_METRIC["injection"][li],
            "baseline": "4,1%",
            "candidate": "3,7%",
            "delta": "-0,4 pt",
            "tone": "ok",
        },
        {
            "metric": _IMPACT_METRIC["pii"][li],
            "baseline": "95%",
            "candidate": "95%",
            "delta": "0",
            "tone": "neutral",
        },
        {
            "metric": _IMPACT_METRIC["tool"][li],
            "baseline": "862",
            "candidate": "921",
            "delta": "+59 (+6,9%)",
            "tone": "warn",
        },
    ]

    sensitive_actions = [
        {"key": "rollback", "role": "Admin+"},
        {"key": "force_activation", "role": "Admin+"},
        {"key": "disable", "role": "Admin+"},
        {"key": "delete_draft", "role": "Admin+"},
    ]

    quick_links = ["audit_journal", "export_siem", "evidence_pack", "release_control"]

    if chain.verified:
        chain_label = f"{_t('chain_intact', lang)} · {_t('chain_entries', lang)}".format(
            n=_fmt_int(chain.length)
        )
    else:
        chain_label = _t("chain_broken", lang).format(n=chain.broken_at)

    return {
        "generated_at": now.isoformat(),
        "active_version": version,
        "compare_to": "—",
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
        "footer": {"source": "guard/policy.yaml · Git", "chain": chain_label},
    }
