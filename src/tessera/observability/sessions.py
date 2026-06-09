"""Session-level goal-completion metrics (ADR 0010, idea #21).

Turn-level scores miss the business question: did the *conversation* resolve the
user's need, and how fast? Grouping scored turns by conversation gives
session-level analytics — turns per session (a proxy for turns-to-resolution),
the share of single-turn sessions (resolved immediately), and mean quality.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["SessionReport", "aggregate_sessions"]


@dataclass(frozen=True, slots=True)
class SessionReport:
    """Session-level goal-completion analytics."""

    n_sessions: int
    total_turns: int
    mean_turns_per_session: float
    single_turn_rate: float  # share of sessions resolved in one turn
    mean_score: float


def aggregate_sessions(turns: Iterable[tuple[str | None, float]]) -> SessionReport:
    """Aggregate ``(conversation_id, score)`` turns into session metrics."""
    by_conversation: dict[str, list[float]] = defaultdict(list)
    for conversation_id, score in turns:
        by_conversation[conversation_id or "<none>"].append(score)

    n_sessions = len(by_conversation)
    sizes = [len(scores) for scores in by_conversation.values()]
    total_turns = sum(sizes)
    single = sum(1 for size in sizes if size == 1)
    all_scores = [s for scores in by_conversation.values() for s in scores]

    return SessionReport(
        n_sessions=n_sessions,
        total_turns=total_turns,
        mean_turns_per_session=(total_turns / n_sessions if n_sessions else 0.0),
        single_turn_rate=(single / n_sessions if n_sessions else 0.0),
        mean_score=(sum(all_scores) / len(all_scores) if all_scores else 0.0),
    )
