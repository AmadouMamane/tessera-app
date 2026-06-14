"""Roles & access cockpit overview (page #18).

Composes the "Rôles & accès" overview: the access posture (users, roles, groups,
active access, pending requests, SoD violations, inactive accounts), the role
catalogue table, the selected-role detail (members, permission distribution,
access scope) and the governance panels (top roles, access by resource, pending
requests, SoD violations).

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_access_overview"]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_access_overview() -> dict[str, object]:
    """Return the full Roles & access overview payload.

    Returns:
        A JSON-serialisable mapping with the access posture KPIs, the role table,
        the selected-role detail and the governance panels.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("users", "342", "+12 ce mois", [318, 324, 329, 333, 337, 340, 342]),
        _kpi("roles", "28", "+2", [24, 25, 26, 26, 27, 28, 28]),
        _kpi("groups", "15", "+1", [13, 13, 14, 14, 15, 15, 15]),
        _kpi("active_access", "1 842", "+27%", [1400, 1500, 1600, 1680, 1740, 1800, 1842]),
        _kpi("pending", "27", "demandes", [18, 20, 22, 24, 25, 26, 27]),
        _kpi("sod_violations", "5", "actives", [8, 7, 7, 6, 6, 5, 5]),
        _kpi("inactive", "14", ">90 jours", [18, 17, 16, 16, 15, 15, 14]),
    ]

    roles = [
        {
            "id": "ROLE-001",
            "name": "Platform Admin",
            "type": "systeme",
            "description": "Administration complète de la plateforme",
            "users": 3,
            "groups": 1,
            "permissions": 142,
            "scope": "Globale",
            "environment": "Tous",
            "modified": "11/06/2026 09:12",
            "status": "active",
        },
        {
            "id": "ROLE-002",
            "name": "Security Administrator",
            "type": "systeme",
            "description": "Gestion des risques, garde-fous, accès et conformité",
            "users": 5,
            "groups": 2,
            "permissions": 86,
            "scope": "Globale",
            "environment": "Tous",
            "modified": "11/06/2026 08:54",
            "status": "active",
        },
        {
            "id": "ROLE-003",
            "name": "Compliance Officer",
            "type": "metier",
            "description": "Supervision conformité, preuves et audits",
            "users": 12,
            "groups": 3,
            "permissions": 54,
            "scope": "Globale",
            "environment": "Tous",
            "modified": "10/06/2026 16:33",
            "status": "active",
        },
        {
            "id": "ROLE-004",
            "name": "AI Quality Engineer",
            "type": "metier",
            "description": "Évaluation et curation des jeux de test",
            "users": 18,
            "groups": 2,
            "permissions": 47,
            "scope": "Prod",
            "environment": "Prod",
            "modified": "10/06/2026 11:20",
            "status": "active",
        },
        {
            "id": "ROLE-005",
            "name": "Auditor (read-only)",
            "type": "metier",
            "description": "Lecture seule sur les journaux et preuves",
            "users": 9,
            "groups": 1,
            "permissions": 22,
            "scope": "Globale",
            "environment": "Tous",
            "modified": "09/06/2026 14:02",
            "status": "active",
        },
        {
            "id": "ROLE-006",
            "name": "Data Steward",
            "type": "metier",
            "description": "Gouvernance des sources et de la mémoire",
            "users": 7,
            "groups": 2,
            "permissions": 38,
            "scope": "Prod",
            "environment": "Prod",
            "modified": "08/06/2026 10:41",
            "status": "active",
        },
        {
            "id": "ROLE-007",
            "name": "Legacy Operator",
            "type": "systeme",
            "description": "Rôle hérité — en cours de dépréciation",
            "users": 2,
            "groups": 0,
            "permissions": 31,
            "scope": "Preprod",
            "environment": "Preprod",
            "modified": "02/06/2026 09:27",
            "status": "deprecated",
        },
    ]

    selected = {
        "id": "ROLE-002",
        "name": "Security Administrator",
        "type": "systeme",
        "scope": "Globale",
        "description": (
            "Gestion des risques, garde-fous, accès et conformité sur l'ensemble de la plateforme."
        ),
        "owner": "alice (AI Quality Team)",
        "created": "05/04/2026 10:12",
        "modified": "11/06/2026 08:54 par bob",
        "status": "active",
        "environment": "Tous",
        "members": [
            {"name": "alice", "team": "AI Quality Team", "status": "active"},
            {"name": "bob", "team": "AI Quality Team", "status": "active"},
            {"name": "carla", "team": "AI Quality Team", "status": "active"},
            {"name": "dave", "team": "Data Platform", "status": "active"},
            {"name": "eve", "team": "Compliance Team", "status": "active"},
        ],
        "permission_dist": [
            {"key": "full", "count": 32, "pct": 37, "color": "#60a5fa"},
            {"key": "partial", "count": 41, "pct": 48, "color": "#a78bfa"},
            {"key": "readonly", "count": 9, "pct": 10, "color": "#34d399"},
            {"key": "none", "count": 4, "pct": 3, "color": "#64748b"},
        ],
        "access_scope": [
            {"key": "data", "count": 42, "pct": 43, "color": "#60a5fa"},
            {"key": "guardrails", "count": 21, "pct": 22, "color": "#f87171"},
            {"key": "compliance", "count": 14, "pct": 15, "color": "#a78bfa"},
            {"key": "audit", "count": 9, "pct": 10, "color": "#34d399"},
            {"key": "system", "count": 9, "pct": 10, "color": "#fbbf24"},
        ],
    }

    top_roles = [
        {"name": "AI Quality Engineer", "value": 18, "label": "18 accès"},
        {"name": "Compliance Officer", "value": 12, "label": "12 accès"},
        {"name": "Auditor (read-only)", "value": 9, "label": "9 accès"},
        {"name": "Data Steward", "value": 7, "label": "7 accès"},
        {"name": "Security Administrator", "value": 5, "label": "5 accès"},
    ]

    access_by_resource = [
        {"key": "data", "count": 642, "pct": 35, "color": "#60a5fa"},
        {"key": "guardrails", "count": 384, "pct": 21, "color": "#f87171"},
        {"key": "compliance", "count": 312, "pct": 17, "color": "#a78bfa"},
        {"key": "audit", "count": 268, "pct": 15, "color": "#34d399"},
        {"key": "system", "count": 236, "pct": 12, "color": "#fbbf24"},
    ]

    pending_requests = [
        {"user": "frank", "role": "AI Quality Engineer", "since": "21 min", "risk": "low"},
        {"user": "grace", "role": "Compliance Officer", "since": "1 h 05", "risk": "medium"},
        {"user": "heidi", "role": "Platform Admin", "since": "2 h 40", "risk": "high"},
    ]

    sod_violations = [
        {"user": "ivan", "conflict": "Auditor + Data Steward", "severity": "high"},
        {"user": "judy", "conflict": "Compliance + Platform Admin", "severity": "high"},
        {"user": "mallory", "conflict": "Operator + Auditor", "severity": "medium"},
    ]

    inactive_accounts = [
        {"user": "oscar", "last_seen": "il y a 124 j", "role": "Auditor (read-only)"},
        {"user": "peggy", "last_seen": "il y a 98 j", "role": "Data Steward"},
        {"user": "trent", "last_seen": "il y a 92 j", "role": "Legacy Operator"},
    ]

    return {
        "generated_at": now.isoformat(),
        "total_roles": 28,
        "page_size": 7,
        "kpis": kpis,
        "roles": roles,
        "selected": selected,
        "top_roles": top_roles,
        "access_by_resource": access_by_resource,
        "pending_requests": pending_requests,
        "sod_violations": sod_violations,
        "inactive_accounts": inactive_accounts,
        "footer": {"total": 28, "source": "YAML · Git"},
    }
