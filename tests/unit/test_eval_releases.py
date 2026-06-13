"""Unit tests for the release + quality-regression status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.eval.releases import (
    detect_regressions,
    load_releases,
    release_status,
)
from tessera.observability.eval.runs import RunRegistry, RunSummary

if TYPE_CHECKING:
    from pathlib import Path

_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- pending one
- pending two

## [0.3.0] — 2026-05-29

### Added
- a
- b

### Changed
- c

### Fixed
- d
- e
- f

## [0.2.0] — 2026-05-28
"""


def _run(model: str, run_at: str, rate: float, total: int = 60) -> RunSummary:
    return RunSummary(
        run_id=f"{model}-{run_at}",
        run_at=run_at,
        model=model,
        language="fr",
        total=total,
        passed=int(rate * total),
        failed=total - int(rate * total),
        pass_rate=rate,
        est_cost_eur=None,
        mean_latency_ms=None,
        catalogue_version="63-abc",
    )


def _registry(runs: list[RunSummary]) -> RunRegistry:
    return RunRegistry(
        n=len(runs),
        runs=sorted(runs, key=lambda r: r.run_at, reverse=True),
        catalogue_cases=max((r.total for r in runs), default=0),
        catalogue_version="63-abc",
        models=sorted({r.model for r in runs}),
        languages=["fr"],
    )


def test_load_releases_parses_versions_and_counts(tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_CHANGELOG, encoding="utf-8")
    releases = load_releases(path)
    versions = [r.version for r in releases]
    assert versions == ["Unreleased", "0.3.0", "0.2.0"]
    unreleased = releases[0]
    assert unreleased.date is None
    assert unreleased.added == 2
    v030 = releases[1]
    assert v030.date == "2026-05-29"
    assert (v030.added, v030.changed, v030.fixed) == (2, 1, 3)
    assert v030.total_changes == 6


def test_missing_changelog_is_empty(tmp_path: Path) -> None:
    assert load_releases(tmp_path / "nope.md") == []


def test_detect_regressions_only_flags_real_drops() -> None:
    runs = [
        _run("good", "20260601T000000Z", 0.80),
        _run("good", "20260604T000000Z", 0.90),  # improved
        _run("bad", "20260601T000000Z", 0.95),
        _run("bad", "20260604T000000Z", 0.58),  # regressed
        _run("smoke", "20260604T000000Z", 1.0, total=1),  # too small to count
    ]
    regressions, compared = detect_regressions(_registry(runs))
    assert compared == 2  # good + bad (smoke has one tiny run)
    assert len(regressions) == 1
    assert regressions[0].model == "bad"
    assert regressions[0].delta < 0
    assert regressions[0].prev_rate == 0.95
    assert regressions[0].last_rate == 0.58


def test_release_status_assembles_rate(tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_CHANGELOG, encoding="utf-8")
    runs = [
        _run("good", "20260601T000000Z", 0.80),
        _run("good", "20260604T000000Z", 0.90),
        _run("bad", "20260601T000000Z", 0.95),
        _run("bad", "20260604T000000Z", 0.58),
    ]
    status = release_status(changelog=path, registry=_registry(runs))
    assert status.current is not None
    assert status.current.version == "0.3.0"  # most recent *dated* release
    assert status.n_regressions == 1
    assert status.models_compared == 2
    assert status.non_regression_rate == 0.5


def test_real_sources_load() -> None:
    status = release_status()
    assert status.current is not None  # CHANGELOG has dated releases
    assert 0.0 <= status.non_regression_rate <= 1.0
