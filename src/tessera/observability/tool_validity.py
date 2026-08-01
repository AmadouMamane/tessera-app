"""Tool-call validity observability (ADR 0010, idea #29).

Agents hallucinate tools and malformed arguments. The guard already records,
for every tool invocation, whether it was allowed or denied and which policy
rule fired. This module reads that audit trail and reports how many tool calls
were valid vs blocked, and how many were specifically argument-validation
failures (a malformed IBAN, an impossible amount, …).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.guard.ledger_store import ledger_source, read_ledger_entries, tool_validity_scan
from tessera.observability._asof import occurred_before
from tessera.observability.spine.scope import Scope

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
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


def compute_tool_validity(
    path: Path | None = None,
    *,
    at: str | None = None,
    agent_id: str | None = None,
    days: float | None = None,
) -> ToolValidityReport:
    """Compute tool-call validity from the audit log at ``path``.

    With ``at`` set, only entries that occurred at or before instant T are
    counted — the as-of-T read for the cockpit time rail (ADR 0011). With
    ``agent_id`` set, only that agent's tool calls (audit entries are tagged).
    With ``days`` set, only entries inside the cockpit's selected period.

    Postgres tallies the outcomes in SQL (one row per outcome, never the chain); the flat journal
    has no index, so file mode keeps the whole-log Python fold. The two are byte-identical (verified
    on the live ledger and a synthetic boundary CTE); the only divergence is a malformed non-null
    ``occurred_at``, which ``emit_audit`` never writes and the hash chain forbids.
    """
    scope = Scope(at=at, agent_id=agent_id, period_days=days)
    since, _ = scope.window()
    if ledger_source() == "postgres":
        allowed, denied, errored, arg_failures = _scan_postgres(at, agent_id, since)
    else:
        allowed, denied, errored, arg_failures = _scan_file(path, at, agent_id, scope)

    total = allowed + denied + errored
    return ToolValidityReport(
        total=total,
        allowed=allowed,
        denied=denied,
        errored=errored,
        arg_failures=arg_failures,
        validity_rate=(allowed / total if total else 1.0),
    )


def _scan_postgres(
    at: str | None, agent_id: str | None, since: datetime | None = None
) -> tuple[int, int, int, int]:
    """Outcome tallies rolled up in bounded SQL (one row per outcome).

    ``arg_failures`` is the ``denied`` group's arg-failure filter count — a denied subset, exactly
    as the Python ``elif``; every other outcome's filter count is ignored.
    """
    allowed = denied = errored = arg_failures = 0
    for outcome, count, arg_fail in tool_validity_scan(at, agent_id, since):
        if outcome == "allowed":
            allowed = count
        elif outcome == "denied":
            denied = count
            arg_failures = arg_fail
        elif outcome == "error":
            errored = count
    return allowed, denied, errored, arg_failures


def _scan_file(
    path: Path | None, at: str | None, agent_id: str | None, scope: Scope | None = None
) -> tuple[int, int, int, int]:
    """Whole-log Python fold over the flat journal — no index to push the tally down to."""
    allowed = denied = errored = arg_failures = 0
    windowed = scope is not None and scope.period_days is not None
    for obj in read_ledger_entries(path):
        if obj.get("type") != "tessera.guard.audit" or obj.get("target") == "user_input":
            continue
        if not occurred_before(obj.get("occurred_at"), at):
            continue
        if windowed and scope is not None and not scope.within(obj.get("occurred_at")):
            continue
        if agent_id is not None and obj.get("agent_id") != agent_id:
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
    return allowed, denied, errored, arg_failures
