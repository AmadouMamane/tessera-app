"""pgvector-backed document store.

The store owns one process-wide async connection pool, the schema migration
required to host pgvector columns of the active embedding dimension, and the
basic insert / nearest-neighbour query helpers used by ingestion and
search.

The schema is created idempotently on the first call to :func:`ensure_schema`
and depends on ``pgvector`` being installed in the target database — see
``infra/terraform/postgres.tf``.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from tessera.retrieval.embeddings import embedding_dimension, embedding_model_name
from tessera.settings import LanguageCode, get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from psycopg import AsyncConnection

__all__ = [
    "DocumentRecord",
    "VectorHit",
    "ensure_schema",
    "get_pool",
    "insert_documents",
    "knn_search",
]


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """A document chunk ready to insert."""

    corpus: str
    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    embedding: list[float]
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class VectorHit:
    """A single nearest-neighbour result."""

    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    score: float
    metadata: dict[str, str]


_pool: AsyncConnectionPool | None = None

# Fixed key serialising per-env schema creation across concurrently-opened
# pool connections (see :func:`_isolate_environment`). Arbitrary constant; only
# its stability matters, so all bootstrappers contend on the same lock.
_SCHEMA_BOOTSTRAP_LOCK = 0x7E55E2A04154  # "TESSERA ISA" leet, fits in a signed bigint


async def _isolate_environment(conn: AsyncConnection[Any]) -> None:
    """Pin every pooled connection to this environment's schema (ADR 0014).

    Creates ``<schema>`` if missing and sets ``search_path`` to ``<schema>,
    public`` so every durable write (transcript, eval, memory, lineage, …) lands
    in the environment's namespace while pgvector's ``vector`` type and other
    shared objects still resolve from ``public``. For production the schema is
    ``public`` itself, making this a no-op that leaves the deployed stack exactly
    as it was. Runs on each new connection; ``CREATE SCHEMA IF NOT EXISTS`` is
    idempotent and cheap.
    """
    schema = get_settings().pg_schema
    async with conn.cursor() as cur:
        # ``CREATE SCHEMA IF NOT EXISTS`` still races to a duplicate-key error when
        # the pool opens several connections at once; a transaction-scoped advisory
        # lock serialises the bootstrap so the IF NOT EXISTS guard actually holds.
        await cur.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_BOOTSTRAP_LOCK,))
        await cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        await cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
    await conn.commit()


def get_pool() -> AsyncConnectionPool:
    """Return the lazily-initialised process-wide async pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=str(settings.postgres.dsn),
            min_size=settings.postgres.pool_min_size,
            max_size=settings.postgres.pool_max_size,
            configure=_isolate_environment,
            open=False,
        )
    return _pool


@asynccontextmanager
async def _connection() -> AsyncIterator[AsyncConnection[Any]]:
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn:
        yield conn


