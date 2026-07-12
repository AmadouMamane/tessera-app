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
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["SiemEvent", "SiemExport", "to_siem_events"]

# ECS-style numeric severity by audit decision/outcome.
_SEVERITY = {"denied": 8, "deny": 8, "transform": 5, "allowed": 2, "allow": 2}
_MAX_EVENTS = 100


@dataclass(frozen=True, slots=True)
class SiemEvent:
    """One security event in an ECS-aligned, SIEM-shippable shape.

    **``actor`` and ``subject`` are different people, and this export used to confuse them.**
    It filled ``actor`` from ``arguments["subject_id"]`` — the id of the person whose data was
    touched — under a comment that read *"related.user / the subject"*. For a ``memory.forget``,
    which this module itself classifies as ``iam`` severity 7, that shipped to the bank's SOC an
    identity event naming **the erased data subject as the author of their own erasure**.

    A SOC alert is read by someone deciding whether to open an incident. "Who did this?" is the
    first question they ask, and the answer it was being handed was the victim.
    """

    timestamp: str  # @timestamp
    category: str  # event.category — e.g. "intrusion_detection", "iam"
    action: str  # event.action — the audited target
    outcome: str  # event.outcome — success | failure
    severity: int  # event.severity — 0..10
    actor: str  # user.name — WHO performed the act (the verified principal, or system:<task>)
    subject: str  # related.user — WHOSE data it touched (the data subject); "" when not applicable
    message: str


@dataclass(frozen=True, slots=True)
class SiemExport:
    """A batch of normalised SIEM events with severity rollup."""

    n_events: int
    n_high_severity: int
    by_category: dict[str, int]
    events: list[SiemEvent] = field(default_factory=list)


#: What the SOC sees for an entry written before the audit schema carried an actor (v2 and
#: earlier). It is deliberately ugly and deliberately not a name: an event whose author was
#: never recorded must arrive labelled as unattributable, so an analyst investigates the gap
#: instead of trusting a plausible substitute. The old code substituted the data subject.
_UNATTRIBUTED: Final = "unattributed (pre-v3 audit entry)"


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
        subject = str(args.get("subject_id", "")) if isinstance(args, dict) else ""
        # WHO acted is a TOP-LEVEL field of the entry (audit entry v3 and every S1 sibling
        # event); WHOSE data it touched lives in `arguments`. Reading the second into the first
        # is what made this export name the victim. Entries written before v3 recorded no actor
        # at all, so they say so — an unattributable event must reach the SOC labelled as such,
        # never dressed in a plausible name.
        actor = str(entry.get("actor", "")) or _UNATTRIBUTED

        events.append(
            SiemEvent(
                timestamp=str(entry.get("occurred_at", "")),
                category=category,
                action=target,
                outcome="failure" if outcome == "denied" else "success",
                severity=severity,
                actor=actor,
                subject=subject,
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
