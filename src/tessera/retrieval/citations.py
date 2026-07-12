"""Durable, live per-source citation telemetry.

Every real retrieval query records, in Postgres (the same database that hosts
the pgvector index), how many queries ran and which knowledge-source categories
were cited above the similarity threshold. The Sources & memory dashboard reads
these counters back as a cheap aggregate — no ``/tmp`` cache, no round-trip
through the trace backend, and the figures update on every agent turn.

Two daily counter tables keep reads trivial and feed per-day sparklines:

* ``retrieval_query_daily(day, queries, queries_with_hit)`` — one row per day.
* ``retrieval_citation_daily(day, category, hits)`` — one row per cited category
  per day; ``hits`` counts the queries that cited that category that day.

Writes are best-effort: a telemetry failure must never break a retrieval, so
:func:`record_retrieval_query` swallows every exception. The schema is created
idempotently on first write.

The table names are module constants and are **validated** by
:func:`tessera.sql.safe_identifier` at definition — not merely trusted for being literals
(audit P0.3 ``sql-fstring``). The ``# noqa: S608`` suppressions stay because S608 is a
syntactic rule and cannot see that validation; see ``tessera.sql`` for why they cannot be
deleted and what would replace them.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from psycopg.rows import tuple_row

from tessera.retrieval.store import get_pool
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable
    from datetime import date

    from psycopg import AsyncConnection

__all__ = [
    "CitationCounts",
    "backfill_daily",
    "ensure_citation_schema",
    "load_citation_counts",
    "record_retrieval_query",
]

# Validated at definition, like every other identifier (audit P0.3 `sql-fstring`).
_QUERY_TABLE = safe_identifier("retrieval_query_daily")
_CATEGORY_TABLE = safe_identifier("retrieval_citation_daily")

# Set once the tables are known to exist, so the hot path skips the DDL.
_schema_ready = False


@dataclass(frozen=True, slots=True)
class CitationCounts:
    """Aggregated citation counters over a window."""

    queries: int
    queries_with_hit: int
    hits: dict[str, int]


@asynccontextmanager
async def _connection() -> AsyncIterator[AsyncConnection[Any]]:
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn:
        yield conn


async def ensure_citation_schema() -> None:
    """Create the citation counter tables idempotently."""
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_QUERY_TABLE} ("
            "day date PRIMARY KEY, "
            "queries bigint NOT NULL DEFAULT 0, "
            "queries_with_hit bigint NOT NULL DEFAULT 0)"
        )
        await cur.execute(
            f"CREATE TABLE IF NOT EXISTS {_CATEGORY_TABLE} ("
            "day date NOT NULL, category text NOT NULL, "
            "hits bigint NOT NULL DEFAULT 0, "
            "PRIMARY KEY (day, category))"
        )
        await conn.commit()
    global _schema_ready
    _schema_ready = True


async def record_retrieval_query(categories: Iterable[str]) -> None:
    """Count one retrieval query and each category it cited, for today (UTC).

    Best-effort: never raises. A telemetry write must not break the agent turn.
    The category list is the already-thresholded set from
    :func:`tessera.retrieval.hybrid_search._cited_categories`.
    """
    cited = sorted({c for c in categories if c})
    try:
        if not _schema_ready:
            await ensure_citation_schema()
        today = datetime.now(UTC).date()
        had_hit = 1 if cited else 0
        async with _connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"INSERT INTO {_QUERY_TABLE} (day, queries, queries_with_hit) "  # noqa: S608
                "VALUES (%s, 1, %s) "
                "ON CONFLICT (day) DO UPDATE SET "
                f"queries = {_QUERY_TABLE}.queries + 1, "
                f"queries_with_hit = {_QUERY_TABLE}.queries_with_hit + EXCLUDED.queries_with_hit",
                (today, had_hit),
            )
            if cited:
                await cur.executemany(
                    f"INSERT INTO {_CATEGORY_TABLE} (day, category, hits) "  # noqa: S608
                    "VALUES (%s, %s, 1) "
                    "ON CONFLICT (day, category) DO UPDATE SET "
                    f"hits = {_CATEGORY_TABLE}.hits + 1",
                    [(today, cat) for cat in cited],
                )
            await conn.commit()
    except Exception as exc:  # telemetry must never break retrieval
        sys.stderr.write(f"tessera.retrieval.citations: record failed: {exc}\n")


async def backfill_daily(
    day: date,
    *,
    queries: int,
    queries_with_hit: int,
    hits: dict[str, int],
) -> None:
    """Replace the counters for ``day`` (idempotent reconstruction from a source).

    Used by the Phoenix backfill tool to seed historical days from real spans.
    Unlike :func:`record_retrieval_query` this *replaces* the day's totals, so
    re-running the backfill is idempotent. Do not run it for the current day if
    live writes are already accumulating there.
    """
    if not _schema_ready:
        await ensure_citation_schema()
    async with _connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"INSERT INTO {_QUERY_TABLE} (day, queries, queries_with_hit) "  # noqa: S608
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (day) DO UPDATE SET "
            "queries = EXCLUDED.queries, queries_with_hit = EXCLUDED.queries_with_hit",
            (day, queries, queries_with_hit),
        )
        await cur.execute(
            f"DELETE FROM {_CATEGORY_TABLE} WHERE day = %s",  # noqa: S608
            (day,),
        )
        if hits:
            await cur.executemany(
                f"INSERT INTO {_CATEGORY_TABLE} (day, category, hits) VALUES (%s, %s, %s)",  # noqa: S608
                [(day, cat, n) for cat, n in hits.items() if n],
            )
        await conn.commit()


async def load_citation_counts(*, window_days: int | None = None) -> CitationCounts | None:
    """Aggregate the counters over the last ``window_days`` (all-time if ``None``).

    Returns ``None`` when the counters are unavailable (tables absent or the
    database is unreachable) so the caller can fall back to another source.
    """
    where = ""
    params: tuple[object, ...] = ()
    if window_days is not None:
        where = "WHERE day >= (CURRENT_DATE - %s::int)"
        params = (window_days,)
    try:
        async with _connection() as conn:
            # Pooled connections may carry dict_row from a prior knn_search; force
            # positional rows so the index access below is correct.
            conn.row_factory = tuple_row
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT COALESCE(SUM(queries), 0), COALESCE(SUM(queries_with_hit), 0) "  # noqa: S608
                    f"FROM {_QUERY_TABLE} {where}",
                    params,
                )
                qrow = await cur.fetchone()
                await cur.execute(
                    f"SELECT category, COALESCE(SUM(hits), 0) "  # noqa: S608
                    f"FROM {_CATEGORY_TABLE} {where} GROUP BY category",
                    params,
                )
                crows = await cur.fetchall()
    except Exception as exc:  # degrade gracefully for the dashboard
        sys.stderr.write(f"tessera.retrieval.citations: read failed: {exc}\n")
        return None
    queries = int(qrow[0]) if qrow else 0
    with_hit = int(qrow[1]) if qrow else 0
    hits = {str(cat): int(n) for cat, n in crows}
    return CitationCounts(queries=queries, queries_with_hit=with_hit, hits=hits)
