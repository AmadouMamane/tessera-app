"""Guard decision explainability (ADR 0010, idea #19).

The guard's verdict is only trustworthy if you can say *why* it fired. Every
audit entry records the policy rules that triggered on a turn; this module rolls
them up across the trail into a ranked breakdown — which rules fire most, and
whether they allow, deny, or transform — so an operator can see at a glance what
the guard is actually doing and which rule is doing the heavy lifting.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.guard.ledger_store import guard_explain_scan, ledger_source, read_ledger_entries

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["GuardExplainReport", "RuleCount", "compute_guard_explain"]

_TOP_LIMIT = 10


@dataclass(frozen=True, slots=True)
class RuleCount:
    """How often one (rule, decision) pair fired."""

    rule: str
    decision: str
    count: int


@dataclass(frozen=True, slots=True)
class GuardExplainReport:
    """Ranked breakdown of which guard rules fired across the audit trail."""

    n_entries: int
    n_decisions: int
    n_denials: int
    rules: list[RuleCount] = field(default_factory=list)


def _assemble(n_entries: int, groups: list[tuple[str, str, int, int]]) -> GuardExplainReport:
    """Build the report from grouped ``(rule, kind, count, first_seen)`` rows (postgres path).

    Sorting by ``(-count, first_seen)`` reproduces ``Counter.most_common(_TOP_LIMIT)`` exactly:
    count descending, count-ties broken by first-seen (= first-insertion) order. ``first_seen`` is
    unique per group (each ``(seq, ordinality)`` belongs to one pair), so the order is total.
    """
    n_decisions = sum(count for _, _, count, _ in groups)
    n_denials = sum(count for _, kind, count, _ in groups if kind == "deny")
    top = sorted(groups, key=lambda g: (-g[2], g[3]))[:_TOP_LIMIT]
    rules = [RuleCount(rule=rule, decision=kind, count=count) for rule, kind, count, _ in top]
    return GuardExplainReport(
        n_entries=n_entries, n_decisions=n_decisions, n_denials=n_denials, rules=rules
    )


def compute_guard_explain(path: Path | None = None) -> GuardExplainReport:
    """Aggregate fired guard rules from the audit trail.

    Postgres: one bounded ``GROUP BY`` over the unnested decisions (:func:`guard_explain_scan`) —
    a few dozen rows, never the chain. File source: the flat journal has no index, so it keeps the
    Python ``Counter`` scan; both produce a byte-identical report (count desc, count-ties by
    first-seen), verified against the live ledger.
    """
    if ledger_source() == "postgres":
        return _assemble(*guard_explain_scan())

    pair_counts: Counter[tuple[str, str]] = Counter()
    n_entries = 0
    n_decisions = 0
    n_denials = 0

    for obj in read_ledger_entries(path):
        if obj.get("type") != "tessera.guard.audit":
            continue
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            continue
        n_entries += 1
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            rule = str(decision.get("policy_rule", "unknown"))
            kind = str(decision.get("decision", "unknown"))
            pair_counts[(rule, kind)] += 1
            n_decisions += 1
            if kind == "deny":
                n_denials += 1

    rules = [
        RuleCount(rule=rule, decision=kind, count=count)
        for (rule, kind), count in pair_counts.most_common(_TOP_LIMIT)
    ]
    return GuardExplainReport(
        n_entries=n_entries,
        n_decisions=n_decisions,
        n_denials=n_denials,
        rules=rules,
    )
