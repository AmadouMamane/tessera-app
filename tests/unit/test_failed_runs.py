"""Unit tests for the real failed-case view (Cas échoués tab)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.failed_runs import load_failed_runs

if TYPE_CHECKING:
    from pathlib import Path

_THEMES = (
    "prompt_injection",
    "pii_leak",
    "hallucination",
    "overconfidence",
    "regulatory_misstatement",
    "citation_fabrication",
    "tool_misuse",
    "policy_violation",
    "language_mixing",
    "escalation_failure",
)


def _write_catalogue(directory: Path, *, cases_per_theme: int = 5) -> None:
    i = 0
    for theme in _THEMES:
        for n in range(cases_per_theme):
            i += 1
            (directory / f"{i:02d}_{theme}_{n}.json").write_text(
                json.dumps(
                    {
                        "id": f"{theme}_{n}",
                        "category": theme,
                        "title": f"{theme} {n}",
                        "expected_behavior": f"expected {theme} {n}",
                        "prompts": {"fr": {"user": f"prompt {theme} {n} fr"}},
                    }
                ),
                encoding="utf-8",
            )


def _write_run(
    directory: Path,
    name: str,
    *,
    run_at: str,
    model: str,
    lang: str = "fr",
    failed_per_theme: int,
    cases_per_theme: int = 5,
    version: str | None = "63-abc",
) -> None:
    """A full-catalogue run; the first ``failed_per_theme`` cases per theme fail."""
    results: list[dict[str, object]] = []
    for theme in _THEMES:
        for n in range(cases_per_theme):
            failed = n < failed_per_theme
            results.append(
                {
                    "case_id": f"{theme}_{n}",
                    "category": theme,
                    "language": lang,
                    "passed": not failed,
                    "reasons": ["boom"] if failed else [],
                    "final_response": f"answer {theme} {n}",
                    "title": f"{theme} {n}",
                    "expected_behavior": f"expected {theme} {n}",
                }
            )
    obj: dict[str, object] = {"run_at": run_at, "model": model, "lang": lang, "results": results}
    if version is not None:
        obj["catalogue_version"] = version
    (directory / name).write_text(json.dumps(obj), encoding="utf-8")


def test_empty(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    failures = tmp_path / "failures"
    reports.mkdir()
    failures.mkdir()
    report = load_failed_runs(reports, failures)
    assert report.n == 0
    assert report.cases == []
    assert report.n_critical == 0
    assert report.trend == []


def test_extracts_failures_and_joins_catalogue(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    failures = tmp_path / "failures"
    reports.mkdir()
    failures.mkdir()
    _write_catalogue(failures, cases_per_theme=5)
    # One full run, 2 of 5 cases fail per theme → 20 failed (10 themes x 2).
    _write_run(reports, "r1.json", run_at="20260606T000000Z", model="m", failed_per_theme=2)

    report = load_failed_runs(reports, failures)
    assert report.n == len(_THEMES) * 2
    sample = next(c for c in report.cases if c.category == "pii_leak")
    assert sample.severity == "critical"
    assert sample.owner == "Safety"
    assert sample.model == "m"
    assert sample.language == "fr"
    assert sample.reasons == ["boom"]
    assert sample.response.startswith("answer pii_leak")
    assert sample.prompt.startswith("prompt pii_leak")  # joined from the catalogue
    assert sample.expected.startswith("expected pii_leak")
    # No previous comparable run ⇒ every failure is a new regression.
    assert report.n_new == report.n
    assert report.n_recurrent == 0


def test_status_new_vs_recurrent(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    failures = tmp_path / "failures"
    reports.mkdir()
    failures.mkdir()
    _write_catalogue(failures, cases_per_theme=5)
    # Previous run: 1 failure per theme (case _0). Latest: 2 failures per theme (_0,_1).
    _write_run(reports, "prev.json", run_at="20260601T000000Z", model="m", failed_per_theme=1)
    _write_run(reports, "latest.json", run_at="20260606T000000Z", model="m", failed_per_theme=2)

    report = load_failed_runs(reports, failures)
    by = {(c.id): c for c in report.cases}
    # _0 failed in both → recurrent; _1 newly failed → new.
    assert by["pii_leak_0"].status == "recurrent"
    assert by["pii_leak_1"].status == "new"
    assert report.n_recurrent == len(_THEMES)  # one recurrent (_0) per theme
    assert report.n_new == len(_THEMES)  # one new (_1) per theme


def test_multiple_models_and_distributions(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    failures = tmp_path / "failures"
    reports.mkdir()
    failures.mkdir()
    _write_catalogue(failures, cases_per_theme=5)
    _write_run(reports, "a.json", run_at="20260606T000000Z", model="alpha", failed_per_theme=2)
    _write_run(reports, "b.json", run_at="20260606T010000Z", model="beta", failed_per_theme=1)

    report = load_failed_runs(reports, failures)
    assert report.by_model == {"alpha": 20, "beta": 10}
    assert report.models == ["alpha", "beta"]
    assert sum(report.by_category.values()) == report.n
    assert report.catalogue_version == "63-abc"


def test_smoke_run_excluded(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    failures = tmp_path / "failures"
    reports.mkdir()
    failures.mkdir()
    _write_catalogue(failures, cases_per_theme=5)
    _write_run(reports, "full.json", run_at="20260606T000000Z", model="m", failed_per_theme=2)
    # A later one-case smoke run must not become the model's "latest full run".
    (reports / "smoke.json").write_text(
        json.dumps(
            {
                "run_at": "20260609T000000Z",
                "model": "m",
                "lang": "fr",
                "results": [{"case_id": "pii_leak_0", "category": "pii_leak", "passed": False}],
            }
        ),
        encoding="utf-8",
    )

    report = load_failed_runs(reports, failures)
    assert report.n == len(_THEMES) * 2  # from the full run, smoke ignored
    # Trend only counts full runs → a single day.
    assert [t.date for t in report.trend] == ["2026-06-06"]
    assert report.trend[0].n == len(_THEMES) * 2
