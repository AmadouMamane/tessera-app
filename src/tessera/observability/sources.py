"""Sources & memory cockpit overview (page #17, configurer/sources-memoire).

Replaces the former deterministic fixture (invented Kafka / MySQL / EUR figures)
with the agent's **real** data substrate, read live from Postgres:

  * the grounded knowledge **corpus** - one row per corpus category in the
    ``documents`` pgvector table (chunks, documents, languages, freshness,
    citation rate), reusing the same source taxonomy as Connaissances
    (:mod:`tessera.observability.knowledge`);
  * the **long-term memory** store (``long_term_memory``, ADR 0007) - persisted
    cross-session facts (rows, distinct subjects, kinds);
  * the durable **conversation transcript** (``conversation_messages``) - every
    persisted user/assistant message (rows, distinct conversations).

Read-only by design: the corpus is owned by Git / the ingestion pipeline and the
two memory stores are written by the running agent, not edited from this console.
Like Prompts and Integrations the functional axis is wired search / filter / sort
/ row-select / nav + export, not a fabricated mutation. Every displayed value
traces to a real artifact; unsourceable slots (cost) are dropped, not faked.

Free-text is localized (fr/de/en) via ``lang``; enum keys (type/status/
classification) stay stable and are translated frontend-side.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from tessera.memory.governance import ttl_for
from tessera.observability.knowledge import (
    _LANG_IDX,
    _SOURCE_META,
    _Aggregate,
    _aggregate,
    _ago,
    _fetch_rows,
    _freshness,
    _load_probe,
    _norm_lang,
    _source_name,
)
from tessera.retrieval.embeddings import embedding_dimension
from tessera.retrieval.store import _connection

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["available_source_ids", "build_sources_overview"]

# Stable ids for the two non-corpus memory stores.
_LTM_ID = "memory_longterm"
_TX_ID = "memory_transcript"

# type -> donut colour (keys are translated frontend-side).
_TYPE_COLOR: dict[str, str] = {
    "regulation": "#60a5fa",
    "product": "#a78bfa",
    "memory": "#f87171",
    "transcript": "#fbbf24",
}
_LANG_COLOR: dict[str, str] = {"fr": "#60a5fa", "de": "#fbbf24", "en": "#34d399"}

# Localized free-text labels. Enum keys (type/status/classification) are NOT here
# - the frontend owns those via next-intl. French carries its accents; only the
# punctuation stays ASCII (apostrophes, hyphens) to keep RUF001 happy.
_TR: dict[str, tuple[str, str, str]] = {
    "subtitle": (
        "Le substrat de données réel de l'agent : corpus pgvector + mémoire (live).",
        "Das reale Datensubstrat des Agenten: pgvector-Korpus + Speicher (live).",
        "The agent's real data substrate: pgvector corpus + memory (live).",
    ),
    "readonly": (
        "Lecture seule - corpus (Git/ingestion) et mémoire (écrite par l'agent)",
        "Schreibgeschützt - Korpus (Git/Ingestion) und Speicher (vom Agenten)",
        "Read-only - corpus (Git/ingestion) and memory (written by the agent)",
    ),
    "kpi_sources": ("Sources totales", "Quellen gesamt", "Total sources"),
    "kpi_corpus": ("Catégories de corpus", "Korpuskategorien", "Corpus categories"),
    "kpi_chunks": ("Chunks indexés", "Indexierte Chunks", "Indexed chunks"),
    "kpi_documents": ("Documents", "Dokumente", "Documents"),
    "kpi_languages": ("Langues du corpus", "Korpussprachen", "Corpus languages"),
    "kpi_memory": ("Souvenirs long terme", "Langzeit-Erinnerungen", "Long-term memories"),
    "kpi_transcript": ("Messages transcrits", "Transkribierte Nachrichten", "Transcript messages"),
    "kpi_conversations": ("Conversations", "Konversationen", "Conversations"),
    "name_ltm": (
        "Mémoire long terme",
        "Langzeitspeicher",
        "Long-term memory",
    ),
    "name_tx": (
        "Transcription des conversations",
        "Konversationstranskript",
        "Conversation transcript",
    ),
    "desc_corpus": (
        "Corpus ancré dans pgvector : {chunks} chunks issus de {docs} documents, en {langs}.",
        "In pgvector verankerter Korpus: {chunks} Chunks aus {docs} Dokumenten, in {langs}.",
        "Corpus grounded in pgvector: {chunks} chunks from {docs} documents, in {langs}.",
    ),
    "desc_ltm": (
        "Faits persistés par l'agent entre sessions ({rows} souvenirs, {subjects} sujets).",
        "Vom Agenten sitzungsübergreifend gespeicherte Fakten ({rows} Erinnerungen, "
        "{subjects} Subjekte).",
        "Facts the agent persists across sessions ({rows} memories, {subjects} subjects).",
    ),
    "desc_tx": (
        "Transcript durable des conversations ({rows} messages, {conv} conversations).",
        "Dauerhaftes Konversationstranskript ({rows} Nachrichten, {conv} Konversationen).",
        "Durable conversation transcript ({rows} messages, {conv} conversations).",
    ),
    "sec_overview": ("Vue d'ensemble", "Überblick", "Overview"),
    "sec_content": ("Contenu", "Inhalt", "Content"),
    "sec_usage": ("Usage", "Nutzung", "Usage"),
    "sec_governance": ("Gouvernance", "Governance", "Governance"),
    "l_type": ("Type", "Typ", "Type"),
    "l_classification": ("Classification", "Klassifizierung", "Classification"),
    "l_store": ("Magasin", "Speicher", "Store"),
    "l_connector": ("Connecteur", "Konnektor", "Connector"),
    "l_languages": ("Langues", "Sprachen", "Languages"),
    "l_status": ("Statut", "Status", "Status"),
    "l_chunks": ("Chunks indexés", "Indexierte Chunks", "Indexed chunks"),
    "l_documents": ("Documents distincts", "Eindeutige Dokumente", "Distinct documents"),
    "l_locators": ("Locators ancrés", "Verankerte Locators", "Grounded locators"),
    "l_embed": ("Modèle d'embedding", "Embedding-Modell", "Embedding model"),
    "l_dim": ("Dimension", "Dimension", "Dimension"),
    "l_distance": ("Distance", "Distanz", "Distance"),
    "l_rows": ("Lignes stockées", "Gespeicherte Zeilen", "Stored rows"),
    "l_subjects": ("Sujets distincts", "Eindeutige Subjekte", "Distinct subjects"),
    "l_kinds": ("Types de mémoire", "Speichertypen", "Memory kinds"),
    "l_messages": ("Messages", "Nachrichten", "Messages"),
    "l_conversations": ("Conversations", "Konversationen", "Conversations"),
    "l_citation": ("Taux de citation", "Zitationsrate", "Citation rate"),
    "l_hits": ("Requêtes ayant cité", "Anfragen mit Treffer", "Queries that cited"),
    "l_share": ("Part du corpus", "Korpusanteil", "Corpus share"),
    "l_lastindex": ("Dernière indexation", "Letzte Indexierung", "Last indexed"),
    "l_lastwrite": ("Dernière écriture", "Letzte Schreibung", "Last write"),
    "l_firstwrite": ("Première écriture", "Erste Schreibung", "First write"),
    "l_owner": ("Responsable", "Verantwortlich", "Owner"),
    "l_retention": ("Rétention", "Aufbewahrung", "Retention"),
    "l_screening": ("Filtrage PII", "PII-Filterung", "PII screening"),
    "owner_corpus": (
        "Équipe corpus (Git / ingestion)",
        "Korpus-Team (Git / Ingestion)",
        "Corpus team (Git / ingestion)",
    ),
    "owner_memory": (
        "Agent Tessera (gouvernance mémoire)",
        "Tessera-Agent (Speicher-Governance)",
        "Tessera agent (memory governance)",
    ),
    "ret_corpus": (
        "Permanente (versionnée dans Git)",
        "Permanent (in Git versioniert)",
        "Permanent (versioned in Git)",
    ),
    "ret_tx": ("Durable (transcript)", "Dauerhaft (Transkript)", "Durable (transcript)"),
    "screening_corpus": (
        "Documents publics / internes - pas de PII client",
        "Oeffentliche / interne Dokumente - keine Kunden-PII",
        "Public / internal documents - no customer PII",
    ),
    "screening_memory": (
        "Filtrage PII + consentement (memory.governance)",
        "PII-Filterung + Einwilligung (memory.governance)",
        "PII screening + consent (memory.governance)",
    ),
    "zone_bytype": ("Répartition par type", "Verteilung nach Typ", "Distribution by type"),
    "zone_volume": ("Volume par source", "Volumen pro Quelle", "Volume per source"),
    "zone_langs": ("Répartition par langue", "Verteilung nach Sprache", "Distribution by language"),
    "footer_source": (
        "pgvector (documents) + long_term_memory + conversation_messages",
        "pgvector (documents) + long_term_memory + conversation_messages",
        "pgvector (documents) + long_term_memory + conversation_messages",
    ),
    "unit_chunks": ("{n} chunks", "{n} Chunks", "{n} chunks"),
    "unit_rows": ("{n} lignes", "{n} Zeilen", "{n} rows"),
    "days": ("{n} jours", "{n} Tage", "{n} days"),
    "permanent": ("Permanente", "Permanent", "Permanent"),
    "ub_title": ("Utilisé par", "Verwendet von", "Used by"),
    "ub_col": ("Utilisé par", "Verwendet von", "Used by"),
    "ub_infra": ("Infra partagée (tous)", "Geteilte Infra (alle)", "Shared infra (all)"),
    "ub_none": ("Aucun produit", "Kein Produkt", "No product"),
    "ub_all": ("{n} produits (tous)", "{n} Produkte (alle)", "{n} products (all)"),
    "ub_n": ("{n} produits", "{n} Produkte", "{n} products"),
    "ub_regate": ("{n} à re-valider", "{n} neu zu validieren", "{n} to re-validate"),
    "ub_note": (
        "Modifier cette source re-gate les produits consommateurs (define -> "
        "consommateurs -> re-valider). La pastille = verdict eval-gate actuel du produit.",
        "Diese Quelle zu aendern re-gated die konsumierenden Produkte (define -> "
        "Konsumenten -> neu validieren). Der Punkt = aktuelles Eval-Gate-Verdikt.",
        "Changing this source re-gates the consuming products (define -> consumers -> "
        "re-validate). The dot = the product's current eval-gate verdict.",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _as_dt(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _vn(row: dict[str, object]) -> int:
    """Read a row's numeric volume (typed for mypy)."""
    value = row.get("volume_num")
    return value if isinstance(value, int) else 0


