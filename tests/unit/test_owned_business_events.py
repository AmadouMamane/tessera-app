"""ADR 0017 §5 / Phase D — the owned ClickHouse business-event store (offline).

Locks the Phase-D mechanism without a live ClickHouse: the JSONEachRow line + dedup key are
pure; the read store rebuilds ``BusinessEvent`` s and is honest-empty when unreachable; the
per-fact flip routes reads (jsonl default → owned → shadow); GDPR erasure reaches the owned
business-event table (count-then-delete, bound params, deferred-never-faked); the dual-write
is best-effort and gated; the backfill inserts exactly the difference.
"""

from __future__ import annotations

from tessera.observability import business_events as be, erasure
from tessera.observability.business_events import (
    BusinessEventName,
    ClickHouseBusinessEventStore,
    record_business_event,
    reset_business_event_store,
)
from tessera.observability.clickhouse_business_events import (
    business_event_line,
    business_event_row_key,
)
from tessera.observability.spine.adapters import clickhouse as ch_mod
from tessera.observability.spine.adapters.base import SpineUnavailableError
from tessera.observability.spine.adapters.clickhouse import ClickHouseAdapter, ClickHouseConfig


def _to_row() -> dict[str, object]:
    reset_business_event_store()
    event = record_business_event(
        event_name=BusinessEventName.BUSINESS_RULE_CHECKED,
        agent_id="recouvrement",
        conversation_id="conv-be",
        turn_id="turn-be",
        workflow_id="recouvrement_collections_v1",
        decision="allowed",
        payload={"rule_id": "contact_window"},
        actor="operator",
    )
    return event.to_row()


def _offline_adapter() -> ClickHouseAdapter:
    return ClickHouseAdapter(
        ClickHouseConfig(
            url="http://localhost:1",
            user="u",
            password="p",  # noqa: S106 — synthetic offline credential
            database="tessera",
        )
    )


# --- pure line + dedup key -------------------------------------------------------


def test_line_and_key_are_pure_and_ms_precise() -> None:
    row = {
        "timestamp": "2026-07-02T16:01:25.317934+00:00",
        "event_name": "artifact.created",
        "agent_id": "recouvrement",
        "conversation_id": "conv-1",
        "turn_id": "t1",
        "artifact_id": "a1",
        "reason_codes": ["OUTSIDE_CONTACT_WINDOW"],
        "payload": {"task": "draft_reminder"},
    }
    key = business_event_row_key(row)
    assert key == (
        "2026-07-02 16:01:25.317",
        "recouvrement",
        "artifact.created",
        "conv-1",
        "t1",
        "a1",
    )
    assert key == business_event_row_key(dict(row))  # stable
    line = business_event_line(row)
    assert line is not None
    assert b"artifact.created" in line and b"OUTSIDE_CONTACT_WINDOW" in line


def test_row_without_instant_or_name_has_no_line_or_key() -> None:
    assert business_event_row_key({"event_name": "x"}) is None
    assert business_event_line({"event_name": "x"}) is None
    assert business_event_line({"timestamp": "2026-07-02T16:01:25+00:00"}) is None


def test_none_dimensions_become_empty_markers() -> None:
    import json

    line = business_event_line(
        {"timestamp": "2026-07-02T16:01:25+00:00", "event_name": "intent.routed"}
    )
    assert line is not None
    payload = json.loads(line.decode())
    assert payload["agent_id"] == "" and payload["actor"] == "system" and payload["payload"] == ""


# --- read store: rebuild + honest-empty ------------------------------------------


class _StubAdapter:
    def __init__(self, rows: list[dict[str, object]] | None = None, *, down: bool = False) -> None:
        self._rows = rows or []
        self._down = down
        self.calls: list[dict[str, object]] = []

    def business_events(self, **filters: object) -> list[dict[str, object]]:
        if self._down:
            raise SpineUnavailableError("clickhouse down")
        self.calls.append(filters)
        return self._rows


def test_read_store_rebuilds_events(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = _to_row()
    stub = _StubAdapter(rows=[row])
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: stub)
    events = ClickHouseBusinessEventStore().list(agent_id="recouvrement")
    assert len(events) == 1
    assert events[0].event_name == "business_rule.checked"
    assert events[0].actor == "operator"
    assert stub.calls[0]["agent_id"] == "recouvrement"  # filter pushed through


def test_read_store_is_honest_empty_when_unreachable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(down=True))
    assert ClickHouseBusinessEventStore().list(agent_id="recouvrement") == []  # never fabricated


# --- per-fact flip routing -------------------------------------------------------


def test_reads_default_to_the_in_process_store(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
    monkeypatch.delenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", raising=False)
    store = be._read_store()
    assert type(store).__name__ == "InMemoryBusinessEventStore"


def test_flip_routes_reads_to_the_owned_store(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "spine")
    assert isinstance(be._read_store(), ClickHouseBusinessEventStore)
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "shadow")
    assert type(be._read_store()).__name__ == "_ShadowBusinessEventStore"


