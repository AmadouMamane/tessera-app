"""Locale-aware formatting correctness (ADR 0010, idea #51).

A trilingual banking agent must render money the way each locale expects:
``4 567,89 €`` in French, ``4.567,89 €`` in German, ``€4,567.89`` in English.
Getting the thousands/decimal separators wrong is a small but corrosive
correctness bug — it reads as machine-translated and, for an amount, can be
genuinely ambiguous.

To stay unambiguous and date-safe, this module classifies only *grouped* amounts
(numbers carrying a thousands separator): the grouping/decimal pair is a clean
locale fingerprint there, where a bare ``09.06`` could be a German date. It flags
any grouped amount whose style belongs to a different locale than the turn's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["LocaleFormatReport", "LocaleFormatSummary", "aggregate_formatting", "classify_number"]

# Grouped amounts only: at least one 3-digit group, optional 1-2 digit decimal.
# Lookarounds anchor the whole number so a date like ``09.06.2026`` (whose year
# is 4 digits) cannot spawn a spurious 3-digit group.
_AMOUNT = re.compile(r"(?<![\d.,])\d{1,3}(?:[ .,]\d{3})+(?:[.,]\d{1,2})?(?![\d.,])")
_EXAMPLE_LIMIT = 5


def classify_number(token: str) -> str:
    """Classify a grouped-amount token as ``fr``/``de``/``en`` or ``ambiguous``.

    - ``de``: dot grouping, comma decimal — ``1.234,56``
    - ``en``: comma grouping, dot decimal — ``1,234.56``
    - ``fr``: space grouping, comma decimal — ``1 234,56``
    """
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", token):
        return "de"
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", token):
        return "en"
    if re.fullmatch(r"\d{1,3}(?: \d{3})+(?:,\d{1,2})?", token):
        return "fr"
    return "ambiguous"


@dataclass(frozen=True, slots=True)
class LocaleFormatReport:
    """Formatting correctness for a single answer in one locale."""

    locale: str
    n_amounts: int
    n_violations: int
    violations: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LocaleFormatSummary:
    """Aggregate locale-formatting correctness over several turns."""

    n_turns: int
    n_amounts: int
    n_violations: int
    correctness_rate: float
    examples: list[str] = field(default_factory=list)


def analyze_formatting(*, answer: str, locale: str) -> LocaleFormatReport:
    """Flag grouped amounts in ``answer`` whose style does not match ``locale``."""
    violations: list[str] = []
    amounts = _AMOUNT.findall(answer)
    for token in amounts:
        style = classify_number(token)
        if style not in ("ambiguous", locale):
            violations.append(token)
    return LocaleFormatReport(
        locale=locale,
        n_amounts=len(amounts),
        n_violations=len(violations),
        violations=violations,
    )


def aggregate_formatting(turns: Iterable[tuple[str, str]]) -> LocaleFormatSummary:
    """Aggregate over ``(answer, locale)`` turns."""
    n_turns = 0
    n_amounts = 0
    n_violations = 0
    examples: list[str] = []
    for answer, locale in turns:
        report = analyze_formatting(answer=answer, locale=locale)
        n_turns += 1
        n_amounts += report.n_amounts
        n_violations += report.n_violations
        for token in report.violations:
            if len(examples) < _EXAMPLE_LIMIT:
                examples.append(f"{token} ({locale})")
    correct = n_amounts - n_violations
    return LocaleFormatSummary(
        n_turns=n_turns,
        n_amounts=n_amounts,
        n_violations=n_violations,
        correctness_rate=(correct / n_amounts if n_amounts else 1.0),
        examples=examples,
    )
