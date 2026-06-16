"""Real evaluation data read from the failure-catalogue run reports.

The agent quality dashboards (Evaluations, and downstream Garde-fous / Synthese)
must not display invented numbers. This module loads the most recent
*comprehensive* run of the smallest local model (``llama3.2:3b``) from
``eval/reports/`` and exposes aggregates computed from the actual harness output:
overall pass rate, per-category pass rates, language coverage, escalation and
tool-invocation counts. Every figure traces back to a real model run.

If no report is present the loader raises; callers wrap the computation in a
try/except and surface ``available: False`` rather than fabricating data.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

__all__ = ["CategoryStat", "EvalSnapshot", "load_eval_snapshot"]

_REPORTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "reports"
# The brief is explicit: source quality numbers from the smallest model only.
SMALLEST_MODEL = "llama3.2:3b"

# Human-facing French labels for the failure-catalogue categories. Keys are the
# verbatim category ids emitted by the harness; values are the demo set names.
CATEGORY_LABELS: dict[str, str] = {
    "prompt_injection": "Securite - Injection de prompt",
    "pii_leak": "Confidentialite - Fuite de PII",
    "hallucination": "Factualite - Hallucinations",
    "overconfidence": "Prudence - Sur-confiance",
    "citation_fabrication": "Citations - Fabrication",
    "tool_misuse": "Outils - Mauvais usage",
    "policy_violation": "Politiques - Violations",
    "regulatory_misstatement": "Reglementaire - Erreurs",
    "language_mixing": "Multilingue - Melange de langues",
    "escalation_failure": "Escalade - Echecs",
}


@dataclass(frozen=True, slots=True)
class CategoryStat:
    """Per-category pass statistics for one catalogue run."""

    category: str
    total: int
    passed: int

    @property
    def failed(self) -> int:
        """Number of failing cases."""
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        """Fraction of cases that passed (0.0 when empty)."""
        return self.passed / self.total if self.total else 0.0

    @property
    def label(self) -> str:
        """Human-facing French label for the category."""
        return CATEGORY_LABELS.get(self.category, self.category)


@dataclass(frozen=True, slots=True)
class SessionRow:
    """One catalogue case run, presented as an agent "session"."""

    case_id: str
    language: str
    category: str
    title: str
    passed: bool
    needs_escalation: bool
    tools: tuple[str, ...]
    duration_ms: float
    input_tokens: int
    output_tokens: int
    response: str
    started_at: str

    @property
    def label(self) -> str:
        """Human-facing French label for the case category."""
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def total_tokens(self) -> int:
        """Combined input + output tokens for the turn."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class EvalSnapshot:
    """Aggregates from a single comprehensive failure-catalogue run."""

    model: str
    run_at: str
    catalogue_version: str
    total: int
    passed: int
    languages: tuple[tuple[str, int], ...]
    categories: tuple[CategoryStat, ...]
    escalations: int
    tool_invocations: int
    sessions: tuple[SessionRow, ...]

    def latencies_ms(self) -> list[float]:
        """Sorted positive per-session durations (empty if untimed)."""
        return sorted(s.duration_ms for s in self.sessions if s.duration_ms > 0)

    def latency_percentile(self, pct: float) -> float:
        """Nearest-rank percentile of session latency in ms (0.0 if untimed)."""
        values = self.latencies_ms()
        if not values:
            return 0.0
        rank = max(0, min(len(values) - 1, round(pct / 100 * (len(values) - 1))))
        return values[rank]

    def token_totals(self) -> tuple[int, int]:
        """(total input tokens, total output tokens) across sessions."""
        return (
            sum(s.input_tokens for s in self.sessions),
            sum(s.output_tokens for s in self.sessions),
        )

    @property
    def failed(self) -> int:
        """Number of failing cases across the run."""
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        """Overall fraction of cases that passed (0.0 when empty)."""
        return self.passed / self.total if self.total else 0.0

    def category(self, name: str) -> CategoryStat | None:
        """Return the stats for one category, or None if absent."""
        for stat in self.categories:
            if stat.category == name:
                return stat
        return None

    def categories_by_pass_rate(self) -> tuple[CategoryStat, ...]:
        """Categories from worst to best pass rate (ties: larger set first)."""
        return tuple(sorted(self.categories, key=lambda c: (c.pass_rate, -c.total)))

    def run_datetime(self) -> datetime | None:
        """Parse the compact run_at stamp into a datetime, or None."""
        try:
            return datetime.strptime(self.run_at, "%Y%m%dT%H%M%SZ")
        except (ValueError, TypeError):
            return None


def _score_report(payload: dict[str, object]) -> tuple[int, str]:
    """Rank a report: more results wins, then most recent run_at."""
    results = payload.get("results")
    n = len(results) if isinstance(results, list) else 0
    run_at = payload.get("run_at")
    return n, str(run_at) if isinstance(run_at, str) else ""


@lru_cache(maxsize=1)
def load_eval_snapshot() -> EvalSnapshot:
    """Return aggregates from the richest ``llama3.2:3b`` run in eval/reports.

    Raises:
        FileNotFoundError: if no usable report for the smallest model exists.
    """
    best: dict[str, object] | None = None
    best_rank: tuple[int, str] = (0, "")
    for path in _REPORTS_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("model") != SMALLEST_MODEL:
            continue
        rank = _score_report(payload)
        if rank > best_rank:
            best, best_rank = payload, rank

    if best is None or best_rank[0] == 0:
        msg = f"no usable {SMALLEST_MODEL} report under {_REPORTS_DIR}"
        raise FileNotFoundError(msg)

    raw_results = best.get("results")
    results = (
        [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []
    )
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    lang_counter: Counter[str] = Counter(str(r.get("language", "")) for r in results)
    cat_total: Counter[str] = Counter(str(r.get("category", "")) for r in results)
    cat_pass: Counter[str] = Counter(str(r.get("category", "")) for r in results if r.get("passed"))
    categories = tuple(
        CategoryStat(category=cat, total=cat_total[cat], passed=cat_pass[cat])
        for cat in CATEGORY_LABELS
        if cat_total[cat]
    )
    escalations = sum(1 for r in results if r.get("needs_escalation"))
    tool_invocations = sum(
        len(r["invoked_tools"]) for r in results if isinstance(r.get("invoked_tools"), list)
    )
    sessions = tuple(
        SessionRow(
            case_id=str(r.get("case_id", "")),
            language=str(r.get("language", "")),
            category=str(r.get("category", "")),
            title=str(r.get("title", "")),
            passed=bool(r.get("passed")),
            needs_escalation=bool(r.get("needs_escalation")),
            tools=tuple(str(t) for t in r["invoked_tools"])
            if isinstance(r.get("invoked_tools"), list)
            else (),
            duration_ms=float(r.get("duration_ms", 0) or 0),
            input_tokens=int(r.get("input_tokens", 0) or 0),
            output_tokens=int(r.get("output_tokens", 0) or 0),
            response=str(r.get("final_response", "")),
            started_at=str(r.get("started_at", "")),
        )
        for r in results
    )
    summary = best.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("passed"), int):
        passed = int(summary["passed"])
        total = int(summary.get("total", total))

    return EvalSnapshot(
        model=str(best.get("model", SMALLEST_MODEL)),
        run_at=str(best.get("run_at", "")),
        catalogue_version=str(best.get("catalogue_version", "")),
        total=total,
        passed=passed,
        languages=tuple(sorted(lang_counter.items())),
        categories=categories,
        escalations=escalations,
        tool_invocations=tool_invocations,
        sessions=sessions,
    )
