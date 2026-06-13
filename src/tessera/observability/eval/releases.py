"""Release + quality-regression status from real repo sources (image 00 rail).

Two real, exact sources — no fabrication:

* **Releases** are parsed from ``CHANGELOG.md`` (Keep a Changelog format): the
  version headers (``## [x.y.z] — date``) and the count of Added/Changed/Fixed
  bullets in each. The "current" release is the most recent *dated* one.
* **Regressions** are derived from the eval report archive: for each model with
  at least two full-catalogue runs, the pass-rate change between its two most
  recent runs; a negative change is a real regression. The non-regression rate
  is the fraction of compared models that did not regress.

The release's quality status is therefore a fact (``n_regressions`` open), not an
invented "blocked" flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tessera.observability.eval.runs import RunRegistry, load_runs

__all__ = [
    "Regression",
    "Release",
    "ReleaseStatus",
    "default_changelog_path",
    "detect_regressions",
    "load_releases",
    "release_status",
]

# A model needs at least this many cases for a run to count as a full evaluation
# (smoke runs of a handful of cases are not a fair regression baseline).
_MIN_CASES = 20
# Two comparable runs are needed to call a regression (before/after).
_MIN_RUNS = 2

_VERSION_RE = re.compile(r"^##\s*\[(?P<version>[^\]]+)\](?:\s*[—-]\s*(?P<date>.+?))?\s*$")
_SECTION_RE = re.compile(r"^###\s+(?P<name>Added|Changed|Fixed)\s*$")
_BULLET_RE = re.compile(r"^- ")


@dataclass(frozen=True, slots=True)
class Release:
    """One CHANGELOG release: version, date, and change counts."""

    version: str
    date: str | None  # None for the Unreleased section
    added: int
    changed: int
    fixed: int

    @property
    def total_changes(self) -> int:
        """Total Added + Changed + Fixed entries in the release."""
        return self.added + self.changed + self.fixed


@dataclass(frozen=True, slots=True)
class Regression:
    """A model whose pass rate dropped between its two most recent full runs."""

    model: str
    prev_run_at: str
    last_run_at: str
    prev_rate: float
    last_rate: float
    delta: float  # last_rate - prev_rate (negative)
    total: int


@dataclass(frozen=True, slots=True)
class ReleaseStatus:
    """Current release plus the real open-regression picture."""

    current: Release | None
    releases: list[Release] = field(default_factory=list)
    regressions: list[Regression] = field(default_factory=list)
    n_regressions: int = 0
    models_compared: int = 0
    non_regression_rate: float = 1.0


def default_changelog_path() -> Path:
    """Repo path of ``CHANGELOG.md``."""
    return Path(__file__).resolve().parents[4] / "CHANGELOG.md"


def load_releases(changelog: Path | None = None) -> list[Release]:
    """Parse the changelog into releases, newest first.

    Args:
        changelog: Path to ``CHANGELOG.md``; defaults to the repo root file.

    Returns:
        Releases in document order (newest first). A missing file yields an empty
        list rather than raising.
    """
    path = changelog or default_changelog_path()
    if not path.exists():
        return []
    releases: list[Release] = []
    version: str | None = None
    date: str | None = None
    counts = {"Added": 0, "Changed": 0, "Fixed": 0}
    section: str | None = None

    def flush() -> None:
        if version is not None:
            releases.append(
                Release(
                    version=version,
                    date=date,
                    added=counts["Added"],
                    changed=counts["Changed"],
                    fixed=counts["Fixed"],
                )
            )

    for raw in path.read_text(encoding="utf-8").splitlines():
        header = _VERSION_RE.match(raw)
        if header:
            flush()
            version = header.group("version")
            date = header.group("date")
            counts = {"Added": 0, "Changed": 0, "Fixed": 0}
            section = None
            continue
        sec = _SECTION_RE.match(raw)
        if sec:
            section = sec.group("name")
            continue
        if section and _BULLET_RE.match(raw):
            counts[section] += 1
    flush()
    return releases


def detect_regressions(registry: RunRegistry) -> tuple[list[Regression], int]:
    """Find models whose latest full run regressed against the previous one.

    Only runs of at least :data:`_MIN_CASES` cases are compared, so a tiny smoke
    run never triggers (or masks) a regression.

    Returns:
        ``(regressions, models_compared)`` — regressions sorted by severity
        (largest drop first), and the count of models that had two comparable
        runs (the denominator of the non-regression rate).
    """
    by_model: dict[str, list[tuple[str, float, int]]] = {}
    for run in registry.runs:
        if run.total < _MIN_CASES:
            continue
        by_model.setdefault(run.model, []).append((run.run_at, run.pass_rate, run.total))

    regressions: list[Regression] = []
    compared = 0
    for model, runs in by_model.items():
        if len(runs) < _MIN_RUNS:
            continue
        compared += 1
        runs.sort(key=lambda r: r[0])
        prev, last = runs[-2], runs[-1]
        delta = last[1] - prev[1]
        if delta < 0:
            regressions.append(
                Regression(
                    model=model,
                    prev_run_at=prev[0],
                    last_run_at=last[0],
                    prev_rate=prev[1],
                    last_rate=last[1],
                    delta=delta,
                    total=last[2],
                )
            )
    regressions.sort(key=lambda r: r.delta)
    return regressions, compared


def release_status(
    changelog: Path | None = None,
    registry: RunRegistry | None = None,
) -> ReleaseStatus:
    """Assemble the release rail: current release + real open regressions.

    Args:
        changelog: Override the changelog path (tests).
        registry: Override the run registry (tests); otherwise loaded from disk.

    Returns:
        A :class:`ReleaseStatus`. ``current`` is the most recent *dated* release.
        ``non_regression_rate`` is ``1.0`` when no models could be compared.
    """
    releases = load_releases(changelog)
    current = next((r for r in releases if r.date), None)
    reg_registry = registry if registry is not None else load_runs()
    regressions, compared = detect_regressions(reg_registry)
    n = len(regressions)
    rate = (compared - n) / compared if compared else 1.0
    return ReleaseStatus(
        current=current,
        releases=releases,
        regressions=regressions,
        n_regressions=n,
        models_compared=compared,
        non_regression_rate=rate,
    )
