"""Guard decision explainability (ADR 0010, idea #19).

The guard's verdict is only trustworthy if you can say *why* it fired. Every
audit entry records the policy rules that triggered on a turn; this module rolls
them up across the trail into a ranked breakdown — which rules fire most, and
whether they allow, deny, or transform — so an operator can see at a glance what
the guard is actually doing and which rule is doing the heavy lifting.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.settings import get_settings

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


def compute_guard_explain(path: Path | None = None) -> GuardExplainReport:
    """Aggregate fired guard rules from the audit log at ``path``."""
    audit_path = path or get_settings().guard.audit_file
    pair_counts: Counter[tuple[str, str]] = Counter()
    n_entries = 0
    n_decisions = 0
    n_denials = 0

    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
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
