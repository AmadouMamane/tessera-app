"""Telemetry → product roadmap (ADR 0010, idea #124).

Observability usually stops at "here is what is wrong". This module takes the
last step: it mines the live signals — low-faithfulness turns, unhandled intents,
coverage gaps (#28), stale corpora (#50) — and synthesises a *ranked product
backlog*. Each recurring failure mode becomes a roadmap item with its evidence
count, a severity, and a concrete suggested action, so the dashboard answers
"what should we build next?" straight from production data rather than opinion.

The builder is a pure function over aggregated counts, so it is trivially
testable and the endpoint simply feeds it the numbers it already computes
elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["RoadmapItem", "RoadmapReport", "RoadmapSignals", "build_roadmap"]

# Severity thresholds on the *rate* of a failure (evidence / total turns).
_HIGH_RATE = 0.30
_MED_RATE = 0.10
# Severity thresholds on an *absolute* count (signals with no turn denominator).
_HIGH_COUNT = 2
_MED_COUNT = 1
_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True, slots=True)
class RoadmapSignals:
    """Aggregated telemetry the roadmap is mined from."""

    n_turns: int = 0
    n_low_score: int = 0
    n_unknown_intent: int = 0
    n_coverage_gaps: int = 0
    n_stale_corpora: int = 0
    languages_low: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoadmapItem:
    """One prioritised backlog item mined from telemetry."""

    theme: str
    signal: str  # machine key for the source signal
    evidence: int  # how many observations back this item
    severity: str  # "high" | "medium" | "low"
    suggestion: str


@dataclass(frozen=True, slots=True)
class RoadmapReport:
    """A ranked backlog synthesised from telemetry."""

    n_turns: int
    n_items: int
    items: list[RoadmapItem] = field(default_factory=list)


def _severity_by_rate(evidence: int, total: int) -> str:
    if total <= 0:
        return "low"
    rate = evidence / total
    if rate >= _HIGH_RATE:
        return "high"
    if rate >= _MED_RATE:
        return "medium"
    return "low"


def _severity_by_count(evidence: int) -> str:
    if evidence >= _HIGH_COUNT:
        return "high"
    if evidence >= _MED_COUNT:
        return "medium"
    return "low"


def build_roadmap(signals: RoadmapSignals) -> RoadmapReport:
    """Synthesise a ranked backlog from aggregated telemetry signals.

    Args:
        signals: The aggregated counts mined from recent telemetry.

    Returns:
        A :class:`RoadmapReport` whose items are ordered by severity then
        evidence (most pressing first). Only signals with evidence are emitted.
    """
    items: list[RoadmapItem] = []
    total = signals.n_turns

    if signals.n_low_score > 0:
        items.append(
            RoadmapItem(
                theme="Grounding quality",
                signal="low_faithfulness",
                evidence=signals.n_low_score,
                severity=_severity_by_rate(signals.n_low_score, total),
                suggestion=(
                    "Curate low-faithfulness turns into the regression set and "
                    "expand the corpus where answers drift from the grounding."
                ),
            )
        )
    if signals.n_coverage_gaps > 0:
        items.append(
            RoadmapItem(
                theme="Retrieval coverage",
                signal="coverage_gap",
                evidence=signals.n_coverage_gaps,
                severity=_severity_by_rate(signals.n_coverage_gaps, total),
                suggestion=(
                    "Author corpus content for under-covered questions where even "
                    "the best chunk is weakly related (#28)."
                ),
            )
        )
    if signals.n_unknown_intent > 0:
        items.append(
            RoadmapItem(
                theme="Intent coverage",
                signal="unknown_intent",
                evidence=signals.n_unknown_intent,
                severity=_severity_by_rate(signals.n_unknown_intent, total),
                suggestion=(
                    "Add intent patterns or a dedicated worker for the questions "
                    "the router currently cannot classify."
                ),
            )
        )
    if signals.n_stale_corpora > 0:
        items.append(
            RoadmapItem(
                theme="Corpus freshness",
                signal="stale_corpus",
                evidence=signals.n_stale_corpora,
                severity=_severity_by_count(signals.n_stale_corpora),
                suggestion="Re-ingest the regulatory corpora past their review horizon (#50).",
            )
        )
    for language, count in sorted(signals.languages_low.items(), key=lambda kv: -kv[1]):
        if count <= 0:
            continue
        items.append(
            RoadmapItem(
                theme=f"Language quality: {language}",
                signal=f"low_quality_{language}",
                evidence=count,
                severity=_severity_by_rate(count, total),
                suggestion=(
                    f"Investigate {language} answer quality — prompts, corpus "
                    f"translation, or locale formatting may be lagging."
                ),
            )
        )

    items.sort(key=lambda it: (_SEVERITY_RANK[it.severity], it.evidence), reverse=True)
    return RoadmapReport(n_turns=total, n_items=len(items), items=items)
