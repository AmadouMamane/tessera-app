"""Clickable, verifiable citations (ADR 0010, idea #132).

A regulatory answer that *cites* DORA Article 5 is only trustworthy if that
citation can be followed to the actual source. This module resolves the citations
an answer makes against the known corpus sources: each citation that matches a
real corpus document becomes a verifiable link target; each one that does not is
*dangling* — a citation the user cannot check, and a hallucination risk (it pairs
with #49, citation validity).

Matching is token-based and order-free: a citation resolves when the regulation
words and article number it names are all present in a known source id
(``DORA/art-5``). The resolver is pure over ``(citations, known_sources)``; the
endpoint extracts citations from captured answers and builds the source set from
the regulatory corpus, returning the resolvable rate and the link map.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence, Set as AbstractSet

__all__ = ["CitationLink", "CitationResolution", "resolve_citations"]

_WORD_RE = re.compile(r"[a-z]{3,}")
_NUM_RE = re.compile(r"\d+")


def _key(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """Token signature of a citation/source: (alpha words 3+, numbers)."""
    lowered = text.lower()
    return frozenset(_WORD_RE.findall(lowered)), frozenset(_NUM_RE.findall(lowered))


def _matches(
    citation: tuple[frozenset[str], frozenset[str]],
    source: tuple[frozenset[str], frozenset[str]],
) -> bool:
    """A citation matches a source when they share an article number and a word.

    Word matching is prefix-based so ``article`` matches ``art`` (the source-id
    abbreviation), and order-free so phrasing does not matter.
    """
    words_c, nums_c = citation
    words_s, nums_s = source
    if not (nums_c & nums_s):
        return False
    return any(wc.startswith(ws) or ws.startswith(wc) for wc in words_c for ws in words_s)


@dataclass(frozen=True, slots=True)
class CitationLink:
    """A citation and the source it resolved to, if any."""

    citation: str
    resolved: bool
    source: str | None


@dataclass(frozen=True, slots=True)
class CitationResolution:
    """Resolvability of an answer's citations against the corpus."""

    n_citations: int
    n_resolved: int
    resolvable_rate: float
    links: list[CitationLink] = field(default_factory=list)


def resolve_citations(
    citations: Iterable[str],
    sources: AbstractSet[str] | Sequence[str],
) -> CitationResolution:
    """Resolve citations against the known corpus source ids.

    Args:
        citations: Citation strings extracted from an answer (e.g. "DORA Article 5").
        sources: Known corpus source identifiers (e.g. ``{"DORA/art-5", ...}``).

    Returns:
        A :class:`CitationResolution`; a citation resolves when its token
        signature is a subset of some source's signature.
    """
    source_keys = [(src, _key(src)) for src in sources]

    links: list[CitationLink] = []
    n_resolved = 0
    for citation in citations:
        ckey = _key(citation)
        match: str | None = None
        if ckey[1]:  # needs at least one article number to resolve
            for src, skey in source_keys:
                if _matches(ckey, skey):
                    match = src
                    break
        if match is not None:
            n_resolved += 1
        links.append(CitationLink(citation=citation, resolved=match is not None, source=match))

    n = len(links)
    return CitationResolution(
        n_citations=n,
        n_resolved=n_resolved,
        resolvable_rate=n_resolved / n if n else 1.0,
        links=links,
    )
