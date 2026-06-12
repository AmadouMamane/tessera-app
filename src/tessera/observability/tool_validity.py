"""Tool-call validity observability (ADR 0010, idea #29).

Agents hallucinate tools and malformed arguments. The guard already records,
for every tool invocation, whether it was allowed or denied and which policy
rule fired. This module reads that audit trail and reports how many tool calls
were valid vs blocked, and how many were specifically argument-validation
failures (a malformed IBAN, an impossible amount, …).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability._asof import occurred_before
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

__all__ = ["ToolValidityReport", "compute_tool_validity"]


@dataclass(frozen=True, slots=True)
class ToolValidityReport:
    """Validity of tool calls over the audit trail."""

    total: int
    allowed: int
    denied: int
    errored: int
    arg_failures: int
    validity_rate: float  # allowed / total, 0..1


def _has_arg_failure(decisions: Iterable[dict[str, object]]) -> bool:
    return any(".argument." in str(d.get("policy_rule", "")) for d in decisions)


def compute_tool_validity(path: Path | None = None, *, at: str | None = None) -> ToolValidityReport:
    """Compute tool-call validity from the audit log at ``path``.

    With ``at`` set, only entries that occurred at or before instant T are
    counted — the as-of-T read for the cockpit time rail (ADR 0011).
    """
    target = path or get_settings().guard.audit_file
    allowed = denied = errored = arg_failures = 0
    if target.exists():
        with target.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "tessera.guard.audit" or obj.get("target") == "user_input":
                    continue
                if not occurred_before(obj.get("occurred_at"), at):
                    continue
                outcome = obj.get("outcome")
                if outcome == "allowed":
                    allowed += 1
                elif outcome == "denied":
                    denied += 1
                    if _has_arg_failure(obj.get("decisions", [])):
                        arg_failures += 1
                elif outcome == "error":
                    errored += 1

    total = allowed + denied + errored
    return ToolValidityReport(
        total=total,
        allowed=allowed,
        denied=denied,
        errored=errored,
        arg_failures=arg_failures,
        validity_rate=(allowed / total if total else 1.0),
    )
