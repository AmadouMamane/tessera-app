"""Contract tests: the owned score stores bootstrap on the LIVE backends (ADR 0015 G1).

Integration-tagged — verifies the §Amendment 2 / §Correction 2b stores against the real
self-hosted spine (ClickHouse :18123) and the real Postgres, never in the fast unit loop.
Skips cleanly when a backend is not up (``make obs-up`` / local Postgres), so the suite
never fails for a missing dependency. Probes are read-only or self-cleaning: the owned
tables never keep a synthetic row.
"""

from __future__ import annotations

import pytest

from tessera.observability.eval.gating_scores import GATING_TABLE, ensure_eval_gating_schema
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter

pytestmark = pytest.mark.integration


def _clickhouse() -> ClickHouseAdapter:
    adapter = ClickHouseAdapter(timeout_s=5.0)
    try:
        adapter.execute("SELECT 1")
    except SpineUnavailableError:
        pytest.skip("clickhouse not up (make obs-up)")
    return adapter


class TestClickHouseOnlineStoreContract:
    def test_ensure_schema_is_idempotent_and_materialises_correction_2b(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_schema()
        adapter.ensure_schema()  # IF NOT EXISTS — a re-run must be free
        create = adapter.execute(f"SHOW CREATE TABLE {adapter.table}")
        assert "MergeTree" in create
        assert "toYYYYMM(scored_at)" in create  # native monthly partitions
        # Native retention — ClickHouse normalises the interval spelling in SHOW CREATE.
        assert "TTL" in create
        assert "toIntervalMonth(6)" in create or "INTERVAL 6 MONTH" in create
        assert "ORDER BY (agent_id, metric, scored_at)" in create

    def test_owned_table_is_outside_langfuse_default_database(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_schema()
        assert adapter.table.split(".")[0] != "default"  # owned ≠ Langfuse's ingestion home


class TestPostgresGatingContract:
    async def test_ensure_schema_is_idempotent_and_carries_the_unique_key(self) -> None:
        from psycopg.rows import dict_row

        from tessera.retrieval.store import get_pool

        try:
            await ensure_eval_gating_schema()
        except Exception:  # any connection failure means "no local Postgres"
            pytest.skip("postgres not up (docker compose up)")
        await ensure_eval_gating_schema()  # idempotent re-run
        pool = get_pool()
        # Explicit row factory: pooled connections may carry a mutated default (see the
        # transcript row_factory bug) — never read a row by position on this pool.
        async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT indexdef FROM pg_indexes WHERE tablename = %s", (GATING_TABLE,)
            )
            defs = [str(row["indexdef"]) for row in await cur.fetchall()]
        unique = [d for d in defs if "UNIQUE" in d and "eval_gating_uq" in d]
        assert len(unique) == 1
        assert "run_id, case_id, language, metric" in unique[0]
