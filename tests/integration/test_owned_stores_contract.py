"""Contract tests: the owned score stores bootstrap on the LIVE backends (ADR 0015 G1).

Integration-tagged — verifies the §Amendment 2 / §Correction 2b stores against the real
self-hosted spine (ClickHouse :18123) and the real Postgres, never in the fast unit loop.
Skips cleanly when a backend is not up (``make obs-up`` / local Postgres), so the suite
never fails for a missing dependency. Probes are read-only or self-cleaning: the owned
tables never keep a synthetic row.
"""

from __future__ import annotations

import time
import uuid

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


class TestClickHouseWriteContract:
    def test_online_insert_round_trips_and_cleans_up(self) -> None:
        from tessera.observability.clickhouse_scores import online_score_line

        adapter = _clickhouse()
        adapter.ensure_schema()
        probe_metric = f"contract-probe-{uuid.uuid4().hex[:12]}"
        line = online_score_line(
            {
                "scored_at": "2026-01-01T00:00:00+00:00",
                "metric": probe_metric,
                "score": 0.5,
                "language": "fr",
                "judge_model": "probe",
                "conversation_id": "contract-probe-conv",
                "trace_id": "contract-probe-trace",
                "sampled": True,
                "agent_id": "contract-probe-agent",
                "model": "probe-model",
            }
        )
        assert line is not None
        adapter.execute(f"INSERT INTO {adapter.table} FORMAT JSONEachRow", data=line)
        try:
            count = adapter.execute(
                f"SELECT count() FROM {adapter.table} WHERE metric = '{probe_metric}'"  # noqa: S608 — fixed probe literals
            ).strip()
            assert count == "1"
        finally:
            # Lightweight delete: the probe never lingers (G4 parity counts must stay real).
            adapter.execute(f"DELETE FROM {adapter.table} WHERE metric = '{probe_metric}'")  # noqa: S608
        # Lightweight-delete visibility can lag one beat on a fresh table — poll, bounded.
        remaining = "?"
        for _ in range(10):
            remaining = adapter.execute(
                f"SELECT count() FROM {adapter.table} WHERE metric = '{probe_metric}'"  # noqa: S608 — fixed probe literals
            ).strip()
            if remaining == "0":
                break
            time.sleep(0.3)
        assert remaining == "0"


class TestClickHouseReadContract:
    def test_online_scores_scoped_read_round_trips(self) -> None:
        from tessera.observability.clickhouse_scores import online_score_line
        from tessera.observability.spine.scope import Scope

        adapter = _clickhouse()
        adapter.ensure_schema()
        probe_agent = f"g3-read-probe-{uuid.uuid4().hex[:12]}"
        lines = []
        for stamp, metric in (
            ("2026-01-01T00:00:00+00:00", "faithfulness"),
            ("2026-01-02T00:00:00+00:00", "grounding"),
        ):
            line = online_score_line(
                {
                    "scored_at": stamp,
                    "metric": metric,
                    "score": 0.7,
                    "language": "fr",
                    "judge_model": "probe",
                    "conversation_id": "g3-conv",
                    "trace_id": "g3-trace",
                    "sampled": True,
                    "agent_id": probe_agent,
                    "model": "probe-model",
                }
            )
            assert line is not None
            lines.append(line)
        adapter.execute(f"INSERT INTO {adapter.table} FORMAT JSONEachRow", data=b"\n".join(lines))
        try:
            rows = adapter.online_scores(Scope(agent_id=probe_agent))
            assert [r["metric"] for r in rows] == ["faithfulness", "grounding"]
            assert rows[0]["scored_at"] == "2026-01-01T00:00:00.000+00:00"
            assert rows[0]["sampled"] is True
            # As-of-T excludes the later row server-side.
            asof = adapter.online_scores(
                Scope(agent_id=probe_agent, at="2026-01-01T12:00:00+00:00")
            )
            assert [r["metric"] for r in asof] == ["faithfulness"]
            # Language slice composes with agent.
            assert adapter.online_scores(Scope(agent_id=probe_agent, language="de")) == []
        finally:
            adapter.execute(
                f"DELETE FROM {adapter.table} WHERE agent_id = '{probe_agent}'"  # noqa: S608 — fixed probe literal
            )


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

    async def test_record_gating_report_is_idempotent_and_cleans_up(self) -> None:
        from psycopg.rows import dict_row

        from tessera.observability.eval.gating_scores import record_gating_report
        from tessera.retrieval.store import get_pool

        probe_run_at = "20260101T000000Z"
        report: dict[str, object] = {
            "run_at": probe_run_at,
            "agent_id": "contract-probe-agent",
            "model": "probe-model",
            "catalogue_version": "probe-1",
            "results": [
                {"case_id": "probe_case", "language": "fr", "passed": True},
                {"case_id": "probe_case", "language": "de", "passed": False},
            ],
        }
        try:
            first = await record_gating_report(report)
        except Exception:  # any connection failure means "no local Postgres"
            pytest.skip("postgres not up (docker compose up)")
        run_id = f"{probe_run_at}_contract-probe-agent"
        pool = get_pool()
        try:
            assert first == 2
            assert await record_gating_report(report) == 0  # unique key → re-ingest is free
            async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT language, passed, score FROM eval_gating_scores"
                    " WHERE run_id = %s ORDER BY language",
                    (run_id,),
                )
                rows = await cur.fetchall()
            assert [(r["language"], r["passed"], r["score"]) for r in rows] == [
                ("de", False, 0.0),
                ("fr", True, 1.0),
            ]
        finally:
            # The porteur never keeps a synthetic run.
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute("DELETE FROM eval_gating_scores WHERE run_id = %s", (run_id,))
                await conn.commit()

    async def test_gating_adapter_reads_the_porteur_scoped(self) -> None:
        from tessera.observability.eval.gating_scores import record_gating_report
        from tessera.observability.spine.adapters.postgres import PostgresGatingAdapter
        from tessera.observability.spine.scope import Scope
        from tessera.retrieval.store import get_pool

        probe_agent = "g3-gating-probe-agent"
        report: dict[str, object] = {
            "run_at": "20260102T000000Z",
            "agent_id": probe_agent,
            "model": "probe-model",
            "catalogue_version": "probe-1",
            "results": [
                {"case_id": "01", "language": "fr", "passed": True},
                {"case_id": "02", "language": "de", "passed": False},
            ],
        }
        try:
            inserted = await record_gating_report(report)
        except Exception:  # any connection failure means "no local Postgres"
            pytest.skip("postgres not up (docker compose up)")
        run_id = f"20260102T000000Z_{probe_agent}"
        adapter = PostgresGatingAdapter()
        try:
            assert inserted == 2
            rows = adapter.gating_scores(Scope(agent_id=probe_agent))
            assert [r["case_id"] for r in rows] == ["01", "02"]
            assert rows[0]["metric"] == "case_pass"
            assert isinstance(rows[0]["scored_at"], str)  # ISO — the shared row shape
            # As-of-T before the run → nothing; language slice composes with agent.
            assert (
                adapter.gating_scores(Scope(agent_id=probe_agent, at="2026-01-01T00:00:00+00:00"))
                == []
            )
            french = adapter.gating_scores(Scope(agent_id=probe_agent, language="fr"))
            assert [r["case_id"] for r in french] == ["01"]
        finally:
            pool = get_pool()
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute("DELETE FROM eval_gating_scores WHERE run_id = %s", (run_id,))
                await conn.commit()