def _retention_for_memory(kinds: list[tuple[str, int]], lang: str) -> str:
    """Real per-kind TTL ceiling from memory.governance.ttl_for."""
    if not kinds:
        return _t("permanent", lang)
    worst = max(ttl_for(kind).days for kind, _ in kinds)
    return _t("days", lang).format(n=worst)


class _MemStat:
    """Live counters for one Postgres memory table."""

    __slots__ = ("conversations", "first", "kinds", "last", "rows", "subjects")

    def __init__(self) -> None:
        self.rows = 0
        self.subjects = 0
        self.conversations = 0
        self.kinds: list[tuple[str, int]] = []
        self.last: datetime | None = None
        self.first: datetime | None = None


async def _scalar_stat(sql: str) -> dict[str, object]:
    """Run one read-only aggregate; return {} if the table is absent."""
    async with _connection() as conn:
        conn.row_factory = dict_row
        try:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                row = await cur.fetchone()
                return dict(row) if row else {}
        except Exception:
            await conn.rollback()
            return {}


async def _fetch_longterm() -> _MemStat:
    stat = _MemStat()
    agg = await _scalar_stat(
        "SELECT count(*) AS rows, count(DISTINCT subject_id) AS subjects, "
        "max(created_at) AS last, min(created_at) AS first FROM long_term_memory"
    )
    stat.rows = _as_int(agg.get("rows"))
    stat.subjects = _as_int(agg.get("subjects"))
    stat.last = _as_dt(agg.get("last"))
    stat.first = _as_dt(agg.get("first"))
    if stat.rows:
        async with _connection() as conn:
            conn.row_factory = dict_row
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT kind, count(*) AS n FROM long_term_memory "
                        "GROUP BY kind ORDER BY n DESC"
                    )
                    stat.kinds = [(str(r["kind"]), int(r["n"])) for r in await cur.fetchall()]
            except Exception:
                await conn.rollback()
    return stat


