"""Real Prompts data: the agent's system prompts from the YAML source of truth.

The inventory is read from ``src/tessera/agent/prompts/{fr,de,en}.yaml`` - the
same files the agent loads at start-up. Every row is a real prompt key with its
category, the languages it is defined in, the template variables it declares
(``{name}`` placeholders), its length per language and the file's last-modified
time. The detail panel shows the actual prompt text in each language, so the
displayed values all trace to a real artifact.

This page is read-only: prompts live in Git (edited via PR, loaded at start-up),
so the page wires search / filters / selection / cross-app navigation but does
not mutate the files from the UI. Display labels are localized (fr/de/en); logic
keys (tones, categories) stay stable. Source is ASCII-only (accents allowed).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["build_agent_prompts"]

_LANG_IDX: dict[str, int] = {"fr": 0, "de": 1, "en": 2}
_LANGS = ("fr", "de", "en")
_VAR_RE = re.compile(r"\{(\w+)\}")


def _norm_lang(lang: str) -> str:
    return lang if lang in _LANG_IDX else "fr"


def _t(triple: tuple[str, str, str], lang: str) -> str:
    return triple[_LANG_IDX[_norm_lang(lang)]]


# --- Prompt catalogue ---------------------------------------------------------
# Keys match the YAML keys the agent loads. Category is an editorial grouping of
# what each prompt drives; names/descriptions are localized.


_CATEGORY: dict[str, tuple[str, str, str]] = {
    "orch": ("Orchestration", "Orchestrierung", "Orchestration"),
    "syn": ("Synthèse", "Synthese", "Synthesis"),
    "rep": ("Réponse", "Antwort", "Response"),
    "mem": ("Mémoire", "Speicher", "Memory"),
}

_PROMPT_CAT: dict[str, str] = {
    "system": "orch",
    "planner": "orch",
    "reviewer": "orch",
    "reporter": "orch",
    "synthesis_context": "syn",
    "synthesis_tool_context": "syn",
    "escalation": "rep",
    "escalation_urgent_card": "rep",
    "decline": "rep",
    "summary": "rep",
    "memory_extract": "mem",
    "memory_summary_header": "mem",
    "memory_entities_header": "mem",
    "memory_context_header": "mem",
}

_PROMPT_NAME: dict[str, tuple[str, str, str]] = {
    "system": ("Assistant - Systeme", "Assistent - System", "Assistant - System"),
    "planner": ("Agent - Planificateur", "Agent - Planer", "Agent - Planner"),
    "reviewer": ("Agent - Relecteur", "Agent - Pruefer", "Agent - Reviewer"),
    "reporter": ("Agent - Rapporteur", "Agent - Berichter", "Agent - Reporter"),
    "synthesis_context": (
        "Synthese - Contexte",
        "Synthese - Kontext",
        "Synthesis - Context",
    ),
    "synthesis_tool_context": (
        "Synthese - Contexte outils",
        "Synthese - Werkzeugkontext",
        "Synthesis - Tool context",
    ),
    "escalation": ("Reponse - Escalade", "Antwort - Eskalation", "Response - Escalation"),
    "escalation_urgent_card": (
        "Reponse - Carte urgente",
        "Antwort - Dringende Karte",
        "Response - Urgent card",
    ),
    "decline": ("Reponse - Refus", "Antwort - Ablehnung", "Response - Decline"),
    "summary": ("Reponse - Resume", "Antwort - Zusammenfassung", "Response - Summary"),
    "memory_extract": (
        "Memoire - Extraction",
        "Speicher - Extraktion",
        "Memory - Extraction",
    ),
    "memory_summary_header": (
        "Memoire - En-tete resume",
        "Speicher - Zusammenfassungskopf",
        "Memory - Summary header",
    ),
    "memory_entities_header": (
        "Memoire - En-tete entites",
        "Speicher - Entitaetenkopf",
        "Memory - Entities header",
    ),
    "memory_context_header": (
        "Memoire - En-tete contexte",
        "Speicher - Kontextkopf",
        "Memory - Context header",
    ),
}

_PROMPT_DESC: dict[str, tuple[str, str, str]] = {
    "system": (
        "Prompt systeme principal : comportement global, ton et regles de reponse.",
        "Haupt-Systemprompt: Gesamtverhalten, Ton und Antwortregeln.",
        "Main system prompt: global behaviour, tone and answer rules.",
    ),
    "planner": (
        "Decompose la demande en etapes et choisit les outils a appeler.",
        "Zerlegt die Anfrage in Schritte und waehlt die aufzurufenden Werkzeuge.",
        "Breaks the request into steps and picks the tools to call.",
    ),
    "reviewer": (
        "Relit la reponse candidate et verifie l'ancrage et la conformite.",
        "Prueft die Kandidatenantwort auf Verankerung und Konformitaet.",
        "Reviews the candidate answer for grounding and compliance.",
    ),
    "reporter": (
        "Met en forme la reponse finale destinee a l'utilisateur.",
        "Formatiert die endgueltige Antwort fuer den Nutzer.",
        "Formats the final answer for the user.",
    ),
    "synthesis_context": (
        "Injecte le contexte recupere (RAG) avant la synthese.",
        "Fuegt den abgerufenen Kontext (RAG) vor der Synthese ein.",
        "Injects the retrieved context (RAG) before synthesis.",
    ),
    "synthesis_tool_context": (
        "Injecte les resultats d'outils avant la synthese.",
        "Fuegt die Werkzeugergebnisse vor der Synthese ein.",
        "Injects tool results before synthesis.",
    ),
    "escalation": (
        "Gabarit d'escalade vers un agent humain.",
        "Vorlage fuer die Eskalation an einen menschlichen Agenten.",
        "Template for escalation to a human agent.",
    ),
    "escalation_urgent_card": (
        "Carte d'action urgente (ex. carte perdue ou volee).",
        "Dringende Aktionskarte (z. B. verlorene oder gestohlene Karte).",
        "Urgent action card (e.g. lost or stolen card).",
    ),
    "decline": (
        "Gabarit de refus poli hors perimetre.",
        "Vorlage fuer hoefliche Ablehnung ausserhalb des Bereichs.",
        "Polite out-of-scope decline template.",
    ),
    "summary": (
        "Gabarit de resume de conversation.",
        "Vorlage fuer die Gespraechszusammenfassung.",
        "Conversation summary template.",
    ),
    "memory_extract": (
        "Extrait les faits durables a memoriser apres un tour.",
        "Extrahiert dauerhafte Fakten zur Speicherung nach einem Zug.",
        "Extracts durable facts to remember after a turn.",
    ),
    "memory_summary_header": (
        "En-tete du resume memoire injecte dans le contexte.",
        "Kopfzeile der in den Kontext eingefuegten Speicherzusammenfassung.",
        "Header of the memory summary injected into context.",
    ),
    "memory_entities_header": (
        "En-tete de la liste d'entites memorisees.",
        "Kopfzeile der Liste gespeicherter Entitaeten.",
        "Header of the remembered-entities list.",
    ),
    "memory_context_header": (
        "En-tete du contexte memoire cross-session.",
        "Kopfzeile des sitzungsuebergreifenden Speicherkontexts.",
        "Header of the cross-session memory context.",
    ),
}

_STR: dict[str, tuple[str, str, str]] = {
    "title": ("Prompts", "Prompts", "Prompts"),
    "subtitle": (
        "Les prompts systeme, gabarits et instructions charges par l'agent (live YAML).",
        "Die vom Agenten geladenen Systemprompts, Vorlagen und Anweisungen (live YAML).",
        "The system prompts, templates and instructions the agent loads (live YAML).",
    ),
    "act_asof": ("Voir a date (as-of)", "Stand anzeigen (as-of)", "View as-of"),
    "act_create": ("Ouvrir le Playground", "Playground oeffnen", "Open the Playground"),
    "snap_tag": ("SNAPSHOT ACTIF", "AKTIVER SNAPSHOT", "ACTIVE SNAPSHOT"),
    "snap_label": ("Prompts a date", "Prompts (Stand)", "Prompts as-of"),
    "snap_updated": ("Derniere mise a jour", "Letzte Aktualisierung", "Last updated"),
    "snap_source": ("Source de verite", "Quelle der Wahrheit", "Source of truth"),
    "snap_files": ("Fichiers", "Dateien", "Files"),
    "snap_coverage": ("Couverture i18n", "i18n-Abdeckung", "i18n coverage"),
    "kpi_prompts": ("Prompts", "Prompts", "Prompts"),
    "kpi_categories": ("Categories", "Kategorien", "Categories"),
    "kpi_coverage": ("Couverture i18n", "i18n-Abdeckung", "i18n coverage"),
    "kpi_variables": ("Variables uniques", "Eindeutige Variablen", "Unique variables"),
    "kpi_avglen": ("Longueur moyenne", "Durchschnittslaenge", "Average length"),
    "kpi_missing": ("Langues manquantes", "Fehlende Sprachen", "Missing languages"),
    "f_search": (
        "Rechercher un prompt ou une variable...",
        "Prompt oder Variable suchen...",
        "Search a prompt or variable...",
    ),
    "f_category": ("Categorie", "Kategorie", "Category"),
    "f_variables": ("Variables", "Variablen", "Variables"),
    "f_var_with": ("Avec variables", "Mit Variablen", "With variables"),
    "f_var_without": ("Sans variables", "Ohne Variablen", "Without variables"),
    "f_all_f": ("Toutes", "Alle", "All"),
    "f_more": ("Filtres", "Filter", "Filters"),
    "col_name": ("Nom du prompt", "Prompt-Name", "Prompt name"),
    "col_category": ("Categorie", "Kategorie", "Category"),
    "col_status": ("Statut", "Status", "Status"),
    "col_langs": ("Langues", "Sprachen", "Languages"),
    "col_vars": ("Variables", "Variablen", "Variables"),
    "col_updated": ("Derniere mise a jour", "Letzte Aktualisierung", "Last updated"),
    "col_source": ("Source", "Quelle", "Source"),
    "col_length": ("Longueur (FR)", "Laenge (FR)", "Length (FR)"),
    "st_active": ("Charge", "Geladen", "Loaded"),
    "complete": ("Complete", "Vollstaendig", "Complete"),
    "chars": ("car.", "Z.", "chars"),
    "watch_title": ("A surveiller", "Zu beobachten", "Watchlist"),
    "watch_cta": ("Lancer une evaluation", "Evaluierung starten", "Run an evaluation"),
    "quick_title": ("Actions rapides", "Schnellaktionen", "Quick actions"),
    "q_playground": ("Ouvrir le Playground", "Playground oeffnen", "Open the Playground"),
    "q_eval": ("Lancer une evaluation", "Evaluierung starten", "Run an evaluation"),
    "q_history": ("Voir l'historique", "Verlauf ansehen", "View history"),
    "q_memory": ("Sources & memoire", "Quellen & Speicher", "Sources & memory"),
    "bytype_title": ("Volume par categorie", "Volumen nach Kategorie", "Volume by category"),
    "bytype_cta": ("Voir le detail", "Details ansehen", "View details"),
    "detail_eyebrow": ("Details du prompt", "Prompt-Details", "Prompt details"),
    "tab_summary": ("Resume", "Zusammenfassung", "Summary"),
    "tab_content": ("Contenu", "Inhalt", "Content"),
    "tab_config": ("Configuration", "Konfiguration", "Configuration"),
    "fld_category": ("Categorie", "Kategorie", "Category"),
    "fld_langs": ("Langues", "Sprachen", "Languages"),
    "fld_vars": ("Variables", "Variablen", "Variables"),
    "fld_length": ("Longueur (FR)", "Laenge (FR)", "Length (FR)"),
    "fld_updated": ("Derniere mise a jour", "Letzte Aktualisierung", "Last updated"),
    "fld_source": ("Fichier source", "Quelldatei", "Source file"),
    "tags_label": ("Variables de gabarit", "Vorlagenvariablen", "Template variables"),
    "tags_none": ("Aucune variable", "Keine Variablen", "No variables"),
    "config_title": (
        "Configuration technique",
        "Technische Konfiguration",
        "Technical configuration",
    ),
    "config_cta": ("Voir le YAML", "YAML ansehen", "View YAML"),
    "cfg_model": ("Modele cible", "Zielmodell", "Target model"),
    "cfg_format": ("Format", "Format", "Format"),
    "cfg_loaded": ("Chargement", "Laden", "Loading"),
    "cfg_loaded_v": ("Au demarrage", "Beim Start", "At start-up"),
    "rbac_title": ("Longueur par langue", "Laenge je Sprache", "Length per language"),
    "rbac_cta": ("", "", ""),
    "info_title": ("Informations", "Informationen", "Information"),
    "info_key": ("Cle YAML", "YAML-Schluessel", "YAML key"),
    "info_files": ("Fichiers", "Dateien", "Files"),
    "info_words": ("Mots (FR)", "Woerter (FR)", "Words (FR)"),
    "ft_truth": ("Source de verite", "Quelle der Wahrheit", "Source of truth"),
    "ft_format": ("Format", "Format", "Format"),
    "ft_langs": ("Langues", "Sprachen", "Languages"),
    "ft_load": ("Chargement", "Laden", "Loading"),
    "realtime": ("Temps reel", "Echtzeit", "Realtime"),
    "good": ("Bonne", "Gut", "Good"),
}

_W_COVERAGE: dict[str, str] = {
    "fr": "Couverture i18n complete - {n} prompts en FR/DE/EN",
    "de": "Vollstaendige i18n-Abdeckung - {n} Prompts in FR/DE/EN",
    "en": "Full i18n coverage - {n} prompts in FR/DE/EN",
}
_W_LONGEST: dict[str, str] = {
    "fr": "Prompt le plus long : {name} ({n} car.)",
    "de": "Laengster Prompt: {name} ({n} Z.)",
    "en": "Longest prompt: {name} ({n} chars)",
}
_W_VARS: dict[str, str] = {
    "fr": "{n} variables de gabarit detectees",
    "de": "{n} Vorlagenvariablen erkannt",
    "en": "{n} template variables detected",
}


def _subtabs(lang: str) -> list[str]:
    table = {
        "fr": ["Vue d'ensemble", "Variables", "Couverture i18n"],
        "de": ["Uebersicht", "Variablen", "i18n-Abdeckung"],
        "en": ["Overview", "Variables", "i18n coverage"],
    }
    return table[_norm_lang(lang)]


# --- Source loading -----------------------------------------------------------


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "agent" / "prompts"


def _load_yaml(path: Path) -> dict[str, str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _load_all() -> tuple[dict[str, dict[str, str]], datetime]:
    """Return ``{lang: {key: text}}`` and the newest source mtime."""
    directory = _prompts_dir()
    per_lang: dict[str, dict[str, str]] = {}
    newest = datetime.fromtimestamp(0, tz=UTC)
    for lang in _LANGS:
        path = directory / f"{lang}.yaml"
        per_lang[lang] = _load_yaml(path)
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            newest = max(newest, mtime)
        except OSError:
            continue
    return per_lang, newest


# --- Formatting helpers -------------------------------------------------------


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _rel_age(when: datetime, now: datetime, lang: str) -> str:
    secs = (now - when).total_seconds()
    lng = _norm_lang(lang)
    day = 86_400
    if secs < day:
        n = max(1, int(secs // 3600))
        return {"fr": f"il y a {n} h", "de": f"vor {n} Std", "en": f"{n}h ago"}[lng]
    n = int(secs // day)
    return {"fr": f"il y a {n} j", "de": f"vor {n} T", "en": f"{n}d ago"}[lng]


def _variables(per_lang: dict[str, dict[str, str]], key: str) -> list[str]:
    found: list[str] = []
    for lang in _LANGS:
        for var in _VAR_RE.findall(per_lang.get(lang, {}).get(key, "")):
            if var not in found:
                found.append(var)
    return sorted(found)


# --- Public builder -----------------------------------------------------------


async def build_agent_prompts(lang: str = "fr") -> dict[str, object]:
    """Assemble the Prompts payload from the live YAML source of truth."""
    per_lang, newest = _load_all()
    return _assemble(per_lang, newest, lang, now=datetime.now(UTC))


def _present_langs(per_lang: dict[str, dict[str, str]], key: str) -> list[str]:
    return [lng for lng in _LANGS if per_lang.get(lng, {}).get(key, "").strip()]


def _assemble(
    per_lang: Mapping[str, dict[str, str]],
    newest: datetime,
    lang: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Pure assembly of the Prompts payload (no I/O) - unit-testable."""
    lang = _norm_lang(lang)
    now = now or datetime.now(UTC)
    per = dict(per_lang)

    # Discover the keys present in the FR source, ordered by the catalogue.
    catalogue = [k for k in _PROMPT_CAT if k in per.get("fr", {})]
    extras = [k for k in per.get("fr", {}) if k not in _PROMPT_CAT]
    keys = catalogue + extras

    updated_label = _rel_age(newest, now, lang)
    updated_abs = newest.strftime("%d/%m/%Y %H:%M")

    rows: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    cat_count: dict[str, int] = {c: 0 for c in _CATEGORY}
    all_vars: set[str] = set()
    missing = 0
    fr_len_total = 0
    longest_name = ""
    longest_len = 0

    for key in keys:
        cat = _PROMPT_CAT.get(key, "rep")
        cat_count[cat] = cat_count.get(cat, 0) + 1
        present = _present_langs(per, key)
        if len(present) < len(_LANGS):
            missing += 1
        variables = _variables(per, key)
        all_vars.update(variables)
        fr_text = per.get("fr", {}).get(key, "")
        fr_len = len(fr_text)
        fr_len_total += fr_len
        name = _name(key, lang)
        if fr_len > longest_len:
            longest_len, longest_name = fr_len, name

        rows.append(
            {
                "key": key,
                "name": name,
                "type": _t(_CATEGORY[cat], lang),
                "type_tone": cat,
                "status": _t(_STR["st_active"], lang),
                "status_tone": "good",
                "version": "/".join(p.upper() for p in present),
                "langs_present": present,
                "quality": str(len(variables)),
                "quality_tone": "good" if variables else "mut",
                "vars_count": len(variables),
                "updated": updated_abs,
                "owner": f"{', '.join(f'{p}.yaml' for p in present)}",
                "tests": f"{_fmt_int(fr_len)} {_t(_STR['chars'], lang)}",
                "fr_len": fr_len,
            }
        )
        details.append(_build_detail(key, per, cat, variables, present, updated_abs, lang))

    n_prompts = len(rows)
    n_cats = sum(1 for c in cat_count.values() if c)
    avg_len = round(fr_len_total / n_prompts) if n_prompts else 0
    cov_pct = round(100 * (n_prompts - missing) / n_prompts) if n_prompts else 0

    return {
        "title": _t(_STR["title"], lang),
        "subtitle": _t(_STR["subtitle"], lang),
        "actions": {"asof": _t(_STR["act_asof"], lang), "create": _t(_STR["act_create"], lang)},
        "subtabs": _subtabs(lang),
        "snapshot": {
            "tag": _t(_STR["snap_tag"], lang),
            "label": _t(_STR["snap_label"], lang),
            "updated_label": _t(_STR["snap_updated"], lang),
            "updated": updated_abs,
            "updated_rel": updated_label,
            "version_label": _t(_STR["snap_source"], lang),
            "version": "prompts/*.yaml",
            "version_status": "Git",
            "evalset_label": _t(_STR["snap_files"], lang),
            "evalset": f"{len(_LANGS)} (FR/DE/EN)",
            "coverage_label": _t(_STR["snap_coverage"], lang),
            "coverage": cov_pct,
            "coverage_tone": _t(_STR["good"], lang),
            "asof": _t(_STR["act_asof"], lang),
            "compare": _t(_STR["snap_source"], lang),
        },
        "kpis": [
            _kpi("prompts", _t(_STR["kpi_prompts"], lang), str(n_prompts), "", good=True),
            _kpi("categories", _t(_STR["kpi_categories"], lang), str(n_cats), "", good=True),
            _kpi(
                "coverage",
                _t(_STR["kpi_coverage"], lang),
                _t(_STR["complete"], lang) if missing == 0 else f"{cov_pct}%",
                "",
                good=True,
                gauge=cov_pct,
            ),
            _kpi("variables", _t(_STR["kpi_variables"], lang), str(len(all_vars)), "", good=True),
            _kpi(
                "avglen",
                _t(_STR["kpi_avglen"], lang),
                f"{_fmt_int(avg_len)} {_t(_STR['chars'], lang)}",
                "",
                good=True,
            ),
            _kpi("missing", _t(_STR["kpi_missing"], lang), str(missing), "", good=missing == 0),
        ],
        "filters": {
            "search": _t(_STR["f_search"], lang),
            "selects": [
                {"label": _t(_STR["f_category"], lang), "value": _t(_STR["f_all_f"], lang)},
                {"label": _t(_STR["f_variables"], lang), "value": _t(_STR["f_all_f"], lang)},
            ],
            "var_options": [
                {"value": "all", "label": _t(_STR["f_all_f"], lang)},
                {"value": "with", "label": _t(_STR["f_var_with"], lang)},
                {"value": "without", "label": _t(_STR["f_var_without"], lang)},
            ],
            "more": _t(_STR["f_more"], lang),
        },
        "table": {
            "columns": [
                _t(_STR["col_name"], lang),
                _t(_STR["col_category"], lang),
                _t(_STR["col_status"], lang),
                _t(_STR["col_langs"], lang),
                _t(_STR["col_vars"], lang),
                _t(_STR["col_updated"], lang),
                _t(_STR["col_source"], lang),
                _t(_STR["col_length"], lang),
            ],
            "rows": rows,
            "count": str(n_prompts),
            "pages": 1,
        },
        "watch": _build_watch(n_prompts, longest_name, longest_len, len(all_vars), lang),
        "quick": {
            "title": _t(_STR["quick_title"], lang),
            "items": [
                {"label": _t(_STR["q_playground"], lang), "href": "/assistant"},
                {"label": _t(_STR["q_eval"], lang), "href": "/agent/evaluations"},
                {"label": _t(_STR["q_history"], lang), "href": "/agent/historique"},
                {"label": _t(_STR["q_memory"], lang), "href": "/configurer/sources-memoire"},
            ],
        },
        "by_type": _build_bytype(cat_count, n_prompts, lang),
        "details": details,
        "footer": [
            {"label": _t(_STR["ft_truth"], lang), "value": "prompts/{fr,de,en}.yaml"},
            {"label": _t(_STR["ft_format"], lang), "value": "YAML / Git"},
            {"label": _t(_STR["ft_langs"], lang), "value": "FR / DE / EN"},
            {"label": _t(_STR["ft_load"], lang), "value": _t(_STR["cfg_loaded_v"], lang)},
        ],
    }


