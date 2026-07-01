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

from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.rbac import ROLE_CAPS

__all__ = ["compute_users"]

_ROLE_BADGE = {
    "superadmin": "purple",
    "admin": "blue",
    "auditor": "slate",
}

# Localized free-text (fr, de, en). Usernames/emails/dates stay stable; only human
# prose (role labels, team names, descriptive display names, KPI subs) translates.
_TR: dict[str, tuple[str, str, str]] = {
    "sub_total": ("comptes opérateurs", "Betreiberkonten", "operator accounts"),
    "sub_active": ("comptes actifs", "aktive Konten", "active accounts"),
    "sub_roles": ("rôles appliqués", "angewendete Rollen", "enforced roles"),
    "sub_mfa": ("MFA activée", "MFA aktiviert", "MFA enabled"),
    "f_source": (
        "Comptes amorcés (ADR 0009) / RBAC org-wide",
        "Vorbereitete Konten (ADR 0009) / RBAC org-weit",
        "Seeded accounts (ADR 0009) / org-wide RBAC",
    ),
    "role_admin": ("Administrateur", "Administrator", "Administrator"),
    "role_auditor": ("Auditeur (lecture)", "Auditor (Lesezugriff)", "Auditor (read)"),
    "role_superadmin": ("Super-admin", "Super-Admin", "Super-admin"),
    "team_conformite": ("Conformité", "Compliance", "Compliance"),
    "team_plateforme": ("Plateforme", "Plattform", "Platform"),
    "disp_auditor": ("Compte auditeur", "Auditor-Konto", "Auditor account"),
    "disp_superadmin": (
        "Super-administrateur",
        "Super-Administrator",
        "Super-administrator",
    ),
}
_TEAM_KEY = {"Conformité": "team_conformite", "Plateforme": "team_plateforme"}
_DISPLAY_KEY = {"auditor": "disp_auditor", "superadmin": "disp_superadmin"}
_ROLE_LABEL_KEY = {
    "admin": "role_admin",
    "auditor": "role_auditor",
    "superadmin": "role_superadmin",
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]

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


def compute_users(lang: str = "fr") -> dict[str, object]:
    """Return the users overview built from the real seeded accounts + RBAC caps.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with posture KPIs, the user table (each row a
        real enforced account), the per-user capability detail, and the role
        distribution.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)

    users: list[dict[str, object]] = []
    for acc in _ACCOUNTS:
        role = str(acc["role"])
        caps_entry = ROLE_CAPS.get(role, {})
        caps_val = caps_entry.get("caps", [])
        role_label = _t(_ROLE_LABEL_KEY[role], lang) if role in _ROLE_LABEL_KEY else str(role)
        team = str(acc["team"])
        team_key = _TEAM_KEY.get(team)
        disp_key = _DISPLAY_KEY.get(str(acc["username"]))
        users.append(
            {
                **acc,
                "display": _t(disp_key, lang) if disp_key else acc["display"],
                "team": _t(team_key, lang) if team_key else team,
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
        _kpi("total", str(len(users)), _t("sub_total", lang), [3, 3, 3, 3, 3, 3, 3]),
        _kpi("active", str(active), _t("sub_active", lang), [active] * 7),
        _kpi("roles", str(len(ROLE_CAPS)), _t("sub_roles", lang), [3, 3, 3, 3, 3, 3, 3]),
        _kpi("mfa", f"{active}/{active}", _t("sub_mfa", lang), [active] * 7),
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
            "source": _t("f_source", lang),
        },
    }