async def _fetch_transcript() -> _MemStat:
    stat = _MemStat()
    agg = await _scalar_stat(
        "SELECT count(*) AS rows, count(DISTINCT conversation_id) AS conversations, "
        "max(created_at) AS last, min(created_at) AS first FROM conversation_messages"
    )
    stat.rows = _as_int(agg.get("rows"))
    stat.conversations = _as_int(agg.get("conversations"))
    stat.last = _as_dt(agg.get("last"))
    stat.first = _as_dt(agg.get("first"))
    return stat


# How many trailing days of memory growth the Historique tab plots.
_HISTORY_DAYS = 30


async def _daily_growth(table: str) -> list[dict[str, object]]:
    """Real per-day row counts for a memory table (last _HISTORY_DAYS days).

    The corpus has no time axis (one ingest batch), but the two memory tables
    carry a real ``created_at`` spanning weeks - so this is genuine history, not
    a fabricated snapshot timeline. Returns [] if the table is absent.
    """
    async with _connection() as conn:
        conn.row_factory = dict_row
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT date_trunc('day', created_at)::date AS day, count(*) AS n "  # noqa: S608
                    f"FROM {table} "
                    f"WHERE created_at >= now() - interval '{int(_HISTORY_DAYS)} days' "
                    "GROUP BY 1 ORDER BY 1"
                )
                return [
                    {"day": str(r["day"]), "count": int(r["n"])} for r in await cur.fetchall()
                ]
        except Exception:
            await conn.rollback()
            return []


