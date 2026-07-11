"""Structured failed-case catalogue for the Qualité IA cockpit (reference image 03).

The non-regression harness documents real agent failures as JSON under
``eval/failures/NN_*.json`` (each validated against ``_schema.json``). This module
reads that catalogue into rows the dashboard can table and chart: one case with
its category, a triage severity, the example prompt and the expected behaviour,
plus a category distribution for the "Répartition des échecs" donut.

This is the real, in-repo failure set — no fabrication. Severity is a documented
triage heuristic over the category (below), not a runtime score: producing a live
per-case score would require executing the eval harness (a separate concern).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "FailedCase",
    "FailedCasesReport",
    "default_failures_dir",
    "load_failed_cases",
]

# Triage severity by failure category — a documented heuristic, not a live score.
# Critical: safety/security breaches; High: incorrect or unsafe content; Medium:
# sourcing/confidence defects; Low: presentation/locale issues.
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
_LANG_FALLBACK = ("fr", "en", "de")


@dataclass(frozen=True, slots=True)
class FailedCase:
    """One documented failure case, surfaced as a dashboard row."""

    case_id: str
    title: str
    category: str
    severity: str
    language: str  # the language the example prompt is shown in
    example: str  # the user prompt that triggers the failure mode
    expected: str  # the expected (correct) behaviour
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FailedCasesReport:
    """The failure catalogue plus its category/severity distributions."""

    n: int
    cases: list[FailedCase]
    by_category: dict[str, int]
    by_severity: dict[str, int]


def default_failures_dir() -> Path:
    """Repo path of the documented-failure catalogue (``eval/failures``)."""
    return Path(__file__).resolve().parents[4] / "eval" / "failures"


def _example_for(prompts: object, language: str) -> tuple[str, str]:
    """Pick the example prompt in the preferred language, falling back sensibly.

    Returns ``(language_used, prompt_text)``; empty text when none is present.
    """
    if not isinstance(prompts, dict):
        return language, ""
    order = (language, *[lang for lang in _LANG_FALLBACK if lang != language])
    for lang in order:
        entry = prompts.get(lang)
        if isinstance(entry, dict) and entry.get("user"):
            return lang, str(entry["user"])
    return language, ""


def load_failed_cases(
    directory: Path | None = None,
    *,
    language: str = "fr",
    limit: int | None = None,
) -> FailedCasesReport:
    """Load the documented failure catalogue, sorted worst-severity first.

    Args:
        directory: Failure catalogue directory; defaults to ``eval/failures``.
        language: Preferred language for the example prompt.
        limit: Optional cap on the number of cases returned (the distributions
            still count the full catalogue).

    Returns:
        A :class:`FailedCasesReport`. An unreadable or absent directory yields an
        empty report rather than raising.
    """
    failures_dir = directory or default_failures_dir()
    cases: list[FailedCase] = []
    by_category: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()

    if failures_dir.exists():
        for path in sorted(failures_dir.glob("[0-9]*.json")):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # best-effort: skip an unreadable/corrupt failure JSON — non-gating (0015)
                continue
            category = str(obj.get("category", "unknown"))
            severity = _SEVERITY.get(category, "medium")
            lang_used, example = _example_for(obj.get("prompts"), language)
            tags_raw = obj.get("tags", [])
            tags = [str(tag) for tag in tags_raw] if isinstance(tags_raw, list) else []
            cases.append(
                FailedCase(
                    case_id=str(obj.get("id", path.stem)),
                    title=str(obj.get("title", "")),
                    category=category,
                    severity=severity,
                    language=lang_used,
                    example=example or str(obj.get("title", "")),
                    expected=str(obj.get("expected_behavior", "")),
                    tags=tags,
                )
            )
            by_category[category] += 1
            by_severity[severity] += 1

    cases.sort(key=lambda c: (_SEVERITY_RANK.get(c.severity, 9), c.category, c.case_id))
    total = len(cases)
    if limit is not None:
        cases = cases[:limit]
    return FailedCasesReport(
        n=total,
        cases=cases,
        by_category=dict(by_category.most_common()),
        by_severity={sev: by_severity.get(sev, 0) for sev in _SEVERITY_RANK},
    )
