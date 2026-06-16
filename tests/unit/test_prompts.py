"""Unit tests for the Prompts payload assembly (no file I/O).

Feed :func:`tessera.observability.agent_prompts._assemble` synthetic YAML maps
and assert the real inventory: row count, categories, template-variable
extraction, i18n coverage / missing-language detection, the per-prompt content
in the detail, and localization (fr/de/en).
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability import agent_prompts as p

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
MTIME = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)


def _per_lang() -> dict[str, dict[str, str]]:
    return {
        "fr": {
            "system": "Tu es l'assistant de {bank}. Reponds en {lang}.",
            "planner": "Decompose la demande.",
            "decline": "Desole, hors perimetre.",
        },
        "de": {
            "system": "Du bist der Assistent von {bank}. Antworte auf {lang}.",
            "planner": "Zerlege die Anfrage.",
            # 'decline' intentionally missing in DE -> a missing language.
        },
        "en": {
            "system": "You are the assistant of {bank}. Answer in {lang}.",
            "planner": "Break down the request.",
            "decline": "Sorry, out of scope.",
        },
    }


def _assemble(lang: str = "fr") -> dict:
    return p._assemble(_per_lang(), MTIME, lang, now=NOW)


def test_fmt_int_groups_thousands() -> None:
    assert p._fmt_int(2966) == "2 966"


def test_variables_are_extracted_and_deduped() -> None:
    variables = p._variables(_per_lang(), "system")
    assert variables == ["bank", "lang"]
    assert p._variables(_per_lang(), "planner") == []


def test_rows_cover_every_fr_key() -> None:
    rows = _assemble()["table"]["rows"]
    keys = {r["key"] for r in rows}
    assert keys == {"system", "planner", "decline"}
    assert len(rows) == 3


def test_kpis_count_prompts_and_missing_languages() -> None:
    kpis = {k["key"]: k for k in _assemble()["kpis"]}
    assert kpis["prompts"]["value"] == "3"
    # 'decline' is missing DE -> 1 missing, coverage < 100, KPI not 'good'.
    assert kpis["missing"]["value"] == "1"
    assert kpis["missing"]["good"] is False
    assert kpis["variables"]["value"] == "2"  # {bank}, {lang}


def test_row_langs_and_vars_are_real() -> None:
    rows = {r["key"]: r for r in _assemble()["table"]["rows"]}
    assert rows["system"]["version"] == "FR/DE/EN"
    assert rows["system"]["vars_count"] == 2
    assert rows["decline"]["version"] == "FR/EN"  # no DE
    assert rows["planner"]["quality_tone"] == "mut"  # no variables


def test_detail_content_holds_real_text_per_language() -> None:
    details = {d["key"]: d for d in _assemble()["details"]}
    content = {c["lang"]: c["text"] for c in details["system"]["content"]}
    assert content["FR"].startswith("Tu es l'assistant")
    assert content["DE"].startswith("Du bist")
    assert content["EN"].startswith("You are")
    # 'decline' has no DE -> only FR/EN content entries.
    decline_langs = {c["lang"] for c in details["decline"]["content"]}
    assert decline_langs == {"FR", "EN"}


def test_detail_tags_are_the_variables() -> None:
    details = {d["key"]: d for d in _assemble()["details"]}
    assert details["system"]["tags"] == ["bank", "lang"]


def test_localization_de() -> None:
    payload = _assemble(lang="de")
    assert payload["kpis"][0]["label"] == "Prompts"
    cats = {r["type"] for r in payload["table"]["rows"]}
    assert "Orchestrierung" in cats  # system/planner -> Orchestration (de)


def test_by_type_counts_categories() -> None:
    by_type = {it["label"]: it for it in _assemble()["by_type"]["items"]}
    # system + planner -> Orchestration (2); decline -> Response (1).
    assert by_type["Orchestration"]["value"] == "2"