def available_source_ids(corpus_categories: Sequence[str] | None = None) -> set[str]:
    """The known source ids (corpus categories + the two memory stores)."""
    cats = set(corpus_categories) if corpus_categories is not None else set(_SOURCE_META)
    return cats | {_LTM_ID, _TX_ID}


def _corpus_of(cat: str) -> str:
    """Map a fine-grained corpus category to the corpus id agents actually bind.

    Agents bind knowledge at the corpus level in ``agents.yaml`` (``credit_aurore``,
    ``regulations_dora``...), while this page lists per-category rows (``dora``,
    ``comptes``...). The regulation categories map 1-1 to ``regulations_<cat>``;
    every product category rolls up to the single ``credit_aurore`` corpus.
    """
    return f"regulations_{cat}" if _SOURCE_META.get(cat) == "reg" else "credit_aurore"


def _fetch_consumers() -> tuple[dict[str, list[dict[str, object]]], list[dict[str, object]]]:
    """Invert the registry knowledge bindings: corpus id -> consuming products.

    Returns ``(index, fleet)`` where ``index`` maps each corpus id to the list of
    consumer products (with their current eval-gate verdict) and ``fleet`` is the
    de-duplicated union of every consuming product (used for the shared memory
    stores, which every agent reads/writes). Degrades to empty on any failure so
    the page never breaks.
    """
    try:
        from tessera.observability.catalogue_consumers import catalogue_consumers

        data = catalogue_consumers("knowledge")
    except Exception:  # registry/release unavailable - degrade silently
        return {}, []
    index: dict[str, list[dict[str, object]]] = {}
    fleet: dict[str, dict[str, object]] = {}
    items = data.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        corpus_id = str(item.get("item", ""))
        consumers: list[dict[str, object]] = []
        raw = item.get("consumers")
        for con in raw if isinstance(raw, list) else []:
            if not isinstance(con, dict):
                continue
            rel = con.get("release")
            rel = rel if isinstance(rel, dict) else {}
            entry = {
                "agent_id": str(con.get("agent_id", "")),
                "name": str(con.get("name", con.get("agent_id", ""))),
                "tone": str(rel.get("verdict_tone", "muted")),
                "label": str(rel.get("verdict_label", "")),
                "passed": bool(rel.get("passed", False)),
            }
            consumers.append(entry)
            fleet[str(entry["agent_id"])] = entry
        index[corpus_id] = consumers
    fleet_list = sorted(fleet.values(), key=lambda c: str(c["name"]))
    return index, fleet_list


async def build_sources_overview(lang: str = "fr") -> dict[str, object]:
    """Assemble the Sources & memory payload from the live Postgres substrate."""
    lang = _norm_lang(lang)
    rows = await _fetch_rows()
    ltm = await _fetch_longterm()
    tx = await _fetch_transcript()
    consumers, fleet = _fetch_consumers()
    history = {
        _LTM_ID: await _daily_growth("long_term_memory"),
        _TX_ID: await _daily_growth("conversation_messages"),
    }
    return _assemble(rows, ltm, tx, _load_probe(), consumers, fleet, history, lang)


