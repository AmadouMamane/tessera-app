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


def _freshness(now: datetime, when: datetime) -> str:
    days = (now - when).days
    if days <= 0:
        return "Aujourd'hui"
    if days == 1:
        return "Hier"
    return f"il y a {days} j"


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


async def build_connaissances() -> dict[str, object]:
    """Assemble the Connaissances payload from the live retrieval store."""
    now = datetime.now(UTC)
    state = _load_state()
    probe = _load_probe()
    agg = _aggregate(await _fetch_rows())
    chunks, freshest, docs = agg.chunks, agg.freshest, agg.docs

    max_chunks = max(chunks.values(), default=1)
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
        meta_name, type_label, type_tone = _SOURCE_META[cat]
        st = state.get(cat, {"attached": True, "active": True})
        if not st.get("attached", True):
            attachable.append({"key": cat, "name": meta_name, "type": type_label})
            continue
        active = st.get("active", True)
        cite_pct = _cite_of(cat)
        rows_out.append(
            {
                "key": cat,
                "name": meta_name,
                "path": rows_chunks_label(chunks[cat], len(docs[cat])),
                "type": type_label,
                "type_tone": type_tone,
                "status": "Active" if active else "Desactivee",
                "status_tone": "good" if active else "off",
                "coverage": round(100 * chunks[cat] / max_chunks),
                "freshness": _freshness(now, freshest[cat]) if cat in freshest else "-",
                "fresh_days": (now - freshest[cat]).days if cat in freshest else 9999,
                "citation": f"{round(cite_pct)}%" if cite_pct is not None else "-",
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

    kpis = [
        {
            "key": "sources",
            "label": "Sources rattachees",
            "value": str(attached_count),
            "series": doc_series,
        },
        {
            "key": "coverage",
            "label": "Couverture des requetes",
            "value": _pct_or_dash(overall.get("coverage")),
            "series": chunk_series,
        },
        {
            "key": "freshness",
            "label": "Fraicheur",
            "value": "Aujourd'hui" if fresh_days <= 0 else f"{fresh_days} j",
            "series": fresh_series,
        },
        {
            "key": "citation",
            "label": "Taux de citation",
            "value": _pct_or_dash(overall.get("citation")),
            "series": cite_series,
        },
        {
            "key": "hitrate",
            "label": "Hit-rate retrieval",
            "value": _pct_or_dash(overall.get("hitrate")),
            "series": hit_series,
        },
    ]

    details = [_build_detail(r, agg, state) for r in rows_out]

    return {
        "title": "Connaissances",
        "subtitle": "Les sources sur lesquelles cet agent est ancre (live pgvector).",
        "actions": {
            "manage": "Gerer le catalogue",
            "memory": "Sources & memoire",
            "attach": "Rattacher une source",
        },
        "kpis": kpis,
        "attachable": attachable,
        "filters": {
            "search": "Rechercher une source rattachee...",
            "selects": [
                {"label": "Statut", "value": "Tous"},
                {"label": "Type", "value": "Tous"},
                {"label": "Periode", "value": "30 derniers jours"},
            ],
            "more": "Filtres",
        },
        "table": {
            "columns": ["Source", "Type", "Statut", "Couverture", "Fraicheur", "Taux de citation"],
            "rows": rows_out,
            "count": f"1-{len(rows_out)} sur {len(rows_out)} sources",
        },
        "details": details,
    }


def rows_chunks_label(chunks: int, docs: int) -> str:
    """Subtitle under a source name: real chunk and document counts."""
    return f"{chunks} chunks / {docs} documents"


def _pct_or_dash(value: object) -> str:
    return f"{round(value)}%" if isinstance(value, int | float) else "-"


def _build_detail(
    row: dict[str, object],
    agg: _Aggregate,
    state: dict[str, dict[str, bool]],
) -> dict[str, object]:
    cat = str(row["key"])
    st = state.get(cat, {"attached": True, "active": True})
    locs = agg.locators.get(cat, [])
    return {
        "name": str(row["name"]),
        "status": str(row["status"]),
        "status_tone": str(row["status_tone"]),
        "tabs": ["Usage", "Reponses ancrees", "Parametres"],
        "summary_title": "Resume",
        "summary": (
            f"Source ancree dans pgvector : {agg.chunks[cat]} chunks issus de "
            f"{len(agg.docs[cat])} documents, en {', '.join(sorted(agg.langs[cat]))}."
        ),
        "usage_title": "Utilisation par cet agent",
        "usage": [
            {"label": "Taux de citation", "value": str(row["citation"])},
            {"label": "Couverture des requetes", "value": f"{row['coverage']}%"},
            {"label": "Chunks indexes", "value": str(agg.chunks[cat])},
            {"label": "Documents", "value": str(len(agg.docs[cat]))},
            {"label": "Langues", "value": ", ".join(sorted(agg.langs[cat]))},
            {
                "label": "Derniere indexation",
                "value": agg.freshest[cat].strftime("%d/%m/%Y") if cat in agg.freshest else "-",
            },
        ],
        "answers_title": "Documents ancres (locators reels)",
        "answers": [{"text": loc, "time": ""} for loc in locs[:4]],
        "actions_title": "Actions",
        "toggle_label": "Active pour cet agent",
        "toggle_on": bool(st.get("active", True)),
        "detach": "Detacher de l'agent",
        "full_sheet": "Voir la fiche complete dans Sources & memoire",
        "key": cat,
    }
