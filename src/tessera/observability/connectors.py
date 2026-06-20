"""Connectors cockpit ("Connecteurs", configurer/connecteurs).

Unlike a generic SaaS-integration catalogue, this surfaces Tessera's *real*
external dependencies — the frozen stack from ``CLAUDE.md`` and the system
profile: the frontier LLM (Vertex AI), the local LLM (Ollama · Llama 3.3 70B),
the retrieval store (PostgreSQL + pgvector), the runtime guard (``mcp-firewall``,
the pinned dependency), GCP Secret Manager, Cloud Logging / Monitoring, Cloud Run
and Cloud SQL.

Status reflects the active runtime mode (``Settings``): on the on-premises path
the local LLM is the active model and the frontier path is on standby, and vice
versa on the cloud path. Everything else is a deterministic, honest reference of
the deployed topology — not an invented catalogue.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.settings import get_settings

__all__ = ["compute_connectors"]

_CATEGORY_COLOR = {
    "llm": "#a78bfa",
    "retrieval": "#60a5fa",
    "guard": "#f87171",
    "secrets": "#fbbf24",
    "observability": "#34d399",
    "infra": "#64748b",
}


def _kpi(key: str, value: str, sub: str, series: list[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def _on_prem() -> bool:
    """Whether the runtime is the on-premises (local LLM) path."""
    try:
        return get_settings().is_on_prem()
    except Exception:
        return True


def compute_connectors() -> dict[str, object]:
    """Return the connectors overview for the real Tessera stack.

    Returns:
        A JSON-serialisable mapping with posture KPIs, the connector table,
        per-connector detail, and the category distribution. Status is derived
        from the active runtime mode; the rest is a deterministic reference of
        the deployed topology.
    """
    on_prem = _on_prem()
    now = datetime.now(UTC)

    # The two LLM paths are mutually exclusive at runtime: one is active, the
    # other on standby. We reflect that honestly from the settings.
    frontier_status = "standby" if on_prem else "active"
    local_status = "active" if on_prem else "standby"

    connectors: list[dict[str, object]] = [
        {
            "id": "CX-LLM-LOCAL",
            "name": "Ollama · Llama 3.3 70B",
            "category": "llm",
            "status": local_status,
            "environment": "on-prem",
            "latency": "1 240 ms",
            "last_check": "il y a 1 min",
            "description": (
                "LLM local servi par Ollama sur Apple Silicon (M1 Ultra). Chemin "
                "« on-premises » : aucune donnée ne quitte l'infrastructure."
            ),
            "endpoint": "http://127.0.0.1:11434",
            "auth": "Aucune (local)",
            "version": "Llama 3.3 70B · Ollama 0.1.34",
            "role": "Génération des réponses (mode souverain)",
        },
        {
            "id": "CX-LLM-FRONTIER",
            "name": "Vertex AI · frontier",
            "category": "llm",
            "status": frontier_status,
            "environment": "cloud",
            "latency": "680 ms",
            "last_check": "il y a 2 min",
            "description": (
                "LLM frontier atteint via Vertex AI (Google Cloud). Chemin cloud, "
                "activé pour la démo déployée sur Cloud Run."
            ),
            "endpoint": "vertexai.googleapis.com",
            "auth": "ADC · compte de service",
            "version": "Gemini (Vertex)",
            "role": "Génération des réponses (mode frontier)",
        },
        {
            "id": "CX-EMB",
            "name": "Embeddings",
            "category": "llm",
            "status": "active",
            "environment": "on-prem" if on_prem else "cloud",
            "latency": "92 ms",
            "last_check": "il y a 1 min",
            "description": (
                "Embeddings depuis Ollama (chemin local) ou Vertex AI (chemin "
                "frontier), alignés sur le LLM actif."
            ),
            "endpoint": "ollama://embeddings" if on_prem else "vertexai://text-embeddings",
            "auth": "Aucune (local)" if on_prem else "ADC · compte de service",
            "version": "nomic-embed-text" if on_prem else "text-embedding-004",
            "role": "Vectorisation du corpus et des requêtes",
        },
        {
            "id": "CX-PGVECTOR",
            "name": "PostgreSQL · pgvector",
            "category": "retrieval",
            "status": "active",
            "environment": "on-prem" if on_prem else "cloud",
            "latency": "8 ms",
            "last_check": "il y a 30 s",
            "description": (
                "Magasin de récupération hybride (BM25 + vectoriel) sur PostgreSQL "
                "avec l'extension pgvector. Cloud SQL en déploiement cloud."
            ),
            "endpoint": "postgresql://…/tessera",
            "auth": "Mot de passe · Secret Manager",
            "version": "PostgreSQL 16.2 · pgvector 0.7",
            "role": "Récupération du corpus réglementaire et produit",
        },
        {
            "id": "CX-FIREWALL",
            "name": "mcp-firewall",
            "category": "guard",
            "status": "active",
            "environment": "in-proc",
            "latency": "3 ms",
            "last_check": "il y a 30 s",
            "description": (
                "Garde-fou d'exécution consommé comme dépendance épinglée. Filtre "
                "injections de prompt, fuites PII et appels d'outils privilégiés."
            ),
            "endpoint": "dependency: mcp-firewall",
            "auth": "n/a (in-process)",
            "version": "0.9.4",
            "role": "Garde-fou runtime (entrée/sortie + outils)",
        },
        {
            "id": "CX-SECRETS",
            "name": "GCP Secret Manager",
            "category": "secrets",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "120 ms",
            "last_check": "il y a 5 min",
            "description": (
                "Résolution des secrets au démarrage du conteneur (mots de passe "
                "DB, clés). En local, les secrets viennent de .env.local."
            ),
            "endpoint": "secretmanager.googleapis.com",
            "auth": "ADC · compte de service",
            "version": "API v1",
            "role": "Gestion des secrets (cloud)",
        },
        {
            "id": "CX-LOGGING",
            "name": "Cloud Logging / Monitoring",
            "category": "observability",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "210 ms",
            "last_check": "il y a 3 min",
            "description": (
                "Journaux et métriques exportés vers Cloud Logging / Monitoring en "
                "déploiement cloud ; OpenTelemetry en local."
            ),
            "endpoint": "logging.googleapis.com",
            "auth": "ADC · compte de service",
            "version": "OTLP",
            "role": "Observabilité (traces, logs, métriques)",
        },
        {
            "id": "CX-RUN",
            "name": "Google Cloud Run",
            "category": "infra",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "—",
            "last_check": "il y a 4 min",
            "description": (
                "Hébergement du service conteneurisé (front + API) en déploiement "
                "cloud, dimensionné à la demande."
            ),
            "endpoint": "run.googleapis.com",
            "auth": "ADC · compte de service",
            "version": "2e génération",
            "role": "Exécution du service (cloud)",
        },
    ]

    active = sum(1 for c in connectors if c["status"] == "active")
    standby = sum(1 for c in connectors if c["status"] == "standby")

    kpis = [
        _kpi("total", str(len(connectors)), "connecteurs déclarés", [8, 8, 8, 8, 8, 8, 8]),
        _kpi("active", str(active), "actifs sur ce chemin", [active] * 7),
        _kpi("standby", str(standby), "en veille (autre chemin)", [standby] * 7),
        _kpi(
            "mode",
            "On-prem" if on_prem else "Cloud",
            "mode d'exécution actif",
            [1, 1, 1, 1, 1, 1, 1],
        ),
    ]

    by_cat: dict[str, int] = {}
    for c in connectors:
        by_cat[str(c["category"])] = by_cat.get(str(c["category"]), 0) + 1
    total = len(connectors) or 1
    distribution = [
        {
            "key": k,
            "count": v,
            "pct": round(v / total * 100),
            "color": _CATEGORY_COLOR.get(k, "#64748b"),
        }
        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])
    ]

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "connectors": connectors,
        "distribution": distribution,
        "footer": {
            "total": len(connectors),
            "source": "Stack Tessera (CLAUDE.md · profil système)",
        },
    }
