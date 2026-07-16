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

from tessera.observability.eval.report_paths import iter_report_files, reports_write_dir

__all__ = [
    "CategoryStat",
    "EvalSnapshot",
    "RunHistoryEntry",
    "load_agent_or_global_snapshot",
    "load_agent_run_history",
    "load_eval_snapshot",
]
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
    # The grader's diagnostic for THIS case (report ``reasons``): why it failed
    # (or, for a pass, which criterion it cleared). Empty when the run predates the
    # field. Surfaced verbatim on the Errors view so a failure explains itself.
    reasons: tuple[str, ...] = ()

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
    # Per-agent provenance (empty/None for the global catalogue snapshot).
    agent_id: str = ""
    eval_set: str = ""
    gate_passed: bool | None = None
    gate_failed_critical: tuple[str, ...] = ()
    # The non-critical counts: a measurement, never compared to a bar (ADR 0021 removed
    # `gate.min_pass_rate` — a historical report may still carry the key; it is not read).
    gate_standard_passed: int = 0
    gate_standard_total: int = 0

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


@dataclass(frozen=True, slots=True)
class RunHistoryEntry:
    """One per-agent run, for the ER-01 rail (run history) on the Evaluations page.

    Every field is read from the run's own report — stored provenance, never derived:
    the eval-gate policy (§ provenance) requires each run to carry its date AND its
    catalogue version, and a gate verdict is only ever the one recorded at run time
    (``None`` = not recorded, which the rail must say rather than invent). An empty
    ``catalogue_version`` means the report did not record one.
    """

    run_at: str
    total: int
    passed: int
    gate_passed: bool | None
    eval_set: str
    catalogue_version: str
    model: str

    @property
    def pass_rate(self) -> float:
        """Overall pass rate of this run (0.0 when empty)."""
        return self.passed / self.total if self.total else 0.0

    def run_datetime(self) -> datetime | None:
        """Parse the compact run_at stamp, or None."""
        try:
            return datetime.strptime(self.run_at, "%Y%m%dT%H%M%SZ")
        except (ValueError, TypeError):
            return None


def load_agent_run_history(agent_id: str, limit: int = 24) -> tuple[RunHistoryEntry, ...]:
    """Return an agent's runs (newest first), deduped by run_at — the ER-01 rail.

    Reconstructs which run/scores were current over time by reading every
    per-agent report (archives + the per-agent latest) under ``eval/reports``.
    """
    by_run: dict[str, RunHistoryEntry] = {}
    for path in iter_report_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # best-effort: skip an unreadable/corrupt eval-report JSON — non-gating (0015)
            continue
        if not isinstance(payload, dict) or payload.get("agent_id") != agent_id:
            continue
        if payload.get("model") != SMALLEST_MODEL:
            continue
        summary = payload.get("summary")
        summary = summary if isinstance(summary, dict) else {}
        run_at = str(payload.get("run_at", ""))
        gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
        gate = gate if isinstance(gate, dict) else {}
        gate_passed = gate.get("passed")
        entry = RunHistoryEntry(
            run_at=run_at,
            total=int(summary.get("total", 0) or 0),
            passed=int(summary.get("passed", 0) or 0),
            gate_passed=bool(gate_passed) if isinstance(gate_passed, bool) else None,
            eval_set=str(payload.get("eval_set") or ""),
            catalogue_version=str(payload.get("catalogue_version") or ""),
            model=str(payload.get("model") or ""),
        )
        # Dedup by run_at; keep the richest copy (latest mirrors an archive).
        existing = by_run.get(run_at)
        if existing is None or entry.total > existing.total:
            by_run[run_at] = entry
    history = sorted(by_run.values(), key=lambda e: e.run_at, reverse=True)
    return tuple(history[:limit])


def load_agent_or_global_snapshot(agent_id: str | None) -> EvalSnapshot:
    """Prefer an agent's own run; fall back to the global catalogue snapshot.

    Lets agent pages show the agent's OWN quality when a per-agent run exists, and
    degrade gracefully (rather than 500) to the cross-agent snapshot when it does
    not yet — without ever fabricating numbers.
    """
    if agent_id:
        try:
            return load_eval_snapshot(agent_id)
        except FileNotFoundError:
            # best-effort: no per-agent run — fall back to the global snapshot (0015)
            pass
    return load_eval_snapshot(None)


def _score_report(payload: dict[str, object]) -> tuple[int, str]:
    """Rank a report: more results wins, then most recent run_at."""
    results = payload.get("results")
    n = len(results) if isinstance(results, list) else 0
    run_at = payload.get("run_at")
    return n, str(run_at) if isinstance(run_at, str) else ""


@lru_cache(maxsize=8)
def load_eval_snapshot(agent_id: str | None = None) -> EvalSnapshot:
    """Return aggregates from the richest ``llama3.2:3b`` run in eval/reports.

    Args:
        agent_id: when set, select the richest run whose ``agent_id`` matches
            (each agent reads its OWN run over its OWN set, so quality genuinely
            differs per agent). When ``None``, select the richest *catalogue* run
            (a report with no ``agent_id``) — the global, cross-agent snapshot.

    Raises:
        FileNotFoundError: if no usable report for the smallest model exists.
    """
    best: dict[str, object] | None = None
    best_rank: tuple[int, str] = (0, "")
    for path in iter_report_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # best-effort: skip an unreadable/corrupt eval-report JSON — non-gating (0015)
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("model") != SMALLEST_MODEL:
            continue
        report_agent = payload.get("agent_id")
        if agent_id is None:
            if report_agent:  # keep the global snapshot a pure catalogue run
                continue
        elif report_agent != agent_id:
            continue
        rank = _score_report(payload)
        if rank > best_rank:
            best, best_rank = payload, rank

    if best is None or best_rank[0] == 0:
        scope = f"agent {agent_id!r}" if agent_id else "catalogue"
        msg = f"no usable {SMALLEST_MODEL} {scope} report under {reports_write_dir()}"
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
            reasons=tuple(str(x) for x in r["reasons"])
            if isinstance(r.get("reasons"), list)
            else (),
        )
        for r in results
    )
    summary = best.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("passed"), int):
        passed = int(summary["passed"])
        total = int(summary.get("total", total))

    gate = best.get("gate") if isinstance(best.get("gate"), dict) else {}
    gate = gate if isinstance(gate, dict) else {}
    failed_critical = gate.get("failed_critical")
    gate_passed = gate.get("passed")

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
        agent_id=str(best.get("agent_id") or ""),
        eval_set=str(best.get("eval_set") or ""),
        gate_passed=bool(gate_passed) if isinstance(gate_passed, bool) else None,
        gate_failed_critical=tuple(str(c) for c in failed_critical)
        if isinstance(failed_critical, list)
        else (),
        gate_standard_passed=int(gate.get("standard_passed", 0) or 0),
        gate_standard_total=int(gate.get("standard_total", 0) or 0),
    )