async def ensure_schema() -> None:
    """Create the documents table and HNSW index idempotently."""
    settings = get_settings()
    table = safe_identifier(settings.postgres.vector_table)
    dim = embedding_dimension()
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id           bigserial PRIMARY KEY,
                corpus       text       NOT NULL,
                source       text       NOT NULL,
                chunk_id     text       NOT NULL,
                language     varchar(2) NOT NULL,
                text         text       NOT NULL,
                embedding    vector({dim}) NOT NULL,
                metadata     jsonb      NOT NULL DEFAULT '{{}}'::jsonb,
                inserted_at  timestamptz NOT NULL DEFAULT now(),
                UNIQUE (corpus, source, chunk_id)
            );
            """
        )
        # The embedding SPACE each row was built in, recorded at ingestion.
        #
        # Without these two columns `/observability/embedding-skew` had no corpus fingerprint
        # to compare against, so it passed the ACTIVE embedder as both sides — a comparison of
        # a thing with itself, which cannot fail. It reported `corpus_known: false` rather than
        # a clean bill, which was honest, but it measured nothing. Now it can.
        #
        # Added with IF NOT EXISTS rather than in the CREATE above: the table already exists in
        # every deployment, and rows ingested before this stay NULL — which is the truthful
        # record of "we did not write it down at the time", and is what lets the probe say
        # which part of the corpus it can and cannot vouch for.
        await cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_model text;")
        await cur.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_dimension integer;"
        )
        await cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {table}_embedding_hnsw
                ON {table} USING hnsw (embedding vector_cosine_ops);
            """
        )
        await cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {table}_corpus_language
                ON {table} (corpus, language);
            """
        )
        await conn.commit()


async def insert_documents(records: Sequence[DocumentRecord]) -> int:
    """Bulk-insert ``records``; returns the number of rows actually inserted."""
    if not records:
        return 0
    table = safe_identifier(get_settings().postgres.vector_table)
    model = embedding_model_name()
    async with _connection() as conn, conn.cursor() as cur:
        rows = [
            (
                r.corpus,
                r.source,
                r.chunk_id,
                r.language.value,
                r.text,
                r.embedding,
                json.dumps(r.metadata),
                model,
                # The dimension comes from the VECTOR, not from the config. It is a fact about
                # the row; the model name is a claim about how the row was made. Recording the
                # config's dimension would make the two columns agree by construction and the
                # skew check would go back to comparing a thing with itself.
                len(r.embedding),
            )
            for r in records
        ]
        await cur.executemany(
            f"""
            INSERT INTO {table}
                (corpus, source, chunk_id, language, text, embedding, metadata,
                 embedding_model, embedding_dimension)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (corpus, source, chunk_id) DO NOTHING;
            """,
            rows,
        )
        await conn.commit()
        return cur.rowcount or 0


async def knn_search(
    *,
    query_embedding: list[float],
    corpus: str,
    language: LanguageCode | None,
    top_k: int = 10,
) -> list[VectorHit]:
    """Return the ``top_k`` nearest chunks in ``corpus``.

    When ``language`` is ``None`` the search spans all languages — used by
    the regulation lookup where EU texts are stored in their source language
    regardless of the active conversation language.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if language is not None:
            await cur.execute(
                f"""
                    SELECT source, chunk_id, language, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM {table}
                    WHERE corpus = %s AND language = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                (query_embedding, corpus, language.value, query_embedding, top_k),
            )
        else:
            await cur.execute(
                f"""
                    SELECT source, chunk_id, language, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM {table}
                    WHERE corpus = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                (query_embedding, corpus, query_embedding, top_k),
            )
        rows = await cur.fetchall()
    return [
        VectorHit(
            source=str(row["source"]),
            chunk_id=str(row["chunk_id"]),
            language=LanguageCode(row["language"]),
            text=str(row["text"]),
            metadata=dict(row.get("metadata") or {}),
            score=float(row["score"]),
        )
        for row in rows
    ]


async def corpus_fingerprints() -> list[tuple[str | None, int | None, int]]:
    """The embedding spaces the corpus actually holds: ``[(model, dimension, rows)]``.

    This is what turns `/observability/embedding-skew` from a tautology into a measurement. It
    reads what the STORE recorded, not what the process is configured to use — the whole point
    being that those two can differ, silently, after a profile flip or a model swap.

    A ``(None, None, n)`` group is rows ingested before the fingerprint columns existed. That
    is neither a skew nor a clean bill: it is the part of the corpus the probe cannot vouch
    for, and it travels separately so the surface can say exactly that (ADR 0026 — a witness
    that cannot see reports where the blindness is).

    Returns:
        One tuple per distinct space, largest group first. Empty when the corpus is empty.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT embedding_model, embedding_dimension, count(*)::int
              FROM {table}
             GROUP BY embedding_model, embedding_dimension
             ORDER BY count(*) DESC;
            """  # noqa: S608 — fixed, validated identifier; no caller string reaches the SQL
        )
        rows = await cur.fetchall()
    return [(r[0], r[1], int(r[2])) for r in rows]
