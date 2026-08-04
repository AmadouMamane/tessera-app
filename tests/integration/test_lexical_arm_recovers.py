"""ADR 0050 — the lexical arm reaches what the dense arm cannot. Asked of PostgreSQL.

The unit witnesses next door prove the code *issues* a lexical query and that fusion keeps a
lexical-only document. Neither of them proves the SQL is valid, that the generated column
exists, that the GIN index is usable, or that German is analysed as German. Only a database
can answer that, so this file asks one.

The embeddings are hand-made orthogonal unit vectors, not a model's output: that makes "the
dense arm cannot see this document" an exact, reproducible fact rather than a property of
whatever embedder happens to be installed. Every row is inserted under a probe-only corpus id
and deleted afterwards; the real corpora are never touched.

Skips cleanly when Postgres is not up (``make dev-up`` / ``docker compose up postgres``).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from tessera.retrieval import store
from tessera.retrieval.embeddings import embedding_dimension
from tessera.retrieval.reranking import fuse, rerank
from tessera.settings import LanguageCode, get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration


#: A literal a dense embedder smears and a lexical index does not: the exact class of token a
#: banking corpus is addressed by (product references, article ids, contract numbers).
_RARE_LITERAL = "AUR-2024-118"


def _unit_vector(axis: int) -> list[float]:
    """A one-hot vector: cosine 1.0 with itself, exactly 0.0 with any other axis."""
    dim = embedding_dimension()
    vector = [0.0] * dim
    vector[axis] = 1.0
    return vector


@pytest.fixture
async def probe_corpus() -> AsyncIterator[str]:
    """Four documents on orthogonal axes, in a corpus nothing else reads."""
    corpus = f"lexical-probe-{uuid.uuid4().hex[:12]}"
    try:
        await store.ensure_schema()
    except Exception as exc:
        pytest.skip(f"postgres not up: {exc}")

    await store.insert_documents(
        [
            store.DocumentRecord(
                corpus=corpus,
                source="near",
                chunk_id="c1",
                language=LanguageCode.FR,
                text="Conditions générales du compte courant et des services associés.",
                embedding=_unit_vector(0),
                metadata={"category": "product"},
            ),
            store.DocumentRecord(
                corpus=corpus,
                source="middle",
                chunk_id="c1",
                language=LanguageCode.FR,
                text="Barème des frais de tenue de compte pour les particuliers.",
                embedding=_unit_vector(1),
                metadata={"category": "product"},
            ),
            store.DocumentRecord(
                corpus=corpus,
                source="far",
                chunk_id="c1",
                language=LanguageCode.FR,
                text=(
                    f"Le taux du prêt immobilier est fixé par la référence {_RARE_LITERAL} "
                    "pour les dossiers déposés cette année."
                ),
                embedding=_unit_vector(2),
                metadata={"category": "product"},
            ),
            store.DocumentRecord(
                corpus=corpus,
                source="german",
                chunk_id="c1",
                language=LanguageCode.DE,
                text="Die Bedingungen für Immobilienkredite werden jährlich überprüft.",
                embedding=_unit_vector(3),
                metadata={"category": "product"},
            ),
        ]
    )
    try:
        yield corpus
    finally:
        table = safe_identifier(get_settings().postgres.vector_table)
        async with store._connection() as conn, conn.cursor() as cur:
            await cur.execute(f"DELETE FROM {table} WHERE corpus = %s;", (corpus,))  # noqa: S608
            await conn.commit()


class TestTheDenseArmGenuinelyCannotSeeIt:
    """The premise. Without it, everything below would prove nothing."""

    async def test_the_knn_top_one_is_the_aligned_document_only(self, probe_corpus: str) -> None:
        hits = await store.knn_search(
            query_embedding=_unit_vector(0),
            corpus=probe_corpus,
            language=LanguageCode.FR,
            top_k=1,
        )
        assert [hit.source for hit in hits] == ["near"]

    async def test_the_previous_implementation_could_not_have_recovered_it(
        self, probe_corpus: str
    ) -> None:
        """``rerank`` over the dense candidates: the document is simply not in the set."""
        dense = await store.knn_search(
            query_embedding=_unit_vector(0),
            corpus=probe_corpus,
            language=LanguageCode.FR,
            top_k=1,
        )
        reordered = rerank(query=_RARE_LITERAL, hits=dense, top_k=4)
        assert "far" not in [item.hit.source for item in reordered]


class TestTheLexicalArmRetrieves:
    async def test_it_finds_the_document_by_its_rare_literal(self, probe_corpus: str) -> None:
        hits = await store.lexical_search(
            query=_RARE_LITERAL,
            query_embedding=_unit_vector(0),
            corpus=probe_corpus,
            language=LanguageCode.FR,
            top_k=12,
        )
        assert "far" in [hit.source for hit in hits]

    async def test_every_hit_carries_a_real_cosine_not_a_placeholder(
        self, probe_corpus: str
    ) -> None:
        [hit] = [
            h
            for h in await store.lexical_search(
                query=_RARE_LITERAL,
                query_embedding=_unit_vector(2),
                corpus=probe_corpus,
                language=LanguageCode.FR,
                top_k=12,
            )
            if h.source == "far"
        ]
        # The query vector IS this document's axis, so the true cosine is 1.0.
        assert hit.score == pytest.approx(1.0, abs=1e-6)
        assert hit.lexical_rank > 0.0

    async def test_a_whole_question_matches_not_only_a_bare_literal(
        self, probe_corpus: str
    ) -> None:
        """The regression the recall probe caught: AND semantics answered nothing, ever.

        This sentence shares *some* terms with the target chunk and not others — exactly the
        shape of a real question, and exactly what an AND-joined tsquery refuses.
        """
        hits = await store.lexical_search(
            query="Quel est le taux du prêt immobilier chez vous cette année ?",
            query_embedding=_unit_vector(0),
            corpus=probe_corpus,
            language=LanguageCode.FR,
            top_k=12,
        )
        assert "far" in [hit.source for hit in hits], (
            "a natural-language question retrieved nothing — a lexical arm that only answers "
            "bare literals is silent on every query a person actually asks"
        )

    async def test_spanning_all_languages_queries_each_with_its_own_config(
        self, probe_corpus: str
    ) -> None:
        """``Bedingung`` only reaches ``Bedingungen`` through the German stemmer."""
        hits = await store.lexical_search(
            query="Bedingung",
            query_embedding=_unit_vector(0),
            corpus=probe_corpus,
            language=None,
            top_k=12,
        )
        assert "german" in [hit.source for hit in hits]

    async def test_the_same_query_under_english_analysis_would_miss_it(self) -> None:
        """The control, and it earned its keep by failing first.

        Its first form asked whether ``Immobilienkredit`` reaches ``Immobilienkredite`` only
        under German — and PostgreSQL answered that English matches it too, because both
        merely strip a trailing ``e``. The claim being defended was wrong: ``german`` is a
        snowball stemmer, not a decompounder. ``Bedingungen`` is a real discriminator —
        ``beding`` under German, untouched under English.
        """
        german_text = "Die Bedingungen für Immobilienkredite werden jährlich überprüft."
        async with store._connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT to_tsvector('german', %s) @@ to_tsquery('german', %s),
                       to_tsvector('english', %s) @@ to_tsquery('english', %s);
                """,
                (german_text, "Bedingung", german_text, "Bedingung"),
            )
            row = await cur.fetchone()
        assert row is not None
        german_matches, english_matches = row
        assert german_matches is True
        assert english_matches is False, (
            "English analysis matched the German form — the control is broken, and the "
            "per-language configuration this test defends would be untestable"
        )

    async def test_a_reference_number_does_not_match_its_neighbour(self, probe_corpus: str) -> None:
        """Splitting on ``\\w+`` alone made AUR-2024-118 match AUR-2024-999. Measured."""
        async with store._connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT to_tsvector('french', %s) @@ to_tsquery('french', %s),
                       to_tsvector('french', %s) @@ to_tsquery('french', %s);
                """,
                (
                    "référence AUR-2024-118 applicable",
                    store._or_tsquery(_RARE_LITERAL),
                    "référence AUR-2024-999 applicable",
                    store._or_tsquery(_RARE_LITERAL),
                ),
            )
            row = await cur.fetchone()
        assert row is not None
        right_reference, wrong_reference = row
        assert right_reference is True
        assert wrong_reference is False, (
            "the query for one reference number also matched a different one — a lexical arm "
            "that cannot tell two contract references apart is worse than none for this corpus"
        )


class TestFusionDeliversTheRecovery:
    async def test_the_unreachable_document_reaches_the_top_k(self, probe_corpus: str) -> None:
        dense, lexical = (
            await store.knn_search(
                query_embedding=_unit_vector(0),
                corpus=probe_corpus,
                language=LanguageCode.FR,
                top_k=1,
            ),
            await store.lexical_search(
                query=_RARE_LITERAL,
                query_embedding=_unit_vector(0),
                corpus=probe_corpus,
                language=LanguageCode.FR,
                top_k=12,
            ),
        )
        fused = fuse(dense, lexical, top_k=4)
        recovered = [item for item in fused if item.source == "far"]
        assert recovered, f"the recovery did not survive fusion: {[i.source for i in fused]}"
        assert recovered[0].found_by == "lexical"


class TestTheIndexIsReallyThere:
    async def test_the_gin_index_exists_on_the_generated_column(self) -> None:
        settings = get_settings()
        async with store._connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT indexdef FROM pg_indexes
                 WHERE schemaname = %s AND tablename = %s AND indexdef ILIKE '%%USING gin%%';
                """,
                (settings.pg_schema, settings.postgres.vector_table),
            )
            rows = await cur.fetchall()
        definitions = [str(row[0]) for row in rows]
        assert any("text_search" in d for d in definitions), (
            f"no GIN index on the tsvector column in {settings.pg_schema}: the lexical query "
            f"would sequentially scan every chunk. Found: {definitions}"
        )

    async def test_the_planner_can_actually_use_it(self) -> None:
        """Is the index *usable* for the ``@@`` predicate — a narrower question than it looks.

        The first form of this test asserted the production query's plan named the GIN index,
        and PostgreSQL refused: it chose ``documents_corpus_language`` instead, because on a
        four-row probe corpus the corpus filter is far more selective than the text predicate.
        That was the planner being right, not the index being absent — so the test was asking
        the wrong question, and a green would have meant nothing about the real corpus either.

        What is worth asserting is that the GIN index *can* serve ``text_search @@ q`` at all;
        which plan wins on a given corpus is the planner's business and changes with its size.
        """
        table = safe_identifier(get_settings().postgres.vector_table)
        async with store._connection() as conn, conn.cursor() as cur:
            await cur.execute("SET LOCAL enable_seqscan = off;")
            await cur.execute(
                f"""
                EXPLAIN SELECT source FROM {table}, to_tsquery('french', %s) AS q
                 WHERE text_search @@ q;
                """,  # noqa: S608 — validated identifier; values bound
                (store._or_tsquery(_RARE_LITERAL),),
            )
            plan = " ".join(str(row[0]) for row in await cur.fetchall())
            await conn.rollback()
        assert "text_search_gin" in plan, f"the GIN index is not usable for this query: {plan}"
