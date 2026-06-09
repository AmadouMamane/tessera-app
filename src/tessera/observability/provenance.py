"""Claim-level attribution / provenance (ADR 0010, idea #11).

Faithfulness as a flat score is opaque. This module makes it *structural*: it
splits an answer into claims (sentences), embeds each claim and each retrieved
chunk, and attributes every claim to its best-supporting chunk by cosine
similarity. A claim whose best support falls below a threshold is an
*unsupported* claim — a structurally-detected hallucination, with no judge
needed. The grounded fraction is the share of claims that are supported.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.retrieval.embeddings import embed

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ProvenanceClaim", "ProvenanceReport", "attribute", "split_claims"]

_DEFAULT_THRESHOLD = 0.55
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_MIN_CLAIM_CHARS = 12


@dataclass(frozen=True, slots=True)
class ProvenanceClaim:
    """One claim and how well a retrieved chunk supports it."""

    text: str
    support: float  # max cosine similarity to any chunk, 0..1
    supported: bool
    best_chunk: int  # index of the supporting chunk, or -1


@dataclass(frozen=True, slots=True)
class ProvenanceReport:
    """Per-claim attribution for an answer."""

    n_claims: int
    grounded_fraction: float
    claims: list[ProvenanceClaim]


def split_claims(answer: str) -> list[str]:
    """Split an answer into claim-sized sentences, dropping trivial fragments."""
    parts = (p.strip() for p in _SENTENCE_RE.split(answer))
    return [p for p in parts if len(p) >= _MIN_CLAIM_CHARS]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def attribute(
    answer: str,
    chunks: Sequence[str],
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> ProvenanceReport:
    """Attribute each claim in ``answer`` to its best-supporting chunk.

    Args:
        answer: The agent's answer to decompose.
        chunks: The retrieved context chunks the answer should be grounded in.
        threshold: Minimum cosine similarity for a claim to count as supported.

    Returns:
        A :class:`ProvenanceReport`. With no chunks, nothing can be supported;
        with no claims, the report is trivially grounded.
    """
    claim_texts = split_claims(answer)
    if not claim_texts:
        return ProvenanceReport(n_claims=0, grounded_fraction=1.0, claims=[])
    if not chunks:
        return ProvenanceReport(
            n_claims=len(claim_texts),
            grounded_fraction=0.0,
            claims=[
                ProvenanceClaim(text=t, support=0.0, supported=False, best_chunk=-1)
                for t in claim_texts
            ],
        )

    vectors = await embed([*claim_texts, *chunks])
    claim_vecs = vectors[: len(claim_texts)]
    chunk_vecs = vectors[len(claim_texts) :]

    claims: list[ProvenanceClaim] = []
    for text, cv in zip(claim_texts, claim_vecs, strict=True):
        sims = [_cosine(cv, kv) for kv in chunk_vecs]
        best = max(range(len(sims)), key=sims.__getitem__)
        support = sims[best]
        claims.append(
            ProvenanceClaim(
                text=text,
                support=support,
                supported=support >= threshold,
                best_chunk=best,
            )
        )

    grounded = sum(1 for c in claims if c.supported) / len(claims)
    return ProvenanceReport(n_claims=len(claims), grounded_fraction=grounded, claims=claims)
