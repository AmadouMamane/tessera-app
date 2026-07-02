"""G1 — the owned score stores (ADR 0015 §Amendment 2 + §Correction 2b), offline.

Locks the two homes' shape to the amendments so a drift is a test failure, not a silent
re-design: the gating socle (Postgres, plain indexed table, unique re-ingest key — the
porteur) and the online monitoring firehose (owned ClickHouse ``MergeTree`` with *native*
monthly partitions + TTL — never Langfuse's Scores ingestion). The live bootstrap against
real backends is covered by the integration contract tests; nothing here touches the
network.
"""

from __future__ import annotations

import io
import urllib.error

import pytest

from tessera.observability.eval.gating_scores import (
    CREATE_GATING_INDEXES,
    CREATE_GATING_TABLE,
    GATING_TABLE,
)
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.clickhouse import (
    ClickHouseAdapter,
    ClickHouseConfig,
    online_scores_ddl,
)


def _config(database: str = "tessera") -> ClickHouseConfig:
    """Dummy offline config — the adapter is stubbed before any network use."""
    return ClickHouseConfig(
        url="http://localhost:1",
        user="u",
        password="p",  # noqa: S106 — synthetic offline credential, never a real secret
        database=database,
    )


class TestClickHouseConfig:
    def test_from_env_defaults_match_the_local_obs_stack(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        for name in (
            "TESSERA_CLICKHOUSE_URL",
            "TESSERA_CLICKHOUSE_USER",
            "TESSERA_CLICKHOUSE_PASSWORD",
            "TESSERA_CLICKHOUSE_DATABASE",
        ):
            monkeypatch.delenv(name, raising=False)
        config = ClickHouseConfig.from_env()
        assert config.url == "http://localhost:18123"
        assert config.database == "tessera"  # the OWNED database, not Langfuse's `default`

    def test_database_name_must_be_a_plain_identifier(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _config(database="bad;db")


class TestOnlineScoresDdl:
    """The §Correction 2b DDL is the contract — partition + TTL are NATIVE, not hand-rolled."""

    def test_ddl_is_the_correction_2b_shape(self) -> None:
        ddl = online_scores_ddl("tessera")
        assert "CREATE TABLE IF NOT EXISTS tessera.eval_online_scores" in ddl
        assert "ENGINE = MergeTree" in ddl
        assert "ORDER BY (agent_id, metric, scored_at)" in ddl  # per-agent/metric + as-of-T
        assert "PARTITION BY toYYYYMM(scored_at)" in ddl  # native monthly partitions
        assert "TTL toDateTime(scored_at) + INTERVAL 6 MONTH" in ddl  # native retention

    def test_ddl_carries_every_amendment_column(self) -> None:
        ddl = online_scores_ddl("tessera")
        for column in (
            "scored_at",
            "agent_id",
            "language",
            "model",
            "metric",
            "score",
            "conversation_id",
            "trace_id",
            "sampled",
            "judge_model",
        ):
            assert column in ddl


class TestClickHouseAdapter:
    def test_ensure_schema_creates_database_then_table(self) -> None:
        adapter = ClickHouseAdapter(_config())
        executed: list[str] = []
        adapter.execute = lambda query: executed.append(query) or ""  # type: ignore[method-assign]
        adapter.ensure_schema()
        assert executed[0] == "CREATE DATABASE IF NOT EXISTS tessera"
        assert "CREATE TABLE IF NOT EXISTS tessera.eval_online_scores" in executed[1]

    def test_unreachable_raises_spine_unavailable(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        def _down(request: object, timeout: float) -> object:
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("urllib.request.urlopen", _down)
        adapter = ClickHouseAdapter(_config())
        with pytest.raises(SpineUnavailableError, match="unreachable"):
            adapter.execute("SELECT 1")

    def test_http_error_surfaces_the_clickhouse_detail(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        def _bad(request: object, timeout: float) -> object:
            raise urllib.error.HTTPError(
                "http://x", 400, "Bad Request", None, io.BytesIO(b"Syntax error: near FROM")
            )

        monkeypatch.setattr("urllib.request.urlopen", _bad)
        adapter = ClickHouseAdapter(_config())
        with pytest.raises(SpineUnavailableError, match="Syntax error"):
            adapter.execute("SELECT bogus")

    def test_table_is_fully_qualified(self) -> None:
        assert ClickHouseAdapter(_config()).table == "tessera.eval_online_scores"


class TestGatingDdl:
    """The §Amendment 2 Nature-1 DDL — plain indexed Postgres, no partition machinery."""

    def test_table_matches_amendment_2(self) -> None:
        assert GATING_TABLE == "eval_gating_scores"
        for column in (
            "run_id",
            "case_id",
            "agent_id",
            "language",
            "model",
            "metric",
            "score",
            "passed",
            "catalogue_version",
            "judge_model",
            "scored_at",
        ):
            assert column in CREATE_GATING_TABLE
        assert "PARTITION" not in CREATE_GATING_TABLE  # bounded volume — no machinery

    def test_unique_reingest_key_is_run_case_language_metric(self) -> None:
        unique = [s for s in CREATE_GATING_INDEXES if "UNIQUE" in s]
        assert len(unique) == 1
        assert "(run_id, case_id, language, metric)" in unique[0]