def _corpus_detail(
    cat: str, agg: _Aggregate, cite_pct: float | None, hits: int, share: int, lang: str
) -> dict[str, object]:
    chunks = agg.chunks.get(cat, 0)
    docs = len(agg.docs.get(cat, set()))
    locs = len(agg.locators.get(cat, []))
    langs = "/".join(sorted(c.upper() for c in agg.langs.get(cat, set())))
    last = agg.freshest[cat].strftime("%d/%m/%Y") if cat in agg.freshest else "-"
    reg = _SOURCE_META[cat] == "reg"
    classification = "public" if reg else "internal"
    return {
        "sections": [
            {
                "key": "overview",
                "title": _t("sec_overview", lang),
                "rows": [
                    {"label": _t("l_type", lang), "value": "regulation" if reg else "product"},
                    {"label": _t("l_classification", lang), "value": classification},
                    {"label": _t("l_store", lang), "value": "pgvector (documents)"},
                    {"label": _t("l_connector", lang), "value": "bge-m3 / cosine"},
                    {"label": _t("l_languages", lang), "value": langs or "-"},
                    {"label": _t("l_status", lang), "value": "active"},
                ],
            },
            {
                "key": "content",
                "title": _t("sec_content", lang),
                "rows": [
                    {"label": _t("l_chunks", lang), "value": _fmt_int(chunks)},
                    {"label": _t("l_documents", lang), "value": str(docs)},
                    {"label": _t("l_locators", lang), "value": str(locs)},
                    {"label": _t("l_embed", lang), "value": "bge-m3"},
                    {"label": _t("l_dim", lang), "value": str(embedding_dimension())},
                    {"label": _t("l_distance", lang), "value": "cosine"},
                ],
            },
            {
                "key": "usage",
                "title": _t("sec_usage", lang),
                "rows": [
                    {
                        "label": _t("l_citation", lang),
                        "value": f"{round(cite_pct)}%" if cite_pct is not None else "-",
                    },
                    {"label": _t("l_hits", lang), "value": str(hits)},
                    {"label": _t("l_share", lang), "value": f"{share}%"},
                    {"label": _t("l_lastindex", lang), "value": last},
                ],
            },
            {
                "key": "governance",
                "title": _t("sec_governance", lang),
                "rows": [
                    {"label": _t("l_classification", lang), "value": classification},
                    {"label": _t("l_retention", lang), "value": _t("ret_corpus", lang)},
                    {"label": _t("l_owner", lang), "value": _t("owner_corpus", lang)},
                    {"label": _t("l_screening", lang), "value": _t("screening_corpus", lang)},
                ],
            },
        ],
    }


def _memory_detail(stat: _MemStat, *, is_ltm: bool, lang: str) -> dict[str, object]:
    last = _ago(stat.last.isoformat(), lang) if stat.last else "-"
    first = stat.first.strftime("%d/%m/%Y") if stat.first else "-"
    store = "long_term_memory" if is_ltm else "conversation_messages"
    content_rows = (
        [
            {"label": _t("l_rows", lang), "value": _fmt_int(stat.rows)},
            {"label": _t("l_subjects", lang), "value": str(stat.subjects)},
            {
                "label": _t("l_kinds", lang),
                "value": ", ".join(k for k, _ in stat.kinds) or "-",
            },
            {"label": _t("l_embed", lang), "value": "bge-m3"},
            {"label": _t("l_dim", lang), "value": str(embedding_dimension())},
        ]
        if is_ltm
        else [
            {"label": _t("l_messages", lang), "value": _fmt_int(stat.rows)},
            {"label": _t("l_conversations", lang), "value": _fmt_int(stat.conversations)},
        ]
    )
    retention = _retention_for_memory(stat.kinds, lang) if is_ltm else _t("ret_tx", lang)
    return {
        "sections": [
            {
                "key": "overview",
                "title": _t("sec_overview", lang),
                "rows": [
                    {"label": _t("l_type", lang), "value": "memory" if is_ltm else "transcript"},
                    {"label": _t("l_classification", lang), "value": "confidential"},
                    {"label": _t("l_store", lang), "value": store},
                    {"label": _t("l_connector", lang), "value": "PostgreSQL"},
                    {"label": _t("l_status", lang), "value": "active" if stat.rows else "disabled"},
                ],
            },
            {"key": "content", "title": _t("sec_content", lang), "rows": content_rows},
            {
                "key": "usage",
                "title": _t("sec_usage", lang),
                "rows": [
                    {"label": _t("l_rows", lang), "value": _fmt_int(stat.rows)},
                    {"label": _t("l_lastwrite", lang), "value": last},
                    {"label": _t("l_firstwrite", lang), "value": first},
                ],
            },
            {
                "key": "governance",
                "title": _t("sec_governance", lang),
                "rows": [
                    {"label": _t("l_classification", lang), "value": "confidential"},
                    {"label": _t("l_retention", lang), "value": retention},
                    {"label": _t("l_owner", lang), "value": _t("owner_memory", lang)},
                    {"label": _t("l_screening", lang), "value": _t("screening_memory", lang)},
                ],
            },
        ],
    }


