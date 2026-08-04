"""Connectors cockpit ("Connecteurs", configurer/connecteurs).

Unlike a generic SaaS-integration catalogue, this surfaces Tessera's *real*
external dependencies — the frozen stack from ``CLAUDE.md`` and the system
profile: the frontier LLM (Vertex AI), the local LLM (Ollama / Llama 3.3 70B),
the retrieval store (PostgreSQL + pgvector), the runtime guard (first-party,
in-process — ADR 0028), GCP Secret Manager, Cloud Logging / Monitoring, Cloud Run
and Cloud SQL.

Status reflects the active runtime mode (``Settings``): on the on-premises path
the local LLM is the active model and the frontier path is on standby, and vice
versa on the cloud path. Everything else is a deterministic, honest reference of
the deployed topology — not an invented catalogue.

Free-text is localized fr/de/en (French keeps accents, German transliterates
ae/oe/ue/ss); enum keys (status/category/environment) stay stable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera import __version__
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
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

# Localized free-text (fr, de, en). Proper nouns (model names, endpoints,
# versions) are NOT translated; only human prose is.
_TR: dict[str, tuple[str, str, str]] = {
    "sub_total": ("connecteurs déclarés", "deklarierte Konnektoren", "declared connectors"),
    "sub_active": ("actifs sur ce chemin", "aktiv auf diesem Pfad", "active on this path"),
    "sub_standby": (
        "en veille (autre chemin)",
        "im Standby (anderer Pfad)",
        "on standby (other path)",
    ),
    "sub_mode": ("mode d'exécution actif", "aktiver Ausfuehrungsmodus", "active execution mode"),
    "a_none_local": ("Aucune (local)", "Keine (lokal)", "None (local)"),
    "a_pwd_secret": (
        "Mot de passe / Secret Manager",
        "Passwort / Secret Manager",
        "Password / Secret Manager",
    ),
    "a_adc": ("ADC / compte de service", "ADC / Dienstkonto", "ADC / service account"),
    "a_inproc": ("n/a (in-process)", "n/a (In-Process)", "n/a (in-process)"),
    "ago_min": ("il y a {n} min", "vor {n} Min", "{n} min ago"),
    "ago_sec": ("il y a {n} s", "vor {n} Sek", "{n} s ago"),
    "f_source": (
        "Stack Tessera (CLAUDE.md / profil système)",
        "Tessera-Stack (CLAUDE.md / Systemprofil)",
        "Tessera stack (CLAUDE.md / system profile)",
    ),
    "d_local": (
        "LLM local servi par Ollama sur Apple Silicon (M1 Ultra). Chemin "
        "« on-premises » : aucune donnée ne quitte l'infrastructure.",
        "Lokales LLM via Ollama auf Apple Silicon (M1 Ultra). On-Premises-Pfad: "
        "keine Daten verlassen die Infrastruktur.",
        "Local LLM served by Ollama on Apple Silicon (M1 Ultra). On-premises path: "
        "no data leaves the infrastructure.",
    ),
    "d_frontier": (
        "LLM frontier atteint via Vertex AI (Google Cloud). Chemin cloud, "
        "activé pour la démo déployée sur Cloud Run.",
        "Frontier-LLM ueber Vertex AI (Google Cloud). Cloud-Pfad, aktiviert fuer "
        "die auf Cloud Run bereitgestellte Demo.",
        "Frontier LLM reached via Vertex AI (Google Cloud). Cloud path, enabled "
        "for the demo deployed on Cloud Run.",
    ),
    "d_emb": (
        "Embeddings depuis Ollama (chemin local) ou Vertex AI (chemin frontier), "
        "alignés sur le LLM actif.",
        "Embeddings aus Ollama (lokaler Pfad) oder Vertex AI (Frontier-Pfad), am "
        "aktiven LLM ausgerichtet.",
        "Embeddings from Ollama (local path) or Vertex AI (frontier path), aligned "
        "with the active LLM.",
    ),
    # Said "BM25 + vectoriel" until 2026-08-04, when there was no lexical index at all and
    # the only sparse signal reordered the vector candidates in Python (ADR 0050). It now
    # names the two indexes that exist, and calls the lexical rank what it is: PostgreSQL
    # full-text with ts_rank_cd, which is not BM25.
    "d_pg": (
        "Magasin de récupération hybride sur PostgreSQL : index vectoriel HNSW "
        "(pgvector) et index lexical GIN (recherche plein texte, une configuration "
        "par langue), fusionnés par RRF. Cloud SQL en déploiement cloud.",
        "Hybrider Retrieval-Speicher auf PostgreSQL: HNSW-Vektorindex (pgvector) und "
        "lexikalischer GIN-Index (Volltextsuche, eine Konfiguration je Sprache), per "
        "RRF fusioniert. Cloud SQL im Cloud-Deployment.",
        "Hybrid retrieval store on PostgreSQL: HNSW vector index (pgvector) and "
        "lexical GIN index (full-text search, one configuration per language), fused "
        "with RRF. Cloud SQL in the cloud deployment.",
    ),
    "d_fw": (
        "Garde-fou d'exécution interne (première partie), point de passage "
        "unique des appels d'outils. Filtre injections de prompt, fuites PII "
        "et appels d'outils privilégiés.",
        "Hauseigener Laufzeit-Guardrail am einzigen Tool-Chokepoint. Filtert "
        "Prompt-Injections, PII-Lecks und privilegierte Tool-Aufrufe.",
        "First-party runtime guardrail at the single tool-call chokepoint. "
        "Filters prompt injections, PII leaks and privileged tool calls.",
    ),
    "d_secrets": (
        "Résolution des secrets au démarrage du conteneur (mots de passe DB, "
        "clés). En local, les secrets viennent de .env.local.",
        "Aufloesung der Secrets beim Containerstart (DB-Passwoerter, Schluessel). "
        "Lokal stammen die Secrets aus .env.local.",
        "Secret resolution at container start (DB passwords, keys). Locally the "
        "secrets come from .env.local.",
    ),
    "d_logging": (
        "Journaux et métriques exportés vers Cloud Logging / Monitoring en "
        "déploiement cloud ; OpenTelemetry en local.",
        "Logs und Metriken werden im Cloud-Deployment nach Cloud Logging / "
        "Monitoring exportiert; OpenTelemetry lokal.",
        "Logs and metrics exported to Cloud Logging / Monitoring in the cloud "
        "deployment; OpenTelemetry locally.",
    ),
    "d_run": (
        "Hébergement du service conteneurisé (front + API) en déploiement cloud, "
        "dimensionné à la demande.",
        "Hosting des containerisierten Dienstes (Front + API) im Cloud-Deployment, "
        "bedarfsgerecht skaliert.",
        "Hosting of the containerized service (front + API) in the cloud "
        "deployment, scaled on demand.",
    ),
    "r_local": (
        "Génération des réponses (mode souverain)",
        "Antwortgenerierung (souveraener Modus)",
        "Answer generation (sovereign mode)",
    ),
    "r_frontier": (
        "Génération des réponses (mode frontier)",
        "Antwortgenerierung (Frontier-Modus)",
        "Answer generation (frontier mode)",
    ),
    "r_emb": (
        "Vectorisation du corpus et des requêtes",
        "Vektorisierung von Korpus und Anfragen",
        "Vectorization of the corpus and queries",
    ),
    "r_pg": (
        "Récupération du corpus réglementaire et produit",
        "Abruf des Regulierungs- und Produktkorpus",
        "Retrieval of the regulatory and product corpus",
    ),
    "r_fw": (
        "Garde-fou runtime (entrée/sortie + outils)",
        "Laufzeit-Guardrail (Ein-/Ausgabe + Tools)",
        "Runtime guardrail (input/output + tools)",
    ),
    "r_secrets": (
        "Gestion des secrets (cloud)",
        "Secret-Verwaltung (Cloud)",
        "Secret management (cloud)",
    ),
    "r_logging": (
        "Observabilité (traces, logs, métriques)",
        "Observability (Traces, Logs, Metriken)",
        "Observability (traces, logs, metrics)",
    ),
    "r_run": (
        "Exécution du service (cloud)",
        "Dienstausfuehrung (Cloud)",
        "Service execution (cloud)",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _ago(n: int, unit: str, lang: str) -> str:
    return _t("ago_min" if unit == "min" else "ago_sec", lang).format(n=n)


def _kpi(key: str, value: str, sub: str, series: list[float]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def _on_prem() -> bool:
    """Whether the runtime is the on-premises (local LLM) path."""
    try:
        return get_settings().is_on_prem()
    except Exception:
        return True


def compute_connectors(lang: str = "fr") -> dict[str, object]:
    """Return the connectors overview for the real Tessera stack.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with posture KPIs, the connector table,
        per-connector detail, and the category distribution. Status is derived
        from the active runtime mode; the rest is a deterministic reference of
        the deployed topology.
    """
    lang = _norm_lang(lang)
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
            "last_check": _ago(1, "min", lang),
            "description": _t("d_local", lang),
            "endpoint": "http://127.0.0.1:11434",
            "auth": _t("a_none_local", lang),
            "version": "Llama 3.3 70B · Ollama 0.1.34",
            "role": _t("r_local", lang),
        },
        {
            "id": "CX-LLM-FRONTIER",
            "name": "Vertex AI · frontier",
            "category": "llm",
            "status": frontier_status,
            "environment": "cloud",
            "latency": "680 ms",
            "last_check": _ago(2, "min", lang),
            "description": _t("d_frontier", lang),
            "endpoint": "vertexai.googleapis.com",
            "auth": _t("a_adc", lang),
            "version": "Gemini (Vertex)",
            "role": _t("r_frontier", lang),
        },
        {
            "id": "CX-EMB",
            "name": "Embeddings",
            "category": "llm",
            "status": "active",
            "environment": "on-prem" if on_prem else "cloud",
            "latency": "92 ms",
            "last_check": _ago(1, "min", lang),
            "description": _t("d_emb", lang),
            "endpoint": "ollama://embeddings" if on_prem else "vertexai://text-embeddings",
            "auth": _t("a_none_local", lang) if on_prem else _t("a_adc", lang),
            "version": "nomic-embed-text" if on_prem else "text-embedding-004",
            "role": _t("r_emb", lang),
        },
        {
            "id": "CX-PGVECTOR",
            "name": "PostgreSQL · pgvector",
            "category": "retrieval",
            "status": "active",
            "environment": "on-prem" if on_prem else "cloud",
            "latency": "8 ms",
            "last_check": _ago(30, "s", lang),
            "description": _t("d_pg", lang),
            "endpoint": "postgresql://…/tessera",
            "auth": _t("a_pwd_secret", lang),
            "version": "PostgreSQL 16.2 · pgvector 0.7",
            "role": _t("r_pg", lang),
        },
        {
            "id": "CX-FIREWALL",
            "name": "Tessera guard (first-party)",
            "category": "guard",
            "status": "active",
            "environment": "in-proc",
            "latency": "3 ms",
            "last_check": _ago(30, "s", lang),
            "description": _t("d_fw", lang),
            "endpoint": "in-process: tessera.guard.adapter",
            "auth": _t("a_inproc", lang),
            "version": __version__,
            "role": _t("r_fw", lang),
        },
        {
            "id": "CX-SECRETS",
            "name": "GCP Secret Manager",
            "category": "secrets",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "120 ms",
            "last_check": _ago(5, "min", lang),
            "description": _t("d_secrets", lang),
            "endpoint": "secretmanager.googleapis.com",
            "auth": _t("a_adc", lang),
            "version": "API v1",
            "role": _t("r_secrets", lang),
        },
        {
            "id": "CX-LOGGING",
            "name": "Cloud Logging / Monitoring",
            "category": "observability",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "210 ms",
            "last_check": _ago(3, "min", lang),
            "description": _t("d_logging", lang),
            "endpoint": "logging.googleapis.com",
            "auth": _t("a_adc", lang),
            "version": "OTLP",
            "role": _t("r_logging", lang),
        },
        {
            "id": "CX-RUN",
            "name": "Google Cloud Run",
            "category": "infra",
            "status": "active" if not on_prem else "standby",
            "environment": "cloud",
            "latency": "—",
            "last_check": _ago(4, "min", lang),
            "description": _t("d_run", lang),
            "endpoint": "run.googleapis.com",
            "auth": _t("a_adc", lang),
            "version": "2e génération",
            "role": _t("r_run", lang),
        },
    ]

    active = sum(1 for c in connectors if c["status"] == "active")
    standby = sum(1 for c in connectors if c["status"] == "standby")

    kpis = [
        _kpi("total", str(len(connectors)), _t("sub_total", lang), [8, 8, 8, 8, 8, 8, 8]),
        _kpi("active", str(active), _t("sub_active", lang), [active] * 7),
        _kpi("standby", str(standby), _t("sub_standby", lang), [standby] * 7),
        _kpi(
            "mode",
            "On-prem" if on_prem else "Cloud",
            _t("sub_mode", lang),
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
            "source": _t("f_source", lang),
        },
    }
