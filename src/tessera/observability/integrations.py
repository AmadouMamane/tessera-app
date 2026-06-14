"""Integrations cockpit overview (page #19).

Composes the "Intégrations" overview: the integration posture (total / active /
warning / error integrations, 24h calls, success rate, response time, cost), the
integration catalogue table, the selected-integration detail (connectivity,
general info, usage, configuration, security) and the type / environment / top
distributions.

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_integrations_overview"]

_TYPE_COLOR = {
    "database": "#60a5fa",
    "warehouse": "#a78bfa",
    "api": "#34d399",
    "saas": "#fbbf24",
    "queue": "#f472b6",
    "storage": "#f87171",
}


def _kpi(key: str, value: str, sub: str, series: list[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_integrations_overview() -> dict[str, object]:
    """Return the full Integrations overview payload.

    Returns:
        A JSON-serialisable mapping with the integration posture KPIs, the
        catalogue table, the selected-integration detail and the type /
        environment / top distributions.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("total", "42", "+3 ce mois", [36, 37, 38, 39, 40, 41, 42]),
        _kpi("active", "38", "90% du total", [33, 34, 35, 36, 37, 38, 38]),
        _kpi("warnings", "3", "à surveiller", [5, 4, 4, 3, 3, 3, 3]),
        _kpi("errors", "1", "à traiter", [2, 2, 1, 1, 2, 1, 1]),
        _kpi("calls", "128,543", "+8% vs 24h", [110, 114, 118, 121, 124, 126, 128]),
        _kpi("success_rate", "99.2%", "+0.3 pp", [98, 98, 99, 99, 99, 99, 99]),
        _kpi("response_time", "432 ms", "-18 ms", [480, 470, 460, 450, 444, 438, 432]),
        _kpi("cost", "€2,148", "+9% vs mois", [1900, 1960, 2010, 2060, 2100, 2130, 2148]),
    ]

    integrations = [
        {
            "id": "INT-0001",
            "name": "Salesforce API",
            "type": "saas",
            "status": "active",
            "environment": "prod",
            "owner": "alice",
            "calls": "12,403",
            "success_rate": "99.4%",
            "response_time": "356 ms",
            "last_sync": "11/06/2026 10:20",
        },
        {
            "id": "INT-0002",
            "name": "PostgreSQL · Clients",
            "type": "database",
            "status": "active",
            "environment": "prod",
            "owner": "alice",
            "calls": "8,739",
            "success_rate": "99.8%",
            "response_time": "87 ms",
            "last_sync": "11/06/2026 10:18",
        },
        {
            "id": "INT-0003",
            "name": "Snowflake · Finance",
            "type": "warehouse",
            "status": "active",
            "environment": "prod",
            "owner": "bob",
            "calls": "6,221",
            "success_rate": "99.6%",
            "response_time": "412 ms",
            "last_sync": "11/06/2026 10:15",
        },
        {
            "id": "INT-0004",
            "name": "Vertex AI · Embeddings",
            "type": "api",
            "status": "active",
            "environment": "prod",
            "owner": "carla",
            "calls": "21,884",
            "success_rate": "99.1%",
            "response_time": "612 ms",
            "last_sync": "11/06/2026 10:21",
        },
        {
            "id": "INT-0005",
            "name": "Kafka · Events",
            "type": "queue",
            "status": "warning",
            "environment": "preprod",
            "owner": "marc",
            "calls": "44,920",
            "success_rate": "97.8%",
            "response_time": "44 ms",
            "last_sync": "11/06/2026 10:19",
        },
        {
            "id": "INT-0006",
            "name": "S3 · Evidence store",
            "type": "storage",
            "status": "active",
            "environment": "prod",
            "owner": "claire",
            "calls": "3,512",
            "success_rate": "100%",
            "response_time": "128 ms",
            "last_sync": "11/06/2026 10:12",
        },
        {
            "id": "INT-0007",
            "name": "ServiceNow · Tickets",
            "type": "saas",
            "status": "error",
            "environment": "prod",
            "owner": "dave",
            "calls": "1,204",
            "success_rate": "82.4%",
            "response_time": "1.2 s",
            "last_sync": "11/06/2026 09:47",
        },
    ]

    selected = {
        "id": "INT-0001",
        "name": "Salesforce API",
        "status": "active",
        "last_sync": "11/06/2026 10:20",
        "response_time": "356 ms",
        "success_rate": "99.4%",
        "description": "Accès aux données Salesforce (objets clients, comptes, opportunités).",
        "owner": "alice (AI Quality Team)",
        "environment": "Production",
        "region": "eu-west-1",
        "criticality": "high",
        "usage": {
            "read": {"value": "256 GB", "delta": "+14%"},
            "write": {"value": "32 GB", "delta": "+6%"},
            "cost": {"value": "€612", "delta": "+9%"},
        },
        "config": {
            "url": "https://acme-dev-ed.my.salesforce.com",
            "version": "v59.0",
            "auth": "OAuth 2.0 · JWT Bearer",
            "timeout": "30 s",
            "retry": "3 tentatives (exponential backoff)",
            "rate_limit": "96 requêtes / min",
            "pagination": "200 éléments / page",
        },
        "security": {
            "method": "OAuth 2.0 · JWT Bearer",
            "client_id": "…sf01",
            "cert": "Configuré",
            "key_rotation": "90 jours",
            "last_rotation": "01/06/2026",
        },
    }

    by_type = [
        {"key": "saas", "count": 12, "pct": 29, "color": _TYPE_COLOR["saas"]},
        {"key": "api", "count": 10, "pct": 24, "color": _TYPE_COLOR["api"]},
        {"key": "database", "count": 8, "pct": 19, "color": _TYPE_COLOR["database"]},
        {"key": "warehouse", "count": 5, "pct": 12, "color": _TYPE_COLOR["warehouse"]},
        {"key": "queue", "count": 4, "pct": 10, "color": _TYPE_COLOR["queue"]},
        {"key": "storage", "count": 3, "pct": 6, "color": _TYPE_COLOR["storage"]},
    ]

    by_env = [
        {"key": "prod", "value": "98,420", "pct": 76, "color": "#34d399"},
        {"key": "preprod", "value": "21,640", "pct": 17, "color": "#60a5fa"},
        {"key": "staging", "value": "6,210", "pct": 5, "color": "#fbbf24"},
        {"key": "dev", "value": "2,273", "pct": 2, "color": "#f472b6"},
    ]

    top_integrations = [
        {"name": "Kafka · Events", "value": 44920, "label": "44,920"},
        {"name": "Vertex AI · Embeddings", "value": 21884, "label": "21,884"},
        {"name": "Salesforce API", "value": 12403, "label": "12,403"},
        {"name": "PostgreSQL · Clients", "value": 8739, "label": "8,739"},
        {"name": "Snowflake · Finance", "value": 6221, "label": "6,221"},
    ]

    return {
        "generated_at": now.isoformat(),
        "total_integrations": 42,
        "page_size": 7,
        "kpis": kpis,
        "integrations": integrations,
        "selected": selected,
        "by_type": by_type,
        "by_type_total": 42,
        "by_env": by_env,
        "top_integrations": top_integrations,
        "footer": {"total": 42, "source": "YAML · Git"},
    }
