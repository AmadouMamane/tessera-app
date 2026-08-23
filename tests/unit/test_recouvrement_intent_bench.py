"""The labeled intent set is a referent, and a referent is held to its own rules.

ADR 0053 §7: the set is the truth layer-1 classifiers (regex today, LLM in slice 3)
are measured against. These tests keep it opposable: schema-valid, unique, covering
every (language x intent) cell with a real n, and naming only intents the agent's
manifest actually declares — a label outside the manifest vocabulary would score a
classifier against a capability that does not exist.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

import jsonschema
import pytest

from eval.intent_bench import (
    DEFAULT_SET_PATH,
    INTENTS_DIR,
    IntentCase,
    build_report,
    load_intent_set,
    score_regex_column,
)
from tessera.agent.recouvrement import DEFAULT_TEXT_INTENT, classify_recouvrement_text
from tessera.agent.registry import get_agent

if TYPE_CHECKING:
    from pathlib import Path

#: The coverage floor per (language x intent) cell. A cell below this makes the
#: bench's per-cell figures counts-in-disguise; the set was authored at 8 per cell.
_CELL_FLOOR = 8


def test_set_loads_and_validates() -> None:
    """The committed set parses, validates, and carries three languages."""
    intent_set = load_intent_set()
    assert intent_set.agent_id == "recouvrement"
    assert {case.language for case in intent_set.cases} == {"fr", "en", "de"}


def test_case_ids_are_unique() -> None:
    """The loader refuses a duplicated case id — a duplicated referent names nothing."""
    raw = json.loads(DEFAULT_SET_PATH.read_text(encoding="utf-8"))
    ids = [case["id"] for case in raw["cases"]]
    assert len(ids) == len(set(ids))


def test_loader_refuses_duplicate_ids(tmp_path: Path) -> None:
    """A synthetic set with a repeated id fails loudly at load, not silently downstream."""
    raw = json.loads(DEFAULT_SET_PATH.read_text(encoding="utf-8"))
    raw["cases"] = [raw["cases"][0], dict(raw["cases"][0])]
    twin = tmp_path / "twin.json"
    twin.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate intent case id"):
        load_intent_set(twin)


def test_loader_refuses_schema_violation(tmp_path: Path) -> None:
    """An unknown intent-case key is a contract violation, not an ignored field."""
    raw = json.loads(DEFAULT_SET_PATH.read_text(encoding="utf-8"))
    raw["cases"][0]["surprise"] = "unread keys must refuse, not vanish"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(jsonschema.ValidationError):
        load_intent_set(bad)


def test_expected_intents_are_declared_capabilities() -> None:
    """Every label names a capability the recouvrement manifest declares (ADR 0017).

    The closed vocabulary of ADR 0053 layer 1 IS the manifest's capability ids: a
    label outside it would measure classifiers against a door the agent does not
    have. Read from the registry, not from a copied list, so a manifest change
    reaches this test without anyone remembering to mirror it.
    """
    agent = get_agent("recouvrement")
    assert agent.observability is not None
    declared = {capability.id for capability in agent.observability.capabilities}
    labeled = {case.expected_intent for case in load_intent_set().cases}
    assert labeled <= declared, f"labels outside the manifest vocabulary: {labeled - declared}"
    assert labeled == declared, f"declared capabilities never labeled: {declared - labeled}"


def test_every_language_intent_cell_holds_the_floor() -> None:
    """Each (language x intent) cell carries at least the authored floor of cases."""
    cells = Counter((case.language, case.expected_intent) for case in load_intent_set().cases)
    thin = {cell: n for cell, n in cells.items() if n < _CELL_FLOOR}
    assert not thin, f"cells under the n={_CELL_FLOOR} floor: {thin}"
    assert len(cells) == 15  # 3 languages x 5 intents — no cell missing entirely


def test_no_case_labels_a_clock_dependent_time() -> None:
    """A 'now' word resolves against the clock — such a case must never label a time."""
    for case in load_intent_set().cases:
        if "requested_time" in case.expected_fields:
            normalized = case.utterance.lower()
            assert not any(word in normalized for word in ("maintenant", "now", "jetzt")), case.id


def test_regex_column_scores_the_router_answer_not_the_matcher_silence() -> None:
    """A case no list matches is scored as the router's default, and counted as such."""
    case = IntentCase(
        id="xx_probe_01",
        language="fr",
        utterance="Bonjour, on fait le point ?",
        expected_intent="summarize_case",
        expected_fields={},
        provenance="hand_authored",
        note=None,
    )
    assert classify_recouvrement_text(case.utterance) is None
    (verdict,) = score_regex_column((case,))
    assert verdict.matched is False
    assert verdict.predicted_intent == DEFAULT_TEXT_INTENT
    assert verdict.correct is False


def test_report_counts_add_up_and_llm_column_is_absent_not_zero() -> None:
    """Population counts reconcile across groupings, and the unwired column says so."""
    intent_set = load_intent_set()
    verdicts = score_regex_column(intent_set.cases)
    report = build_report(intent_set, verdicts)
    regex_column = report["columns"]["regex"]  # type: ignore[index]
    overall = regex_column["overall"]
    by_language = regex_column["by_language"]
    assert overall["n"] == len(intent_set.cases)
    assert sum(counts["n"] for counts in by_language.values()) == overall["n"]
    assert sum(counts["correct"] for counts in by_language.values()) == overall["correct"]
    by_cell = regex_column["by_cell"]
    assert sum(cell["n"] for cell in by_cell.values()) == overall["n"]
    assert len(regex_column["misrouted_case_ids"]) == overall["n"] - overall["correct"]
    llm_column = report["columns"]["llm"]  # type: ignore[index]
    assert llm_column["status"] == "not_run"
    assert "overall" not in llm_column  # an absent ruler carries no numbers at all


def test_reports_directory_is_not_swept_by_gating_ingest() -> None:
    """The bench's report home stays invisible to the gating-report sweep.

    ``ingest_gating_reports`` globs ``*.json`` non-recursively over the per-env
    dir, the flat root and the seed dir. The bench publishes to
    ``eval/reports/intent_bench/`` on the strength of that non-recursion; if the
    sweep ever learns to recurse, this witness turns red before a bench report
    is mistaken for a gating report.
    """
    from tessera.observability.eval import report_paths

    intent_bench_dir = report_paths.reports_flat_root() / "intent_bench"
    swept = {path.parent for path in report_paths.iter_report_files()}
    assert intent_bench_dir not in swept
    assert INTENTS_DIR.name == "intents"  # the set itself lives outside eval/reports entirely
