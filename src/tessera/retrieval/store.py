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

from tessera.retrieval.embeddings import embedding_dimension
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from psycopg import AsyncConnection

__all__ = [
    "DocumentRecord",
    "VectorHit",
    "ensure_schema",
    "existing_chunk_ids",
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


def get_pool() -> AsyncConnectionPool:
    """Return the lazily-initialised process-wide async pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=str(settings.postgres.dsn),
            min_size=settings.postgres.pool_min_size,
            max_size=settings.postgres.pool_max_size,
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
    table = settings.postgres.vector_table
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
    table = get_settings().postgres.vector_table
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
            )
            for r in records
        ]
        await cur.executemany(
            f"""
            INSERT INTO {table}
                (corpus, source, chunk_id, language, text, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (corpus, source, chunk_id) DO NOTHING;
            """,
            rows,
        )
        await conn.commit()
        return cur.rowcount or 0


async def existing_chunk_ids(*, corpus: str, source: str, chunk_ids: Sequence[str]) -> set[str]:
    """Return already-persisted chunk ids for one corpus/source pair."""
    if not chunk_ids:
        return set()
    table = get_settings().postgres.vector_table
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(
                """
            SELECT chunk_id
            FROM {table}
            WHERE corpus = %s
              AND source = %s
              AND chunk_id = ANY(%s);
            """
            ).format(table=sql.Identifier(table)),
            (corpus, source, list(chunk_ids)),
        )
        rows = await cur.fetchall()
    return {str(row[0]) for row in rows}


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
    table = get_settings().postgres.vector_table
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
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
