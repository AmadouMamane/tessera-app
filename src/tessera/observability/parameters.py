"""Settings / parameters cockpit overview (page #21).

Composes the "Paramètres" overview: the active configuration version, the
settings posture (configured parameters, active policies, security rules,
connected integrations, available models, recent changes), the quick-config
categories, the recent parameters table, the configuration-state distribution
and the compliance checks.

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability.knowledge import _LANG_IDX, _norm_lang

__all__ = ["compute_parameters_overview"]

# Localized free-text (fr, de, en). IDs/versions/dates/names/values stay verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "validated": ("Validé", "Validiert", "Validated"),
    "sub_configured": (
        "87% des paramètres actifs",
        "87% der Parameter aktiv",
        "87% of parameters active",
    ),
    "delta_month": ("+{n} ce mois", "+{n} diesen Monat", "+{n} this month"),
    "sub_integrations": ("98% opérationnelles", "98% betriebsbereit", "98% operational"),
    "sub_changes": ("+18% vs 30 j", "+18% vs 30 T", "+18% vs 30d"),
    "v_configured": ("configuré", "konfiguriert", "configured"),
    "backup_daily": ("Quotidienne", "Taeglich", "Daily"),
    "u_days": ("{n} jours", "{n} Tage", "{n} days"),
    "up_rate": ("Limite de taux par utilisateur", "Ratenlimit pro Benutzer", "Per-user rate limit"),
    "up_quota": ("Quota mensuel de tokens", "Monatliches Token-Kontingent", "Monthly token quota"),
    "up_allowlist": ("Liste blanche d'outils", "Tool-Whitelist", "Tool allowlist"),
    "up_filter": ("Filtrage de contenu", "Inhaltsfilterung", "Content filtering"),
    "v_strict": ("Strict", "Strikt", "Strict"),
    "v_tools": ("{n} outils", "{n} Tools", "{n} tools"),
    "cat_security": (
        "Configurez les règles de sécurité, les contrôles d'accès et les permissions.",
        "Konfigurieren Sie Sicherheitsregeln, Zugriffskontrollen und Berechtigungen.",
        "Configure security rules, access controls and permissions.",
    ),
    "cat_retention": (
        "Définissez les règles de rétention, d'archivage et de suppression.",
        "Definieren Sie Aufbewahrungs-, Archivierungs- und Loeschregeln.",
        "Define retention, archival and deletion rules.",
    ),
    "cat_models": (
        "Gérez les modèles, les prompts et les paramètres d'inférence.",
        "Verwalten Sie Modelle, Prompts und Inferenzparameter.",
        "Manage models, prompts and inference settings.",
    ),
    "cat_auth": (
        "Gérez l'authentification SSO, MFA, fournisseurs d'identité et accès.",
        "Verwalten Sie SSO, MFA, Identitaetsanbieter und Zugriff.",
        "Manage SSO, MFA, identity providers and access.",
    ),
    "cat_notif": (
        "Gérez les canaux, les alertes et les abonnements.",
        "Verwalten Sie Kanaele, Warnungen und Abonnements.",
        "Manage channels, alerts and subscriptions.",
    ),
    "cat_integrations": (
        "Configurez les connecteurs, API et flux de données.",
        "Konfigurieren Sie Konnektoren, APIs und Datenfluesse.",
        "Configure connectors, APIs and data flows.",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_parameters_overview(lang: str = "fr") -> dict[str, object]:
    """Return the full Parameters overview payload.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the config version, posture KPIs,
        quick-config categories, recent parameters, configuration-state
        distribution and compliance checks.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    mth = _TR["delta_month"][_LANG_IDX.get(lang, 0)]

    config_version = {
        "version": "cfg-v1.8.2",
        "env": "Production",
        "status": "active",
        "active_since": "11/06/2026 09:45",
        "modified_by": "alice (AI Quality Team)",
        "validation": _t("validated", lang),
        "next_review": "25/06/2026",
    }

    kpis = [
        _kpi("configured", "238", _t("sub_configured", lang), [220, 224, 228, 230, 233, 236, 238]),
        _kpi("policies", "54", mth.format(n=3), [48, 49, 50, 51, 52, 53, 54]),
        _kpi("security_rules", "112", mth.format(n=6), [100, 103, 105, 107, 109, 111, 112]),
        _kpi("integrations", "42", _t("sub_integrations", lang), [38, 39, 40, 40, 41, 42, 42]),
        _kpi("models", "18", mth.format(n=2), [14, 15, 16, 16, 17, 18, 18]),
        _kpi("changes", "127", _t("sub_changes", lang), [98, 104, 110, 116, 120, 124, 127]),
    ]

    categories = [
        {"key": "security_policies", "desc": _t("cat_security", lang)},
        {"key": "data_retention", "desc": _t("cat_retention", lang)},
        {"key": "models_ai", "desc": _t("cat_models", lang)},
        {"key": "authentication", "desc": _t("cat_auth", lang)},
        {"key": "notifications", "desc": _t("cat_notif", lang)},
        {"key": "integrations", "desc": _t("cat_integrations", lang)},
    ]

    recent_params = [
        {
            "name": "rag.chunk_size",
            "category": "models_ai",
            "value": "512 tokens",
            "modified_by": "alice",
            "date": "11/06 09:45",
            "status": "active",
        },
        {
            "name": "guard.pii_threshold",
            "category": "security",
            "value": "0.97",
            "modified_by": "bob",
            "date": "11/06 08:54",
            "status": "active",
        },
        {
            "name": "memory.ttl_days",
            "category": "data",
            "value": "30",
            "modified_by": "a. privacy",
            "date": "10/06 16:33",
            "status": "active",
        },
        {
            "name": "auth.mfa_required",
            "category": "auth",
            "value": "true",
            "modified_by": "claire",
            "date": "10/06 11:20",
            "status": "active",
        },
        {
            "name": "notif.slack_webhook",
            "category": "notifications",
            "value": _t("v_configured", lang),
            "modified_by": "marc",
            "date": "09/06 14:02",
            "status": "draft",
        },
        {
            "name": "cost.monthly_cap",
            "category": "general",
            "value": "€5,000",
            "modified_by": "dave",
            "date": "08/06 10:41",
            "status": "active",
        },
    ]

    config_state = {
        "total": 238,
        "slices": [
            {"key": "active", "count": 207, "pct": 87, "color": "#34d399"},
            {"key": "inactive", "count": 19, "pct": 8, "color": "#60a5fa"},
            {"key": "drafts", "count": 7, "pct": 3, "color": "#fbbf24"},
            {"key": "deprecated", "count": 5, "pct": 2, "color": "#f87171"},
        ],
    }

    compliance = [
        {"key": "security_policies", "status": "ok"},
        {"key": "data_retention", "status": "ok"},
        {"key": "authentication", "status": "ok"},
        {"key": "models_ai", "status": "ok"},
        {"key": "audit", "status": "ok"},
    ]

    usage_policies = [
        {"name": _t("up_rate", lang), "value": "100 / min", "status": "active"},
        {"name": _t("up_quota", lang), "value": "5 M", "status": "active"},
        {
            "name": _t("up_allowlist", lang),
            "value": _t("v_tools", lang).format(n=12),
            "status": "active",
        },
        {"name": _t("up_filter", lang), "value": _t("v_strict", lang), "status": "active"},
    ]

    backup = {
        "last_backup": "11/06/2026 06:00",
        "frequency": _t("backup_daily", lang),
        "retention": _t("u_days", lang).format(n=90),
        "size": "1.2 GB",
    }

    return {
        "generated_at": now.isoformat(),
        "config_version": config_version,
        "kpis": kpis,
        "categories": categories,
        "recent_params": recent_params,
        "config_state": config_state,
        "compliance": compliance,
        "usage_policies": usage_policies,
        "backup": backup,
        "footer": {"version": "cfg-v1.8.2", "source": "YAML · Git"},
    }
