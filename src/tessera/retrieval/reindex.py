"""Evidence-first repair of legacy corpus embeddings with missing provenance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.retrieval import embeddings
from tessera.retrieval.store import (
    ReembeddedChunk,
    UnfingerprintedChunk,
    corpus_fingerprints,
    load_unfingerprinted_chunks,
    replace_unfingerprinted_embeddings,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_MAX_REPAIR_BATCH = 128


class ReindexPreconditionError(RuntimeError):
    """The live repair target differs from the operator-reviewed dry-run plan."""


@dataclass(frozen=True, slots=True)
class EmbeddingReindexPlan:
    """Stable identity of the exact legacy rows a repair would replace."""

    rows: int
    digest: str
    corpora: dict[str, int]
    model: str
    dimension: int


@dataclass(frozen=True, slots=True)
class EmbeddingReindexResult:
    """Post-commit evidence returned by a successful repair."""

    planned_rows: int
    updated_rows: int
    digest: str
    model: str
    dimension: int
    remaining_unfingerprinted_rows: int


def build_reindex_plan(
    chunks: Sequence[UnfingerprintedChunk], *, model: str, dimension: int
) -> EmbeddingReindexPlan:
    """Build a stable content-bound plan without computing or writing an embedding."""
    ordered = sorted(chunks, key=lambda row: (row.corpus, row.source, row.chunk_id))
    keys = [(row.corpus, row.source, row.chunk_id) for row in ordered]
    if len(keys) != len(set(keys)):
        msg = "unfingerprinted corpus contains duplicate chunk keys"
        raise ReindexPreconditionError(msg)
    digest = hashlib.sha256()
    digest.update(
        json.dumps([model, dimension], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    digest.update(b"\n")
    corpora: dict[str, int] = {}
    for row in ordered:
        digest.update(
            json.dumps(
                [row.corpus, row.source, row.chunk_id, row.text],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
        corpora[row.corpus] = corpora.get(row.corpus, 0) + 1
    return EmbeddingReindexPlan(
        rows=len(ordered),
        digest=digest.hexdigest(),
        corpora=dict(sorted(corpora.items())),
        model=model,
        dimension=dimension,
    )


async def inspect_embedding_reindex() -> EmbeddingReindexPlan:
    """Read the live legacy target and return its dry-run plan without model calls or writes."""
    chunks = await load_unfingerprinted_chunks()
    return build_reindex_plan(
        chunks,
        model=embeddings.embedding_model_name(),
        dimension=embeddings.embedding_dimension(),
    )


async def repair_unfingerprinted_embeddings(
    *,
    expected_rows: int,
    expected_digest: str,
    batch_size: int = 32,
) -> EmbeddingReindexResult:
    """Re-embed the reviewed plan and atomically replace every matching legacy vector.

    Args:
        expected_rows: Exact row count printed by :func:`inspect_embedding_reindex`.
        expected_digest: Exact content-bound digest printed by the same dry run.
        batch_size: Maximum texts sent to the embedding facade per call.

    Returns:
        Post-commit reconciliation evidence.

    Raises:
        ReindexPreconditionError: The target, model, count, digest or vector shape changed.
        RuntimeError: The transactional update or post-commit verification failed.
    """
    if batch_size < 1 or batch_size > _MAX_REPAIR_BATCH:
        msg = f"embedding repair batch size must be between 1 and {_MAX_REPAIR_BATCH}"
        raise ReindexPreconditionError(msg)

    chunks = await load_unfingerprinted_chunks()
    plan = build_reindex_plan(
        chunks,
        model=embeddings.embedding_model_name(),
        dimension=embeddings.embedding_dimension(),
    )
    if plan.rows != expected_rows:
        msg = f"reindex row precondition failed: expected {expected_rows}, found {plan.rows}"
        raise ReindexPreconditionError(msg)
    if plan.digest != expected_digest:
        msg = f"reindex digest precondition failed: expected {expected_digest}, found {plan.digest}"
        raise ReindexPreconditionError(msg)

    repairs: list[ReembeddedChunk] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = await embeddings.embed([row.text for row in batch])
        if len(vectors) != len(batch):
            msg = f"embedder returned {len(vectors)} vectors for {len(batch)} texts"
            raise ReindexPreconditionError(msg)
        for row, vector in zip(batch, vectors, strict=True):
            if len(vector) != plan.dimension:
                msg = (
                    f"embedder returned {len(vector)} dimensions for {row.corpus}/"
                    f"{row.source}/{row.chunk_id}; expected {plan.dimension}"
                )
                raise ReindexPreconditionError(msg)
            repairs.append(
                ReembeddedChunk(
                    corpus=row.corpus,
                    source=row.source,
                    chunk_id=row.chunk_id,
                    text=row.text,
                    embedding=vector,
                )
            )

    updated = await replace_unfingerprinted_embeddings(
        repairs,
        model=plan.model,
        dimension=plan.dimension,
    )
    groups = await corpus_fingerprints()
    remaining = sum(rows for model, dimension, rows in groups if model is None or dimension is None)
    if remaining != 0:
        msg = f"embedding repair committed but {remaining} unfingerprinted rows remain"
        raise RuntimeError(msg)
    return EmbeddingReindexResult(
        planned_rows=plan.rows,
        updated_rows=updated,
        digest=plan.digest,
        model=plan.model,
        dimension=plan.dimension,
        remaining_unfingerprinted_rows=remaining,
    )
