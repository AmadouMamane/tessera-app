"""Schema/format conformance rate (ADR 0010, idea #47).

Tool calls are the agent's actions, and each tool argument has a shape the policy
expects (an account id matches ``^[A-Za-z0-9_-]{4,64}$``, a card's last-four is
exactly four digits, …). A malformed argument is a latent bug or an attack
probe. This module reads the audit trail, validates every observable tool
argument against its policy pattern, and reports the conformance rate.

Arguments redacted in the audit (per the PII policy) cannot be inspected and are
skipped — the metric is honest about what it can actually see.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.guard.decisions import load_policy
from tessera.observability._asof import occurred_before
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tessera.guard.decisions import Policy, ToolPolicy

__all__ = ["ConformanceReport", "check_arguments", "compute_conformance"]

_REDACTED = "[redacted]"
_EXAMPLE_LIMIT = 5


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    """Schema/format conformance of tool-call arguments over the audit trail."""

    n_calls: int
    n_fields_checked: int
    n_conformant: int
    n_violations: int
    conformance_rate: float  # conformant / checked, 0..1
    violations: list[str] = field(default_factory=list)  # "tool.field"


def check_arguments(
    arguments: Mapping[str, object], tool_policy: ToolPolicy
) -> tuple[int, int, list[str]]:
    """Validate observable arguments against the tool's patterns.

    Returns:
        ``(n_checked, n_conformant, violations)`` where ``violations`` lists the
        offending ``field`` names. Redacted or pattern-less fields are skipped.
    """
    checked = 0
    conformant = 0
    violations: list[str] = []
    for name, rule in tool_policy.arguments.items():
        if rule.pattern is None:
            continue
        value = arguments.get(name)
        if not isinstance(value, str) or value == _REDACTED:
            continue
        checked += 1
        if rule.pattern.search(value):
            conformant += 1
        else:
            violations.append(name)
    return checked, conformant, violations


def compute_conformance(
    path: Path | None = None, *, policy: Policy | None = None, at: str | None = None
) -> ConformanceReport:
    """Compute tool-argument conformance from the audit log at ``path``.

    With ``at`` set, only entries that occurred at or before instant T are
    counted — the as-of-T read for the cockpit time rail (ADR 0011).
    """
    active_policy = policy or load_policy()
    audit_path = path or get_settings().guard.audit_file
    n_calls = 0
    n_checked = 0
    n_conformant = 0
    violations: list[str] = []

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
                tool = obj.get("target")
                if obj.get("type") != "tessera.guard.audit" or tool == "user_input":
                    continue
                if not occurred_before(obj.get("occurred_at"), at):
                    continue
                arguments = obj.get("arguments")
                if not isinstance(arguments, dict) or not isinstance(tool, str):
                    continue
                n_calls += 1
                checked, conformant, field_violations = check_arguments(
                    arguments, active_policy.tool(tool)
                )
                n_checked += checked
                n_conformant += conformant
                for name in field_violations:
                    if len(violations) < _EXAMPLE_LIMIT:
                        violations.append(f"{tool}.{name}")

    return ConformanceReport(
        n_calls=n_calls,
        n_fields_checked=n_checked,
        n_conformant=n_conformant,
        n_violations=n_checked - n_conformant,
        conformance_rate=(n_conformant / n_checked if n_checked else 1.0),
        violations=violations,
    )
