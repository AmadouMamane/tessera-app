"""The skew probe compares the query embedder to the CORPUS — not to itself.

`/observability/embedding-skew` exists to catch a silent failure: a pgvector store is only
coherent if the corpus and the live queries were embedded by the same model, and a mismatch
returns confident nonsense with no error anywhere. Until 2026-08-01 the endpoint could not
perform that comparison, because the corpus recorded nothing about how it had been embedded.
It passed the ACTIVE embedder as both sides — `corpus = query`, equal by construction.

It said so (`corpus_known: false`, `severity: "unknown"`), which was honest and is why this
was a gap rather than a lie. But an honest witness that cannot see is still a witness that
cannot see. Ingestion now stamps every row with the model it was embedded with and the width
of the vector it produced, and the endpoint reads those back.

These tests hold the three things that must be true of that reading, and the first is the one
that makes the other two mean anything: a skew must be DETECTABLE. A probe that reports "no
skew" over a store it never queried is exactly what was replaced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tessera.api.routes.observability import safety
from tessera.api.routes.observability.schemas_safety import EmbeddingSkewPayload
from tessera.observability.embedding_skew import EmbeddingFingerprint, detect_skew

if TYPE_CHECKING:
    from collections.abc import Callable


def _fake_corpus(groups: list[tuple[str | None, int | None, int]]) -> Callable[[], Any]:
    """A stand-in for the store read, returning the groups a real corpus would."""

    async def _read() -> list[tuple[str | None, int | None, int]]:
        return groups

    return _read


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[Any]], None]:
    """Point the route's store read at a fixture, leaving everything else real."""

    def _apply(groups: list[Any]) -> None:
        import tessera.retrieval.store as store_mod

        monkeypatch.setattr(store_mod, "corpus_fingerprints", _fake_corpus(groups))

    return _apply


@pytest.mark.asyncio
async def test_a_real_skew_is_detected(patched: Callable[[list[Any]], None]) -> None:
    """The measurement the old version could not make, in its hardest form.

    A corpus embedded at 768 dimensions against a query embedder at 1024 is a HARD skew: the
    vectors cannot be compared at all, and nearest-neighbour search over them is meaningless.
    The old endpoint answered "no skew" to this, because it never asked the corpus.
    """
    patched([("text-multilingual-embedding-002", 768, 4200)])
    report = await safety.observability_embedding_skew()

    assert report["corpus_known"] is True
    assert report["corpus_model"] == "text-multilingual-embedding-002"
    assert report["corpus_dimension"] == 768
    # The active embedder in the test environment is the local one (bge-m3, 1024). Whatever it
    # is, it is not the 768-d Vertex model above, so a skew MUST be reported.
    assert report["skew"] is True
    assert report["severity"] in {"soft", "hard"}


@pytest.mark.asyncio
async def test_a_matching_corpus_is_a_finding_not_an_identity(
    patched: Callable[[list[Any]], None],
) -> None:
    """ "No skew" must now be a measurement — a comparison that COULD have failed."""
    from tessera.retrieval.embeddings import embedding_dimension, embedding_model_name

    patched([(embedding_model_name(), embedding_dimension(), 4200)])
    report = await safety.observability_embedding_skew()

    assert report["corpus_known"] is True
    assert report["skew"] is False
    assert report["severity"] == "none"
    assert report["corpus_rows"] == 4200
    assert report["unfingerprinted_rows"] == 0


@pytest.mark.asyncio
async def test_rows_ingested_before_the_columns_existed_are_named_not_assumed(
    patched: Callable[[list[Any]], None],
) -> None:
    """A corpus the probe cannot vouch for must be counted, not folded into either verdict.

    Rows written before ingestion recorded a fingerprint carry NULLs. They are not a skew and
    they are not a clearance — they are the part of the store this witness cannot see, and
    ADR 0026's corollary is that it must say where the blindness is.
    """
    patched([(None, None, 1500)])
    report = await safety.observability_embedding_skew()

    assert report["corpus_known"] is False
    assert report["severity"] == "unknown"
    assert report["unfingerprinted_rows"] == 1500
    assert report["spaces"] == []


@pytest.mark.asyncio
async def test_unknown_is_a_first_class_wire_verdict(
    patched: Callable[[list[Any]], None],
) -> None:
    """The honest blind spot must survive FastAPI response validation unchanged."""
    patched([(None, None, 241)])

    payload = EmbeddingSkewPayload.model_validate(await safety.observability_embedding_skew())

    assert payload.severity == "unknown"
    assert payload.corpus_known is False
    assert payload.corpus_rows == 241
    assert payload.unfingerprinted_rows == 241


@pytest.mark.asyncio
async def test_a_split_corpus_is_visible_rather_than_averaged(
    patched: Callable[[list[Any]], None],
) -> None:
    """A partial re-ingestion leaves TWO spaces, and hiding one is how the skew hides.

    The majority space may match the query, but a minority space can still poison retrieval.
    The verdict therefore follows the worst observed space and keeps the incomplete coverage
    explicit instead of averaging either problem away.
    """
    patched(
        [
            ("bge-m3", 1024, 3000),
            ("text-multilingual-embedding-002", 768, 900),
            (None, None, 100),
        ]
    )
    report = await safety.observability_embedding_skew()

    assert report["corpus_model"] == "text-multilingual-embedding-002"
    assert report["corpus_known"] is False
    assert report["severity"] == "hard"
    assert report["corpus_rows"] == 4000
    assert report["unfingerprinted_rows"] == 100
    spaces = report["spaces"]
    assert isinstance(spaces, list)
    assert len(spaces) == 2, "the second embedding space vanished from the report"


@pytest.mark.asyncio
async def test_partial_matching_fingerprint_is_unknown_not_green(
    patched: Callable[[list[Any]], None],
) -> None:
    """A measured matching subset cannot clear the rows the witness still cannot see."""
    from tessera.retrieval.embeddings import embedding_dimension, embedding_model_name

    patched([(embedding_model_name(), embedding_dimension(), 240), (None, None, 1)])

    report = await safety.observability_embedding_skew()

    assert report["skew"] is False
    assert report["corpus_known"] is False
    assert report["severity"] == "unknown"
    assert report["corpus_rows"] == 241
    assert report["unfingerprinted_rows"] == 1


@pytest.mark.asyncio
async def test_an_unreachable_store_reports_a_blind_spot_never_a_clean_bill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The failure mode that matters most: a probe that cannot read must not say "fine"."""
    import tessera.retrieval.store as store_mod

    async def _boom() -> list[tuple[str | None, int | None, int]]:
        msg = "connection refused"
        raise RuntimeError(msg)

    monkeypatch.setattr(store_mod, "corpus_fingerprints", _boom)
    report = await safety.observability_embedding_skew()

    assert report["corpus_known"] is False
    assert report["severity"] == "unknown"
    assert report["skew"] is False  # …and `corpus_known` is what stops that reading as "fine"


def test_the_comparison_itself_still_distinguishes_hard_from_soft() -> None:
    """The pure function, unchanged — a different width is not a different vocabulary."""
    query = EmbeddingFingerprint(model="bge-m3", dimension=1024)
    assert detect_skew(query, EmbeddingFingerprint("bge-m3", 768)).severity == "hard"
    assert detect_skew(query, EmbeddingFingerprint("e5-large", 1024)).severity == "soft"
    assert detect_skew(query, EmbeddingFingerprint("bge-m3", 1024)).severity == "none"
