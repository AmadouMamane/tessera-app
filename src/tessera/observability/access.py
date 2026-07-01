"""Roles & access cockpit overview (page #18, admin/roles-acces).

Surfaces the **real** access model the system actually enforces, not an invented
300-seat directory. The roles come from :data:`tessera.observability.rbac.ROLE_CAPS`
(mirrored from ``lib/auth/session.ts`` — the same caps the auth layer checks); the
accounts are the seeded operator accounts (ADR 0009, mirror of ``accounts.ts``);
the coverage is the real registry agent count.

Like Prompts, this page is **read-only by design**: RBAC roles are defined in code
(``session.ts`` / this module) and changed via PR, so there is no UI mutation — a
"create role" button would be a fake control. The functional axis is therefore real
data + wired search / filter / sort / row-select / nav, not a fabricated store.

Unsourceable slots (access requests, SoD conflicts, inactive sessions) have no
Phase-1 store, so they render honest **empty** states rather than fabricated rows;
the per-account model is 1 role each, so no separation-of-duties conflict can exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.rbac import ROLE_CAPS

__all__ = ["compute_access_overview"]

# Localized free-text (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "team_conformite": ("Conformité", "Compliance", "Compliance"),
    "team_plateforme": ("Plateforme", "Plattform", "Platform"),
    "role_admin": ("Administrateur", "Administrator", "Administrator"),
    "role_auditor": ("Auditeur (lecture)", "Auditor (Lesezugriff)", "Auditor (read)"),
    "role_superadmin": ("Super-admin", "Super-Admin", "Super-admin"),
    "desc_admin": (
        "Administration de la plateforme : cockpit, produit, configuration et release.",
        "Plattform-Administration: Cockpit, Produkt, Konfiguration und Release.",
        "Platform administration: cockpit, product, configuration and release.",
    ),
    "desc_auditor": (
        "Lecture seule sur le cockpit et les journaux d'audit, sans action.",
        "Nur-Lese-Zugriff auf Cockpit und Audit-Logs, ohne Aktion.",
        "Read-only on the cockpit and audit logs, no action.",
    ),
    "desc_superadmin": (
        "Administration complète incluant l'accès aux modèles frontier.",
        "Vollstaendige Administration inkl. Zugriff auf Frontier-Modelle.",
        "Full administration including access to frontier models.",
    ),
    "scope_org": ("Organisation", "Organisation", "Organization"),
    "env_all": ("Tous", "Alle", "All"),
    "owner_code": (
        "Défini dans le code (session.ts)",
        "Im Code definiert (session.ts)",
        "Defined in code (session.ts)",
    ),
    "sub_accounts": ("comptes opérateurs", "Betreiberkonten", "operator accounts"),
    "sub_roles": ("rôles appliqués", "angewendete Rollen", "enforced roles"),
    "sub_caps": ("capacités distinctes", "eindeutige Faehigkeiten", "distinct capabilities"),
    "sub_agents": ("agents couverts (org)", "abgedeckte Agenten (Org)", "agents covered (org)"),
    "sub_active": ("comptes actifs", "aktive Konten", "active accounts"),
    "sub_mfa": ("MFA activée", "MFA aktiviert", "MFA enabled"),
    "caps_label": ("{n} capacités", "{n} Faehigkeiten", "{n} capabilities"),
}
_TEAM_KEY = {"Conformité": "team_conformite", "Plateforme": "team_plateforme"}
_ROLE_LABEL_KEY = {
    "admin": "role_admin",
    "auditor": "role_auditor",
    "superadmin": "role_superadmin",
}
_ROLE_DESC_KEY = {
    "admin": "desc_admin",
    "auditor": "desc_auditor",
    "superadmin": "desc_superadmin",
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


# Mirror of the seeded operator accounts (accounts.ts / users.py). superadmin is
# only registered when TESSERA_AUTH_SUPERADMIN_PASSWORD is set, so it is marked
# provisioned-on-demand rather than counted as an active session.
_ACCOUNTS = [
    {"username": "admin", "team": "ML Engineering", "role": "admin", "active": True, "mfa": True},
    {"username": "auditor", "team": "Conformité", "role": "auditor", "active": True, "mfa": True},
    {
        "username": "superadmin",
        "team": "Plateforme",
        "role": "superadmin",
        "active": False,
        "mfa": True,
    },
]

# Each capability classified by privilege kind (reuses the perm.* i18n labels) and
# mapped to a resource area (reuses the resource.* i18n labels) for the per-role and
# global distributions. Stable keys; the frontend localises them.
_CAP_KIND = {
    "release": "full",
    "modeles_frontier": "full",
    "cockpit": "partial",
    "produit": "partial",
    "configurer": "partial",
    "cockpit_lecture": "readonly",
    "audit_lecture": "readonly",
}
_CAP_AREA = {
    "cockpit": "cockpit",
    "cockpit_lecture": "cockpit",
    "produit": "produit",
    "configurer": "configuration",
    "release": "release",
    "modeles_frontier": "modeles",
    "audit_lecture": "audit",
}
_KIND_COLOR = {"full": "#60a5fa", "partial": "#a78bfa", "readonly": "#34d399", "none": "#64748b"}
_AREA_COLOR = {
    "cockpit": "#60a5fa",
    "produit": "#22d3ee",
    "configuration": "#a78bfa",
    "release": "#f59e0b",
    "modeles": "#f472b6",
    "audit": "#34d399",
}
# Privileged (can mutate) vs read-only roles — the axis the Type filter partitions.
_PRIVILEGED = {"admin", "superadmin"}


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def _slice(key: str, count: int, total: int, color: str) -> dict[str, object]:
    pct = round(count / total * 100) if total else 0
    return {"key": key, "count": count, "pct": pct, "color": color}


def _accounts_for(role_id: str, lang: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for acc in _ACCOUNTS:
        if acc["role"] != role_id:
            continue
        status = "active" if acc["active"] else "provisioned"
        team = str(acc["team"])
        team_key = _TEAM_KEY.get(team)
        out.append(
            {
                "name": str(acc["username"]),
                "team": _t(team_key, lang) if team_key else team,
                "status": status,
            }
        )
    return out


def _role_modified() -> str:
    """Real last-modified of the RBAC source file (dd/mm/YYYY HH:MM)."""
    try:
        mtime = Path(__file__).with_name("rbac.py").stat().st_mtime
        return datetime.fromtimestamp(mtime, UTC).strftime("%d/%m/%Y %H:%M")
    except OSError:
        return "-"


def _perm_dist(caps: list[str]) -> list[dict[str, object]]:
    """Per-role capability breakdown by privilege kind (full/partial/readonly)."""
    counts: dict[str, int] = {}
    for cap in caps:
        kind = _CAP_KIND.get(cap, "none")
        counts[kind] = counts.get(kind, 0) + 1
    total = len(caps) or 1
    order = ["full", "partial", "readonly", "none"]
    return [_slice(k, counts[k], total, _KIND_COLOR[k]) for k in order if counts.get(k)]


def _area_dist(caps: list[str]) -> list[dict[str, object]]:
    """Per-role coverage by resource area."""
    counts: dict[str, int] = {}
    for cap in caps:
        area = _CAP_AREA.get(cap, "cockpit")
        counts[area] = counts.get(area, 0) + 1
    total = len(caps) or 1
    return [
        _slice(area, n, total, _AREA_COLOR.get(area, "#64748b"))
        for area, n in sorted(counts.items(), key=lambda kv: -kv[1])
    ]


@dataclass(frozen=True)
class _RoleFull:
    """A fully-resolved role: the public row fields plus caps + members."""

    id: str
    name: str
    type: str
    description: str
    modified: str
    caps: list[str]
    members: list[dict[str, object]]

    @property
    def users(self) -> int:
        return len(self.members)

    @property
    def permissions(self) -> int:
        return len(self.caps)

    def row(self, lang: str) -> dict[str, object]:
        """The client role row: public fields + per-role detail."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "users": self.users,
            "groups": 0,  # honest: no group store in Phase 1
            "permissions": self.permissions,
            "scope": _t("scope_org", lang),
            "environment": _t("env_all", lang),
            "modified": self.modified,
            "status": "active",
            "caps": self.caps,
            "members": self.members,
            "permission_dist": _perm_dist(self.caps),
            "access_scope": _area_dist(self.caps),
            "owner": _t("owner_code", lang),
            "created": "-",
        }


