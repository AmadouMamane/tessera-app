"""Inbox / "À traiter" cockpit overview (page #24).

Composes the "À traiter" overview: the queue posture (items to process, urgent,
SLA-at-risk, overdue, assigned-to-me, resolved-today, average handling time,
resolution rate), the task queue, the by-type distribution and the SLA buckets.

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_inbox_overview"]

_TYPE_COLOR = {
    "conversation": "#60a5fa",
    "incident": "#f87171",
    "alert": "#fbbf24",
    "approval": "#a78bfa",
    "access": "#34d399",
    "other": "#64748b",
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


def compute_inbox_overview() -> dict[str, object]:
    """Return the full Inbox / À traiter overview payload.

    Returns:
        A JSON-serialisable mapping with the queue posture KPIs, the task queue,
        the by-type distribution, the SLA buckets and the recent activity.
    """
    now = datetime.now(UTC)

    rail = {
        "period": "24h",
        "sla": "Temps réel",
        "updated": "11/06/2026 10:42:15",
        "compare": "Ce matin (08:00)",
    }

    kpis = [
        _kpi("total", "23", "+18%", False, [16, 18, 19, 20, 21, 22, 23]),
        _kpi("urgent", "6", "+33%", False, [3, 4, 4, 5, 5, 6, 6]),
        _kpi("sla_2h", "4", "+100%", False, [1, 2, 2, 3, 3, 4, 4]),
        _kpi("overdue", "3", "+50%", False, [1, 1, 2, 2, 2, 3, 3]),
        _kpi("assigned", "9", "+11%", True, [7, 8, 8, 8, 9, 9, 9]),
        _kpi("resolved", "18", "+22%", True, [12, 13, 14, 15, 16, 17, 18]),
        _kpi("avg_time", "1h 42m", "+12%", False, [88, 92, 96, 98, 100, 102, 102]),
        _kpi("resolution_rate", "92%", "+3 pts", True, [86, 87, 88, 89, 90, 91, 92]),
    ]

    items = [
        {
            "id": "TSK-1042",
            "priority": "urgent",
            "type": "incident",
            "title": "Régression qualité détectée en production",
            "source": "Auto-page",
            "assignee": "M. Engineer",
            "sla": "18 min",
            "sla_tone": "crit",
            "due": "11/06 11:00",
            "status": "todo",
        },
        {
            "id": "TSK-1041",
            "priority": "urgent",
            "type": "alert",
            "title": "Fuite PII potentielle — mémoire",
            "source": "Guard",
            "assignee": "A. Privacy",
            "sla": "24 min",
            "sla_tone": "crit",
            "due": "11/06 11:06",
            "status": "todo",
        },
        {
            "id": "TSK-1039",
            "priority": "high",
            "type": "approval",
            "title": "Approbation purge mémoire RGPD",
            "source": "Workflow",
            "assignee": "Moi",
            "sla": "1 h 05",
            "sla_tone": "warn",
            "due": "11/06 11:47",
            "status": "in_progress",
        },
        {
            "id": "TSK-1037",
            "priority": "high",
            "type": "conversation",
            "title": "Escalade conversation client — litige",
            "source": "Assistant",
            "assignee": "DevRel",
            "sla": "1 h 40",
            "sla_tone": "warn",
            "due": "11/06 12:22",
            "status": "todo",
        },
        {
            "id": "TSK-1035",
            "priority": "medium",
            "type": "access",
            "title": "Demande d'accès — rôle Compliance",
            "source": "IAM",
            "assignee": "Moi",
            "sla": "3 h 10",
            "sla_tone": "ok",
            "due": "11/06 13:52",
            "status": "waiting",
        },
        {
            "id": "TSK-1033",
            "priority": "medium",
            "type": "conversation",
            "title": "Réponse langue dégradée à vérifier",
            "source": "Eval",
            "assignee": "S. SysAdmin",
            "sla": "4 h 20",
            "sla_tone": "ok",
            "due": "11/06 15:02",
            "status": "todo",
        },
        {
            "id": "TSK-1031",
            "priority": "low",
            "type": "incident",
            "title": "Conformité Art. 50 — divulgation manquante",
            "source": "Compliance",
            "assignee": "A. Compliance",
            "sla": "1 j",
            "sla_tone": "ok",
            "due": "12/06 10:00",
            "status": "in_progress",
        },
        {
            "id": "TSK-1028",
            "priority": "medium",
            "type": "approval",
            "title": "Validation lot de curation CUR-042",
            "source": "Curation",
            "assignee": "Moi",
            "sla": "6 h",
            "sla_tone": "ok",
            "due": "11/06 16:42",
            "status": "todo",
        },
        {
            "id": "TSK-1024",
            "priority": "low",
            "type": "other",
            "title": "Revue trimestrielle des accès",
            "source": "IAM",
            "assignee": "—",
            "sla": "2 j",
            "sla_tone": "ok",
            "due": "13/06 10:00",
            "status": "waiting",
        },
        {
            "id": "TSK-1019",
            "priority": "high",
            "type": "alert",
            "title": "Budget coût hebdo dépassé",
            "source": "FinOps",
            "assignee": "dave",
            "sla": "2 h 30",
            "sla_tone": "warn",
            "due": "11/06 13:12",
            "status": "todo",
        },
    ]

    by_type = [
        {"key": "conversation", "count": 9, "pct": 39, "color": _TYPE_COLOR["conversation"]},
        {"key": "incident", "count": 6, "pct": 26, "color": _TYPE_COLOR["incident"]},
        {"key": "alert", "count": 4, "pct": 17, "color": _TYPE_COLOR["alert"]},
        {"key": "approval", "count": 2, "pct": 9, "color": _TYPE_COLOR["approval"]},
        {"key": "access", "count": 1, "pct": 4, "color": _TYPE_COLOR["access"]},
        {"key": "other", "count": 1, "pct": 4, "color": _TYPE_COLOR["other"]},
    ]

    sla_buckets = [
        {"key": "overdue", "count": 3, "color": "#f87171"},
        {"key": "lt2h", "count": 4, "color": "#fbbf24"},
        {"key": "h2_8", "count": 7, "color": "#fbbf24"},
        {"key": "gt8h", "count": 9, "color": "#34d399"},
    ]

    recent_activity = [
        {"time": "10:41", "actor": "M. Engineer", "action": "a résolu TSK-1040"},
        {"time": "10:38", "actor": "A. Privacy", "action": "a pris TSK-1041"},
        {"time": "10:32", "actor": "Moi", "action": "a approuvé TSK-1036"},
        {"time": "10:21", "actor": "Auto-escalade", "action": "a escaladé TSK-1042"},
        {"time": "10:05", "actor": "DevRel", "action": "a commenté TSK-1037"},
    ]

    return {
        "generated_at": now.isoformat(),
        "rail": rail,
        "kpis": kpis,
        "items": items,
        "total_items": 23,
        "by_type": by_type,
        "by_type_total": 23,
        "sla_buckets": sla_buckets,
        "recent_activity": recent_activity,
        "footer": {"total": 23, "source": "File d'attente · temps réel"},
    }
