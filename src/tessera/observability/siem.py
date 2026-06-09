"""SIEM integration — security signals for the bank's SOC (ADR 0010, idea #172).

A bank's Security Operations Centre runs on a SIEM (Splunk / Sentinel /
Chronicle), and an AI agent is just another monitored system to it. This module
normalises the agent's security-relevant audit events into a SIEM-friendly,
ECS-aligned shape (``event.category`` / ``event.action`` / ``event.outcome`` /
``event.severity``) so they can be shipped to the SOC and correlated with the
rest of the bank's estate — a guard denial, a blocked poisoned memory, an erasure
are all events the SOC should see.

The mapping is pure over audit-entry dicts; the endpoint feeds it the guard audit
trail and returns the most recent normalised events for forwarding/preview.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["SiemEvent", "SiemExport", "to_siem_events"]

# ECS-style numeric severity by audit decision/outcome.
_SEVERITY = {"denied": 8, "deny": 8, "transform": 5, "allowed": 2, "allow": 2}
_MAX_EVENTS = 100


@dataclass(frozen=True, slots=True)
class SiemEvent:
    """One security event in an ECS-aligned, SIEM-shippable shape."""

    timestamp: str  # @timestamp
    category: str  # event.category — e.g. "intrusion_detection", "iam"
    action: str  # event.action — the audited target
    outcome: str  # event.outcome — success | failure
    severity: int  # event.severity — 0..10
    actor: str  # related.user / the subject
    message: str


@dataclass(frozen=True, slots=True)
class SiemExport:
    """A batch of normalised SIEM events with severity rollup."""

    n_events: int
    n_high_severity: int
    by_category: dict[str, int]
    events: list[SiemEvent] = field(default_factory=list)


def _category(target: str) -> str:
    if target.startswith("memory."):
        return "iam" if target == "memory.forget" else "data_protection"
    return "intrusion_detection"


def to_siem_events(entries: Iterable[dict[str, object]]) -> SiemExport:
    """Normalise audit entries into SIEM/ECS security events.

    Args:
        entries: Parsed guard-audit objects (``type == 'tessera.guard.audit'``).

    Returns:
        A :class:`SiemExport`; only security-relevant entries (a deny/transform
        decision, or any memory governance action) are emitted.
    """
    events: list[SiemEvent] = []
    by_category: dict[str, int] = {}
    n_high = 0

    for entry in entries:
        target = entry.get("target")
        if not isinstance(target, str):
            continue
        outcome = str(entry.get("outcome", "allowed"))
        decisions = entry.get("decisions")
        decision = "allow"
        rationale = ""
        if isinstance(decisions, list) and decisions and isinstance(decisions[0], dict):
            decision = str(decisions[0].get("decision", "allow"))
            rationale = str(decisions[0].get("rationale", ""))

        is_memory = target.startswith("memory.")
        # Only forward security-relevant events: a block/transform, or any
        # memory governance action (writes/reads/erasure are all SOC-relevant).
        if not is_memory and decision == "allow" and outcome != "denied":
            continue

        severity = _SEVERITY.get(outcome, _SEVERITY.get(decision, 2))
        if severity >= 7:  # noqa: PLR2004 — ECS high-severity floor
            n_high += 1
        category = _category(target)
        by_category[category] = by_category.get(category, 0) + 1

        args = entry.get("arguments")
        actor = ""
        if isinstance(args, dict):
            actor = str(args.get("subject_id", ""))

        events.append(
            SiemEvent(
                timestamp=str(entry.get("occurred_at", "")),
                category=category,
                action=target,
                outcome="failure" if outcome == "denied" else "success",
                severity=severity,
                actor=actor,
                message=rationale or f"{target} {decision}",
            )
        )

    events = events[-_MAX_EVENTS:]
    return SiemExport(
        n_events=len(events),
        n_high_severity=n_high,
        by_category=by_category,
        events=events,
    )