def test_shadow_serves_primary_and_does_not_raise(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = _to_row()  # one event in the in-process store
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(rows=[]))
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "shadow")
    served = be._read_store().list(agent_id="recouvrement")
    # served from the primary in-process store (owned is empty → divergence is logged, not raised)
    assert len(served) == 1
    assert served[0].conversation_id == row["conversation_id"]


# --- owned-store erasure (G4) ----------------------------------------------------


def test_delete_business_events_counts_then_deletes_with_bound_params() -> None:
    adapter = _offline_adapter()
    calls: list[tuple[str, dict[str, str] | None]] = []

    def _execute(
        query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
    ) -> str:
        calls.append((query, params))
        return "3\n" if query.startswith("SELECT") else ""

    adapter.execute = _execute  # type: ignore[method-assign]
    assert adapter.delete_business_events("conv-9") == 3
    assert len(calls) == 2
    assert calls[0][0].startswith("SELECT count()")
    assert calls[1][0].startswith("DELETE FROM tessera.business_events")
    assert calls[0][1] == {"conv": "conv-9"} == calls[1][1]  # value-bound, never inline


def test_delete_business_events_zero_rows_skips_delete() -> None:
    adapter = _offline_adapter()
    calls: list[str] = []
    adapter.execute = (  # type: ignore[method-assign]
        lambda query, *_args, **_kwargs: calls.append(query) or "0\n"
    )
    assert adapter.delete_business_events("unknown") == 0
    assert len(calls) == 1  # count only — no pointless mutation


def test_purge_owned_business_events_defers_when_unreachable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _down(_conversation_id: str) -> int:
        raise SpineUnavailableError("down")

    monkeypatch.setattr(erasure, "_owned_business_events_delete", _down)
    deleted, reached = erasure.purge_owned_business_events("conv-1")
    assert deleted == 0
    assert reached is False  # deferred and reported — never faked


def test_purge_telemetry_folds_the_business_events_leg(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(erasure.replay_mod, "purge_conversation", lambda _c: 1)
    monkeypatch.setattr(erasure.scores_mod, "purge_conversation", lambda _c: 3)
    monkeypatch.setattr(erasure, "_owned_scores_delete", lambda _c: 3)
    monkeypatch.setattr(erasure, "_owned_business_events_delete", lambda _c: 4)
    monkeypatch.setattr(erasure, "_spine_delete", lambda _c: 2)
    fp = erasure.purge_telemetry("conv-1")
    assert fp.n_owned_business_events == 4
    assert fp.owned_business_events_reached is True


# --- dual-write wiring -----------------------------------------------------------


def test_record_business_event_dual_writes_the_owned_row(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import tessera.observability.clickhouse_business_events as cbe

    captured: list[dict[str, object]] = []
    monkeypatch.setattr(cbe, "record_business_event_row", lambda row: captured.append(dict(row)))
    reset_business_event_store()
    record_business_event(
        event_name=BusinessEventName.INTENT_ROUTED,
        agent_id="recouvrement",
        conversation_id="conv-dw",
        turn_id="turn-dw",
    )
    assert len(captured) == 1
    assert captured[0]["event_name"] == "intent.routed"
    assert captured[0]["conversation_id"] == "conv-dw"


# --- backfill inserts exactly the difference -------------------------------------


def test_backfill_inserts_exactly_the_difference(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from scripts import backfill_owned_business_events as bf

    present = {
        "timestamp": "2026-07-02T16:01:25.317934+00:00",
        "event_name": "business_rule.checked",
        "agent_id": "recouvrement",
        "conversation_id": "conv-1",
        "turn_id": "t1",
        "artifact_id": "",
        "reason_codes": [],
        "payload": {},
    }
    missing = {
        **present,
        "timestamp": "2026-07-02T16:01:28.570000+00:00",
        "event_name": "artifact.created",
        "artifact_id": "a9",
    }
    monkeypatch.setattr(bf, "_source_rows", lambda: [present, missing])

    inserts: list[bytes] = []

    class _BackfillAdapter:
        business_events_table = "tessera.business_events"

        def ensure_business_events_schema(self) -> None:
            pass

        def execute(
            self, query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
        ) -> str:
            if query.startswith("SELECT"):
                return (
                    '{"occurred_at":"2026-07-02 16:01:25.317","agent_id":"recouvrement",'
                    '"event_name":"business_rule.checked","conversation_id":"conv-1",'
                    '"turn_id":"t1","artifact_id":""}\n'
                )
            assert data is not None
            inserts.append(data)
            return ""

    total, inserted, skipped = bf.backfill_business_events(_BackfillAdapter())  # type: ignore[arg-type]
    assert (total, inserted, skipped) == (2, 1, 0)
    assert b"artifact.created" in inserts[0] and b"business_rule.checked" not in inserts[0]
