"""Real Connaissances data: the agent's knowledge sources from pgvector.

Unlike the other dashboards, this one is backed by the live retrieval store. The
source inventory (name, type, chunk count, languages, freshness, coverage) is
read from the ``documents`` table that the corpus ingestion populates, so every
row corresponds to chunks you can actually find in pgvector. Per-agent
attach/active state is persisted to a durable JSON file next to the guard audit
log, and mutated by the attach/detach/activate endpoints. Citation rates come
from a cached retrieval probe (see ``scripts/probe_retrieval.py``) when present.

Free-text data is verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from tessera.retrieval import citations
from tessera.retrieval.embeddings import embedding_dimension, embedding_model_name
from tessera.retrieval.store import _connection
from tessera.settings import get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "available_sources",
    "build_connaissances",
    "set_source_state",
]

# category id -> type tone ("reg" | "prod"). Names live in _SOURCE_NAME below.
_SOURCE_META: dict[str, str] = {
    "dora": "reg",
    "gdpr": "reg",
    "bafin": "reg",
    "cnil": "reg",
    "comptes": "prod",
    "cartes": "prod",
    "credit": "prod",
    "epargne": "prod",
    "assurance": "prod",
    "operations": "prod",
    "securite": "prod",
    "service": "prod",
    "conditions": "prod",
    "packages": "prod",
    "fidelite": "prod",
}

# Localized source display names (fr, de, en). The brand/regulation prefix is
# kept; the descriptive suffix and well-known acronyms (RGPD/GDPR/DSGVO) translate.
_SOURCE_NAME: dict[str, tuple[str, str, str]] = {
    "dora": (
        "DORA - Résilience opérationnelle",
        "DORA - Operative Resilienz",
        "DORA - Operational resilience",
    ),
    "gdpr": ("RGPD - Protection des données", "DSGVO - Datenschutz", "GDPR - Data protection"),
    "bafin": ("BaFin - Supervision DE", "BaFin - Aufsicht DE", "BaFin - Supervision DE"),
    "cnil": (
        "CNIL - Données personnelles FR",
        "CNIL - Personenbezogene Daten FR",
        "CNIL - Personal data FR",
    ),
    "comptes": ("Crédit Aurore - Comptes", "Crédit Aurore - Konten", "Crédit Aurore - Accounts"),
    "cartes": ("Crédit Aurore - Cartes", "Crédit Aurore - Karten", "Crédit Aurore - Cards"),
    "credit": ("Crédit Aurore - Crédit", "Crédit Aurore - Kredit", "Crédit Aurore - Credit"),
    "epargne": ("Crédit Aurore - Épargne", "Crédit Aurore - Sparen", "Crédit Aurore - Savings"),
    "assurance": (
        "Crédit Aurore - Assurances",
        "Crédit Aurore - Versicherungen",
        "Crédit Aurore - Insurance",
    ),
    "operations": (
        "Crédit Aurore - Opérations",
        "Crédit Aurore - Transaktionen",
        "Crédit Aurore - Operations",
    ),
    "securite": (
        "Crédit Aurore - Sécurité",
        "Crédit Aurore - Sicherheit",
        "Crédit Aurore - Security",
    ),
    "service": (
        "Crédit Aurore - Service client",
        "Crédit Aurore - Kundenservice",
        "Crédit Aurore - Customer service",
    ),
    "conditions": (
        "Crédit Aurore - Conditions générales",
        "Crédit Aurore - AGB",
        "Crédit Aurore - General terms",
    ),
    "packages": (
        "Crédit Aurore - Offres groupées",
        "Crédit Aurore - Paketangebote",
        "Crédit Aurore - Bundled offers",
    ),
    "fidelite": ("Crédit Aurore - Fidélité", "Crédit Aurore - Treue", "Crédit Aurore - Loyalty"),
}


def _source_name(cat: str, lang: str) -> str:
    """Localized display name for a source category (falls back to French)."""
    return _SOURCE_NAME[cat][_LANG_IDX.get(lang, 0)]


# --- Localization (fr/de/en). Logic keys (tones, fresh_days, coverage) stay
# stable; only display labels are translated here. ASCII-only per file convention.
_LANG_IDX: dict[str, int] = {"fr": 0, "de": 1, "en": 2}
_TR: dict[str, tuple[str, str, str]] = {
    "subtitle": (
        "Les sources sur lesquelles cet agent est ancré (live pgvector).",
        "Die Quellen, auf denen dieser Agent verankert ist (live pgvector).",
        "The sources this agent is grounded on (live pgvector).",
    ),
    "act_manage": ("Gérer le catalogue", "Katalog verwalten", "Manage catalogue"),
    "act_memory": ("Sources & mémoire", "Quellen & Speicher", "Sources & memory"),
    "act_attach": ("Rattacher une source", "Quelle hinzufügen", "Attach a source"),
    "kpi_sources": ("Sources rattachées", "Verknüpfte Quellen", "Attached sources"),
    "kpi_coverage": ("Couverture des sources", "Quellenabdeckung", "Source coverage"),
    "kpi_freshness": ("Fraîcheur", "Aktualität", "Freshness"),
    "kpi_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "kpi_hitrate": ("Hit-rate retrieval", "Retrieval-Trefferquote", "Retrieval hit-rate"),
    "f_search": (
        "Rechercher une source rattachée...",
        "Verknüpfte Quelle suchen...",
        "Search an attached source...",
    ),
    "f_more": ("Filtres", "Filter", "Filters"),
    "col_source": ("Source", "Quelle", "Source"),
    "col_type": ("Type", "Typ", "Type"),
    "col_status": ("Statut", "Status", "Status"),
    "col_volume": ("Volume", "Volumen", "Volume"),
    "col_freshness": ("Fraîcheur", "Aktualität", "Freshness"),
    "col_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "type_reg": ("Réglementation", "Regulierung", "Regulation"),
    "type_prod": ("Corpus produit", "Produktkorpus", "Product corpus"),
    "st_active": ("Active", "Aktiv", "Active"),
    "st_off": ("Désactivée", "Deaktiviert", "Disabled"),
    "tab_usage": ("Usage", "Nutzung", "Usage"),
    "tab_answers": ("Réponses ancrées", "Verankerte Antworten", "Grounded answers"),
    "tab_params": ("Paramètres", "Parameter", "Parameters"),
    "summary_title": ("Résumé", "Zusammenfassung", "Summary"),
    "usage_title": (
        "Utilisation par cet agent",
        "Nutzung durch diesen Agenten",
        "Usage by this agent",
    ),
    "u_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "u_hits": ("Requêtes ayant cité", "Anfragen mit Treffer", "Queries that cited"),
    "u_share": ("Part du corpus", "Korpusanteil", "Corpus share"),
    "u_grounded": ("Réponses ancrées", "Verankerte Antworten", "Grounded answers"),
    "u_lastused": ("Dernière utilisation", "Letzte Nutzung", "Last used"),
    "u_chunks": ("Chunks indexés", "Indexierte Chunks", "Indexed chunks"),
    "u_lastindex": ("Dernière indexation", "Letzte Indexierung", "Last indexed"),
    "ans_real": (
        "Échanges réels ancrés sur cette source",
        "Reale verankerte Dialoge zu dieser Quelle",
        "Real grounded exchanges on this source",
    ),
    "ans_docs": (
        "Documents ancrés (locators réels)",
        "Verankerte Dokumente (reale Locators)",
        "Grounded documents (real locators)",
    ),
    "params_title": ("Paramètres d'ancrage", "Verankerungsparameter", "Grounding parameters"),
    "p_embed": ("Modèle d'embedding", "Embedding-Modell", "Embedding model"),
    "p_dim": ("Dimension", "Dimension", "Dimension"),
    "p_corpus": ("Corpus", "Korpus", "Corpus"),
    "p_docs": ("Documents", "Dokumente", "Documents"),
    "p_langs": ("Langues", "Sprachen", "Languages"),
    "p_topk": ("Top-k retrieval", "Top-k Retrieval", "Top-k retrieval"),
    "p_distance": ("Distance", "Distanz", "Distance"),
    "p_status": ("Statut d'ancrage", "Verankerungsstatus", "Grounding status"),
    "actions_title": ("Actions", "Aktionen", "Actions"),
    "attach_title": ("État du rattachement", "Verknüpfungsstatus", "Attachment state"),
    "a_attached": ("Rattachée à l'agent", "Mit dem Agenten verknüpft", "Attached to the agent"),
    "a_active": ("Active pour cet agent", "Für diesen Agenten aktiv", "Active for this agent"),
    "a_index": ("Dernière indexation", "Letzte Indexierung", "Last indexing"),
    "a_used": ("Dernière utilisation", "Letzte Nutzung", "Last use"),
    "yes": ("Oui", "Ja", "Yes"),
    "no": ("Non", "Nein", "No"),
    "toggle_label": ("Active pour cet agent", "Für diesen Agenten aktiv", "Active for this agent"),
    "detach": ("Détacher de l'agent", "Vom Agenten lösen", "Detach from agent"),
    "full_sheet": (
        "Voir la fiche complète dans Sources & mémoire",
        "Vollständige Karte in Quellen & Speicher ansehen",
        "View full sheet in Sources & memory",
    ),
    "today": ("Aujourd'hui", "Heute", "Today"),
    "day_unit": ("j", "T", "d"),
}


def _norm_lang(lang: str) -> str:
    return lang if lang in _LANG_IDX else "fr"


def _t(key: str, lang: str) -> str:
    """Localized label for ``key`` (falls back to French)."""
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "knowledge_state.json"


def _probe_path() -> Path:
    return get_settings().guard.audit_file.parent / "knowledge_citations.json"


def _load_state() -> dict[str, dict[str, bool]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, bool]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _load_probe() -> dict[str, object]:
    """Return the full cached retrieval-probe payload (categories + _overall).

    Offline fallback only — the live path is :func:`load_citation_probe`, which
    reads the durable Postgres counters. This still reads the file written by
    ``scripts/probe_retrieval.py`` so an offline replay keeps working when the
    database has no recorded queries yet.
    """
    path = _probe_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def citation_probe_from_counts(counts: citations.CitationCounts) -> dict[str, object]:
    """Shape durable citation counters into the probe payload (categories + _overall).

    Identical format to ``scripts/probe_retrieval.py`` so the dashboards consume
    it unchanged: ``categories[cat] = {citation, hits}`` plus an ``_overall``
    block carrying citation / hitrate / coverage.
    """
    denom = counts.queries or 1
    n_cats = len(_SOURCE_META)
    cats: dict[str, object] = {
        cat: {
            "citation": round(100 * counts.hits.get(cat, 0) / denom, 1),
            "hits": counts.hits.get(cat, 0),
        }
        for cat in _SOURCE_META
    }
    overall = {
        "citation": round(100 * sum(counts.hits.values()) / (denom * n_cats), 1),
        "hitrate": round(100 * counts.queries_with_hit / denom, 1),
        "coverage": round(100 * sum(1 for v in counts.hits.values() if v) / n_cats, 1),
    }
    return {
        "run_at": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "source": "postgres",
        "queries": counts.queries,
        "categories": cats,
        "_overall": overall,
    }


async def load_citation_probe() -> dict[str, object]:
    """Live citation telemetry: durable Postgres counters, file as fallback.

    Reads the per-source citation counters recorded on every real retrieval
    (:func:`tessera.retrieval.citations.record_retrieval_query`). Falls back to
    the offline probe cache when the counters are unavailable or still empty.
    """
    counts = await citations.load_citation_counts()
    if counts is None or counts.queries == 0:
        return _load_probe()
    return citation_probe_from_counts(counts)


def _load_traffic() -> dict[str, object]:
    """Return per-category grounded-question traffic (from generate_traffic)."""
    path = _state_path().parent / "knowledge_traffic.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    cats = data.get("categories") if isinstance(data, dict) else None
    return cats if isinstance(cats, dict) else {}


def _rel_days(n: int, lang: str) -> str:
    return {"fr": f"il y a {n} j", "de": f"vor {n} T", "en": f"{n}d ago"}[_norm_lang(lang)]


def _ago(iso: str, lang: str) -> str:
    """Relative localized age from an ISO timestamp ('' on parse failure)."""
    try:
        moment = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    delta = datetime.now(UTC) - moment
    hour_s = 3600
    if delta.days >= 1:
        return _rel_days(delta.days, lang)
    secs = delta.total_seconds()
    if secs < hour_s:
        n = max(1, int(secs // 60))
        return {"fr": f"il y a {n} min", "de": f"vor {n} Min", "en": f"{n}m ago"}[_norm_lang(lang)]
    n = int(secs // hour_s)
    return {"fr": f"il y a {n} h", "de": f"vor {n} Std", "en": f"{n}h ago"}[_norm_lang(lang)]


async def _fetch_rows() -> list[dict[str, object]]:
    """Return every chunk's (corpus, source, language, category, locator, inserted_at)."""
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT corpus, source, language, metadata, inserted_at FROM {table}"  # noqa: S608
            )
            return list(await cur.fetchall())


