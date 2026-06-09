"""Regulatory citation validity (ADR 0010, idea #49).

The most damaging hallucination for a compliance agent is a *confident, specific,
wrong* citation — "DORA Article 28(3) requires …" when Article 28(3) says no such
thing, or does not exist (documented failure #05). The falsifiable part of a
regulatory citation is its article number, so this module extracts every article
reference from an answer and checks that the same article is actually present in
the grounding context. An article cited in the answer but absent from the
retrieved regulation is a fabricated citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CitationReport", "CitationSummary", "aggregate_citations", "analyze_citations"]

# "Article 28", "Art. 28(3)", "art 5" → captures the article number.
_ARTICLE = re.compile(r"\bart(?:icle|\.)?\s*(\d+)", re.IGNORECASE)
_EXAMPLE_LIMIT = 5


def _article_numbers(text: str) -> list[str]:
    return _ARTICLE.findall(text)


@dataclass(frozen=True, slots=True)
class CitationReport:
    """Citation validity for a single answer."""

    n_citations: int
    n_supported: int
    n_unsupported: int
    validity_rate: float  # supported / total, 0..1
    unsupported: list[str] = field(default_factory=list)  # article numbers


@dataclass(frozen=True, slots=True)
class CitationSummary:
    """Aggregate regulatory-citation validity over several turns."""

    n_turns: int
    n_citations: int
    n_unsupported: int
    validity_rate: float
    unsupported_examples: list[str] = field(default_factory=list)


def analyze_citations(*, answer: str, context: str) -> CitationReport:
    """Check that every article cited in ``answer`` appears in ``context``.

    Args:
        answer: The agent's response.
        context: The grounding regulation text.

    Returns:
        A :class:`CitationReport`; unsupported article numbers are fabricated.
    """
    cited = _article_numbers(answer)
    grounded = set(_article_numbers(context))
    unsupported = [num for num in cited if num not in grounded]
    n_citations = len(cited)
    n_supported = n_citations - len(unsupported)
    return CitationReport(
        n_citations=n_citations,
        n_supported=n_supported,
        n_unsupported=len(unsupported),
        validity_rate=(n_supported / n_citations if n_citations else 1.0),
        unsupported=[f"Art. {num}" for num in unsupported],
    )


def aggregate_citations(turns: Iterable[tuple[str, str]]) -> CitationSummary:
    """Aggregate citation validity over ``(answer, context)`` turns."""
    n_turns = 0
    n_citations = 0
    n_unsupported = 0
    examples: list[str] = []
    for answer, context in turns:
        report = analyze_citations(answer=answer, context=context)
        n_turns += 1
        n_citations += report.n_citations
        n_unsupported += report.n_unsupported
        for art in report.unsupported:
            if len(examples) < _EXAMPLE_LIMIT:
                examples.append(art)
    n_supported = n_citations - n_unsupported
    return CitationSummary(
        n_turns=n_turns,
        n_citations=n_citations,
        n_unsupported=n_unsupported,
        validity_rate=(n_supported / n_citations if n_citations else 1.0),
        unsupported_examples=examples,
    )
