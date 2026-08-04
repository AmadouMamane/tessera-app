"""The embedding repair is reviewed, content-bound and atomic at its store seam."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tessera.retrieval import reindex
from tessera.retrieval.store import (
    ReembeddedChunk,
    UnfingerprintedChunk,
    replace_unfingerprinted_embeddings,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _chunks() -> list[UnfingerprintedChunk]:
    return [
        UnfingerprintedChunk("regulations", "DORA/1", "DORA/1#0000", "first"),
        UnfingerprintedChunk("regulations", "GDPR/2", "GDPR/2#0000", "second"),
    ]


def test_plan_digest_is_order_independent_and_content_bound() -> None:
    """The reviewed identity follows exact rows and texts, not database return order."""
    plan = reindex.build_reindex_plan(_chunks(), model="bge-m3", dimension=2)
    reversed_plan = reindex.build_reindex_plan(
        list(reversed(_chunks())), model="bge-m3", dimension=2
    )
    changed = [
        *_chunks()[:-1],
        UnfingerprintedChunk("regulations", "GDPR/2", "GDPR/2#0000", "changed"),
    ]

    assert plan.digest == reversed_plan.digest
    assert plan.digest != reindex.build_reindex_plan(changed, model="bge-m3", dimension=2).digest
    assert (
        plan.digest
        != reindex.build_reindex_plan(_chunks(), model="text-embedding-v2", dimension=2).digest
    )
    assert plan.corpora == {"regulations": 2}


@pytest.mark.asyncio
async def test_inspection_is_read_only_and_never_calls_the_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The operator can review a plan without spending model work or opening a write seam."""

    async def load() -> list[UnfingerprintedChunk]:
        return _chunks()

    async def must_not_embed(texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError(f"embed called for {texts}")

    monkeypatch.setattr(reindex, "load_unfingerprinted_chunks", load)
    monkeypatch.setattr(reindex.embeddings, "embedding_model_name", lambda: "bge-m3")
    monkeypatch.setattr(reindex.embeddings, "embedding_dimension", lambda: 2)
    monkeypatch.setattr(reindex.embeddings, "embed", must_not_embed)

    plan = await reindex.inspect_embedding_reindex()

    assert plan.rows == 2
    assert plan.model == "bge-m3"


@pytest.mark.asyncio
async def test_store_rejects_an_invalid_stage_before_opening_a_connection() -> None:
    """Duplicate identities and wrong vector widths never reach the transactional seam."""
    row = ReembeddedChunk("regulations", "DORA/1", "DORA/1#0000", "first", [1.0, 2.0])

    with pytest.raises(ValueError, match="duplicate chunk keys"):
        await replace_unfingerprinted_embeddings([row, row], model="bge-m3", dimension=2)

    with pytest.raises(ValueError, match="outside the declared 3-d space"):
        await replace_unfingerprinted_embeddings([row], model="bge-m3", dimension=3)


@pytest.mark.asyncio
async def test_wrong_reviewed_count_refuses_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An obsolete approval cannot spend model work or reach the write seam."""

    async def load() -> list[UnfingerprintedChunk]:
        return _chunks()

    async def must_not_embed(texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError(f"embed called for {texts}")

    monkeypatch.setattr(reindex, "load_unfingerprinted_chunks", load)
    monkeypatch.setattr(reindex.embeddings, "embedding_model_name", lambda: "bge-m3")
    monkeypatch.setattr(reindex.embeddings, "embedding_dimension", lambda: 2)
    monkeypatch.setattr(reindex.embeddings, "embed", must_not_embed)

    with pytest.raises(reindex.ReindexPreconditionError, match="row precondition"):
        await reindex.repair_unfingerprinted_embeddings(
            expected_rows=241,
            expected_digest="obsolete",
        )


@pytest.mark.asyncio
async def test_repair_reembeds_every_exact_text_and_verifies_the_blind_spot_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only freshly generated vectors reach the atomic replacement seam."""
    chunks = _chunks()
    plan = reindex.build_reindex_plan(chunks, model="bge-m3", dimension=2)
    staged: list[ReembeddedChunk] = []

    async def load() -> list[UnfingerprintedChunk]:
        return chunks

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        return [[float(i), float(i + 1)] for i, _ in enumerate(texts)]

    async def replace(repairs: Sequence[ReembeddedChunk], *, model: str, dimension: int) -> int:
        assert model == "bge-m3"
        assert dimension == 2
        staged.extend(repairs)
        return len(repairs)

    async def fingerprints() -> list[tuple[str | None, int | None, int]]:
        return [("bge-m3", 2, 2)]

    monkeypatch.setattr(reindex, "load_unfingerprinted_chunks", load)
    monkeypatch.setattr(reindex, "replace_unfingerprinted_embeddings", replace)
    monkeypatch.setattr(reindex, "corpus_fingerprints", fingerprints)
    monkeypatch.setattr(reindex.embeddings, "embedding_model_name", lambda: "bge-m3")
    monkeypatch.setattr(reindex.embeddings, "embedding_dimension", lambda: 2)
    monkeypatch.setattr(reindex.embeddings, "embed", embed)

    result = await reindex.repair_unfingerprinted_embeddings(
        expected_rows=2,
        expected_digest=plan.digest,
        batch_size=1,
    )

    assert [row.text for row in staged] == ["first", "second"]
    assert result.updated_rows == 2
    assert result.remaining_unfingerprinted_rows == 0


@pytest.mark.asyncio
async def test_vector_dimension_mismatch_refuses_before_the_store_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured model name cannot certify vectors whose observed width differs."""
    chunks = _chunks()
    plan = reindex.build_reindex_plan(chunks, model="bge-m3", dimension=2)

    async def load() -> list[UnfingerprintedChunk]:
        return chunks

    async def bad_embed(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    async def must_not_replace(*args: object, **kwargs: object) -> int:
        raise AssertionError(f"replace called with {args} {kwargs}")

    monkeypatch.setattr(reindex, "load_unfingerprinted_chunks", load)
    monkeypatch.setattr(reindex, "replace_unfingerprinted_embeddings", must_not_replace)
    monkeypatch.setattr(reindex.embeddings, "embedding_model_name", lambda: "bge-m3")
    monkeypatch.setattr(reindex.embeddings, "embedding_dimension", lambda: 2)
    monkeypatch.setattr(reindex.embeddings, "embed", bad_embed)

    with pytest.raises(reindex.ReindexPreconditionError, match="expected 2"):
        await reindex.repair_unfingerprinted_embeddings(
            expected_rows=2,
            expected_digest=plan.digest,
        )