def _name(key: str, lang: str) -> str:
    triple = _PROMPT_NAME.get(key)
    return _t(triple, lang) if triple else key


def _kpi(
    key: str, label: str, value: str, delta: str, *, good: bool, gauge: int | None = None
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "gauge": gauge,
    }


def _build_watch(
    n_prompts: int, longest_name: str, longest_len: int, n_vars: int, lang: str
) -> dict[str, object]:
    lng = _norm_lang(lang)
    return {
        "title": _t(_STR["watch_title"], lang),
        "cta": _t(_STR["watch_cta"], lang),
        "items": [
            {"title": _W_COVERAGE[lng].format(n=n_prompts), "detail": "", "tone": "info"},
            {
                "title": _W_LONGEST[lng].format(name=longest_name, n=_fmt_int(longest_len)),
                "detail": "",
                "tone": "info",
            },
            {"title": _W_VARS[lng].format(n=n_vars), "detail": "", "tone": "info"},
        ],
    }


def _build_bytype(cat_count: dict[str, int], total: int, lang: str) -> dict[str, object]:
    items: list[dict[str, object]] = []
    tones = {"orch": "green", "syn": "green", "rep": "amber", "mem": "green"}
    for cat, count in sorted(cat_count.items(), key=lambda kv: -kv[1]):
        if not count:
            continue
        pct = round(100 * count / total) if total else 0
        items.append(
            {"label": _t(_CATEGORY[cat], lang), "value": str(count), "pct": pct, "tone": tones[cat]}
        )
    return {
        "title": _t(_STR["bytype_title"], lang),
        "cta": _t(_STR["bytype_cta"], lang),
        "items": items,
    }


