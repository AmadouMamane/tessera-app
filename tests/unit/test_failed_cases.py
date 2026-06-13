"""Unit tests for the documented failed-case catalogue loader."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.failed_cases import load_failed_cases

if TYPE_CHECKING:
    from pathlib import Path


def _write(directory: Path, name: str, obj: dict[str, object]) -> None:
    (directory / name).write_text(json.dumps(obj), encoding="utf-8")


def test_empty_directory_yields_empty_report(tmp_path: Path) -> None:
    report = load_failed_cases(tmp_path)
    assert report.n == 0
    assert report.cases == []
    assert report.by_category == {}
    assert report.by_severity["critical"] == 0


def test_loads_cases_with_severity_and_distribution(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "01_inj.json",
        {
            "id": "01_inj",
            "title": "Injection",
            "category": "prompt_injection",
            "prompts": {"fr": {"user": "ignore tout"}, "en": {"user": "ignore all"}},
            "expected_behavior": "refuse",
            "tags": ["guard"],
        },
    )
    _write(
        tmp_path,
        "02_mix.json",
        {
            "id": "02_mix",
            "title": "Mixing",
            "category": "language_mixing",
            "prompts": {"en": {"user": "mix langs"}},
            "expected_behavior": "stay in fr",
        },
    )
    report = load_failed_cases(tmp_path, language="fr")
    assert report.n == 2
    # Critical (prompt_injection) sorts before low (language_mixing).
    assert report.cases[0].case_id == "01_inj"
    assert report.cases[0].severity == "critical"
    assert report.cases[0].language == "fr"
    assert report.cases[0].example == "ignore tout"
    assert report.cases[0].tags == ["guard"]
    assert report.cases[1].severity == "low"
    # Falls back to another language when the preferred one is absent.
    assert report.cases[1].language == "en"
    assert report.by_category == {"prompt_injection": 1, "language_mixing": 1}
    assert report.by_severity["critical"] == 1
    assert report.by_severity["low"] == 1


def test_limit_caps_rows_but_not_distribution(tmp_path: Path) -> None:
    for i in range(5):
        _write(
            tmp_path,
            f"0{i}_h.json",
            {"id": f"0{i}_h", "category": "hallucination", "prompts": {}},
        )
    report = load_failed_cases(tmp_path, limit=2)
    assert len(report.cases) == 2
    assert report.n == 5
    assert report.by_category["hallucination"] == 5


def test_real_catalogue_loads() -> None:
    report = load_failed_cases()
    assert report.n >= 40
    assert report.cases[0].severity == "critical"
    assert sum(report.by_category.values()) == report.n
