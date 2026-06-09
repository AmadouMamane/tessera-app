"""AI Act disclosure UX (ADR 0010, idea #134; compliance is #76).

EU AI Act Art. 50 requires that a user be told, clearly, that they are
interacting with an AI system. That is a *UX* obligation — the disclosure has to
actually be shown, in the user's language — and therefore an observable one: a
missing or untranslated disclosure is a compliance gap, not just a copy bug.

This module owns the canonical, per-locale disclosure text and reports its
coverage: is it enabled, and is it present for every required locale (fr/de/en)?
The status is pure over the required-locale set; the endpoint surfaces it, and it
feeds the transparency obligation in the AI Act compliance posture (#76).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["DISCLOSURE_TEXT", "DisclosureReport", "disclosure_status"]

# Canonical Art. 50 disclosure, per locale. The chat UI renders the active
# locale's text; the dashboard observes that all locales are covered.
DISCLOSURE_TEXT: dict[str, str] = {
    "en": (
        "You are chatting with Tessera, an AI assistant. Responses are generated "
        "automatically and may be imperfect; for binding advice, ask to speak to a human."
    ),
    "fr": (
        "Vous discutez avec Tessera, un assistant IA. Les réponses sont générées "
        "automatiquement et peuvent être imparfaites ; pour un conseil engageant, "
        "demandez à parler à un conseiller."
    ),
    "de": (
        "Sie chatten mit Tessera, einem KI-Assistenten. Antworten werden automatisch "
        "erzeugt und können fehlerhaft sein; für verbindliche Auskünfte bitten Sie um "
        "ein Gespräch mit einem Menschen."
    ),
}

_REQUIRED = ("fr", "de", "en")


@dataclass(frozen=True, slots=True)
class DisclosureReport:
    """Coverage of the AI-interaction disclosure across locales."""

    enabled: bool
    article: str
    n_locales: int
    all_covered: bool
    missing_locales: list[str] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)


def disclosure_status(required_locales: Sequence[str] = _REQUIRED) -> DisclosureReport:
    """Report whether the AI-interaction disclosure is enabled and fully localised.

    Args:
        required_locales: Locales that must carry the disclosure.

    Returns:
        A :class:`DisclosureReport`; ``all_covered`` is ``True`` only when every
        required locale has disclosure text.
    """
    missing = [loc for loc in required_locales if not DISCLOSURE_TEXT.get(loc, "").strip()]
    return DisclosureReport(
        enabled=True,
        article="Art. 50",
        n_locales=len(DISCLOSURE_TEXT),
        all_covered=not missing,
        missing_locales=missing,
        texts=dict(DISCLOSURE_TEXT),
    )
