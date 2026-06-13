"""Unit tests for the themed quality-datasets view (Runs & datasets tab)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.observability.eval.datasets import load_quality_datasets, pipeline_status

if TYPE_CHECKING:
    from pathlib import Path

# Ten themes mirroring the real failure catalogue, so a synthetic catalogue is a
# valid "full-catalogue" run (>= 8 categories, >= 40 cases).
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


def _write_failures(directory: Path, *, cases_per_theme: int = 5) -> None:
    """Write ``cases_per_theme`` catalogue files per theme (fr/de/en prompts)."""
    i = 0
    for theme in _THEMES:
        for n in range(cases_per_theme):
            i += 1
            (directory / f"{i:02d}_{theme}_{n}.json").write_text(
                json.dumps(
                    {
                        "id": f"{i:02d}_{theme}_{n}",
                        "category": theme,
                        "title": f"{theme} {n}",
                        "prompts": {
                            "fr": {"user": "q"},
                            "de": {"user": "q"},
                            "en": {"user": "q"},
                        },
                    }
                ),
                encoding="utf-8",
            )


def _write_report(
    directory: Path,
    name: str,
    *,
    run_at: str,
    model: str,
    passed_per_theme: int,
    cases_per_theme: int = 5,
    version: str | None = "63-abc",
    themes: tuple[str, ...] = _THEMES,
) -> None:
    """Write one full-catalogue report with a fixed pass count per theme."""
    results: list[dict[str, object]] = []
    for theme in themes:
        for n in range(cases_per_theme):
            results.append(
                {
                    "case_id": f"{theme}_{n}",
                    "category": theme,
                    "language": "fr",
                    "passed": n < passed_per_theme,
                }
            )
    obj: dict[str, object] = {"run_at": run_at, "model": model, "results": results}
    if version is not None:
        obj["catalogue_version"] = version
    (directory / name).write_text(json.dumps(obj), encoding="utf-8")


def test_empty_catalogue(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    report = load_quality_datasets(failures, reports)
    assert report.n == 0
    assert report.datasets == []
    assert report.total_cases == 0
    assert report.coverage_pct is None
    assert report.pipeline.runs_total == 0


def test_catalogue_themes_and_languages(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    _write_failures(failures, cases_per_theme=5)

    report = load_quality_datasets(failures, reports)
    assert report.n == len(_THEMES)
    assert report.total_cases == len(_THEMES) * 5
    assert sorted(report.languages) == ["de", "en", "fr"]
    # No reports → run-derived metrics are honestly absent.
    for d in report.datasets:
        assert d.pass_rate is None
        assert d.drift is None
        assert d.coverage is None
        assert d.cases == 5
        assert d.owner  # documented governance assignment is always set


def test_pass_rate_drift_and_coverage(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    _write_failures(failures, cases_per_theme=5)
    # Previous full run: 2/5 pass per theme. Latest: 4/5 per theme → drift +0.4.
    _write_report(
        reports, "prev.json", run_at="20260601T000000Z", model="m", passed_per_theme=2
    )
    _write_report(
        reports, "latest.json", run_at="20260606T000000Z", model="m", passed_per_theme=4
    )

    report = load_quality_datasets(failures, reports)
    by_key = {d.key: d for d in report.datasets}
    pii = by_key["pii_leak"]
    assert pii.pass_rate == 4 / 5
    assert pii.drift is not None
    assert abs(pii.drift - 0.4) < 1e-9
    assert pii.coverage == 1.0  # all 5 cases evaluated
    assert pii.version == "63-abc"
    assert pii.updated_at == "20260606T000000Z"
    assert report.coverage_pct == 1.0
    assert report.catalogue_version == "63-abc"


def test_partial_coverage_and_missing_theme(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    _write_failures(failures, cases_per_theme=6)
    # Latest run evaluates 5 of the 6 cases per theme, and drops one theme. With 9
    # themes x 5 cases = 45 it stays a substantive full-catalogue run (>= 40, >= 8).
    _write_report(
        reports,
        "latest.json",
        run_at="20260606T000000Z",
        model="m",
        passed_per_theme=5,
        cases_per_theme=5,
        themes=_THEMES[:9],  # escalation_failure omitted
    )

    report = load_quality_datasets(failures, reports)
    by_key = {d.key: d for d in report.datasets}
    # Evaluated theme: 5/6 cases → coverage ≈ 0.833, no previous run → drift None.
    pi = by_key["prompt_injection"]
    assert abs((pi.coverage or 0) - 5 / 6) < 1e-9
    assert pi.drift is None
    assert pi.pass_rate == 1.0  # all 5 evaluated cases pass
    # Omitted theme: no run metrics, but catalogue facts remain.
    missing = by_key["escalation_failure"]
    assert missing.pass_rate is None
    assert missing.coverage is None
    assert missing.cases == 6


def test_smoke_run_excluded_from_drift(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    _write_failures(failures, cases_per_theme=5)
    _write_report(reports, "full.json", run_at="20260601T000000Z", model="m", passed_per_theme=2)
    # A later one-case smoke run must not become the "latest full run".
    (reports / "smoke.json").write_text(
        json.dumps(
            {
                "run_at": "20260609T000000Z",
                "model": "m",
                "results": [{"case_id": "x", "category": "pii_leak", "passed": True}],
            }
        ),
        encoding="utf-8",
    )

    report = load_quality_datasets(failures, reports)
    by_key = {d.key: d for d in report.datasets}
    # Metrics come from the full run, not the smoke run.
    assert by_key["pii_leak"].pass_rate == 2 / 5


def test_pipeline_status_real_and_absent_signals(tmp_path: Path) -> None:
    failures = tmp_path / "failures"
    reports = tmp_path / "reports"
    failures.mkdir()
    reports.mkdir()
    _write_failures(failures, cases_per_theme=5)
    _write_report(reports, "r1.json", run_at="20260606T010000Z", model="m", passed_per_theme=3)
    _write_report(reports, "r2.json", run_at="20260606T020000Z", model="m", passed_per_theme=4)

    report = load_quality_datasets(failures, reports)
    pipe = report.pipeline
    assert pipe.runs_total == 2
    assert pipe.jobs_window == 2  # both within 24h of the newest run
    assert pipe.data_freshness_seconds is not None
    assert pipe.catalogue_coverage == 1.0
    # No real source in Tessera → honest None, never a fabricated count.
    assert pipe.workers is None
    assert pipe.queue_depth is None
    assert pipe.evidence_retention_days is None

    # Standalone helper agrees with the embedded pipeline status.
    assert pipeline_status(reports).runs_total == 2