def _kpi(key: str, label: str, value: str, series: Sequence[float]) -> dict[str, object]:
    return {"key": key, "label": label, "value": value, "series": list(series)}


def _attach_descriptions(
    rows_out: list[dict[str, object]],
    agg: _Aggregate,
    ltm: _MemStat,
    tx: _MemStat,
    lang: str,
) -> None:
    """Localized description + identity fields, keyed onto each row's detail."""
    for row in rows_out:
        rid = str(row["id"])
        detail = row["detail"]
        if not isinstance(detail, dict):
            continue
        if rid == _LTM_ID:
            detail["description"] = _t("desc_ltm", lang).format(
                rows=ltm.rows, subjects=ltm.subjects
            )
        elif rid == _TX_ID:
            detail["description"] = _t("desc_tx", lang).format(rows=tx.rows, conv=tx.conversations)
        else:
            lang_str = ", ".join(sorted(agg.langs.get(rid, set())))
            detail["description"] = _t("desc_corpus", lang).format(
                chunks=agg.chunks[rid], docs=len(agg.docs.get(rid, set())), langs=lang_str
            )
        detail.update(
            {
                "id": rid,
                "name": str(row["name"]),
                "status": str(row["status"]),
                "type": str(row["type"]),
                "classification": str(row["classification"]),
            }
        )


def _used_by_label(cons: list[dict[str, object]], *, infra: bool, total: int, lang: str) -> str:
    """Compact 'Used by' cell: infra / all / a couple of names / a count."""
    if infra:
        return _t("ub_infra", lang)
    count = len(cons)
    if count == 0:
        return _t("ub_none", lang)
    if total and count >= total:
        return _t("ub_all", lang).format(n=count)
    if count <= 2:  # noqa: PLR2004 - two names fit, beyond that show a count
        return ", ".join(str(c["name"]) for c in cons)
    return _t("ub_n", lang).format(n=count)


def _attach_used_by(
    rows_out: list[dict[str, object]],
    consumers: dict[str, list[dict[str, object]]],
    fleet: list[dict[str, object]],
    lang: str,
) -> None:
    """Enrich each row + its detail with the consuming products (real used-by).

    Corpus rows inherit the consumers of their parent corpus binding (see
    :func:`_corpus_of`); the shared memory stores are infra read/written by the
    whole fleet, so they list every product. Each consumer carries its current
    eval-gate verdict, so a shared-source change shows its re-validation blast
    radius (define -> consumers -> re-validate).
    """
    total = len(fleet)
    for row in rows_out:
        rid = str(row["id"])
        infra = rid in {_LTM_ID, _TX_ID}
        cons = list(fleet) if infra else consumers.get(_corpus_of(rid), [])
        regate = sum(1 for c in cons if not c.get("passed", False))
        row["used_by"] = _used_by_label(cons, infra=infra, total=total, lang=lang)
        row["used_by_count"] = len(cons)
        row["consumer_ids"] = [str(c["agent_id"]) for c in cons]
        row["infra"] = infra
        detail = row["detail"]
        if isinstance(detail, dict):
            detail["consumers"] = {
                "title": _t("ub_title", lang),
                "label": row["used_by"],
                "count": len(cons),
                "regate_count": regate,
                "regate_label": _t("ub_regate", lang).format(n=regate) if regate else "",
                "infra": infra,
                "note": _t("ub_note", lang),
                "items": cons,
            }