def set_source_state(
    category: str, *, attached: bool | None = None, active: bool | None = None
) -> None:
    """Persist an attach/active change for one source category."""
    state = _load_state()
    entry = state.get(category, {"attached": True, "active": True})
    if attached is not None:
        entry["attached"] = attached
    if active is not None:
        entry["active"] = active
    state[category] = entry
    _save_state(state)


def available_sources() -> set[str]:
    """The set of known source category ids (for endpoint validation)."""
    return set(_SOURCE_META)


def _freshness(now: datetime, when: datetime, lang: str) -> str:
    days = (now - when).days
    if days <= 0:
        return _t("today", lang)
    return _rel_days(days, lang)


class _Aggregate:
    """Per-category aggregates collected from the pgvector rows."""

    __slots__ = ("chunks", "docs", "freshest", "langs", "locators")

    def __init__(self) -> None:
        self.chunks: dict[str, int] = {}
        self.langs: dict[str, set[str]] = {}
        self.freshest: dict[str, datetime] = {}
        self.docs: dict[str, set[str]] = {}
        self.locators: dict[str, list[str]] = {}


def _aggregate(rows: list[dict[str, object]]) -> _Aggregate:
    agg = _Aggregate()
    for row in rows:
        meta = row["metadata"]
        if not isinstance(meta, dict):
            meta = json.loads(meta) if isinstance(meta, str) else {}
        cat = str(meta.get("category", ""))
        if cat not in _SOURCE_META:
            continue
        agg.chunks[cat] = agg.chunks.get(cat, 0) + 1
        agg.langs.setdefault(cat, set()).add(str(row["language"]))
        agg.docs.setdefault(cat, set()).add(str(row["source"]))
        loc = str(meta.get("locator", "")).strip()
        if loc and loc not in agg.locators.setdefault(cat, []):
            agg.locators[cat].append(loc)
        ins = row["inserted_at"]
        if isinstance(ins, datetime):
            agg.freshest[cat] = max(agg.freshest.get(cat, ins), ins)
    return agg


