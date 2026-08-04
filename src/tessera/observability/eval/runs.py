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
from dataclasses import dataclass, field, replace
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
    """One eval run over the failure catalogue, and the ruler that judged it.

    A *run* is a sampling event — ``run_at``, a model, an eval set, the responses
    it recorded. The *grading* is a separate act: the same recorded responses can
    be re-judged later under moved criteria (``make eval-regrade``), which changes
    every verdict without spending a token. ``regraded_at`` and
    ``grader_criteria_sha`` name that second act, so a displayed pass rate can say
    **when it was judged and by which ruler** — not only when it was sampled.
    """

    run_id: str
    run_at: str
    model: str
    language: str | None
    total: int
    passed: int
    failed: int
    pass_rate: float
    est_cost_eur: float | None
    mean_latency_ms: float | None
    catalogue_version: str | None
    eval_set: str | None = None
    regraded_at: str | None = None
    grader_criteria_sha: str | None = None
    #: Older gradings of this same run that this row supersedes (0 in the normal case).
    superseded_copies: int = 0

    @property
    def graded_at(self) -> str:
        """When the verdicts in this row were decided — the re-grade, else the run."""
        return self.regraded_at or self.run_at


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
    """The run archive plus the catalogue it was run against.

    ``n`` counts **runs**, not files: a run re-graded after the fact exists on disk
    twice (the ``latest_<agent>.json`` pointer and its timestamped archive), and
    counting files published one run as two — with two different rulers and, when
    a judgement had moved, two different pass rates. ``superseded`` says out loud
    how many older gradings were folded away, so the fold is never silent.
    """

    n: int
    runs: list[RunSummary]
    catalogue_cases: int
    catalogue_version: str | None
    models: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    superseded: int = 0


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
            # best-effort: skip a result row with a bad start/end time — non-gating (0015)
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
    return RunSummary(
        run_id=path.stem,
        run_at=str(obj.get("run_at", path.stem)),
        model=model,
        # A multilingual agent run carries `lang: null`. `str(None)` turned that absence into
        # the four-character *value* "None", which then travelled into the registry's language
        # list and offered the operator a language filter for a language that does not exist.
        # An absent language is None, and the screen renders "—" from it.
        language=_optional_str(obj.get("lang")),
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        est_cost_eur=est_cost,
        mean_latency_ms=_mean_latency_ms(obj.get("results")),
        catalogue_version=_optional_str(obj.get("catalogue_version")),
        eval_set=_optional_str(obj.get("eval_set")) or _optional_str(obj.get("agent_id")),
        regraded_at=_optional_str(obj.get("regraded_at")),
        grader_criteria_sha=_optional_str(obj.get("grader_criteria_sha")),
    )


def _optional_str(value: object) -> str | None:
    """A non-empty string, or ``None`` — never the *text* of a missing value."""
    return value if isinstance(value, str) and value else None


def _run_identity(run: RunSummary) -> tuple[str, str, str, str]:
    """What makes two report files the SAME run rather than two runs.

    The sampling event: when it ran, which model answered, which set it ran over,
    in which language. Two files agreeing on all four hold one run's responses —
    typically the ``latest_<agent>.json`` pointer and its timestamped archive.
    """
    return (run.run_at, run.model, run.eval_set or "", run.language or "")


def _grading_rank(run: RunSummary) -> tuple[str, int, str]:
    """Order two gradings of one run, newest grading first once reversed.

    Deterministic and stated, because the alternative is not: folding on first-seen
    would let the *filesystem enumeration order* decide which verdicts an operator
    reads, and the two copies genuinely disagreed (one judgement on ``recouvrement``)
    after the 2026-08-04 re-grade wrote only the pointer. A run whose ruler is named
    outranks one whose ruler is not; ``run_id`` breaks a remaining tie so the answer
    never depends on the disk.
    """
    return (run.graded_at, 1 if run.grader_criteria_sha else 0, run.run_id)


def load_runs(directory: Path | None = None) -> RunRegistry:
    """Load every eval report into a registry, newest run first.

    Args:
        directory: Report directory; defaults to ``eval/reports``.

    One row per *run*, not per file: a re-graded run exists twice on disk and its
    two copies can carry different verdicts, so the newest **grading** of each run
    wins and the count of folded copies is reported rather than swallowed.

    Returns:
        A :class:`RunRegistry`. An absent or unreadable directory yields an empty
        registry rather than raising.
    """
    parsed: list[RunSummary] = []
    files = report_files_for(directory)
    if files:
        for path in files:
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # best-effort: skip an unreadable/corrupt eval-report JSON — non-gating (0015)
                continue
            if not isinstance(obj, dict):
                continue
            run = _summary_run(path, obj)
            if run is not None:
                parsed.append(run)

    kept: dict[tuple[str, str, str, str], RunSummary] = {}
    folded: dict[tuple[str, str, str, str], int] = {}
    for run in parsed:
        key = _run_identity(run)
        current = kept.get(key)
        if current is None:
            kept[key] = run
            continue
        folded[key] = folded.get(key, 0) + 1
        if _grading_rank(run) > _grading_rank(current):
            kept[key] = run

    runs = [
        replace(run, superseded_copies=folded.get(key, 0)) for key, run in kept.items()
    ]
    runs.sort(key=lambda r: (r.run_at, r.run_id), reverse=True)
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
        superseded=sum(folded.values()),
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
