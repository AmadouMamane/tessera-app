"""Automations cockpit overview (page #13).

Composes the "Automations" overview: the automation posture (active rules,
24h executions, success rate, approvals, guardrail blocks, sensitive actions,
auto-MTTR), the rule catalogue, the execution pipeline funnel, the breakdowns
(by type, by environment), the execution journal, the pending approvals, the
most-used guardrails, the 30-day performance and savings, and the governance /
release context.

The dataset is a deterministic reference fixture (no live automation store in
this build); values are stable across calls so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_automations_overview"]

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline fixture string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


_TYPE_COLOR = {
    "qualite": "#60a5fa",
    "securite": "#f87171",
    "conformite": "#a78bfa",
    "memoire": "#34d399",
    "release": "#fbbf24",
    "cout": "#f472b6",
}
_ENV_COLOR = {"prod": "#34d399", "preprod": "#60a5fa", "staging": "#fbbf24", "dev": "#f472b6"}


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


def compute_automations_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Automations overview payload.

    Args:
        lang: Locale (fr / de / en) for the free-text fixture fields the
            frontend renders verbatim (rule names, triggers, actions, scopes,
            incident labels, journal entries, governance scopes). All other
            chrome is localized in the frontend via next-intl keys.

    Returns:
        A JSON-serialisable mapping with the automation posture KPIs, the rule
        catalogue, the execution pipeline, the type / environment breakdowns,
        the execution journal, the pending approvals, the most-used guardrails,
        the performance / savings trends and the governance & release context.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("active", "28", "+3", True, [22, 23, 24, 25, 26, 27, 28]),
        _kpi("executions", "1 284", "+11%", True, [980, 1040, 1100, 1150, 1200, 1240, 1284]),
        _kpi("success_rate", "96.8%", "+2.4 pts", True, [93, 94, 94, 95, 95, 96, 97]),
        _kpi("approvals", "9", "+1", True, [6, 7, 7, 8, 8, 9, 9]),
        _kpi("blocked", "17", "+2", False, [11, 12, 13, 14, 15, 16, 17]),
        _kpi("sensitive", "6", "-1", True, [8, 8, 7, 7, 6, 7, 6]),
        _kpi("mttr", "3m 42s", "-18 s", False, [5, 5, 4, 4, 4, 4, 3]),
    ]

    sys_role = _loc(lang, "Système", "System", "System")
    sec_role = _loc(lang, "Sécurité", "Sicherheit", "Security")
    catalogue = [
        {
            "name": _loc(
                lang,
                "Gel des releases après régression qualité",
                "Releases bei Qualitaetsregression einfrieren",
                "Freeze releases after quality regression",
            ),
            "trigger": _loc(
                lang, "Gate FAIL (qualité)", "Gate FAIL (Qualitaet)", "Gate FAIL (quality)"
            ),
            "action": _loc(lang, "Geler release", "Release einfrieren", "Freeze release"),
            "scope": "Release",
            "mode": "auto",
            "last_run": "12/05/25 11:54",
            "success": "100% (7/7)",
            "role": "Operator+",
            "status": "active",
        },
        {
            "name": _loc(
                lang,
                "Lancer red-team après incident",
                "Red-Team nach Vorfall starten",
                "Launch red-team after incident",
            ),
            "trigger": _loc(lang, "Incident critique", "Kritischer Vorfall", "Critical incident"),
            "action": _loc(lang, "Lancer red-team", "Red-Team starten", "Launch red-team"),
            "scope": sys_role,
            "mode": "auto",
            "last_run": "12/05/25 11:09",
            "success": "99% (88/89)",
            "role": sys_role,
            "status": "active",
        },
        {
            "name": _loc(
                lang,
                "Purge mémoire RGPD sur demande validée",
                "DSGVO-Speicherbereinigung bei validierter Anfrage",
                "GDPR memory purge on approved request",
            ),
            "trigger": _loc(lang, "Demande RGPD", "DSGVO-Anfrage", "GDPR request"),
            "action": _loc(lang, "Purger mémoire", "Speicher bereinigen", "Purge memory"),
            "scope": _loc(lang, "Mémoire", "Speicher", "Memory"),
            "mode": "approb",
            "last_run": "12/05/25 10:58",
            "success": "95% (40/42)",
            "role": sys_role,
            "status": "active",
        },
        {
            "name": _loc(
                lang,
                "Générer evidence pack après Gate FAIL",
                "Evidence-Pack nach Gate FAIL erzeugen",
                "Generate evidence pack after Gate FAIL",
            ),
            "trigger": "Gate FAIL",
            "action": _loc(
                lang,
                "Générer evidence pack",
                "Evidence-Pack erzeugen",
                "Generate evidence pack",
            ),
            "scope": _loc(lang, "Conformité", "Konformitaet", "Compliance"),
            "mode": "auto",
            "last_run": "12/05/25 10:41",
            "success": "98% (51/52)",
            "role": sys_role,
            "status": "active",
        },
        {
            "name": _loc(
                lang,
                "Escalade humaine sur PII leakage",
                "Menschliche Eskalation bei PII-Leak",
                "Human escalation on PII leakage",
            ),
            "trigger": _loc(lang, "Détection PII", "PII-Erkennung", "PII detection"),
            "action": _loc(
                lang, "Notifier sécurité", "Sicherheit benachrichtigen", "Notify security"
            ),
            "scope": sec_role,
            "mode": "approb",
            "last_run": "12/05/25 11:54",
            "success": "88% (15/17)",
            "role": sec_role,
            "status": "active",
        },
        {
            "name": _loc(
                lang,
                "Geler budget si dépassement hebdo",
                "Budget bei woechentlicher Ueberschreitung einfrieren",
                "Freeze budget on weekly overrun",
            ),
            "trigger": "Budget cap",
            "action": _loc(lang, "Geler budget", "Budget einfrieren", "Freeze budget"),
            "scope": _loc(lang, "Coût", "Kosten", "Cost"),
            "mode": "auto",
            "last_run": "12/05/25 09:27",
            "success": "92% (12/13)",
            "role": "Admin",
            "status": "paused",
        },
    ]

    recent_incidents = [
        {
            "severity": "critique",
            "id": "AUTO-014",
            "label": _loc(
                lang,
                "Triage réglage détecté en production",
                "Triage-Anpassung in Produktion erkannt",
                "Triage tuning detected in production",
            ),
            "time": "11:52",
        },
        {
            "severity": "eleve",
            "id": "AUTO-022",
            "label": _loc(
                lang,
                "Gate conformité Art. 50 FAIL",
                "Konformitaets-Gate Art. 50 FAIL",
                "Compliance gate Art. 50 FAIL",
            ),
            "time": "11:47",
        },
        {
            "severity": "eleve",
            "id": "AUTO-017",
            "label": _loc(
                lang,
                "Qualité dégradée — Precision < 0.8",
                "Qualitaet verschlechtert — Precision < 0.8",
                "Quality degraded — Precision < 0.8",
            ),
            "time": "10:58",
        },
        {
            "severity": "moyen",
            "id": "AUTO-019",
            "label": _loc(
                lang,
                "Budget coût dépassé (hebdo)",
                "Kostenbudget ueberschritten (woechentlich)",
                "Cost budget exceeded (weekly)",
            ),
            "time": "10:41",
        },
        {
            "severity": "faible",
            "id": "AUTO-011",
            "label": _loc(
                lang,
                "Mémoire obsolète détectée",
                "Veralteter Speicher erkannt",
                "Stale memory detected",
            ),
            "time": "09:27",
        },
    ]

    pipeline = [
        {"key": "trigger", "count": "1 284", "pct": 100},
        {"key": "evaluation", "count": "1 221", "pct": 95.1},
        {"key": "guardrail", "count": "1 148", "pct": 89.5},
        {"key": "approval", "count": "312", "pct": 24.3},
        {"key": "execution", "count": "1 042", "pct": 81.2},
        {"key": "proof", "count": "1 006", "pct": 78.4},
    ]

    by_type = [
        {"key": "qualite", "count": 9, "pct": 32, "color": _TYPE_COLOR["qualite"]},
        {"key": "securite", "count": 6, "pct": 21, "color": _TYPE_COLOR["securite"]},
        {"key": "conformite", "count": 5, "pct": 18, "color": _TYPE_COLOR["conformite"]},
        {"key": "memoire", "count": 3, "pct": 11, "color": _TYPE_COLOR["memoire"]},
        {"key": "release", "count": 3, "pct": 11, "color": _TYPE_COLOR["release"]},
        {"key": "cout", "count": 2, "pct": 7, "color": _TYPE_COLOR["cout"]},
    ]

    by_env = [
        {"key": "prod", "count": 812, "color": _ENV_COLOR["prod"]},
        {"key": "preprod", "count": 246, "color": _ENV_COLOR["preprod"]},
        {"key": "staging", "count": 152, "color": _ENV_COLOR["staging"]},
        {"key": "dev", "count": 74, "color": _ENV_COLOR["dev"]},
    ]

    journal = [
        {
            "time": "12/05 11:54",
            "automation": _loc(
                lang,
                "Escalade humaine sur PII leakage",
                "Menschliche Eskalation bei PII-Leak",
                "Human escalation on PII leakage",
            ),
            "trigger": _loc(lang, "Détection PII", "PII-Erkennung", "PII detection"),
            "actor": "M. Engineer",
            "evidence": "ev_8b6a1c",
            "duration": "0,8 s",
            "result": "approb",
        },
        {
            "time": "12/05 11:38",
            "automation": _loc(
                lang,
                "Lancer red-team après incident",
                "Red-Team nach Vorfall starten",
                "Launch red-team after incident",
            ),
            "trigger": _loc(lang, "Incident critique", "Kritischer Vorfall", "Critical incident"),
            "actor": sys_role,
            "evidence": "ev_3f12d2e",
            "duration": "12 s",
            "result": "success",
        },
        {
            "time": "12/05 11:21",
            "automation": _loc(
                lang,
                "Gel des releases après régression",
                "Releases bei Regression einfrieren",
                "Freeze releases after regression",
            ),
            "trigger": "Gate FAIL",
            "actor": "S. SysAdmin",
            "evidence": "ev_77c0b1",
            "duration": "1,2 s",
            "result": "success",
        },
        {
            "time": "12/05 10:58",
            "automation": _loc(
                lang,
                "Purge mémoire RGPD",
                "DSGVO-Speicherbereinigung",
                "GDPR memory purge",
            ),
            "trigger": _loc(lang, "Demande RGPD", "DSGVO-Anfrage", "GDPR request"),
            "actor": "Admin",
            "evidence": "ev_92ad11",
            "duration": "3,4 s",
            "result": "approb",
        },
        {
            "time": "12/05 10:41",
            "automation": _loc(
                lang,
                "Générer evidence pack",
                "Evidence-Pack erzeugen",
                "Generate evidence pack",
            ),
            "trigger": "Gate FAIL",
            "actor": sys_role,
            "evidence": "ev_b21f0a",
            "duration": "0,6 s",
            "result": "success",
        },
    ]

    approvals = [
        {
            "name": _loc(
                lang,
                "Purge mémoire RGPD sur demande validée",
                "DSGVO-Speicherbereinigung bei validierter Anfrage",
                "GDPR memory purge on approved request",
            ),
            "since": "21 min",
            "role": "Admin",
        },
        {
            "name": _loc(
                lang,
                "Escalade humaine sur PII leakage",
                "Menschliche Eskalation bei PII-Leak",
                "Human escalation on PII leakage",
            ),
            "since": "8 min",
            "role": sec_role,
        },
        {
            "name": _loc(
                lang,
                "Déployer modèle en production",
                "Modell in Produktion bereitstellen",
                "Deploy model to production",
            ),
            "since": "3 min",
            "role": "Admin",
        },
    ]

    guardrails = [
        {"key": "pii_guard", "count": 228, "pct": 25},
        {"key": "release_gate", "count": 194, "pct": 21},
        {"key": "policy_check", "count": 152, "pct": 17},
        {"key": "dual_control", "count": 96, "pct": 11},
        {"key": "budget_cap", "count": 64, "pct": 7},
    ]

    performance = {
        "labels": ["03/05", "05/05", "07/05", "09/05", "11/05"],
        "success": [94, 95, 95, 96, 97],
        "average": [88, 89, 90, 91, 92],
    }

    savings = [
        {"key": "tickets", "value": "152", "delta": "+24%"},
        {"key": "minutes", "value": "2 148 min", "delta": "+18%"},
        {"key": "executions", "value": "21 436", "delta": "+11%"},
        {"key": "evidences", "value": "1 006", "delta": "+9%"},
    ]

    context = {
        "version": "v1.7.0",
        "last_modified": "12/05/25 11:10",
        "author": "A. Compliance",
        "branch": "main",
        "scope": "Prod",
    }

    governance = {
        "dual_control": True,
        "roles": [
            {
                "mode": "Admin",
                "scope": _loc(
                    lang,
                    "Actions sensibles / système",
                    "Sensible Aktionen / System",
                    "Sensitive actions / system",
                ),
            },
            {
                "mode": "Compliance+",
                "scope": _loc(
                    lang,
                    "Conformité / RGPD / preuve",
                    "Konformitaet / DSGVO / Nachweis",
                    "Compliance / GDPR / evidence",
                ),
            },
            {
                "mode": "Operator+",
                "scope": _loc(
                    lang, "Qualité / release", "Qualitaet / Release", "Quality / release"
                ),
            },
        ],
        "default_scope": _loc(
            lang,
            "Système entier (prod, preprod, staging, dev)",
            "Gesamtes System (prod, preprod, staging, dev)",
            "Entire system (prod, preprod, staging, dev)",
        ),
    }

    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "catalogue": catalogue,
        "recent_incidents": recent_incidents,
        "pipeline": pipeline,
        "completion": "78.4%",
        "by_type": by_type,
        "by_type_total": 28,
        "by_env": by_env,
        "journal": journal,
        "approvals": approvals,
        "guardrails": guardrails,
        "performance": performance,
        "savings": savings,
        "context": context,
        "governance": governance,
        "footer": {
            "source": "YAML · Git",
            "certified": _loc(
                lang,
                "Certifié par Tessera Verified",
                "Zertifiziert von Tessera Verified",
                "Certified by Tessera Verified",
            ),
        },
    }
