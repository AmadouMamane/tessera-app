"""Deterministic extraction of literal entities — the anti-degradation core.

Summarising a banking exchange with an LLM silently corrupts the tokens that
matter most: ``€4 567,89`` becomes "about €4,500", ``FR76 …`` becomes "the
IBAN", ``DORA Art. 28(3)`` becomes "the DORA provisions". The fix (ADR 0007,
Tier 1) is to lift those literals *out* of the text with regular expressions —
not an LLM — before any summarisation, and carry them verbatim in an
:class:`~tessera.memory.protocol.EntityLedger`.

Extraction is intentionally regex-based and language-agnostic: the patterns
cover FR/DE/EN number, date, and citation conventions at once. It is best-effort
recall, not a parser — a missed entity degrades gracefully (it simply isn't
pinned), and a false positive is harmless (a verbatim string is re-shown).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Final

from tessera.guard.redaction import mask_pan
from tessera.memory.protocol import EntityLedger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from tessera.agent.state import ConversationMessage

__all__ = [
    "extract_entities",
    "extract_from_messages",
    "ledger_from_json",
    "ledger_to_json",
    "mask_ledger_pans",
]


# --- Amounts --------------------------------------------------------------
# A money "number" in FR (1 234,56 / 1.234,56), EN (1,234.56) or plain (1234.56).
_MONEY_NUM = (
    r"\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?"
)
# Leading currency (€/EUR before the number) or trailing currency (after it).
# A word boundary is required only for letter currencies — "€" is not a word
# character, so "€\b" would never match.
_AMOUNT_RE: Final = re.compile(
    rf"(?:(?:€|EUR|euros?)\s?(?:{_MONEY_NUM})|(?:{_MONEY_NUM})\s?(?:€|EUR\b|euros?\b|Euro\b))",
    re.IGNORECASE,
)

# --- Account references ---------------------------------------------------
# IBAN: 2 letters + 2 digits + space-grouped alphanumerics (groups of 2-4).
_IBAN_RE: Final = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{2,4}){2,}\b")
_ACCOUNT_RE: Final = re.compile(
    r"\b(?:compte|konto|account|n°|numéro|number|no\.?)\s*[:#]?\s*(\d{5,})",
    re.IGNORECASE,
)

# --- Dates ----------------------------------------------------------------
_MONTHS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|"
    "décembre|decembre|"
    "Januar|Februar|März|Maerz|April|Juni|Juli|August|September|Oktober|November|Dezember|"
    "January|February|March|May|June|July|October|December"
)
_DATE_RE: Final = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"  # ISO 2024-03-12
    r"|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"  # 12/03/2024, 12.03.2024
    rf"|\b\d{{1,2}}(?:er|\.)?\s+(?:{_MONTHS})\s+\d{{4}}\b"  # 12 mars 2024 / 12. März 2024
    rf"|\b(?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}}\b",  # March 12, 2024
    re.IGNORECASE,
)

# --- Ticket / case references --------------------------------------------
_TICKET_RE: Final = re.compile(
    r"\b(?:ticket|dossier|réf\.?|ref\.?|reference|référence|case|vorgang(?:snummer)?)\s*"
    r"[:#]?\s*([A-Z]{2,}-?\d{3,}|\d{6,})",
    re.IGNORECASE,
)

# --- Products -------------------------------------------------------------
_PRODUCT_RE: Final = re.compile(r"\bCrédit\s+Aurore(?:\s+[A-ZÉÈ][\wÉÈéè]+)?\b")

# --- Regulatory citations -------------------------------------------------
_CITATION_RE: Final = re.compile(
    r"\b(?:DORA|RGPD|GDPR|DSGVO|BaFin|CNIL|MiFID\s?II|PSD2)\b"
    r"(?:\s+(?:Art\.?|Article|Artikel|Rundschreiben)\s?\d+(?:\s?\(\d+\))?(?:/\d+)?)?",
    re.IGNORECASE,
)


def _dedup(values: Iterable[str]) -> tuple[str, ...]:
    """Return ``values`` with duplicates removed, order preserved."""
    seen: dict[str, None] = {}
    for raw in values:
        cleaned = raw.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return tuple(seen)


def extract_entities(text: str) -> EntityLedger:
    """Extract a literal :class:`EntityLedger` from one block of text."""
    if not text:
        return EntityLedger()
    return EntityLedger(
        amounts=_dedup(m.group(0) for m in _AMOUNT_RE.finditer(text)),
        account_refs=_dedup(
            [*_IBAN_RE.findall(text), *(m.group(1) for m in _ACCOUNT_RE.finditer(text))]
        ),
        dates=_dedup(m.group(0) for m in _DATE_RE.finditer(text)),
        ticket_refs=_dedup(m.group(1) for m in _TICKET_RE.finditer(text)),
        products=_dedup(m.group(0) for m in _PRODUCT_RE.finditer(text)),
        citations=_dedup(m.group(0) for m in _CITATION_RE.finditer(text)),
    )


def extract_from_messages(messages: Sequence[ConversationMessage]) -> EntityLedger:
    """Extract and merge the entity ledger across a sequence of messages."""
    ledger = EntityLedger()
    for message in messages:
        ledger = ledger.merge(extract_entities(message.content))
    return ledger


def mask_ledger_pans(ledger: EntityLedger) -> EntityLedger:
    """Return ``ledger`` with every Luhn-valid PAN value stored masked.

    The designed entity seam of the input-side PAN redaction
    (docs/design/pii-input-redaction.md, Option A seam 3): extraction runs on
    the raw text for detection fidelity, but a card number captured as an
    account/ticket reference (or grazed by any other field's pattern) is
    persisted in the output leg's masked form. IBANs pass through untouched —
    the Luhn gate and IBAN-context exclusion live in
    :func:`tessera.guard.redaction.mask_pan`, the single input-leg primitive.
    """

    def _mask_all(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(mask_pan(value).text for value in values)

    masked = EntityLedger(
        amounts=_mask_all(ledger.amounts),
        account_refs=_mask_all(ledger.account_refs),
        dates=_mask_all(ledger.dates),
        ticket_refs=_mask_all(ledger.ticket_refs),
        products=_mask_all(ledger.products),
        citations=_mask_all(ledger.citations),
    )
    return ledger if masked == ledger else masked


def ledger_to_json(ledger: EntityLedger) -> str:
    """Serialise an :class:`EntityLedger` to a JSON string for jsonb storage."""
    return json.dumps(
        {
            "amounts": list(ledger.amounts),
            "account_refs": list(ledger.account_refs),
            "dates": list(ledger.dates),
            "ticket_refs": list(ledger.ticket_refs),
            "products": list(ledger.products),
            "citations": list(ledger.citations),
        }
    )


def ledger_from_json(data: dict[str, list[str]] | None) -> EntityLedger:
    """Rebuild an :class:`EntityLedger` from a parsed jsonb mapping."""
    data = data or {}
    return EntityLedger(
        amounts=tuple(data.get("amounts", [])),
        account_refs=tuple(data.get("account_refs", [])),
        dates=tuple(data.get("dates", [])),
        ticket_refs=tuple(data.get("ticket_refs", [])),
        products=tuple(data.get("products", [])),
        citations=tuple(data.get("citations", [])),
    )
