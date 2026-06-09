"""Anomalous-conversation detection (ADR 0010, idea #69).

Most sessions are short and varied. The interesting ones are the outliers: a
conversation that runs unusually long, one where the user (or a looping agent)
asks the *same thing* over and over, or one with little variety across turns —
all of which can signal a stuck agent, a frustrated user, or an automated abuse
loop burning tokens. This extends the session metrics (#21) with an unsupervised,
dependency-free screen built on turn counts and textual repetition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["AnomalyReport", "SessionAnomaly", "detect_anomalies"]

_LONG_TURNS = 6  # sessions at/above this many turns are "long"
_REPEAT_SIMILARITY = 0.85  # consecutive questions this alike are "repeats"
_LOOP_DISTINCT_RATIO = 0.5  # distinct/total below this (with ≥3 turns) is "looping"
_MIN_LOOP_TURNS = 3


@dataclass(frozen=True, slots=True)
class SessionAnomaly:
    """Anomaly screen for one conversation."""

    conversation_id: str
    n_turns: int
    repeated_pairs: int
    distinct_ratio: float
    anomalous: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AnomalyReport:
    """Anomalous-conversation screen over several sessions."""

    n_sessions: int
    n_anomalous: int
    sessions: list[SessionAnomaly] = field(default_factory=list)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _analyze_session(conversation_id: str, questions: Sequence[str]) -> SessionAnomaly:
    n_turns = len(questions)
    normalized = [_normalize(q) for q in questions]
    repeated_pairs = sum(
        1
        for i in range(1, n_turns)
        if SequenceMatcher(None, normalized[i - 1], normalized[i]).ratio() >= _REPEAT_SIMILARITY
    )
    distinct_ratio = len(set(normalized)) / n_turns if n_turns else 1.0

    reasons: list[str] = []
    if n_turns >= _LONG_TURNS:
        reasons.append("long")
    if repeated_pairs > 0:
        reasons.append("repetitive")
    if n_turns >= _MIN_LOOP_TURNS and distinct_ratio < _LOOP_DISTINCT_RATIO:
        reasons.append("looping")

    return SessionAnomaly(
        conversation_id=conversation_id,
        n_turns=n_turns,
        repeated_pairs=repeated_pairs,
        distinct_ratio=distinct_ratio,
        anomalous=bool(reasons),
        reasons=reasons,
    )


def detect_anomalies(sessions: Mapping[str, Sequence[str]]) -> AnomalyReport:
    """Screen each conversation's questions for anomalies.

    Args:
        sessions: Mapping of conversation id to its ordered question texts.

    Returns:
        An :class:`AnomalyReport` with a per-session verdict.
    """
    results = [_analyze_session(cid, questions) for cid, questions in sessions.items()]
    return AnomalyReport(
        n_sessions=len(results),
        n_anomalous=sum(1 for r in results if r.anomalous),
        sessions=results,
    )
