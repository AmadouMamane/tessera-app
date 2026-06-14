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


def compute_automations_overview() -> dict[str, object]:
    """Return the full Automations overview payload.

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

    catalogue = [
        {
            "name": "Gel des releases après régression qualité",
            "trigger": "Gate FAIL (qualité)",
            "action": "Geler release",
            "scope": "Release",
            "mode": "auto",
            "last_run": "12/05/25 11:54",
            "success": "100% (7/7)",
            "role": "Operator+",
            "status": "active",
        },
        {
            "name": "Lancer red-team après incident",
            "trigger": "Incident critique",
            "action": "Lancer red-team",
            "scope": "Système",
            "mode": "auto",
            "last_run": "12/05/25 11:09",
            "success": "99% (88/89)",
            "role": "Système",
            "status": "active",
        },
        {
            "name": "Purge mémoire RGPD sur demande validée",
            "trigger": "Demande RGPD",
            "action": "Purger mémoire",
            "scope": "Mémoire",
            "mode": "approb",
            "last_run": "12/05/25 10:58",
            "success": "95% (40/42)",
            "role": "Système",
            "status": "active",
        },
        {
            "name": "Générer evidence pack après Gate FAIL",
            "trigger": "Gate FAIL",
            "action": "Générer evidence pack",
            "scope": "Conformité",
            "mode": "auto",
            "last_run": "12/05/25 10:41",
            "success": "98% (51/52)",
            "role": "Système",
            "status": "active",
        },
        {
            "name": "Escalade humaine sur PII leakage",
            "trigger": "Détection PII",
            "action": "Notifier sécurité",
            "scope": "Sécurité",
            "mode": "approb",
            "last_run": "12/05/25 11:54",
            "success": "88% (15/17)",
            "role": "Sécurité",
            "status": "active",
        },
        {
            "name": "Geler budget si dépassement hebdo",
            "trigger": "Budget cap",
            "action": "Geler budget",
            "scope": "Coût",
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
            "label": "Triage réglage détecté en production",
            "time": "11:52",
        },
        {
            "severity": "eleve",
            "id": "AUTO-022",
            "label": "Gate conformité Art. 50 FAIL",
            "time": "11:47",
        },
        {
            "severity": "eleve",
            "id": "AUTO-017",
            "label": "Qualité dégradée — Precision < 0.8",
            "time": "10:58",
        },
        {
            "severity": "moyen",
            "id": "AUTO-019",
            "label": "Budget coût dépassé (hebdo)",
            "time": "10:41",
        },
        {
            "severity": "faible",
            "id": "AUTO-011",
            "label": "Mémoire obsolète détectée",
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
            "automation": "Escalade humaine sur PII leakage",
            "trigger": "Détection PII",
            "actor": "M. Engineer",
            "evidence": "ev_8b6a1c",
            "duration": "0,8 s",
            "result": "approb",
        },
        {
            "time": "12/05 11:38",
            "automation": "Lancer red-team après incident",
            "trigger": "Incident critique",
            "actor": "Système",
            "evidence": "ev_3f12d2e",
            "duration": "12 s",
            "result": "success",
        },
        {
            "time": "12/05 11:21",
            "automation": "Gel des releases après régression",
            "trigger": "Gate FAIL",
            "actor": "S. SysAdmin",
            "evidence": "ev_77c0b1",
            "duration": "1,2 s",
            "result": "success",
        },
        {
            "time": "12/05 10:58",
            "automation": "Purge mémoire RGPD",
            "trigger": "Demande RGPD",
            "actor": "Admin",
            "evidence": "ev_92ad11",
            "duration": "3,4 s",
            "result": "approb",
        },
        {
            "time": "12/05 10:41",
            "automation": "Générer evidence pack",
            "trigger": "Gate FAIL",
            "actor": "Système",
            "evidence": "ev_b21f0a",
            "duration": "0,6 s",
            "result": "success",
        },
    ]

    approvals = [
        {"name": "Purge mémoire RGPD sur demande validée", "since": "21 min", "role": "Admin"},
        {"name": "Escalade humaine sur PII leakage", "since": "8 min", "role": "Sécurité"},
        {"name": "Déployer modèle en production", "since": "3 min", "role": "Admin"},
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
            {"mode": "Admin", "scope": "Actions sensibles / système"},
            {"mode": "Compliance+", "scope": "Conformité / RGPD / preuve"},
            {"mode": "Operator+", "scope": "Qualité / release"},
        ],
        "default_scope": "Système entier (prod, preprod, staging, dev)",
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
        "footer": {"source": "YAML · Git", "certified": "Certifié par Tessera Verified"},
    }