def _build_detail(
    key: str,
    per: dict[str, dict[str, str]],
    cat: str,
    variables: list[str],
    present: list[str],
    updated_abs: str,
    lang: str,
) -> dict[str, object]:
    fr_text = per.get("fr", {}).get(key, "")
    desc = _PROMPT_DESC.get(key)
    description = _t(desc, lang) if desc else _t(_CATEGORY[cat], lang)
    content = [
        {"lang": lng.upper(), "text": per.get(lng, {}).get(key, "")}
        for lng in _LANGS
        if per.get(lng, {}).get(key, "").strip()
    ]
    model = get_settings().vertex.chat_model
    return {
        "key": key,
        "name": _name(key, lang),
        "id": key,
        "status": _t(_STR["st_active"], lang),
        "status_tone": "good",
        "tabs": [
            _t(_STR["tab_summary"], lang),
            _t(_STR["tab_content"], lang),
            _t(_STR["tab_config"], lang),
        ],
        "description": description,
        "fields": [
            {"label": _t(_STR["fld_category"], lang), "value": _t(_CATEGORY[cat], lang)},
            {"label": _t(_STR["fld_langs"], lang), "value": "/".join(p.upper() for p in present)},
            {"label": _t(_STR["fld_vars"], lang), "value": str(len(variables))},
            {
                "label": _t(_STR["fld_length"], lang),
                "value": f"{_fmt_int(len(fr_text))} {_t(_STR['chars'], lang)}",
            },
            {"label": _t(_STR["fld_updated"], lang), "value": updated_abs},
            {
                "label": _t(_STR["fld_source"], lang),
                "value": f"{lang if lang in _LANGS else 'fr'}.yaml",
            },
        ],
        "content": content,
        "tags_label": _t(_STR["tags_label"], lang),
        "tags": variables if variables else [_t(_STR["tags_none"], lang)],
        "config_title": _t(_STR["config_title"], lang),
        "config_cta": _t(_STR["config_cta"], lang),
        "config": [
            {"label": _t(_STR["cfg_model"], lang), "value": model},
            {"label": _t(_STR["cfg_format"], lang), "value": "YAML"},
            {"label": _t(_STR["fld_langs"], lang), "value": "/".join(p.upper() for p in present)},
            {"label": _t(_STR["cfg_loaded"], lang), "value": _t(_STR["cfg_loaded_v"], lang)},
        ],
        "rbac_title": _t(_STR["rbac_title"], lang),
        "rbac_cta": _t(_STR["rbac_cta"], lang),
        "rbac": [
            {
                "role": lng.upper(),
                "access": (
                    f"{_fmt_int(len(per.get(lng, {}).get(key, '')))} {_t(_STR['chars'], lang)}"
                ),
            }
            for lng in _LANGS
        ],
        "rbac_more": "",
        "info_title": _t(_STR["info_title"], lang),
        "info": [
            {"label": _t(_STR["info_key"], lang), "value": key},
            {"label": _t(_STR["info_files"], lang), "value": str(len(present))},
            {
                "label": _t(_STR["info_words"], lang),
                "value": _fmt_int(len(fr_text.split())),
            },
        ],
    }
