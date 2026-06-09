"""Intent / router observability (ADR 0010, idea #63).

Tessera's language router is deterministic, but the *business intent* of a turn —
account lookup, product question, regulatory query, a simulation, or an
escalation — drives which worker should handle it. Mis-reading intent sends a
turn down the wrong path. This module classifies each question's intent with a
multilingual keyword classifier and reports the intent mix plus the share of
low-confidence/ambiguous turns, where routing is most likely to go wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["IntentReport", "aggregate_intents", "classify_intent"]

# Multilingual (fr/de/en) markers per business intent.
_MARKERS: dict[str, frozenset[str]] = {
    "account": frozenset(
        {
            "balance", "solde", "kontostand", "account", "compte", "konto",
            "transaction", "virement", "überweisung", "card", "carte", "karte",
            "iban", "statement", "relevé",
        }
    ),
    "product": frozenset(
        {
            "loan", "crédit", "credit", "kredit", "mortgage", "prêt", "hypothek",
            "rate", "taux", "zins", "savings", "épargne", "sparen", "fee", "frais",
            "gebühr", "offer", "offre",
        }
    ),
    "regulation": frozenset(
        {
            "dora", "gdpr", "rgpd", "cnil", "bafin", "regulation", "règlement",
            "verordnung", "article", "compliance", "conformité", "law", "loi", "gesetz",
        }
    ),
    "simulation": frozenset(
        {
            "simulate", "simuler", "simulieren", "estimate", "estimer", "schätzen",
            "combien", "wieviel", "mensualité", "monthly",
        }
    ),
    "escalation": frozenset(
        {
            "complaint", "réclamation", "beschwerde", "human", "conseiller", "berater",
            "agent", "urgent", "manager", "responsable",
        }
    ),
}
_LOW_CONFIDENCE = 0.5


def classify_intent(text: str) -> tuple[str, float, dict[str, int]]:
    """Classify the business intent of ``text`` via keyword counts.

    Returns the best intent, a confidence (share of marker hits), and the raw
    per-intent counts. Returns ``"unknown"`` with 0.0 confidence when no marker
    matches.
    """
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    counts = {intent: sum(1 for w in words if w in markers) for intent, markers in _MARKERS.items()}
    total = sum(counts.values())
    if total == 0:
        return ("unknown", 0.0, counts)
    best = max(counts, key=lambda intent: counts[intent])
    return (best, counts[best] / total, counts)


@dataclass(frozen=True, slots=True)
class IntentReport:
    """Intent mix and routing-confidence over several turns."""

    n: int
    distribution: dict[str, int] = field(default_factory=dict)
    unknown: int = 0
    low_confidence: int = 0
    low_confidence_rate: float = 0.0


def aggregate_intents(questions: Iterable[str]) -> IntentReport:
    """Aggregate intent classification over question texts."""
    distribution: dict[str, int] = {}
    n = 0
    unknown = 0
    low_confidence = 0
    for text in questions:
        intent, confidence, _counts = classify_intent(text)
        n += 1
        distribution[intent] = distribution.get(intent, 0) + 1
        if intent == "unknown":
            unknown += 1
            low_confidence += 1
        elif confidence < _LOW_CONFIDENCE:
            low_confidence += 1
    return IntentReport(
        n=n,
        distribution=distribution,
        unknown=unknown,
        low_confidence=low_confidence,
        low_confidence_rate=(low_confidence / n if n else 0.0),
    )
