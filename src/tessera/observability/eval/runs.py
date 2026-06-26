"""Eval run registry + model comparison from the report archive (images 02 & 04).

The non-regression harness writes one JSON report per run under ``eval/reports``
(``{run_at}_{lang}.json`` and model-named files), each with a ``summary``
(total/passed/pass_rate), per-case ``results``, an optional ``cost`` and a
``catalogue_version``. This module reads that real archive into:

* a **run registry** — one row per report for the Runs & datasets tab;
* a **model comparison** — the latest run per model aggregated for the
  Comparaisons modèles tab, with a documented verdict heuristic.

Nothing is fabricated: a missing cost (local models run free) or missing timing
stays ``None`` rather than becoming a zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tessera.observability.eval.report_paths import report_files_for

__all__ = [
    "ModelStat",
    "RunRegistry",
    "RunSummary",
    "compare_models",
    "default_reports_dir",
    "load_runs",
]


@dataclass(frozen=True, slots=True)
class RunSummary:
    """One eval run over the failure catalogue."""

    run_id: str
    run_at: str
    model: str
    language: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    est_cost_eur: float | None
    mean_latency_ms: float | None
    catalogue_version: str | None


@dataclass(frozen=True, slots=True)
class ModelStat:
    """A model's latest run, for the comparison table."""

    model: str
    n_runs: int
    total_cases: int
    pass_rate: float
    est_cost_eur: float | None
    mean_latency_ms: float | None
    last_run_at: str
    verdict: str  # "best" | "balanced" | "economic" | "avoid"


@dataclass(frozen=True, slots=True)
class RunRegistry:
    """The run archive plus the catalogue it was run against."""

    n: int
    runs: list[RunSummary]
    catalogue_cases: int
    catalogue_version: str | None
    models: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


def default_reports_dir() -> Path:
    """Repo path of the eval report archive (``eval/reports``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports"


def _mean_latency_ms(results: object) -> float | None:
    """Mean per-case wall time from result start/end timestamps, if present."""
    if not isinstance(results, list):
        return None
    spans: list[float] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        start, end = r.get("start_time"), r.get("end_time")
        if not isinstance(start, str) or not isinstance(end, str):
            continue
        try:
            a = datetime.fromisoformat(start)
            b = datetime.fromisoformat(end)
        except ValueError:
            continue
        spans.append((b - a).total_seconds() * 1000.0)
    return sum(spans) / len(spans) if spans else None


def _summary_run(path: Path, obj: dict[str, object]) -> RunSummary | None:
    """Build a :class:`RunSummary` from one report dict, or ``None`` if not a run."""
    summary = obj.get("summary")
    model = obj.get("model")
    if not isinstance(summary, dict) or not isinstance(model, str):
        return None
    cost = obj.get("cost")
    est_cost = None
    if isinstance(cost, dict) and isinstance(cost.get("estimated_cost_eur"), int | float):
        est_cost = float(cost["estimated_cost_eur"])
    total = int(summary.get("total", 0) or 0)
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", max(0, total - passed)) or 0)
    rate = summary.get("pass_rate")
    pass_rate = float(rate) if isinstance(rate, int | float) else (passed / total if total else 0.0)
    version = obj.get("catalogue_version")
    return RunSummary(
        run_id=path.stem,
        run_at=str(obj.get("run_at", path.stem)),
        model=model,
        language=str(obj.get("lang", "")),
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        est_cost_eur=est_cost,
        mean_latency_ms=_mean_latency_ms(obj.get("results")),
        catalogue_version=str(version) if isinstance(version, str) else None,
    )


def load_runs(directory: Path | None = None) -> RunRegistry:
    """Load every eval report into a registry, newest run first.

    Args:
        directory: Report directory; defaults to ``eval/reports``.

    Returns:
        A :class:`RunRegistry`. An absent or unreadable directory yields an empty
        registry rather than raising.
    """
    runs: list[RunSummary] = []
    files = report_files_for(directory)
    if files:
        for path in files:
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue
            run = _summary_run(path, obj)
            if run is not None:
                runs.append(run)
    runs.sort(key=lambda r: r.run_at, reverse=True)
    models = sorted({r.model for r in runs})
    languages = sorted({r.language for r in runs if r.language})
    version = runs[0].catalogue_version if runs else None
    catalogue_cases = max((r.total for r in runs), default=0)
    return RunRegistry(
        n=len(runs),
        runs=runs,
        catalogue_cases=catalogue_cases,
        catalogue_version=version,
        models=models,
        languages=languages,
    )


def compare_models(runs: list[RunSummary]) -> list[ModelStat]:
    """Aggregate the latest run per model into comparison rows, best pass-rate first.

    Each model is represented by its **most complete** recent run (max cases, ties
    broken by recency) so a tiny smoke run never stands in for a full evaluation.
    Verdict heuristic (documented): the top pass-rate model is ``best``; any model
    below 50% is ``avoid``; among the rest a free/local model (no cost) is
    ``economic`` and a priced one ``balanced``.
    """
    latest: dict[str, RunSummary] = {}
    counts: dict[str, int] = {}
    for r in runs:
        counts[r.model] = counts.get(r.model, 0) + 1
        cur = latest.get(r.model)
        if cur is None or (r.total, r.run_at) > (cur.total, cur.run_at):
            latest[r.model] = r
    if not latest:
        return []

    best_model = max(latest.values(), key=lambda r: r.pass_rate).model
    stats: list[ModelStat] = []
    for model, run in latest.items():
        if model == best_model:
            verdict = "best"
        elif run.pass_rate < 0.5:  # noqa: PLR2004 — documented 50% floor
            verdict = "avoid"
        elif not run.est_cost_eur:
            verdict = "economic"
        else:
            verdict = "balanced"
        stats.append(
            ModelStat(
                model=model,
                n_runs=counts[model],
                total_cases=run.total,
                pass_rate=run.pass_rate,
                est_cost_eur=run.est_cost_eur,
                mean_latency_ms=run.mean_latency_ms,
                last_run_at=run.run_at,
                verdict=verdict,
            )
        )
    stats.sort(key=lambda s: s.pass_rate, reverse=True)
    return stats