async def build_connaissances(lang: str = "fr") -> dict[str, object]:
    """Assemble the Connaissances payload from the live retrieval store.

    Display labels are localized via ``lang`` (fr/de/en); logic keys
    (``status_tone``, ``type_tone``, ``fresh_days``, ``coverage``) stay stable.
    """
    return _assemble(
        await _fetch_rows(), _load_state(), await load_citation_probe(), _load_traffic(), lang
    )


def _assemble(
    raw_rows: list[dict[str, object]],
    state: dict[str, dict[str, bool]],
    probe: dict[str, object],
    traffic: dict[str, object],
    lang: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Pure assembly of the Connaissances payload (no I/O) - unit-testable."""
    lang = _norm_lang(lang)
    now = now or datetime.now(UTC)
    agg = _aggregate(raw_rows)
    chunks, freshest, docs = agg.chunks, agg.freshest, agg.docs

    total_chunks = sum(chunks.values()) or 1
    cats_probe = probe.get("categories")
    cats_probe = cats_probe if isinstance(cats_probe, dict) else {}
    overall = probe.get("_overall")
    overall = overall if isinstance(overall, dict) else {}
    ordered = sorted(chunks, key=lambda c: -chunks[c])

    def _cite_of(cat: str) -> float | None:
        entry = cats_probe.get(cat)
        if isinstance(entry, dict) and isinstance(entry.get("citation"), int | float):
            return float(entry["citation"])
        return None

    def _hits_of(cat: str) -> int:
        entry = cats_probe.get(cat)
        return int(entry["hits"]) if isinstance(entry, dict) and "hits" in entry else 0

    rows_out: list[dict[str, object]] = []
    attachable: list[dict[str, object]] = []
    for cat in ordered:
        type_tone = _SOURCE_META[cat]
        meta_name = _source_name(cat, lang)
        type_label = _t("type_reg" if type_tone == "reg" else "type_prod", lang)
        st = state.get(cat, {"attached": True, "active": True})
        if not st.get("attached", True):
            attachable.append({"key": cat, "name": meta_name, "type": type_label})
            continue
        active = st.get("active", True)
        cite_pct = _cite_of(cat)
        tr = traffic.get(cat)
        grounded = (
            int(tr["count"]) if isinstance(tr, dict) and isinstance(tr.get("count"), int) else 0
        )
        rows_out.append(
            {
                "key": cat,
                "name": meta_name,
                "path": rows_chunks_label(chunks[cat], len(docs[cat]), lang),
                "type": type_label,
                "type_tone": type_tone,
                "status": _t("st_active" if active else "st_off", lang),
                "status_tone": "good" if active else "off",
                # Real share of the indexed corpus by chunk volume (sums to ~100%).
                "coverage": round(100 * chunks[cat] / total_chunks),
                "freshness": _freshness(now, freshest[cat], lang) if cat in freshest else "-",
                "fresh_days": (now - freshest[cat]).days if cat in freshest else 9999,
                "citation": f"{round(cite_pct)}%" if cite_pct is not None else "-",
                "hits": _hits_of(cat),
                "langs": sorted(agg.langs.get(cat, set())),
                "grounded": grounded,
            }
        )
    attached_count = len(rows_out)

    # Real distributions across sources (chunk-desc order) for the KPI sparklines.
    doc_series = [len(docs[c]) for c in ordered]
    chunk_series = [chunks[c] for c in ordered]
    fresh_series = [max(0, (now - freshest[c]).days) if c in freshest else 0 for c in ordered]
    cite_series = [round(_cite_of(c) or 0) for c in ordered]
    hit_series = [_hits_of(c) for c in ordered]
    fresh_days = min(((now - w).days for w in freshest.values()), default=0)

    fresh_value = _t("today", lang) if fresh_days <= 0 else f"{fresh_days} {_t('day_unit', lang)}"
    kpis = [
        {
            "key": "sources",
            "label": _t("kpi_sources", lang),
            "value": str(attached_count),
            "series": doc_series,
        },
        {
            "key": "coverage",
            "label": _t("kpi_coverage", lang),
            "value": _pct_or_dash(overall.get("coverage")),
            "series": chunk_series,
        },
        {
            "key": "freshness",
            "label": _t("kpi_freshness", lang),
            "value": fresh_value,
            "series": fresh_series,
        },
        {
            "key": "citation",
            "label": _t("kpi_citation", lang),
            "value": _pct_or_dash(overall.get("citation")),
            "series": cite_series,
        },
        {
            "key": "hitrate",
            "label": _t("kpi_hitrate", lang),
            "value": _pct_or_dash(overall.get("hitrate")),
            "series": hit_series,
        },
    ]

    details = [_build_detail(r, agg, state, traffic, lang) for r in rows_out]

    return {
        "title": "Connaissances",
        "subtitle": _t("subtitle", lang),
        "actions": {
            "manage": _t("act_manage", lang),
            "memory": _t("act_memory", lang),
            "attach": _t("act_attach", lang),
        },
        "kpis": kpis,
        "attachable": attachable,
        "filters": {
            "search": _t("f_search", lang),
            "selects": [],
            "more": _t("f_more", lang),
        },
        "table": {
            "columns": [
                _t("col_source", lang),
                _t("col_type", lang),
                _t("col_status", lang),
                _t("col_volume", lang),
                _t("col_freshness", lang),
                _t("col_citation", lang),
            ],
            "rows": rows_out,
            "count": f"{len(rows_out)}",
        },
        "details": details,
    }


def rows_chunks_label(chunks: int, docs: int, lang: str = "fr") -> str:
    """Subtitle under a source name: real chunk and document counts."""
    if _norm_lang(lang) == "de":
        return f"{chunks} Chunks / {docs} Dokumente"
    return f"{chunks} chunks / {docs} documents"


def _pct_or_dash(value: object) -> str:
    return f"{round(value)}%" if isinstance(value, int | float) else "-"


def _summary(chunks: int, docs: int, langs: str, lang: str) -> str:
    if lang == "de":
        return f"In pgvector verankerte Quelle: {chunks} Chunks aus {docs} Dokumenten, in {langs}."
    if lang == "en":
        return f"Source grounded in pgvector: {chunks} chunks from {docs} documents, in {langs}."
    return f"Source ancrée dans pgvector : {chunks} chunks issus de {docs} documents, en {langs}."


def _build_detail(
    row: dict[str, object],
    agg: _Aggregate,
    state: dict[str, dict[str, bool]],
    traffic: dict[str, object],
    lang: str,
) -> dict[str, object]:
    cat = str(row["key"])
    st = state.get(cat, {"attached": True, "active": True})
    locs = agg.locators.get(cat, [])
    langs = ", ".join(sorted(agg.langs[cat]))
    corpus = "regulations" if row["type_tone"] == "reg" else "credit_aurore"

    tr = traffic.get(cat)
    tr = tr if isinstance(tr, dict) else {}
    raw_answers = tr.get("answers")
    raw_answers = raw_answers if isinstance(raw_answers, list) else []
    grounded = int(tr.get("count", 0)) if isinstance(tr.get("count"), int) else 0
    last_used = _ago(str(tr.get("last_used", "")), lang) or "-"

    if raw_answers:
        answers_title = _t("ans_real", lang)
        answers = [
            {
                "text": str(a.get("text", "")),
                "answer": str(a.get("answer", "")),
                "time": _ago(str(a.get("time", "")), lang),
            }
            for a in raw_answers[:5]
            if isinstance(a, dict)
        ]
    else:
        answers_title = _t("ans_docs", lang)
        answers = [{"text": loc, "answer": "", "time": ""} for loc in locs[:5]]

    return {
        "name": str(row["name"]),
        "status": str(row["status"]),
        "status_tone": str(row["status_tone"]),
        "tabs": [_t("tab_usage", lang), _t("tab_answers", lang), _t("tab_params", lang)],
        "summary_title": _t("summary_title", lang),
        "summary": _summary(agg.chunks[cat], len(agg.docs[cat]), langs, lang),
        "usage_title": _t("usage_title", lang),
        "usage": [
            {"label": _t("u_citation", lang), "value": str(row["citation"])},
            {"label": _t("u_hits", lang), "value": str(row.get("hits", 0))},
            {"label": _t("u_share", lang), "value": f"{row['coverage']}%"},
            {"label": _t("u_grounded", lang), "value": str(grounded)},
            {"label": _t("u_lastused", lang), "value": last_used},
            {"label": _t("u_chunks", lang), "value": str(agg.chunks[cat])},
            {
                "label": _t("u_lastindex", lang),
                "value": agg.freshest[cat].strftime("%d/%m/%Y") if cat in agg.freshest else "-",
            },
        ],
        "answers_title": answers_title,
        "answers": answers,
        "params_title": _t("params_title", lang),
        "params": [
            {"label": _t("p_embed", lang), "value": embedding_model_name()},
            {"label": _t("p_dim", lang), "value": str(embedding_dimension())},
            {"label": _t("p_corpus", lang), "value": corpus},
            {"label": _t("p_docs", lang), "value": str(len(agg.docs[cat]))},
            {"label": _t("p_langs", lang), "value": langs},
            {"label": _t("p_topk", lang), "value": "5"},
            {"label": _t("p_distance", lang), "value": "cosine"},
            {"label": _t("p_status", lang), "value": str(row["status"])},
        ],
        # OT-01 object-trace: the attachment state of this source for this agent.
        # Sourced from the durable attach/active store + the real pgvector ingestion
        # timestamp + traffic. Note: attach/detach are not yet S1-audited, so this
        # is current state + ingestion, not a full versioned event history.
        "attachment": {
            "title": _t("attach_title", lang),
            "rows": [
                {
                    "label": _t("a_attached", lang),
                    "value": _t("yes" if st.get("attached", True) else "no", lang),
                },
                {
                    "label": _t("a_active", lang),
                    "value": _t("yes" if st.get("active", True) else "no", lang),
                },
                {
                    "label": _t("a_index", lang),
                    "value": (
                        agg.freshest[cat].strftime("%d/%m/%Y") if cat in agg.freshest else "-"
                    ),
                },
                {"label": _t("a_used", lang), "value": last_used},
            ],
        },
        "actions_title": _t("actions_title", lang),
        "toggle_label": _t("toggle_label", lang),
        "toggle_on": bool(st.get("active", True)),
        "detach": _t("detach", lang),
        "full_sheet": _t("full_sheet", lang),
        "key": cat,
    }
