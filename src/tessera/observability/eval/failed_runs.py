"""Real failed-case view from the run archive (Cas échoués tab, reference image 03).

The documented failure catalogue (``eval/failures``) holds failure *modes* — it is
not a log of observed failures. The actual failed cases live in the run reports
(``eval/reports/*.json``): every ``results[]`` entry with ``passed: false`` is a
real failure, carrying the model's own answer, the judge's ``reasons``, the
category, the language and the timing.

This module collects those real failures (one row per failed result in each
modelxlanguage's most recent full-catalogue run), joins them with the catalogue
for the triggering prompt and expected behaviour, and derives:

* ``status`` — ``new`` if the case did **not** fail in that modelxlanguage's
  previous full run (a fresh regression), else ``recurrent``;
* ``severity`` — the documented triage band of the category (see below);
* ``owner`` — the governance team responsible for the category (org config);
* distributions and a per-day failure ``trend`` for the tab's charts.

Nothing is fabricated: there is no per-case judge *score* in the reports, so the
score stays absent (the UI renders "—"); timing is ``None`` when unrecorded.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

__all__ = [
    "FailedRunCase",
    "FailedRunsReport",
    "TrendPoint",
    "default_failures_dir",
    "default_reports_dir",
    "load_failed_runs",
]

# A run is "full-catalogue" once it covers most themes and a substantial case set —
# this excludes one-case smoke runs (mirrors datasets.py).
_MIN_FULL_CATEGORIES = 8
_MIN_FULL_TOTAL = 40

_TREND_DAYS = 14

_LANG_FALLBACK = ("fr", "de", "en")

# Triage severity by failure category — documented heuristic, not a runtime score
# (kept in sync with failed_cases.py, the catalogue-side source of truth).
_SEVERITY: dict[str, str] = {
    "prompt_injection": "critical",
    "pii_leak": "critical",
    "policy_violation": "critical",
    "hallucination": "high",
    "regulatory_misstatement": "high",
    "tool_misuse": "high",
    "escalation_failure": "high",
    "citation_fabrication": "medium",
    "overconfidence": "medium",
    "language_mixing": "low",
}
_SEVERITY_RANK: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Governance ownership per failure theme — documented org assignment (mirrors
# datasets.py): which team owns triage for that category.
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
class FailedRunCase:
    """One real failed result, surfaced as a Cas-échoués row."""

    id: str  # case_id
    category: str
    severity: str
    language: str
    title: str
    prompt: str  # the triggering user prompt (from the catalogue)
    expected: str  # expected (correct) behaviour
    response: str  # the model's actual answer
    reasons: list[str]  # judge reasons — the failure's root cause
    model: str
    run_id: str
    run_at: str
    catalogue_version: str | None
    latency_ms: float | None
    owner: str
    status: str  # "new" | "recurrent"


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """Failed-case count for one calendar day, split by triage severity."""

    date: str  # YYYY-MM-DD
    n: int
    by_severity: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FailedRunsReport:
    """The real failed cases plus their distributions and a failure trend."""

    n: int
    cases: list[FailedRunCase]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    by_model: dict[str, int]
    by_language: dict[str, int]
    n_critical: int
    n_new: int
    n_recurrent: int
    trend: list[TrendPoint]
    models: list[str]
    languages: list[str]
    catalogue_version: str | None = None
    mean_latency_ms: float | None = None


def default_failures_dir() -> Path:
    """Repo path of the documented-failure catalogue (``eval/failures``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "failures"


def default_reports_dir() -> Path:
    """Repo path of the eval report archive (``eval/reports``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "reports"


# ───────────────────────────── catalogue side ────────────────────────────────


@dataclass(frozen=True, slots=True)
class _CaseInfo:
    title: str
    expected: str
    prompts: dict[str, str]  # language → user prompt


def _load_catalogue(failures_dir: Path) -> dict[str, _CaseInfo]:
    """Index the failure catalogue by case_id → title/expected/prompts."""
    out: dict[str, _CaseInfo] = {}
    if not failures_dir.exists():
        return out
    for path in sorted(failures_dir.glob("[0-9]*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        case_id = str(obj.get("id", path.stem))
        prompts: dict[str, str] = {}
        raw = obj.get("prompts")
        if isinstance(raw, dict):
            for lang, entry in raw.items():
                if isinstance(entry, dict) and entry.get("user"):
                    prompts[str(lang)] = str(entry["user"])
        out[case_id] = _CaseInfo(
            title=str(obj.get("title", "")),
            expected=str(obj.get("expected_behavior", "")),
            prompts=prompts,
        )
    return out


def _prompt_for(info: _CaseInfo | None, language: str) -> str:
    """Best prompt for the case in the given language, with sensible fallback."""
    if info is None:
        return ""
    order = (language, *[lang for lang in _LANG_FALLBACK if lang != language])
    for lang in order:
        if info.prompts.get(lang):
            return info.prompts[lang]
    return info.title


# ────────────────────────────── reports side ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Run:
    run_id: str
    run_at: str
    model: str
    language: str
    version: str | None
    results: list[dict[str, object]]


def _load_runs(reports_dir: Path) -> list[_Run]:
    """Read every report with a results list, newest last."""
    runs: list[_Run] = []
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
        rows = [r for r in results if isinstance(r, dict)]
        version = obj.get("catalogue_version")
        runs.append(
            _Run(
                run_id=path.stem,
                run_at=str(obj.get("run_at", path.stem)),
                model=str(obj.get("model", "")),
                language=str(obj.get("lang", "")),
                version=str(version) if isinstance(version, str) else None,
                results=rows,
            )
        )
    runs.sort(key=lambda r: r.run_at)
    return runs


def _is_full(run: _Run) -> bool:
    categories = {str(r.get("category", "")) for r in run.results}
    return len(categories) >= _MIN_FULL_CATEGORIES and len(run.results) >= _MIN_FULL_TOTAL


def _latency_ms(row: dict[str, object]) -> float | None:
    start, end = row.get("start_time"), row.get("end_time")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
    except ValueError:
        return None
    return (b - a).total_seconds() * 1000.0


def _failed_ids(run: _Run) -> set[str]:
    return {str(r.get("case_id")) for r in run.results if not r.get("passed")}


def _parse_day(stamp: str) -> str | None:
    """Compact run stamp → ``YYYY-MM-DD`` calendar day, or ``None``."""
    try:
        dt = datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None
    return dt.strftime("%Y-%m-%d")


def _build_trend(runs: list[_Run]) -> list[TrendPoint]:
    """Failed-case count per calendar day, split by severity, over recent runs.

    For each day we keep the **largest** full run that day (so a smoke run doesn't
    dilute a full evaluation), then the last ``_TREND_DAYS`` days. Each point also
    carries the day's failures broken down by triage severity.
    """
    chosen: dict[str, _Run] = {}
    failed_n: dict[str, int] = {}
    for run in runs:
        day = _parse_day(run.run_at)
        if day is None or not _is_full(run):
            continue
        failed = sum(1 for r in run.results if not r.get("passed"))
        if day not in failed_n or failed > failed_n[day]:
            failed_n[day] = failed
            chosen[day] = run
    points: list[TrendPoint] = []
    for day in sorted(chosen)[-_TREND_DAYS:]:
        sev = Counter(
            _SEVERITY.get(str(r.get("category", "")), "medium")
            for r in chosen[day].results
            if not r.get("passed")
        )
        points.append(
            TrendPoint(
                date=day,
                n=failed_n[day],
                by_severity={k: sev.get(k, 0) for k in _SEVERITY_RANK},
            )
        )
    return points


# ─────────────────────────────── public API ──────────────────────────────────


def load_failed_runs(
    reports_dir: Path | None = None,
    failures_dir: Path | None = None,
) -> FailedRunsReport:
    """Collect the real failed cases from the most recent full run per modelxlanguage.

    Args:
        reports_dir: Report archive directory; defaults to ``eval/reports``.
        failures_dir: Failure catalogue directory; defaults to ``eval/failures``.

    Returns:
        A :class:`FailedRunsReport`. An empty archive yields an empty report rather
        than raising; per-case ``status`` falls back to ``recurrent`` only when a
        comparable previous run exists, otherwise ``new``.
    """
    runs = _load_runs(reports_dir or default_reports_dir())
    catalogue = _load_catalogue(failures_dir or default_failures_dir())
    full = [r for r in runs if _is_full(r)]

    # Latest + previous full run per (model, language).
    latest: dict[tuple[str, str], _Run] = {}
    previous: dict[tuple[str, str], _Run] = {}
    for run in full:  # oldest→newest
        key = (run.model, run.language)
        if key in latest:
            previous[key] = latest[key]
        latest[key] = run

    cases: list[FailedRunCase] = []
    trend = _build_trend(runs)
    latest_version: str | None = None

    for key, run in latest.items():
        if run.version is not None:
            latest_version = run.version
        prev_failed = _failed_ids(previous[key]) if key in previous else None
        for row in run.results:
            if row.get("passed"):
                continue
            case_id = str(row.get("case_id", ""))
            category = str(row.get("category", "unknown"))
            language = str(row.get("language", run.language))
            reasons_raw = row.get("reasons", [])
            reasons = [str(x) for x in reasons_raw] if isinstance(reasons_raw, list) else []
            info = catalogue.get(case_id)
            # No comparable previous run ⇒ treat as new; else new iff it passed before.
            status = "recurrent" if prev_failed is not None and case_id in prev_failed else "new"
            cases.append(
                FailedRunCase(
                    id=case_id,
                    category=category,
                    severity=_SEVERITY.get(category, "medium"),
                    language=language,
                    title=str(row.get("title", info.title if info else "")),
                    prompt=_prompt_for(info, language),
                    expected=str(row.get("expected_behavior", info.expected if info else "")),
                    response=str(row.get("final_response", "")),
                    reasons=reasons,
                    model=run.model,
                    run_id=run.run_id,
                    run_at=run.run_at,
                    catalogue_version=run.version,
                    latency_ms=_latency_ms(row),
                    owner=_OWNER.get(category, _DEFAULT_OWNER),
                    status=status,
                )
            )

    cases.sort(
        key=lambda c: (
            _SEVERITY_RANK.get(c.severity, 9),
            0 if c.status == "new" else 1,
            c.model,
            c.id,
        )
    )

    by_category = Counter(c.category for c in cases)
    by_severity = Counter(c.severity for c in cases)
    by_model = Counter(c.model for c in cases)
    by_language = Counter(c.language for c in cases)
    latencies = [c.latency_ms for c in cases if c.latency_ms is not None]
    return FailedRunsReport(
        n=len(cases),
        cases=cases,
        by_category=dict(by_category.most_common()),
        by_severity={sev: by_severity.get(sev, 0) for sev in _SEVERITY_RANK},
        by_model=dict(by_model.most_common()),
        by_language=dict(by_language.most_common()),
        n_critical=by_severity.get("critical", 0),
        n_new=sum(1 for c in cases if c.status == "new"),
        n_recurrent=sum(1 for c in cases if c.status == "recurrent"),
        trend=trend,
        models=sorted(by_model),
        languages=sorted(by_language),
        catalogue_version=latest_version,
        mean_latency_ms=(sum(latencies) / len(latencies) if latencies else None),
    )