def _build_role(role_id: str, meta: dict[str, object], modified: str, lang: str) -> _RoleFull:
    caps_raw = meta.get("caps", [])
    caps = [str(c) for c in caps_raw] if isinstance(caps_raw, list) else []
    label_key = _ROLE_LABEL_KEY.get(role_id)
    desc_key = _ROLE_DESC_KEY.get(role_id)
    return _RoleFull(
        id=role_id,
        name=_t(label_key, lang) if label_key else str(meta.get("label", role_id)),
        type="systeme" if role_id in _PRIVILEGED else "metier",
        description=_t(desc_key, lang) if desc_key else "",
        modified=modified,
        caps=caps,
        members=_accounts_for(role_id, lang),
    )


def compute_access_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Roles & access overview, built from the real RBAC model.

    Returns:
        A JSON-serialisable mapping with the access posture KPIs (accounts, roles,
        capabilities, agents covered, active accounts, MFA), the role catalogue
        (one row per enforced role), the selected-role detail (members, privilege
        and resource distributions) and the governance panels (top roles, access by
        resource, and the honest-empty requests / SoD / inactive panels).
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    modified = _role_modified()

    try:
        from tessera.agent.registry import list_agents

        agent_count = len(list_agents())
    except (OSError, ValueError):
        agent_count = 0

    roles_full = [_build_role(rid, meta, modified, lang) for rid, meta in ROLE_CAPS.items()]

    # ── posture ──────────────────────────────────────────────────────────────
    accounts_per_role = [r.users for r in roles_full]
    caps_per_role = [r.permissions for r in roles_full]
    active_accounts = sum(1 for a in _ACCOUNTS if a["active"])
    mfa_accounts = sum(1 for a in _ACCOUNTS if a["active"] and a["mfa"])
    all_caps = sorted({c for r in roles_full for c in r.caps})
    roles_granting = [sum(1 for r in roles_full if cap in r.caps) for cap in all_caps]

    kpis = [
        _kpi("accounts", str(len(_ACCOUNTS)), _t("sub_accounts", lang), accounts_per_role),
        _kpi("roles", str(len(roles_full)), _t("sub_roles", lang), caps_per_role),
        _kpi("capabilities", str(len(all_caps)), _t("sub_caps", lang), roles_granting),
        _kpi("agents", str(agent_count), _t("sub_agents", lang), caps_per_role),
        _kpi("active", str(active_accounts), _t("sub_active", lang), accounts_per_role),
        _kpi("mfa", f"{mfa_accounts}/{active_accounts}", _t("sub_mfa", lang), accounts_per_role),
    ]

    # ── selected detail (default: first role) — SSR fallback; the client drives
    # the panel from the selected row.
    first = roles_full[0]
    selected = {**first.row(lang), "modified": f"{modified} via PR", "scope": _t("scope_org", lang)}

    # ── governance panels ────────────────────────────────────────────────────
    top_roles = [
        {
            "name": r.name,
            "value": r.permissions,
            "label": _t("caps_label", lang).format(n=r.permissions),
        }
        for r in sorted(roles_full, key=lambda r: -r.permissions)
    ]

    area_totals: dict[str, int] = {}
    for r in roles_full:
        for cap in r.caps:
            area = _CAP_AREA.get(cap, "cockpit")
            area_totals[area] = area_totals.get(area, 0) + 1
    grand = sum(area_totals.values()) or 1
    access_by_resource = [
        _slice(area, n, grand, _AREA_COLOR.get(area, "#64748b"))
        for area, n in sorted(area_totals.items(), key=lambda kv: -kv[1])
    ]

    roles = [r.row(lang) for r in roles_full]

    return {
        "generated_at": now.isoformat(),
        "total_roles": len(roles_full),
        "page_size": len(roles_full),
        "kpis": kpis,
        "roles": roles,
        "selected": selected,
        "top_roles": top_roles,
        "access_by_resource": access_by_resource,
        # No Phase-1 store for these — honest empty, not fabricated rows.
        "pending_requests": [],
        "sod_violations": [],
        "inactive_accounts": [],
        "footer": {"total": len(roles_full), "source": "session.ts (RBAC) · Git"},
    }
