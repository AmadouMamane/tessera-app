"""Cross-session customer journey (ADR 0010, idea #99; memory is ADR 0007).

Long-term memory only earns its name if it ties a customer's *separate* visits
together. This module reconstructs that journey from the memory audit trail:
every ``memory.*`` action carries the subject (the customer identity key), so
grouping by subject and clustering the actions by time gap recovers distinct
sessions — and surfaces the *returning* customers whose memory spans more than
one visit.

Sessions are inferred by a time-gap heuristic (actions more than
``session_gap_minutes`` apart start a new session) rather than an explicit
session id, so it works whether the identity is the real customer key or the
per-conversation proxy Tessera uses until authentication lands (ADR 0007,
"Identity"). The aggregation is pure over ``(subject, action, timestamp)``
events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["Journey", "JourneyReport", "build_journeys"]

_DEFAULT_GAP_MINUTES = 30
_SUBJECT_PREVIEW = 12


@dataclass(frozen=True, slots=True)
class Journey:
    """One subject's activity across inferred sessions."""

    subject: str
    n_sessions: int
    n_actions: int
    n_writes: int
    n_reads: int
    first_seen: str
    last_seen: str
    span_days: float
    returning: bool  # spans more than one session


@dataclass(frozen=True, slots=True)
class JourneyReport:
    """Cross-session journeys mined from the memory audit trail."""

    n_subjects: int
    n_returning: int
    n_events: int
    subjects: list[Journey] = field(default_factory=list)


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def build_journeys(
    events: Iterable[tuple[str, str, str]],
    *,
    session_gap_minutes: int = _DEFAULT_GAP_MINUTES,
) -> JourneyReport:
    """Reconstruct per-subject journeys from memory audit events.

    Args:
        events: ``(subject, action, occurred_at_iso)`` triples, where ``action``
            is a ``memory.*`` target and ``occurred_at_iso`` is ISO-8601.
        session_gap_minutes: Actions farther apart than this start a new session.

    Returns:
        A :class:`JourneyReport`, subjects ordered by session count then activity.
    """
    by_subject: dict[str, list[tuple[datetime, str]]] = {}
    n_events = 0
    for subject, action, ts in events:
        parsed = _parse(ts)
        if parsed is None:
            continue
        by_subject.setdefault(subject, []).append((parsed, action))
        n_events += 1

    gap = session_gap_minutes * 60.0
    journeys: list[Journey] = []
    for subject, actions in by_subject.items():
        actions.sort(key=lambda pair: pair[0])
        times = [t for t, _ in actions]
        n_sessions = 1
        for prev, curr in pairwise(times):
            if (curr - prev).total_seconds() > gap:
                n_sessions += 1
        n_writes = sum(1 for _, a in actions if a == "memory.write")
        n_reads = sum(1 for _, a in actions if a == "memory.read")
        span_days = (times[-1] - times[0]).total_seconds() / 86_400.0
        journeys.append(
            Journey(
                subject=subject[:_SUBJECT_PREVIEW],
                n_sessions=n_sessions,
                n_actions=len(actions),
                n_writes=n_writes,
                n_reads=n_reads,
                first_seen=times[0].isoformat(),
                last_seen=times[-1].isoformat(),
                span_days=span_days,
                returning=n_sessions > 1,
            )
        )

    journeys.sort(key=lambda j: (j.n_sessions, j.n_actions), reverse=True)
    return JourneyReport(
        n_subjects=len(journeys),
        n_returning=sum(1 for j in journeys if j.returning),
        n_events=n_events,
        subjects=journeys,
    )