def _assemble(
    raw_rows: list[dict[str, object]],
    ltm: _MemStat,
    tx: _MemStat,
    probe: dict[str, object],
    consumers: dict[str, list[dict[str, object]]] | None = None,
    fleet: list[dict[str, object]] | None = None,
    mem_history: dict[str, list[dict[str, object]]] | None = None,
    lang: str = "fr",
    now: datetime | None = None,
) -> dict[str, object]:
    """Pure assembly of the Sources & memory payload (no I/O) - unit-testable."""
    lang = _norm_lang(lang)
    consumers = consumers or {}
    fleet = fleet or []
    mem_history = mem_history or {}
    now = now or datetime.now(UTC)
    agg = _aggregate(raw_rows)
    total_chunks = sum(agg.chunks.values()) or 1

    cats_probe = probe.get("categories")
    cats_probe = cats_probe if isinstance(cats_probe, dict) else {}
    overall = probe.get("_overall")
    overall = overall if isinstance(overall, dict) else {}

    def _cite(cat: str) -> float | None:
        entry = cats_probe.get(cat)
        if isinstance(entry, dict) and isinstance(entry.get("citation"), int | float):
            return float(entry["citation"])
        return None

    def _hits(cat: str) -> int:
        entry = cats_probe.get(cat)
        return int(entry["hits"]) if isinstance(entry, dict) and "hits" in entry else 0

    # True per-language chunk counts (one row = one chunk = one language).
    lang_counts: dict[str, int] = {}
    for row in raw_rows:
        meta = row.get("metadata")
        if isinstance(meta, str):
            meta = json.loads(meta)
        cat = str(meta.get("category", "")) if isinstance(meta, dict) else ""
        if cat in _SOURCE_META:
            code = str(row.get("language", ""))
            lang_counts[code] = lang_counts.get(code, 0) + 1

    ordered = sorted(agg.chunks, key=lambda c: -agg.chunks[c])
    rows_out: list[dict[str, object]] = []
    for cat in ordered:
        reg = _SOURCE_META[cat] == "reg"
        share = round(100 * agg.chunks[cat] / total_chunks)
        cite = _cite(cat)
        cat_langs = sorted(agg.langs.get(cat, set()))
        rows_out.append(
            {
                "id": cat,
                "name": _source_name(cat, lang),
                "type": "regulation" if reg else "product",
                "classification": "public" if reg else "internal",
                "volume": _fmt_int(agg.chunks[cat]),
                "volume_num": agg.chunks[cat],
                "units": str(len(agg.docs.get(cat, set()))),
                "languages": "/".join(c.upper() for c in cat_langs) or "-",
                "freshness": (
                    _freshness(now, agg.freshest[cat], lang) if cat in agg.freshest else "-"
                ),
                "status": "active",
                "citation": f"{round(cite)}%" if cite is not None else "-",
                "hits": _hits(cat),
                "retention": _t("permanent", lang),
                "detail": _corpus_detail(cat, agg, cite, _hits(cat), share, lang),
            }
        )

    corpus_count = len(rows_out)
    total_docs = sum(len(agg.docs.get(c, set())) for c in ordered)

    rows_out.append(
        {
            "id": _LTM_ID,
            "name": _t("name_ltm", lang),
            "type": "memory",
            "classification": "confidential",
            "volume": _fmt_int(ltm.rows),
            "volume_num": ltm.rows,
            "units": str(ltm.subjects),
            "languages": "-",
            "freshness": _ago(ltm.last.isoformat(), lang) if ltm.last else "-",
            "status": "active" if ltm.rows else "disabled",
            "citation": "-",
            "hits": 0,
            "retention": _retention_for_memory(ltm.kinds, lang),
            "detail": _memory_detail(ltm, is_ltm=True, lang=lang),
        }
    )
    rows_out.append(
        {
            "id": _TX_ID,
            "name": _t("name_tx", lang),
            "type": "transcript",
            "classification": "confidential",
            "volume": _fmt_int(tx.rows),
            "volume_num": tx.rows,
            "units": _fmt_int(tx.conversations),
            "languages": "-",
            "freshness": _ago(tx.last.isoformat(), lang) if tx.last else "-",
            "status": "active" if tx.rows else "disabled",
            "citation": "-",
            "hits": 0,
            "retention": _t("ret_tx", lang),
            "detail": _memory_detail(tx, is_ltm=False, lang=lang),
        }
    )

    _attach_descriptions(rows_out, agg, ltm, tx, lang)
    _attach_used_by(rows_out, consumers, fleet, lang)
    for row in rows_out:
        # Real daily growth for the memory stores; corpus has no time axis -> [].
        row["growth"] = mem_history.get(str(row["id"]), [])

    total_sources = len(rows_out)
    chunk_series = [agg.chunks[c] for c in ordered] or [0]
    kpis = _build_kpis(
        rows_out, chunk_series, lang_counts, ltm, tx, corpus_count, total_docs, total_chunks, lang
    )
    by_type, by_env, cost_by_source = _build_distributions(rows_out, lang_counts, lang)

    return {
        "generated_at": now.isoformat(),
        "total_sources": total_sources,
        "page_size": total_sources,
        "subtitle": _t("subtitle", lang),
        "readonly_note": _t("readonly", lang),
        "kpis": kpis,
        "sources": rows_out,
        "selected": rows_out[0]["detail"] if rows_out else None,
        "by_type": by_type,
        "by_type_total": total_sources,
        "by_env": by_env,
        "cost_by_source": cost_by_source,
        "zones": {
            "by_type": _t("zone_bytype", lang),
            "by_env": _t("zone_volume", lang),
            "cost": _t("zone_langs", lang),
        },
        "embedding": {
            "model": "bge-m3",
            "dim": str(embedding_dimension()),
            "distance": "cosine",
            "topk": "5",
            "chunks": _fmt_int(total_chunks),
            "documents": _fmt_int(total_docs),
            "languages": str(len(lang_counts)),
        },
        "footer": {"total": total_sources, "source": _t("footer_source", lang)},
    }


