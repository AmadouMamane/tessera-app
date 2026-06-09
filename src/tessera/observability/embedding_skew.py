"""Embedding-version skew (ADR 0010, idea #64).

A pgvector store is only coherent if the corpus and the live queries were
embedded by the *same* model: vectors from ``bge-m3`` (1024-d) and
``text-multilingual-embedding-002`` (768-d) live in incompatible spaces, and
nearest-neighbour search across them returns confident nonsense. The failure is
silent — no error, just quietly worse retrieval — which is exactly the kind of
drift that follows a model swap or a profile change (on-prem ↔ frontier).

This module fingerprints the active query embedder (model + dimension) and
compares it to the fingerprint the corpus was built with. A dimension mismatch is
a hard skew (the vectors cannot even be compared); a model mismatch at equal
dimension is a soft skew (comparable numbers, drifted semantics). The corpus
fingerprint should ideally be read back from the store at ingestion time; until
that is recorded, the endpoint resolves it from the configured profile, so the
check still catches a query-side profile flip.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["EmbeddingFingerprint", "SkewReport", "detect_skew"]


@dataclass(frozen=True, slots=True)
class EmbeddingFingerprint:
    """Identity of an embedding space: which model, how many dimensions."""

    model: str
    dimension: int


@dataclass(frozen=True, slots=True)
class SkewReport:
    """Whether the query and corpus embedding spaces are compatible."""

    query_model: str
    query_dimension: int
    corpus_model: str
    corpus_dimension: int
    dimension_mismatch: bool  # hard skew — vectors are not comparable at all
    model_mismatch: bool  # soft skew — same width, drifted semantics
    skew: bool
    severity: str  # "none" | "soft" | "hard"
    reason: str


def detect_skew(query: EmbeddingFingerprint, corpus: EmbeddingFingerprint) -> SkewReport:
    """Compare the query and corpus embedding fingerprints.

    Args:
        query: Fingerprint of the live query-time embedder.
        corpus: Fingerprint the stored corpus was embedded with.

    Returns:
        A :class:`SkewReport`. A dimension mismatch is ``"hard"`` (incompatible
        spaces); a model mismatch at equal dimension is ``"soft"``.
    """
    dimension_mismatch = query.dimension != corpus.dimension
    model_mismatch = query.model != corpus.model

    if dimension_mismatch:
        severity = "hard"
        reason = (
            f"query embeds at {query.dimension}-d ({query.model}) but the corpus is "
            f"{corpus.dimension}-d ({corpus.model}) — vectors are not comparable"
        )
    elif model_mismatch:
        severity = "soft"
        reason = (
            f"same {query.dimension}-d width but different models "
            f"({query.model} vs {corpus.model}) — semantics may have drifted"
        )
    else:
        severity = "none"
        reason = f"query and corpus share the {query.model} {query.dimension}-d space"

    return SkewReport(
        query_model=query.model,
        query_dimension=query.dimension,
        corpus_model=corpus.model,
        corpus_dimension=corpus.dimension,
        dimension_mismatch=dimension_mismatch,
        model_mismatch=model_mismatch,
        skew=dimension_mismatch or model_mismatch,
        severity=severity,
        reason=reason,
    )
