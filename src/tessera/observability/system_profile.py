"""System profile cockpit overview (page #20).

Composes the "Profil système" overview: the operational posture (availability,
CPU/memory/storage load, active services and nodes), the architecture &
deployment metadata, the topology, the resource distribution, the OS info, the
health checks, the resource time-series and the services & components table.

The dataset is a deterministic reference fixture; values are stable across calls
so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_system_profile"]


def compute_system_profile() -> dict[str, object]:
    """Return the full System profile overview payload.

    Returns:
        A JSON-serialisable mapping with the posture KPIs, architecture &
        deployment metadata, topology, resource distribution, OS info, health
        checks, resource series and services table.
    """
    now = datetime.now(UTC)

    kpis = [
        {
            "key": "status",
            "kind": "status",
            "value": "Opérationnel",
            "sub": "Tous les systèmes fonctionnent",
            "link": "Voir les détails",
            "series": [],
        },
        {
            "key": "availability",
            "kind": "metric",
            "value": "99.92%",
            "sub": "Objectif : 99.9%",
            "delta": "+0.02 pt",
            "series": [99.88, 99.89, 99.9, 99.91, 99.9, 99.92, 99.92],
        },
        {
            "key": "cpu",
            "kind": "chart",
            "value": "42%",
            "sub": "Moyenne CPU",
            "series": [38, 44, 40, 48, 45, 50, 42],
        },
        {
            "key": "memory",
            "kind": "chart",
            "value": "58%",
            "sub": "18.6 / 32 GB",
            "series": [52, 54, 55, 57, 56, 58, 58],
        },
        {
            "key": "storage",
            "kind": "chart",
            "value": "2.47 TB",
            "sub": "sur 6.40 TB (39%)",
            "series": [2.2, 2.3, 2.35, 2.4, 2.42, 2.45, 2.47],
        },
        {
            "key": "services",
            "kind": "metric",
            "value": "28 / 28",
            "sub": "Aucun service dégradé",
            "link": "Voir les services",
            "series": [],
        },
        {
            "key": "nodes",
            "kind": "metric",
            "value": "7 / 7",
            "sub": "Tous les nœuds sains",
            "link": "Voir l'infrastructure",
            "series": [],
        },
        {
            "key": "last_check",
            "kind": "time",
            "value": "11/06/2026 10:22:15",
            "sub": "Il y a 2 minutes",
            "extra": "Planifiée dans 58 min",
            "series": [],
        },
    ]

    architecture = {
        "edition": "Enterprise",
        "version": "Tessera v1.0.0 · build 20260605",
        "deployment": "On-premise",
        "region": "Europe / Paris (UTC+2)",
        "cluster": "tessera-prod-cluster",
        "deployed_at": "05/06/2026 14:32",
        "uptime": "9 j 5 h 50 min",
        "next_maintenance": "15/06/2026",
    }

    topology = {
        "tiers": [
            {"key": "lb", "label": "Load Balancer", "nodes": 2},
            {"key": "gateway", "label": "API Gateway", "nodes": 2},
        ],
        "planes": [
            {"key": "control", "label": "Control Plane", "nodes": 2},
            {"key": "data", "label": "Data Plane", "nodes": 2},
            {"key": "worker", "label": "Worker", "nodes": 4},
        ],
        "stores": [
            {"key": "postgres", "label": "PostgreSQL", "detail": "Primary + 2 replicas"},
            {"key": "redis", "label": "Redis", "detail": "Cluster (3 nœuds)"},
            {"key": "object", "label": "Object Storage", "detail": "S3 compatible"},
        ],
    }

    resources = {
        "total": "64 vCPU",
        "slices": [
            {"key": "control", "count": 16, "pct": 25, "color": "#60a5fa"},
            {"key": "data", "count": 20, "pct": 31, "color": "#a78bfa"},
            {"key": "worker", "count": 18, "pct": 28, "color": "#34d399"},
            {"key": "system", "count": 10, "pct": 16, "color": "#64748b"},
        ],
    }

    os_info = {
        "os": "Ubuntu 22.04.4 LTS",
        "kernel": "5.15.0-101-generic",
        "arch": "x86_64",
        "virtualization": "VMware ESXi 8.0",
        "cpu": "64 vCPU (Intel Xeon Gold 6338N)",
        "memory": "64 GB",
        "system_time": "11/06/2026 10:22:15",
        "timezone": "Europe/Paris (UTC+2)",
        "fqdn": "tessera-prod-01.tessera.local",
        "infra_id": "TSR-EUR-PRD-20260605-001",
        "support": "support@tessera.local",
    }

    health_checks = [
        {"key": "database", "status": "ok"},
        {"key": "storage", "status": "ok"},
        {"key": "cache", "status": "ok"},
        {"key": "queue", "status": "ok"},
        {"key": "critical_services", "status": "ok"},
        {"key": "api_gateway", "status": "ok"},
        {"key": "connectivity", "status": "ok"},
        {"key": "security", "status": "ok"},
        {"key": "backups", "status": "ok"},
        {"key": "monitoring", "status": "warn"},
    ]

    resource_series = {
        "labels": ["10:00", "10:05", "10:10", "10:15", "10:20"],
        "cpu": [38, 44, 40, 48, 42],
        "memory": [52, 54, 55, 57, 58],
        "disk": [120, 140, 110, 160, 130],
        "network": [220, 260, 240, 300, 280],
    }

    services = [
        {"name": "API Gateway", "status": "ok", "version": "v1.0.0", "instances": "2 / 2"},
        {"name": "Agent Orchestrator", "status": "ok", "version": "v1.0.0", "instances": "4 / 4"},
        {"name": "Retrieval Service", "status": "ok", "version": "v1.0.0", "instances": "3 / 3"},
        {"name": "Guard / Firewall", "status": "ok", "version": "v0.9.4", "instances": "2 / 2"},
        {"name": "Eval Harness", "status": "ok", "version": "v1.0.0", "instances": "2 / 2"},
        {"name": "Observability", "status": "warn", "version": "v1.0.0", "instances": "1 / 2"},
    ]

    versions = [
        {"name": "Python", "version": "3.12.3"},
        {"name": "PostgreSQL", "version": "16.2 · pgvector 0.7"},
        {"name": "Redis", "version": "7.2.4"},
        {"name": "Ollama (Llama 3.3 70B)", "version": "0.1.34"},
        {"name": "mcp-firewall", "version": "0.9.4"},
    ]

    licenses = {
        "edition": "Enterprise",
        "seats": "320 / 500",
        "expiry": "31/12/2026",
        "quota_calls": "1.2 M / 5 M",
        "quota_storage": "2.47 TB / 6.40 TB",
    }

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "architecture": architecture,
        "topology": topology,
        "resources": resources,
        "os_info": os_info,
        "health_checks": health_checks,
        "resource_series": resource_series,
        "services": services,
        "versions": versions,
        "licenses": licenses,
        "footer": {"version": "Tessera v1.0.0", "source": "On-premise · tessera-prod-cluster"},
    }
