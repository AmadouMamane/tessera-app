"""Sources & memory cockpit overview (page #17).

Composes the "Sources & mémoire" overview: the catalogue posture (total / active
sources, synced volume, total memory, indexed docs, retention, quality, cost),
the source catalogue table, the selected-source detail (definition, metrics,
data-quality breakdown) and the by-type / by-environment / cost distributions.

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_sources_overview"]

_TYPE_COLOR = {
    "database": "#60a5fa",
    "vector": "#a78bfa",
    "api": "#34d399",
    "files": "#fbbf24",
    "stream": "#f472b6",
    "memory": "#f87171",
}


def _kpi(key: str, value: str, sub: str, series: list[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_sources_overview() -> dict[str, object]:
    """Return the full Sources & memory overview payload.

    Returns:
        A JSON-serialisable mapping with the catalogue posture KPIs, the source
        table, the selected-source detail and the type / environment / cost
        distributions.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("total", "54", "79% du total", [48, 49, 50, 51, 52, 53, 54]),
        _kpi("active", "51", "94% des sources", [46, 47, 48, 49, 50, 50, 51]),
        _kpi("synced", "2.47 TB", "+129 ce mois", [2.1, 2.2, 2.3, 2.35, 2.4, 2.45, 2.47]),
        _kpi("memory", "1.89 TB", "76% du total", [1.6, 1.65, 1.7, 1.78, 1.82, 1.86, 1.89]),
        _kpi("indexed", "12.8 M", "+320 ce mois", [11.4, 11.8, 12.0, 12.3, 12.5, 12.7, 12.8]),
        _kpi("retention", "186 jours", "moyenne", [180, 182, 183, 184, 185, 186, 186]),
        _kpi("quality", "92%", "+3 pts", [86, 87, 88, 89, 90, 91, 92]),
        _kpi("cost", "€1 842", "+12% vs mois préc.", [1620, 1680, 1720, 1760, 1790, 1820, 1842]),
    ]

    sources = [
        {
            "id": "DB-001",
            "name": "PostgreSQL · Clients",
            "type": "database",
            "classification": "confidential",
            "environment": "prod",
            "status": "active",
            "data_total": "342 GB",
            "indexed": "312 GB (91%)",
            "last_sync": "11/06/2026 10:21",
            "quality": 95,
            "freshness": "2 h",
            "owner": "alice",
            "cost": "€243",
        },
        {
            "id": "VEC-002",
            "name": "pgvector · Corpus FR",
            "type": "vector",
            "classification": "internal",
            "environment": "prod",
            "status": "active",
            "data_total": "128 GB",
            "indexed": "128 GB (100%)",
            "last_sync": "11/06/2026 11:40",
            "quality": 97,
            "freshness": "20 min",
            "owner": "bob",
            "cost": "€186",
        },
        {
            "id": "API-003",
            "name": "BaFin · Reg feed",
            "type": "api",
            "classification": "public",
            "environment": "prod",
            "status": "active",
            "data_total": "12 GB",
            "indexed": "12 GB (100%)",
            "last_sync": "11/06/2026 09:05",
            "quality": 90,
            "freshness": "4 h",
            "owner": "claire",
            "cost": "€42",
        },
        {
            "id": "FIL-004",
            "name": "S3 · Policy docs",
            "type": "files",
            "classification": "internal",
            "environment": "prod",
            "status": "active",
            "data_total": "86 GB",
            "indexed": "74 GB (86%)",
            "last_sync": "11/06/2026 08:30",
            "quality": 88,
            "freshness": "1 j",
            "owner": "alice",
            "cost": "€61",
        },
        {
            "id": "STR-005",
            "name": "Kafka · Events",
            "type": "stream",
            "classification": "confidential",
            "environment": "preprod",
            "status": "active",
            "data_total": "1.2 TB",
            "indexed": "—",
            "last_sync": "11/06/2026 11:52",
            "quality": 84,
            "freshness": "live",
            "owner": "marc",
            "cost": "€312",
        },
        {
            "id": "MEM-006",
            "name": "Mémoire · Sessions",
            "type": "memory",
            "classification": "confidential",
            "environment": "prod",
            "status": "active",
            "data_total": "248 GB",
            "indexed": "248 GB (100%)",
            "last_sync": "11/06/2026 11:54",
            "quality": 91,
            "freshness": "live",
            "owner": "a. privacy",
            "cost": "€98",
        },
        {
            "id": "DB-007",
            "name": "MySQL · Legacy CRM",
            "type": "database",
            "classification": "confidential",
            "environment": "prod",
            "status": "deprecated",
            "data_total": "64 GB",
            "indexed": "40 GB (62%)",
            "last_sync": "10/06/2026 22:14",
            "quality": 73,
            "freshness": "13 h",
            "owner": "bob",
            "cost": "€54",
        },
        {
            "id": "API-008",
            "name": "CNIL · Guidelines",
            "type": "api",
            "classification": "public",
            "environment": "prod",
            "status": "disabled",
            "data_total": "4 GB",
            "indexed": "4 GB (100%)",
            "last_sync": "08/06/2026 16:07",
            "quality": 95,
            "freshness": "3 j",
            "owner": "claire",
            "cost": "€12",
        },
    ]

    selected = {
        "id": "DB-001",
        "name": "PostgreSQL · Clients",
        "type": "database",
        "status": "active",
        "description": (
            "Base de données clients utilisée par le système, synchronisée toutes les 2 h."
        ),
        "connector": "PostgreSQL 14",
        "environment": "Production",
        "region": "eu-west-1",
        "classification": "confidential",
        "owner": "alice (AI Quality Team)",
        "created": "12/05/2026 14:22",
        "modified": "11/06/2026 09:12",
        "retention": "180 jours",
        "source": "PostgreSQL · 14.7",
        "tags": ["clients", "crm", "support"],
        "usage": "342 GB",
        "documents": {"value": "2.1 M", "delta": "+3.2%"},
        "queries": {"value": "1.2 M", "delta": "+8.7%"},
        "cost": {"value": "€243", "delta": "+11%"},
        "quality_global": 95,
        "quality_breakdown": [
            {"key": "completeness", "pct": 96, "color": "#60a5fa"},
            {"key": "freshness", "pct": 94, "color": "#a78bfa"},
            {"key": "accuracy", "pct": 95, "color": "#34d399"},
            {"key": "consistency", "pct": 93, "color": "#f97316"},
        ],
    }

    by_type = [
        {"key": "database", "count": 18, "pct": 33, "color": _TYPE_COLOR["database"]},
        {"key": "vector", "count": 12, "pct": 22, "color": _TYPE_COLOR["vector"]},
        {"key": "api", "count": 9, "pct": 17, "color": _TYPE_COLOR["api"]},
        {"key": "files", "count": 7, "pct": 13, "color": _TYPE_COLOR["files"]},
        {"key": "stream", "count": 5, "pct": 9, "color": _TYPE_COLOR["stream"]},
        {"key": "memory", "count": 3, "pct": 6, "color": _TYPE_COLOR["memory"]},
    ]

    by_env = [
        {"key": "prod", "value": "1.42 TB", "pct": 75, "color": "#34d399"},
        {"key": "preprod", "value": "0.31 TB", "pct": 16, "color": "#60a5fa"},
        {"key": "staging", "value": "0.10 TB", "pct": 5, "color": "#fbbf24"},
        {"key": "dev", "value": "0.06 TB", "pct": 3, "color": "#f472b6"},
    ]

    cost_by_source = [
        {"name": "Kafka · Events", "value": 312, "label": "€312"},
        {"name": "PostgreSQL · Clients", "value": 243, "label": "€243"},
        {"name": "pgvector · Corpus FR", "value": 186, "label": "€186"},
        {"name": "Mémoire · Sessions", "value": 98, "label": "€98"},
        {"name": "S3 · Policy docs", "value": 61, "label": "€61"},
    ]

    return {
        "generated_at": now.isoformat(),
        "total_sources": 54,
        "page_size": 8,
        "kpis": kpis,
        "sources": sources,
        "selected": selected,
        "by_type": by_type,
        "by_type_total": 54,
        "by_env": by_env,
        "cost_by_source": cost_by_source,
        "footer": {"total": 54, "source": "YAML · Git"},
    }
