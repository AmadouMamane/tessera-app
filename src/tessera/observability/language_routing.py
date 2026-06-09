"""Language routing / code-switch observability (ADR 0010, idea #37).

A trilingual agent can serve the wrong language or trip on code-switching. Using
a dependency-free stop-word detector, this module compares the *served* language
of a captured turn against the language *detected* from the question, and flags
mismatches (mis-routing) and mixed-language inputs (code-switching). Aggregated
over recent turns it gives a multilingual routing-health read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "RoutingAnalysis",
    "RoutingReport",
    "aggregate_routing",
    "analyze_routing",
    "detect_language",
]

# Characteristic stop-words per language — enough to disambiguate short queries.
_MARKERS: dict[str, frozenset[str]] = {
    "fr": frozenset(
        {"le", "la", "les", "est", "vous", "votre", "quel", "quelle", "compte", "je", "mon", "des"}
    ),
    "de": frozenset(
        {"der", "die", "das", "ist", "ich", "wie", "kann", "für", "mein", "ein", "und", "nach"}
    ),
    "en": frozenset(
        {"the", "is", "what", "my", "account", "how", "can", "your", "a", "of", "to", "do"}
    ),
}
_MIN_MARKERS_FOR_CODE_SWITCH = 2
_MIN_LANGS_FOR_CODE_SWITCH = 2


@dataclass(frozen=True, slots=True)
class RoutingAnalysis:
    """Routing analysis for a single turn."""

    served: str
    detected: str
    confidence: float
    mismatch: bool
    code_switch: bool


@dataclass(frozen=True, slots=True)
class RoutingReport:
    """Aggregate routing health over several turns."""

    n: int
    mismatches: int
    code_switches: int
    mismatch_rate: float
    code_switch_rate: float


def detect_language(text: str) -> tuple[str, float, dict[str, int]]:
    """Detect the language of ``text`` via stop-word counts.

    Returns the best language, a confidence (share of marker hits), and the raw
    per-language counts. Returns ``"unknown"`` when no markers match.
    """
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    counts = {lang: sum(1 for w in words if w in markers) for lang, markers in _MARKERS.items()}
    total = sum(counts.values())
    if total == 0:
        return ("unknown", 0.0, counts)
    best = max(counts, key=lambda lang: counts[lang])
    return (best, counts[best] / total, counts)


def analyze_routing(*, text: str, served_language: str) -> RoutingAnalysis:
    """Compare the served language against the detected one for one turn."""
    detected, confidence, counts = detect_language(text)
    languages_present = [
        lang for lang, count in counts.items() if count >= _MIN_MARKERS_FOR_CODE_SWITCH
    ]
    return RoutingAnalysis(
        served=served_language,
        detected=detected,
        confidence=confidence,
        mismatch=detected not in ("unknown", served_language),
        code_switch=len(languages_present) >= _MIN_LANGS_FOR_CODE_SWITCH,
    )


def aggregate_routing(turns: Iterable[tuple[str, str]]) -> RoutingReport:
    """Aggregate routing health over ``(text, served_language)`` turns."""
    n = 0
    mismatches = 0
    code_switches = 0
    for text, served in turns:
        analysis = analyze_routing(text=text, served_language=served)
        n += 1
        mismatches += int(analysis.mismatch)
        code_switches += int(analysis.code_switch)
    return RoutingReport(
        n=n,
        mismatches=mismatches,
        code_switches=code_switches,
        mismatch_rate=(mismatches / n if n else 0.0),
        code_switch_rate=(code_switches / n if n else 0.0),
    )
