"""Quality datasets view of the non-regression catalogue (reference image 02).

Tessera has **no separate "eval datasets"** product: the non-regression evals run
against one real failure catalogue (``eval/failures/NN_*.json``, ~63 cases) whose
cases are tagged by ``category``. Those categories *are* the real quality datasets
— each is a coherent failure theme (prompt injection, PII leak, hallucination…).

This module joins that catalogue with the run archive (``eval/reports/*.json``,
whose per-case ``results[]`` carry ``case_id`` + ``category`` + ``language`` +
``passed``) to compute, **per theme**, only real, derivable numbers:

* ``cases`` — case count in the catalogue;
* ``languages`` — languages the cases are authored in;
* ``version`` — the catalogue version of the latest run;
* ``pass_rate`` — passed / evaluated in the latest full-catalogue run;
* ``drift`` — pass-rate delta between the two most recent full-catalogue runs;
* ``coverage`` — distinct theme cases evaluated in the latest run / catalogue cases;
* ``updated_at`` — newest run timestamp that exercised the theme.

Nothing is fabricated: a theme absent from the latest run keeps ``pass_rate`` /
``coverage`` / ``drift`` at ``None`` rather than a zero. ``owner`` is a documented
governance assignment (org config, not a measured metric).

The companion :func:`pipeline_status` surfaces the real evaluation-pipeline health
(executions in the trailing window, data freshness, catalogue coverage). Signals
with no real source in Tessera — a worker pool, a job queue, an evidence-retention
TTL — stay ``None`` so the dashboard renders them as "—", never as invented OK.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

__all__ = [
    "PipelineStatus",
    "QualityDataset",
    "QualityDatasetsReport",
    "default_failures_dir",
    "default_reports_dir",
    "load_quality_datasets",
    "pipeline_status",
]

# A run is "full-catalogue" once it covers most themes and a substantial case set;
# this excludes the one-case smoke runs that would otherwise distort drift.
_MIN_FULL_CATEGORIES = 8
_MIN_FULL_TOTAL = 40

# Trailing window (days) for the "executions in 24h" pipeline counter, anchored on
# the newest run so a historical archive still reports real recent activity.
_WINDOW_HOURS = 24
_HOUR_MS = 3_600_000

_LANG_FALLBACK = ("fr", "de", "en")

# Governance ownership per failure theme — documented org assignment (which team
# owns the dataset's quality), not a measured signal. Safety/security themes go to
# the Safety team, regulatory/financial themes to Compliance, the rest to Quality.
_OWNER: dict[str, str] = {
    "prompt_injection": "Safety",
    "pii_leak": "Safety",
    "policy_violation": "Safety",
    "tool_misuse": "Safety",
    "regulatory_misstatement": "Compliance",
    "citation_fabrication": "Compliance",
    "escalation_failure": "Compliance",
    "hallucination": "Quality",
    "overconfidence": "Quality",
    "language_mixing": "Quality",
}
_DEFAULT_OWNER = "Quality"


@dataclass(frozen=True, slots=True)
class QualityDataset:
    """One failure theme surfaced as a monitored quality dataset."""

    key: str  # the failure category (stable identifier)
    cases: int
    languages: list[str]
    version: str | None
    pass_rate: float | None
    drift: float | None
    coverage: float | None
    updated_at: str | None
    owner: str


@dataclass(frozen=True, slots=True)
class PipelineStatus:
    """Real evaluation-pipeline health; absent signals stay ``None`` (→ "—")."""

    jobs_window: int  # eval runs in the trailing 24h window (anchored on newest run)
    runs_total: int
    data_freshness_seconds: float | None  # age of the newest run vs now
    catalogue_coverage: float | None  # distinct cases evaluated / catalogue cases (latest full run)
    evidence_retention_days: int | None  # no evidence-store TTL wired → None
    workers: int | None  # no worker pool in Tessera → None
    queue_depth: int | None  # no job queue in Tessera → None


@dataclass(frozen=True, slots=True)
class QualityDatasetsReport:
    """The themed datasets, their catalogue facts and pipeline health."""

    n: int
    datasets: list[QualityDataset]
    catalogue_version: str | None
    total_cases: int
    languages: list[str]
    monitored: int  # active datasets (= n)
    coverage_pct: float | None  # mean coverage across datasets ("% couverts")
    pipeline: PipelineStatus = field(
        default_factory=lambda: PipelineStatus(0, 0, None, None, None, None, None)
    )


def default_failures_dir() -> Path:
    """Repo path of the documented-failure catalogue (``eval/failures``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "failures"


def default_reports_dir() -> Path:
    """Repo path of the eval report archive (``eval/reports``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports"


# ───────────────────────────── catalogue side ────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Theme:
    cases: int
    languages: list[str]


def _load_catalogue(failures_dir: Path) -> dict[str, _Theme]:
    """Group the failure catalogue by category → case count + authored languages."""
    counts: dict[str, int] = defaultdict(int)
    langs: dict[str, set[str]] = defaultdict(set)
    if failures_dir.exists():
        for path in sorted(failures_dir.glob("[0-9]*.json")):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue
            category = str(obj.get("category", "unknown"))
            counts[category] += 1
            prompts = obj.get("prompts")
            if isinstance(prompts, dict):
                for lang, entry in prompts.items():
                    if isinstance(entry, dict) and entry.get("user"):
                        langs[category].add(str(lang))
    order = {lang: i for i, lang in enumerate(_LANG_FALLBACK)}
    return {
        cat: _Theme(
            cases=counts[cat],
            languages=sorted(langs[cat], key=lambda lang: order.get(lang, 99)),
        )
        for cat in counts
    }


# ────────────────────────────── reports side ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class _CatStat:
    passed: int
    total: int
    case_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _RunCats:
    run_id: str
    run_at: str
    model: str
    n_total: int
    version: str | None
    cats: dict[str, _CatStat]


def _load_run_cats(reports_dir: Path) -> list[_RunCats]:
    """Read each report into per-category pass/total/case-id breakdowns, newest last."""
    runs: list[_RunCats] = []
    if not reports_dir.exists():
        return runs
    for path in reports_dir.glob("*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        results = obj.get("results")
        if not isinstance(results, list) or not results:
            continue
        passed: dict[str, int] = defaultdict(int)
        total: dict[str, int] = defaultdict(int)
        ids: dict[str, set[str]] = defaultdict(set)
        for r in results:
            if not isinstance(r, dict):
                continue
            cat = str(r.get("category", "unknown"))
            total[cat] += 1
            if r.get("passed"):
                passed[cat] += 1
            case_id = r.get("case_id")
            if isinstance(case_id, str):
                ids[cat].add(case_id)
        cats = {
            cat: _CatStat(passed=passed[cat], total=total[cat], case_ids=frozenset(ids[cat]))
            for cat in total
        }
        version = obj.get("catalogue_version")
        runs.append(
            _RunCats(
                run_id=path.stem,
                run_at=str(obj.get("run_at", path.stem)),
                model=str(obj.get("model", "")),
                n_total=sum(s.total for s in cats.values()),
                version=str(version) if isinstance(version, str) else None,
                cats=cats,
            )
        )
    runs.sort(key=lambda r: r.run_at)
    return runs


def _parse_run_at(stamp: str) -> int | None:
    """Compact run stamp ("20260606T075407Z") → epoch ms, or ``None``."""
    try:
        dt = datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None
    return int(dt.timestamp() * 1000)


def _full_runs(runs: list[_RunCats]) -> list[_RunCats]:
    """The substantive full-catalogue runs (enough themes and cases), oldest→newest."""
    return [r for r in runs if len(r.cats) >= _MIN_FULL_CATEGORIES and r.n_total >= _MIN_FULL_TOTAL]


# ─────────────────────────────── public API ──────────────────────────────────


def load_quality_datasets(
    failures_dir: Path | None = None,
    reports_dir: Path | None = None,
) -> QualityDatasetsReport:
    """Join the failure catalogue with the run archive into themed quality datasets.

    Args:
        failures_dir: Failure catalogue directory; defaults to ``eval/failures``.
        reports_dir: Report archive directory; defaults to ``eval/reports``.

    Returns:
        A :class:`QualityDatasetsReport`. An empty catalogue yields an empty report
        rather than raising; per-theme run metrics are ``None`` when the latest run
        did not exercise the theme.
    """
    catalogue = _load_catalogue(failures_dir or default_failures_dir())
    runs = _load_run_cats(reports_dir or default_reports_dir())
    full = _full_runs(runs)

    latest = full[-1] if full else None
    # Previous full run for drift: prefer the same model (true run-over-run), else
    # the immediately preceding full run.
    previous: _RunCats | None = None
    if latest is not None:
        same_model = [r for r in full[:-1] if r.model == latest.model]
        prior_full = full[:-1]  # full runs before the latest
        previous = same_model[-1] if same_model else (prior_full[-1] if prior_full else None)

    # Newest run (any size) that exercised each theme → its "dernière maj".
    last_seen: dict[str, str] = {}
    for r in runs:  # already oldest→newest
        for cat in r.cats:
            last_seen[cat] = r.run_at

    catalogue_version = _catalogue_version(runs)

    datasets: list[QualityDataset] = []
    coverages: list[float] = []
    for cat, theme in catalogue.items():
        latest_stat = latest.cats.get(cat) if latest is not None else None
        pass_rate: float | None = None
        coverage: float | None = None
        if latest_stat is not None and latest_stat.total > 0:
            pass_rate = latest_stat.passed / latest_stat.total
            if theme.cases > 0:
                coverage = min(1.0, len(latest_stat.case_ids) / theme.cases)
                coverages.append(coverage)
        drift: float | None = None
        prev_stat = previous.cats.get(cat) if previous is not None else None
        if pass_rate is not None and prev_stat is not None and prev_stat.total > 0:
            drift = pass_rate - prev_stat.passed / prev_stat.total
        datasets.append(
            QualityDataset(
                key=cat,
                cases=theme.cases,
                languages=theme.languages,
                version=catalogue_version,
                pass_rate=pass_rate,
                drift=drift,
                coverage=coverage,
                updated_at=last_seen.get(cat),
                owner=_OWNER.get(cat, _DEFAULT_OWNER),
            )
        )

    # Worst drift first (operationally most interesting), then most cases.
    datasets.sort(key=lambda d: (-(abs(d.drift) if d.drift is not None else -1.0), -d.cases))

    order = {lang: i for i, lang in enumerate(_LANG_FALLBACK)}
    all_langs = sorted(
        {lang for d in datasets for lang in d.languages}, key=lambda lang: order.get(lang, 99)
    )
    coverage_pct = sum(coverages) / len(coverages) if coverages else None
    return QualityDatasetsReport(
        n=len(datasets),
        datasets=datasets,
        catalogue_version=catalogue_version,
        total_cases=sum(d.cases for d in datasets),
        languages=all_langs,
        monitored=len(datasets),
        coverage_pct=coverage_pct,
        pipeline=_pipeline(runs, latest, sum(t.cases for t in catalogue.values())),
    )


def _catalogue_version(runs: list[_RunCats]) -> str | None:
    """Catalogue version of the newest run that records one (versions came late)."""
    for r in reversed(runs):
        if r.version is not None:
            return r.version
    return None


def _pipeline(
    runs: list[_RunCats],
    latest: _RunCats | None,
    catalogue_cases: int,
) -> PipelineStatus:
    """Real pipeline health from the report archive; unknown signals stay ``None``."""
    stamps = [t for t in (_parse_run_at(r.run_at) for r in runs) if t is not None]
    newest = max(stamps) if stamps else None
    jobs_window = 0
    if newest is not None:
        start = newest - _WINDOW_HOURS * _HOUR_MS
        jobs_window = sum(1 for t in stamps if t >= start)
    freshness: float | None = None
    if newest is not None:
        freshness = max(0.0, (datetime.now().timestamp() * 1000 - newest) / 1000.0)
    coverage: float | None = None
    if latest is not None and catalogue_cases > 0:
        evaluated = len({cid for s in latest.cats.values() for cid in s.case_ids})
        coverage = min(1.0, evaluated / catalogue_cases)
    return PipelineStatus(
        jobs_window=jobs_window,
        runs_total=len(runs),
        data_freshness_seconds=freshness,
        catalogue_coverage=coverage,
        evidence_retention_days=None,  # no evidence-store TTL wired in Tessera
        workers=None,  # no worker pool
        queue_depth=None,  # no job queue
    )


def pipeline_status(reports_dir: Path | None = None) -> PipelineStatus:
    """Standalone evaluation-pipeline health (subset of :func:`load_quality_datasets`)."""
    runs = _load_run_cats(reports_dir or default_reports_dir())
    full = _full_runs(runs)
    catalogue = _load_catalogue(default_failures_dir())
    return _pipeline(runs, full[-1] if full else None, sum(t.cases for t in catalogue.values()))
