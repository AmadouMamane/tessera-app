"""Owned Postgres home of the GATING eval scores (ADR 0015 §Amendment 2, Nature 1).

The release socle — the offline harness verdicts archived under ``eval/reports/*.json``
that **gate a release** — is the opposable, load-bearing eval fact. Its volume is bounded
(cases x languages x metrics x runs; it grows per *release*, not per *traffic*), so it
lives in a plain indexed, transactional Postgres table with **no partition/retention
machinery**. The online monitoring firehose lives elsewhere (owned ClickHouse,
§Correction 2b) and Prometheus keeps the aggregates — this table is never summed on the
hot path.

Schema bootstrap follows the repo's idempotent ``ensure_*_schema`` pattern (not Alembic).
The pool pins ``search_path`` to the active environment's schema (ADR 0014), so the table
materialises per environment at boot and a read never falls through to another
environment's state. The unique ``(run_id, case_id, language, metric)`` key is what makes
re-ingest and backfill idempotent (``ON CONFLICT DO NOTHING``).
"""

from __future__ import annotations

from typing import Final

from tessera.retrieval.store import get_pool

__all__ = ["GATING_TABLE", "ensure_eval_gating_schema"]

GATING_TABLE: Final = "eval_gating_scores"

# Nature-1 DDL (ADR 0015 §Amendment 2) — the release-gating socle: bounded, opposable.
CREATE_GATING_TABLE: Final = f"""
CREATE TABLE IF NOT EXISTS {GATING_TABLE} (
    id                bigserial PRIMARY KEY,
    run_id            text        NOT NULL,
    case_id           text        NOT NULL,
    agent_id          text        NOT NULL,
    language          text        NOT NULL,
    model             text        NOT NULL,
    metric            text        NOT NULL,
    score             double precision NOT NULL,
    passed            boolean     NOT NULL,
    catalogue_version text,
    judge_model       text,
    scored_at         timestamptz NOT NULL
)
"""

CREATE_GATING_INDEXES: Final = (
    f"CREATE INDEX IF NOT EXISTS eval_gating_run ON {GATING_TABLE} (run_id)",
    f"CREATE INDEX IF NOT EXISTS eval_gating_agent ON {GATING_TABLE} (agent_id, scored_at)",
    # Idempotent re-ingest / backfill: a run + case + language + metric is unique.
    "CREATE UNIQUE INDEX IF NOT EXISTS eval_gating_uq "
    f"ON {GATING_TABLE} (run_id, case_id, language, metric)",
)


async def ensure_eval_gating_schema() -> None:
    """Create the gating-scores table and its indexes idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(CREATE_GATING_TABLE)
        for statement in CREATE_GATING_INDEXES:
            await cur.execute(statement)
        await conn.commit()
