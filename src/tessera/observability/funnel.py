"""Conversation funnel per language (ADR 0010, idea #66).

Aggregate quality hides per-language reality: the German path may resolve in one
turn while the French path drags or scores worse. This module breaks the scored
turns down by language into a small funnel — volume, distinct sessions, mean
quality, the share of one-shot resolutions, and the share of low-quality turns —
so a regression or a weak locale is visible per FR/DE/EN, not just in aggregate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["FunnelReport", "LanguageFunnel", "aggregate_funnel"]

_LOW_SCORE = 0.5


@dataclass(frozen=True, slots=True)
class LanguageFunnel:
    """Funnel metrics for a single language."""

    language: str
    n_turns: int
    n_sessions: int
    mean_score: float
    single_turn_rate: float  # sessions resolved in one turn
    low_score_rate: float  # turns scoring below the low-quality threshold


@dataclass(frozen=True, slots=True)
class FunnelReport:
    """Per-language conversation funnel."""

    n_turns: int
    languages: list[LanguageFunnel] = field(default_factory=list)


def aggregate_funnel(turns: Iterable[tuple[str, str | None, float]]) -> FunnelReport:
    """Aggregate ``(language, conversation_id, score)`` turns into per-language funnels."""
    scores_by_lang: dict[str, list[float]] = defaultdict(list)
    sessions_by_lang: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total = 0
    for language, conversation_id, score in turns:
        total += 1
        scores_by_lang[language].append(score)
        sessions_by_lang[language][conversation_id or "<none>"] += 1

    languages: list[LanguageFunnel] = []
    for language in sorted(scores_by_lang):
        scores = scores_by_lang[language]
        sessions = sessions_by_lang[language]
        n_sessions = len(sessions)
        single = sum(1 for size in sessions.values() if size == 1)
        low = sum(1 for s in scores if s < _LOW_SCORE)
        languages.append(
            LanguageFunnel(
                language=language,
                n_turns=len(scores),
                n_sessions=n_sessions,
                mean_score=sum(scores) / len(scores) if scores else 0.0,
                single_turn_rate=(single / n_sessions if n_sessions else 0.0),
                low_score_rate=(low / len(scores) if scores else 0.0),
            )
        )

    return FunnelReport(n_turns=total, languages=languages)
