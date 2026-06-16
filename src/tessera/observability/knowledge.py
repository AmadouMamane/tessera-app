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

from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "available_sources",
    "build_connaissances",
    "set_source_state",
]

# category id -> (display name, type label, type tone, corpus)
_SOURCE_META: dict[str, tuple[str, str, str]] = {
    "dora": ("DORA - Resilience operationnelle", "Reglementation", "reg"),
    "gdpr": ("RGPD - Protection des donnees", "Reglementation", "reg"),
    "bafin": ("BaFin - Supervision DE", "Reglementation", "reg"),
    "cnil": ("CNIL - Donnees personnelles FR", "Reglementation", "reg"),
    "comptes": ("Credit Aurore - Comptes", "Corpus produit", "prod"),
    "cartes": ("Credit Aurore - Cartes", "Corpus produit", "prod"),
    "credit": ("Credit Aurore - Credit", "Corpus produit", "prod"),
    "epargne": ("Credit Aurore - Epargne", "Corpus produit", "prod"),
    "assurance": ("Credit Aurore - Assurances", "Corpus produit", "prod"),
    "operations": ("Credit Aurore - Operations", "Corpus produit", "prod"),
    "securite": ("Credit Aurore - Securite", "Corpus produit", "prod"),
    "service": ("Credit Aurore - Service client", "Corpus produit", "prod"),
    "conditions": ("Credit Aurore - Conditions generales", "Corpus produit", "prod"),
    "packages": ("Credit Aurore - Offres groupees", "Corpus produit", "prod"),
    "fidelite": ("Credit Aurore - Fidelite", "Corpus produit", "prod"),
}

# --- Localization (fr/de/en). Logic keys (tones, fresh_days, coverage) stay
# stable; only display labels are translated here. ASCII-only per file convention.
_LANG_IDX: dict[str, int] = {"fr": 0, "de": 1, "en": 2}
_TR: dict[str, tuple[str, str, str]] = {
    "subtitle": (
        "Les sources sur lesquelles cet agent est ancre (live pgvector).",
        "Die Quellen, auf denen dieser Agent verankert ist (live pgvector).",
        "The sources this agent is grounded on (live pgvector).",
    ),
    "act_manage": ("Gerer le catalogue", "Katalog verwalten", "Manage catalogue"),
    "act_memory": ("Sources & memoire", "Quellen & Speicher", "Sources & memory"),
    "act_attach": ("Rattacher une source", "Quelle hinzufuegen", "Attach a source"),
    "kpi_sources": ("Sources rattachees", "Verknuepfte Quellen", "Attached sources"),
    "kpi_coverage": ("Couverture des sources", "Quellenabdeckung", "Source coverage"),
    "kpi_freshness": ("Fraicheur", "Aktualitaet", "Freshness"),
    "kpi_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "kpi_hitrate": ("Hit-rate retrieval", "Retrieval-Trefferquote", "Retrieval hit-rate"),
    "f_search": (
        "Rechercher une source rattachee...",
        "Verknuepfte Quelle suchen...",
        "Search an attached source...",
    ),
    "f_more": ("Filtres", "Filter", "Filters"),
    "col_source": ("Source", "Quelle", "Source"),
    "col_type": ("Type", "Typ", "Type"),
    "col_status": ("Statut", "Status", "Status"),
    "col_volume": ("Volume", "Volumen", "Volume"),
    "col_freshness": ("Fraicheur", "Aktualitaet", "Freshness"),
    "col_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "type_reg": ("Reglementation", "Regulierung", "Regulation"),
    "type_prod": ("Corpus produit", "Produktkorpus", "Product corpus"),
    "st_active": ("Active", "Aktiv", "Active"),
    "st_off": ("Desactivee", "Deaktiviert", "Disabled"),
    "tab_usage": ("Usage", "Nutzung", "Usage"),
    "tab_answers": ("Reponses ancrees", "Verankerte Antworten", "Grounded answers"),
    "tab_params": ("Parametres", "Parameter", "Parameters"),
    "summary_title": ("Resume", "Zusammenfassung", "Summary"),
    "usage_title": (
        "Utilisation par cet agent",
        "Nutzung durch diesen Agenten",
        "Usage by this agent",
    ),
    "u_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "u_hits": ("Requetes ayant cite", "Anfragen mit Treffer", "Queries that cited"),
    "u_share": ("Part du corpus", "Korpusanteil", "Corpus share"),
    "u_grounded": ("Reponses ancrees", "Verankerte Antworten", "Grounded answers"),
    "u_lastused": ("Derniere utilisation", "Letzte Nutzung", "Last used"),
    "u_chunks": ("Chunks indexes", "Indexierte Chunks", "Indexed chunks"),
    "u_lastindex": ("Derniere indexation", "Letzte Indexierung", "Last indexed"),
    "ans_real": (
        "Echanges reels ancres sur cette source",
        "Reale verankerte Dialoge zu dieser Quelle",
        "Real grounded exchanges on this source",
    ),
    "ans_docs": (
        "Documents ancres (locators reels)",
        "Verankerte Dokumente (reale Locators)",
        "Grounded documents (real locators)",
    ),
    "params_title": ("Parametres d'ancrage", "Verankerungsparameter", "Grounding parameters"),
    "p_embed": ("Modele d'embedding", "Embedding-Modell", "Embedding model"),
    "p_dim": ("Dimension", "Dimension", "Dimension"),
    "p_corpus": ("Corpus", "Korpus", "Corpus"),
    "p_docs": ("Documents", "Dokumente", "Documents"),
    "p_langs": ("Langues", "Sprachen", "Languages"),
    "p_topk": ("Top-k retrieval", "Top-k Retrieval", "Top-k retrieval"),
    "p_distance": ("Distance", "Distanz", "Distance"),
    "p_status": ("Statut d'ancrage", "Verankerungsstatus", "Grounding status"),
    "actions_title": ("Actions", "Aktionen", "Actions"),
    "toggle_label": ("Active pour cet agent", "Fuer diesen Agenten aktiv", "Active for this agent"),
    "detach": ("Detacher de l'agent", "Vom Agenten loesen", "Detach from agent"),
    "full_sheet": (
        "Voir la fiche complete dans Sources & memoire",
        "Vollstaendige Karte in Quellen & Speicher ansehen",
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
    """Return the full cached retrieval-probe payload (categories + _overall)."""
    path = _probe_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


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
    table = get_settings().postgres.vector_table
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
    lang = _norm_lang(lang)
    now = datetime.now(UTC)
    state = _load_state()
    probe = _load_probe()
    traffic = _load_traffic()
    agg = _aggregate(await _fetch_rows())
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
        meta_name, _type_fr, type_tone = _SOURCE_META[cat]
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
    return f"Source ancree dans pgvector : {chunks} chunks issus de {docs} documents, en {langs}."


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
            {"label": _t("p_embed", lang), "value": "bge-m3"},
            {"label": _t("p_dim", lang), "value": "1024"},
            {"label": _t("p_corpus", lang), "value": corpus},
            {"label": _t("p_docs", lang), "value": str(len(agg.docs[cat]))},
            {"label": _t("p_langs", lang), "value": langs},
            {"label": _t("p_topk", lang), "value": "5"},
            {"label": _t("p_distance", lang), "value": "cosine"},
            {"label": _t("p_status", lang), "value": str(row["status"])},
        ],
        "actions_title": _t("actions_title", lang),
        "toggle_label": _t("toggle_label", lang),
        "toggle_on": bool(st.get("active", True)),
        "detach": _t("detach", lang),
        "full_sheet": _t("full_sheet", lang),
        "key": cat,
    }
