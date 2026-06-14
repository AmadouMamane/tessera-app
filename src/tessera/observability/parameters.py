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

__all__ = ["compute_parameters_overview"]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_parameters_overview() -> dict[str, object]:
    """Return the full Parameters overview payload.

    Returns:
        A JSON-serialisable mapping with the config version, posture KPIs,
        quick-config categories, recent parameters, configuration-state
        distribution and compliance checks.
    """
    now = datetime.now(UTC)

    config_version = {
        "version": "cfg-v1.8.2",
        "env": "Production",
        "status": "active",
        "active_since": "11/06/2026 09:45",
        "modified_by": "alice (AI Quality Team)",
        "validation": "Validé",
        "next_review": "25/06/2026",
    }

    kpis = [
        _kpi("configured", "238", "87% des paramètres actifs", [220, 224, 228, 230, 233, 236, 238]),
        _kpi("policies", "54", "+3 ce mois", [48, 49, 50, 51, 52, 53, 54]),
        _kpi("security_rules", "112", "+6 ce mois", [100, 103, 105, 107, 109, 111, 112]),
        _kpi("integrations", "42", "98% opérationnelles", [38, 39, 40, 40, 41, 42, 42]),
        _kpi("models", "18", "+2 ce mois", [14, 15, 16, 16, 17, 18, 18]),
        _kpi("changes", "127", "+18% vs 30 j", [98, 104, 110, 116, 120, 124, 127]),
    ]

    categories = [
        {
            "key": "security_policies",
            "desc": "Configurez les règles de sécurité, les contrôles d'accès et les permissions.",
        },
        {
            "key": "data_retention",
            "desc": "Définissez les règles de rétention, d'archivage et de suppression.",
        },
        {
            "key": "models_ai",
            "desc": "Gérez les modèles, les prompts et les paramètres d'inférence.",
        },
        {
            "key": "authentication",
            "desc": "Gérez l'authentification SSO, MFA, fournisseurs d'identité et accès.",
        },
        {"key": "notifications", "desc": "Gérez les canaux, les alertes et les abonnements."},
        {"key": "integrations", "desc": "Configurez les connecteurs, API et flux de données."},
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
            "value": "configuré",
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
        {"name": "Limite de taux par utilisateur", "value": "100 / min", "status": "active"},
        {"name": "Quota mensuel de tokens", "value": "5 M", "status": "active"},
        {"name": "Liste blanche d'outils", "value": "12 outils", "status": "active"},
        {"name": "Filtrage de contenu", "value": "Strict", "status": "active"},
    ]

    backup = {
        "last_backup": "11/06/2026 06:00",
        "frequency": "Quotidienne",
        "retention": "90 jours",
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