def _build_kpis(
    rows_out: list[dict[str, object]],
    chunk_series: list[int],
    lang_counts: dict[str, int],
    ltm: _MemStat,
    tx: _MemStat,
    corpus_count: int,
    total_docs: int,
    total_chunks: int,
    lang: str,
) -> list[dict[str, object]]:
    """The eight posture KPIs (real counts + real distribution sparklines)."""
    volume_series = [_vn(r) for r in rows_out]
    return [
        _kpi("sources", _t("kpi_sources", lang), str(len(rows_out)), volume_series),
        _kpi("corpus", _t("kpi_corpus", lang), str(corpus_count), chunk_series),
        _kpi("chunks", _t("kpi_chunks", lang), _fmt_int(total_chunks), chunk_series),
        _kpi("documents", _t("kpi_documents", lang), _fmt_int(total_docs), chunk_series),
        _kpi("languages", _t("kpi_languages", lang), str(len(lang_counts)), chunk_series),
        _kpi("memory", _t("kpi_memory", lang), _fmt_int(ltm.rows), volume_series),
        _kpi("transcript", _t("kpi_transcript", lang), _fmt_int(tx.rows), volume_series),
        _kpi(
            "conversations",
            _t("kpi_conversations", lang),
            _fmt_int(tx.conversations),
            volume_series,
        ),
    ]


def _build_distributions(
    rows_out: list[dict[str, object]], lang_counts: dict[str, int], lang: str
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """The donut (by type), volume-per-source bars, and per-language bars."""
    total_sources = len(rows_out) or 1
    type_counts: dict[str, int] = {}
    for row in rows_out:
        ty = str(row["type"])
        type_counts[ty] = type_counts.get(ty, 0) + 1
    by_type = [
        {
            "key": ty,
            "count": n,
            "pct": round(n / total_sources * 100),
            "color": _TYPE_COLOR.get(ty, "#64748b"),
        }
        for ty, n in sorted(type_counts.items(), key=lambda kv: -kv[1])
    ]

    total_volume = sum(_vn(r) for r in rows_out) or 1
    by_env = [
        {
            "key": str(r["id"]),
            "label": str(r["name"]),
            "value": str(r["volume"]),
            "pct": round(_vn(r) / total_volume * 100),
            "color": _TYPE_COLOR.get(str(r["type"]), "#64748b"),
        }
        for r in sorted(rows_out, key=lambda x: -_vn(x))[:6]
    ]

    cost_by_source = [
        {
            "name": code.upper(),
            "value": n,
            "label": _t("unit_chunks", lang).format(n=_fmt_int(n)),
            "color": _LANG_COLOR.get(code, "#64748b"),
        }
        for code, n in sorted(lang_counts.items(), key=lambda kv: -kv[1])
    ]
    return by_type, by_env, cost_by_source
