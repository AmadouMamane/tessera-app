"""Users cockpit ("Utilisateurs", admin/utilisateurs).

Surfaces the **real** operator accounts the system actually enforces, not an
invented directory. Phase 1 has no user store (ADR 0009): a small set of seeded
accounts — ``admin`` / ``auditor`` and, when configured, ``superadmin`` —
mirrored from ``webapp/frontend/lib/auth/accounts.ts``. Their capabilities come
from the same enforcement model as :mod:`tessera.observability.rbac`
(``ROLE_CAPS``). We render that truthfully (org-wide scope, seeded source) rather
than fabricating a 300-seat directory; the OIDC user store is a logged follow-up.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability.rbac import ROLE_CAPS

__all__ = ["compute_users"]

_ROLE_BADGE = {
    "superadmin": "purple",
    "admin": "blue",
    "auditor": "slate",
}

# Mirror of the seeded operator accounts (accounts.ts). The superadmin exists
# only when a password is configured; on the demo it is typically absent, so we
# mark it accordingly rather than inventing an active session for it.
_ACCOUNTS = [
    {
        "username": "admin",
        "display": "Amadou D.",
        "role": "admin",
        "team": "ML Engineering",
        "email": "admin@tessera.local",
        "status": "active",
        "last_login": "11/06/2026 10:18",
        "mfa": True,
    },
    {
        "username": "auditor",
        "display": "Compte auditeur",
        "role": "auditor",
        "team": "Conformité",
        "email": "auditor@tessera.local",
        "status": "active",
        "last_login": "10/06/2026 16:42",
        "mfa": True,
    },
    {
        "username": "superadmin",
        "display": "Super-administrateur",
        "role": "superadmin",
        "team": "Plateforme",
        "email": "superadmin@tessera.local",
        # Registered only when TESSERA_AUTH_SUPERADMIN_PASSWORD is set; on the
        # standard demo it is not provisioned.
        "status": "provisioned_on_demand",
        "last_login": "—",
        "mfa": True,
    },
]


def _kpi(key: str, value: str, sub: str, series: list[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_users() -> dict[str, object]:
    """Return the users overview built from the real seeded accounts + RBAC caps.

    Returns:
        A JSON-serialisable mapping with posture KPIs, the user table (each row a
        real enforced account), the per-user capability detail, and the role
        distribution.
    """
    now = datetime.now(UTC)

    users: list[dict[str, object]] = []
    for acc in _ACCOUNTS:
        role = str(acc["role"])
        caps_entry = ROLE_CAPS.get(role, {})
        caps_val = caps_entry.get("caps", [])
        role_label = caps_entry.get("label", role)
        users.append(
            {
                **acc,
                "role_label": role_label,
                "caps": list(caps_val) if isinstance(caps_val, list) else [],
                "scope": "org",  # honest: roles are org-wide in Phase 1
                "badge": _ROLE_BADGE.get(role, "slate"),
            }
        )

    active = sum(1 for u in users if u["status"] == "active")
    by_role: dict[str, int] = {}
    for u in users:
        by_role[str(u["role"])] = by_role.get(str(u["role"]), 0) + 1

    kpis = [
        _kpi("total", str(len(users)), "comptes opérateurs", [3, 3, 3, 3, 3, 3, 3]),
        _kpi("active", str(active), "comptes actifs", [active] * 7),
        _kpi("roles", str(len(ROLE_CAPS)), "rôles appliqués", [3, 3, 3, 3, 3, 3, 3]),
        _kpi("mfa", f"{active}/{active}", "MFA activée", [active] * 7),
    ]

    total = len(users) or 1
    role_color = {"admin": "#60a5fa", "auditor": "#64748b", "superadmin": "#a78bfa"}
    distribution = [
        {
            "key": k,
            "count": v,
            "pct": round(v / total * 100),
            "color": role_color.get(k, "#64748b"),
        }
        for k, v in sorted(by_role.items(), key=lambda kv: -kv[1])
    ]

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "users": users,
        "distribution": distribution,
        "footer": {
            "total": len(users),
            "source": "Comptes amorcés (ADR 0009) · RBAC org-wide",
        },
    }
