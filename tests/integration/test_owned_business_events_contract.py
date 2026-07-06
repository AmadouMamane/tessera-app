"""Contract tests: the owned business-event store on the LIVE ClickHouse (ADR 0017 §5).

Integration-tagged — verifies the Phase-D table against the real self-hosted spine
(ClickHouse :18123), never in the fast unit loop. Skips cleanly when ClickHouse is not up
(``make obs-up``). Probes are self-cleaning: the owned table never keeps a synthetic row.
"""

from __future__ import annotations

import time
import uuid

import pytest

from tessera.observability.clickhouse_business_events import business_event_line
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


def _row(stamp: str, event_name: str, *, agent: str, conv: str, artifact_id: str = "") -> dict:
    return {
        "timestamp": stamp,
        "event_name": event_name,
        "agent_id": agent,
        "workflow_id": "recouvrement_collections_v1",
        "conversation_id": conv,
        "turn_id": "t1",
        "case_id": "case-1",
        "artifact_id": artifact_id,
        "decision": "allowed",
        "reason_codes": [],
        "payload": {"rule_id": "contact_window"},
        "actor": "operator",
        "schema_version": "business_event.v1",
        "event_version": 1,
        "grammar_version": "workflow_grammar.v1",
    }


class TestBusinessEventsSchemaContract:
    def test_ensure_schema_is_idempotent_and_materialises_adr_0017_section_5(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_business_events_schema()
        adapter.ensure_business_events_schema()  # IF NOT EXISTS — a re-run must be free
        create = adapter.execute(f"SHOW CREATE TABLE {adapter.business_events_table}")
        assert "MergeTree" in create
        assert "toYYYYMM(occurred_at)" in create  # native monthly partitions
        assert "TTL" in create
        assert "toIntervalMonth(6)" in create or "INTERVAL 6 MONTH" in create
        assert "ORDER BY (agent_id, workflow_id, event_name, occurred_at)" in create

    def test_owned_table_is_outside_langfuse_default_database(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_business_events_schema()
        assert adapter.business_events_table.split(".")[0] != "default"


class TestBusinessEventsReadContract:
    def test_scoped_and_asof_read_round_trip(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_business_events_schema()
        probe_agent = f"be-read-probe-{uuid.uuid4().hex[:12]}"
        conv = f"be-conv-{uuid.uuid4().hex[:12]}"
        lines = [
            business_event_line(
                _row(
                    "2026-06-01T00:00:00+00:00", "case.context_loaded", agent=probe_agent, conv=conv
                )
            ),
            business_event_line(
                _row(
                    "2026-06-02T00:00:00+00:00",
                    "artifact.created",
                    agent=probe_agent,
                    conv=conv,
                    artifact_id="a1",
                )
            ),
        ]
        assert all(line is not None for line in lines)
        adapter.execute(
            f"INSERT INTO {adapter.business_events_table} FORMAT JSONEachRow",
            data=b"\n".join(line for line in lines if line is not None),
        )
        try:
            rows = adapter.business_events(agent_id=probe_agent, at="2026-06-03T00:00:00+00:00")
            assert [r["event_name"] for r in rows] == ["case.context_loaded", "artifact.created"]
            assert rows[0]["actor"] == "operator"
            assert rows[0]["payload"] == {"rule_id": "contact_window"}
            # As-of-T excludes the later row server-side.
            asof = adapter.business_events(agent_id=probe_agent, at="2026-06-01T12:00:00+00:00")
            assert [r["event_name"] for r in asof] == ["case.context_loaded"]
        finally:
            adapter.delete_business_events(conv)

    def test_erasure_deletes_the_conversation_rows(self) -> None:
        adapter = _clickhouse()
        adapter.ensure_business_events_schema()
        probe_agent = f"be-erase-probe-{uuid.uuid4().hex[:12]}"
        conv = f"be-erase-conv-{uuid.uuid4().hex[:12]}"
        line = business_event_line(
            _row("2026-06-01T00:00:00+00:00", "policy.decision_made", agent=probe_agent, conv=conv)
        )
        assert line is not None
        adapter.execute(
            f"INSERT INTO {adapter.business_events_table} FORMAT JSONEachRow", data=line
        )
        assert adapter.delete_business_events(conv) == 1
        table = adapter.business_events_table
        remaining = "?"
        for _ in range(10):
            remaining = adapter.execute(
                f"SELECT count() FROM {table} WHERE conversation_id = '{conv}'"  # noqa: S608 — fixed probe literal
            ).strip()
            if remaining == "0":
                break
            time.sleep(0.3)
        assert remaining == "0"  # the owned business-event leg of erasure is real
