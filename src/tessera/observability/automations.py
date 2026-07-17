"""Automations cockpit overview (page #13).

The page has a REAL rule/execution core and a demonstration workflow chrome:

* **REAL (from :mod:`tessera.observability.automation_store` — the created
  source):** the catalogue is the code-defined rule set, each rule evaluating a
  real condition against the owned stores (release gate, audit chain,
  low-faithfulness turns, guard deny volume, curation backlog) with a durable
  enabled flag; the execution journal, posture KPIs, pipeline funnel and
  per-day performance derive from the journalled evaluations actually executed
  via ``POST /observability/automations/evaluate``; the guardrail-solicitation
  counts read the audit ledger; the **approval queue** lists the durable
  requests opened by fired ``approb``-mode rules, decided by the governed
  approve endpoint (author = verified assertion). Storeless figures (MTTR
  auto, blocked-by-guardrail) render ``—``.
* **DEMONSTRATION (``automation_workflow`` synthetic signal):** the
  savings/impact tallies describe a ticketing/ROI subsystem this build does
  not implement; that zone stays flagged with honest dashes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tessera.observability._asof import occurred_before
from tessera.observability.automation_store import (
    RULES,
    approvals_as_of,
    list_rule_states,
    load_runs,
    pending_approvals,
    rule_states_as_of,
)
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import get_settings

__all__ = ["compute_automations_overview"]


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


_TYPE_COLOR = {
    "qualite": "#60a5fa",
    "securite": "#f97316",
    "conformite": "#a78bfa",
    "memoire": "#34d399",
    "release": "#fbbf24",
    "cout": "#f472b6",
}
_ENV_COLOR = {"prod": "#34d399", "preprod": "#60a5fa", "staging": "#fbbf24", "dev": "#f472b6"}

# Localized rule copy (name / trigger / action), keyed by rule id.
_RULE_COPY: dict[str, tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]] = {
    "gate_freeze": (
        (
            "Gel release sur gate FAIL",
            "Release-Freeze bei Gate FAIL",
            "Freeze release on gate FAIL",
        ),
        (
            "Dernier run d'éval : gate FAIL",
            "Letzter Eval-Lauf: Gate FAIL",
            "Latest eval run: gate FAIL",
        ),
        ("Recommander le gel de release", "Release-Freeze empfehlen", "Recommend release freeze"),
    ),
    "chain_alert": (
        ("Alerte chaîne d'audit", "Audit-Ketten-Alarm", "Audit-chain alert"),
        (
            "verify_active_ledger : chaîne rompue",
            "verify_active_ledger: Kette gebrochen",
            "verify_active_ledger: chain broken",
        ),
        ("Alerter conformité", "Compliance alarmieren", "Alert compliance"),
    ),
    "low_faith_review": (
        ("Revue fidélité faible", "Review geringe Treue", "Low-faithfulness review"),
        (
            "Tours capturés sous le seuil de fidélité",
            "Erfasste Turns unter Treue-Schwelle",
            "Captured turns below faithfulness threshold",
        ),
        ("Ouvrir une revue qualité", "Qualitaets-Review oeffnen", "Open a quality review"),
    ),
    "deny_spike": (
        ("Pic de refus guard", "Guard-Ablehnungsspitze", "Guard deny spike"),
        (
            "Refus guard 24h au-dessus du seuil",
            "Guard-Denies 24h ueber Schwelle",
            "Guard denies 24h above threshold",
        ),
        ("Notifier l'équipe sécurité", "Sicherheitsteam benachrichtigen", "Notify security team"),
    ),
    "curation_backlog": (
        ("Backlog de curation", "Kurations-Backlog", "Curation backlog"),
        (
            "Candidats en attente au-dessus du seuil",
            "Wartende Kandidaten ueber Schwelle",
            "Pending candidates above threshold",
        ),
        ("Assigner une revue de curation", "Kurations-Review zuweisen", "Assign a curation review"),
    ),
}


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


def _parse_at(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _guardrail_counts() -> list[dict[str, object]]:
    """Real guardrail solicitations from the ledger (deny/transform per family)."""
    try:
        from tessera.guard.ledger_store import read_ledger_entries

        entries = read_ledger_entries()
    except Exception:
        return []
    pii = injection = tools = 0
    for entry in entries:
        if entry.get("type") != "tessera.guard.audit":
            continue
        decisions = entry.get("decisions")
        for dec in decisions if isinstance(decisions, list) else []:
            if not isinstance(dec, dict):
                continue
            rule = str(dec.get("policy_rule", "") or "")
            kind = str(dec.get("decision", ""))
            if rule.startswith("pii") and kind in {"deny", "transform"}:
                pii += 1
            elif rule.startswith("prompt_injection") and kind == "deny":
                injection += 1
            elif rule.startswith("tool.") and kind == "deny":
                tools += 1
    total = (pii + injection + tools) or 1
    rows: list[tuple[str, int]] = [
        ("pii_guard", pii),
        ("policy_check", injection),
        ("release_gate", tools),
    ]
    return [
        {"key": key, "count": count, "pct": round(count / total * 100)}
        for key, count in rows
        if count > 0
    ]


def _posture_kpis(
    now: datetime,
    runs: list[dict[str, object]],
    states: dict[str, bool],
    day_keys: list[str],
    n_ok: int,
    n_approb: int,
) -> tuple[list[dict[str, object]], list[int]]:
    """REAL posture KPIs from the journal (storeless figures render dashes)."""
    cutoff_24h = now - timedelta(hours=24)
    runs_24h = [r for r in runs if (_parse_at(r.get("at")) or now) >= cutoff_24h]
    n_active = sum(1 for enabled in states.values() if enabled)
    n_sensitive = sum(1 for rule in RULES if rule.role.startswith("Admin"))
    day_runs = dict.fromkeys(day_keys, 0)
    for run in runs:
        when = _parse_at(run.get("at"))
        if when and when.date().isoformat() in day_runs:
            day_runs[when.date().isoformat()] += 1
    run_series = list(day_runs.values())
    kpis = [
        _kpi("active", str(n_active), "0", True, [n_active] * 7),
        _kpi("executions", str(len(runs_24h)), "0", True, run_series),
        _kpi(
            "success_rate",
            f"{n_ok / len(runs) * 100:.1f}%" if runs else "—",
            "—",
            True,
            [0] * 7,
        ),
        _kpi("approvals", str(n_approb), "0", True, [n_approb] * 7),
        _kpi("blocked", "—", "—", False, [0] * 7),
        _kpi("sensitive", str(n_sensitive), "0", False, [n_sensitive] * 7),
        _kpi("mttr", "—", "—", True, [0] * 7),
    ]
    return kpis, run_series


def compute_automations_overview(lang: str = "fr", at: str | None = None) -> dict[str, object]:
    """Return the Automations overview payload (real rule core + flagged demo).

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.
        at: Optional ISO instant T (registre §6 — AGIR reads As-of + acts Live).
            When given, every projection folds to T: rule states from the S1
            governance journal, runs and approvals by their own timestamps.
            Mutations are a LIVE-only affair — the reader is the only as-of.

    Returns:
        A JSON-serialisable mapping with the rule catalogue (real definitions +
        durable enabled state + journalled last runs), the execution journal,
        the posture KPIs, funnel, distributions and governance — plus the
        flagged savings fixture. ``as_of`` echoes T (``None`` in Live).
    """
    lang = _norm_lang(lang)
    now = (_parse_at(at) or datetime.now(UTC)) if at else datetime.now(UTC)
    settings = get_settings()
    env = settings.environment

    states = rule_states_as_of(at) if at else list_rule_states()
    runs = [r for r in load_runs() if occurred_before(str(r.get("at", "")), at)]
    by_rule_runs: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_rule_runs.setdefault(str(run.get("rule_id", "")), []).append(run)

    def _last_run_label(rule_id: str) -> str:
        rule_runs = by_rule_runs.get(rule_id, [])
        if not rule_runs:
            return "—"
        when = _parse_at(rule_runs[-1].get("at"))
        return when.strftime("%d/%m %H:%M") if when else "—"

    # ── REAL catalogue: code-defined rules + durable state + journalled runs ─
    catalogue = []
    for rule in RULES:
        name, trigger, action = _RULE_COPY[rule.id]
        rule_runs = by_rule_runs.get(rule.id, [])
        n_runs = len(rule_runs)
        n_fired = sum(1 for r in rule_runs if r.get("fired"))
        catalogue.append(
            {
                "id": rule.id,
                "name": _loc(lang, *name),
                "trigger": _loc(lang, *trigger),
                "action": _loc(lang, *action),
                "scope": env,
                "mode": rule.mode,
                "last_run": _last_run_label(rule.id),
                "success": f"{n_fired}/{n_runs}" if n_runs else "—",
                "role": rule.role,
                "status": "active" if states.get(rule.id, True) else "paused",
            }
        )

    # ── REAL approvals: fired approb-mode rules opened durable requests ──────
    approvals = _pending_approval_rows(lang, at=at)

    n_ok = sum(1 for r in runs if r.get("result") != "error")
    day_keys = [(now - timedelta(days=d)).date().isoformat() for d in range(6, -1, -1)]
    kpis, run_series = _posture_kpis(now, runs, states, day_keys, n_ok, len(approvals))

    # ── REAL feed: the latest fired evaluations ──────────────────────────────
    sev_by_rule = {rule.id: rule.severity for rule in RULES}
    fired_runs = [r for r in reversed(runs) if r.get("fired")]
    recent_incidents = []
    for run in fired_runs[:5]:
        rule_id = str(run.get("rule_id", ""))
        when = _parse_at(run.get("at"))
        copy = _RULE_COPY.get(rule_id)
        recent_incidents.append(
            {
                "severity": sev_by_rule.get(rule_id, "moyen"),
                "id": f"AUTO-{rule_id}",
                "label": _loc(lang, *copy[0]) if copy else rule_id,
                "time": when.strftime("%H:%M") if when else "—",
            }
        )

    # ── REAL funnel from the journal ─────────────────────────────────────────
    n_total = len(runs)
    n_fired_total = sum(1 for r in runs if r.get("fired"))
    n_approb_fired = sum(
        1
        for r in runs
        if r.get("fired")
        and next((ru.mode for ru in RULES if ru.id == r.get("rule_id")), "") == "approb"
    )

    def _pct(part: int) -> float:
        return round(part / n_total * 100, 1) if n_total else 0.0

    pipeline = [
        {"key": "trigger", "count": str(n_total), "pct": 100.0 if n_total else 0.0},
        {"key": "evaluation", "count": str(n_ok), "pct": _pct(n_ok)},
        {"key": "guardrail", "count": str(n_fired_total), "pct": _pct(n_fired_total)},
        {"key": "approval", "count": str(n_approb_fired), "pct": _pct(n_approb_fired)},
        {"key": "execution", "count": str(n_fired_total), "pct": _pct(n_fired_total)},
        {"key": "proof", "count": str(n_total), "pct": 100.0 if n_total else 0.0},
    ]
    completion = f"{_pct(n_ok):.1f}%" if n_total else "—"

    # ── REAL distributions ───────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for rule in RULES:
        type_counts[rule.type] = type_counts.get(rule.type, 0) + 1
    n_rules = len(RULES) or 1
    by_type = [
        {
            "key": key,
            "count": count,
            "pct": round(count / n_rules * 100),
            "color": _TYPE_COLOR.get(key, "#64748b"),
        }
        for key, count in sorted(type_counts.items(), key=lambda kv: -kv[1])
    ]
    by_env = [
        {"key": env, "count": len(runs), "color": _ENV_COLOR.get(env, "#f472b6")},
    ]

    journal = _journal_rows(runs, lang)

    # ── DEMONSTRATION: savings/ROI tallies (automation_workflow) ─────────────
    savings = [
        {"key": "tickets", "value": "—", "delta": "—"},
        {"key": "minutes", "value": "—", "delta": "—"},
        {"key": "executions", "value": str(len(runs)), "delta": "—"},
        {"key": "evidences", "value": "—", "delta": "—"},
    ]

    guardrails = _guardrail_counts()

    performance = {
        "labels": [k[5:] for k in day_keys],
        "success": run_series,
        "average": [0] * len(run_series),
    }

    context = _context_block(lang, env)

    governance = {
        "dual_control": any(rule.mode == "approb" for rule in RULES),
        "roles": [
            {"mode": rule.role, "scope": _loc(lang, *_RULE_COPY[rule.id][0])} for rule in RULES
        ],
        "default_scope": env,
    }

    return {
        "generated_at": now.isoformat(),
        "as_of": at,
        "period_days": 7,
        "updated_at": now.strftime("%H:%M:%S"),
        "kpis": kpis,
        "catalogue": catalogue,
        "recent_incidents": recent_incidents,
        "pipeline": pipeline,
        "completion": completion,
        "by_type": by_type,
        "by_type_total": len(RULES),
        "by_env": by_env,
        "journal": journal,
        "approvals": approvals,
        "guardrails": guardrails,
        "performance": performance,
        "savings": savings,
        "context": context,
        "governance": governance,
        "footer": {
            "source": "automation_store · journal",
            "certified": "—",
        },
    }


def _pending_approval_rows(lang: str, at: str | None = None) -> list[dict[str, object]]:
    """The pending approval requests, live or as they stood at T (localized copy)."""
    rule_by_id = {rule.id: rule for rule in RULES}
    source = (
        [a for a in approvals_as_of(at) if a.get("status") == "pending"]
        if at
        else pending_approvals()
    )
    rows: list[dict[str, object]] = []
    for req in source:
        rid = str(req.get("rule_id", ""))
        req_copy = _RULE_COPY.get(rid)
        when = _parse_at(req.get("requested_at"))
        rows.append(
            {
                "id": str(req.get("id", "")),
                "rule_id": rid,
                "name": _loc(lang, *req_copy[0]) if req_copy else rid,
                "since": when.strftime("%d/%m %H:%M") if when else "—",
                "observed": str(req.get("observed", "")),
                "role": rule_by_id[rid].role if rid in rule_by_id else "—",
            }
        )
    return rows


def _journal_rows(runs: list[dict[str, object]], lang: str) -> list[dict[str, object]]:
    """The real journal rows, newest first (result mapped to the page enum)."""

    def _result_key(run: dict[str, Any]) -> str:
        if run.get("result") == "error":
            return "fail"
        if run.get("fired"):
            rule_mode = next((ru.mode for ru in RULES if ru.id == run.get("rule_id")), "auto")
            return "approb" if rule_mode == "approb" else "success"
        return "success"

    rows: list[dict[str, object]] = []
    for run in list(reversed(runs))[:8]:
        rule_id = str(run.get("rule_id", ""))
        when = _parse_at(run.get("at"))
        copy = _RULE_COPY.get(rule_id)
        rows.append(
            {
                "time": when.strftime("%H:%M:%S") if when else "—",
                "automation": _loc(lang, *copy[0]) if copy else rule_id,
                "trigger": str(run.get("observed", "")),
                "actor": _loc(lang, "Système", "System", "System"),
                "evidence": "—",
                "duration": f"{run.get('duration_ms', 0)} ms",
                "result": _result_key(run),
            }
        )
    return rows


def _context_block(lang: str, env: str) -> dict[str, object]:
    """Real context: the rule-set size + the store module's own mtime."""
    try:
        from pathlib import Path

        import tessera.observability.automation_store as store_mod

        mtime = datetime.fromtimestamp(Path(store_mod.__file__).stat().st_mtime, tz=UTC)
        modified = mtime.strftime("%d/%m/%y %H:%M")
    except OSError:
        modified = "—"
    return {
        "version": f"{len(RULES)} règles" if lang == "fr" else f"{len(RULES)} rules",
        "last_modified": modified,
        "author": "automation_store.py (code)",
        "branch": env,
        "scope": env,
    }
