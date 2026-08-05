"""ADR 0017 §5 / Phase D — the owned ClickHouse business-event store (offline).

Locks the Phase-D mechanism without a live ClickHouse: the JSONEachRow line + dedup key are
pure; the read store rebuilds ``BusinessEvent`` s and **refuses** when unreachable rather than
answering the empty list (which would assert the agent emitted nothing — see
``test_an_unreachable_store_refuses_rather_than_reporting_empty``); the
per-fact flip routes reads (owned default → local override → shadow); GDPR erasure reaches the owned
business-event table (count-then-delete, bound params, deferred-never-faked); the dual-write
is best-effort and gated; the backfill inserts exactly the difference.
"""

from __future__ import annotations

import pytest

from tessera.authz import Actor
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
        # kind=operator says a HUMAN ordered this, so the author must BE one. Pairing an
        # `operator` kind with a system author is now a hard error, and it is worth saying why
        # that is not pedantry: the old envelope could not express the contradiction at all —
        # one field answered both questions, so "a human did it" and "the system did it" were
        # the same string, and nothing could ever have caught them disagreeing.
        author=Actor(principal="julie@bank.eu", role="collections"),
        event_name=BusinessEventName.BUSINESS_RULE_CHECKED,
        agent_id="recouvrement",
        conversation_id="conv-be",
        turn_id="turn-be",
        workflow_id="recouvrement_collections_v1",
        decision="allowed",
        payload={"rule_id": "contact_window"},
        actor_kind="operator",
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
    assert events[0].actor_kind == "operator"
    assert stub.calls[0]["agent_id"] == "recouvrement"  # filter pushed through


def test_an_unreachable_store_refuses_rather_than_reporting_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """ "Honest-empty when unreachable" was the one thing an empty list cannot be.

    This assertion used to read ``list(...) == []`` under the name *honest empty*, and the name
    was the bug: ``[]`` is the claim *this agent emitted nothing*, and a store that did not
    answer is not entitled to make it. Downstream it became a computed L0, and on 2026-08-05
    the fleet's release column had just learned to block an agent below its required rung — so
    an outage would have printed a measured-sounding refusal over a blind spot (ADR 0026).
    """
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(down=True))
    with pytest.raises(be.BusinessEventsUnavailableError):
        ClickHouseBusinessEventStore().list(agent_id="recouvrement")


def test_the_display_read_still_degrades_to_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Positive control on the other half: pages that only SHOW rows must keep rendering.

    The distinction is for callers who *interpret* emptiness. A table does not, so it keeps the
    old shape — this is why the refusal above did not have to be paid for at every call site.
    """
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "spine")
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(down=True))
    assert be.business_event_rows(agent_id="recouvrement") == []


def test_the_interpreting_read_says_it_could_not_see(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """And the two are told apart by the same call, not by a second guess at the store."""
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "spine")
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(down=True))
    blind = be.business_event_read(agent_id="recouvrement")
    assert blind.rows == []
    assert blind.readable is False
    assert blind.blind is True


def test_a_readable_store_that_holds_nothing_is_not_blind(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Negative control — without it, ``readable`` could be a field that is always False.

    An empty answer and no answer are the two states this whole change exists to separate, so
    the test suite has to exhibit both, and from the same seam.
    """
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "spine")
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(rows=[]))
    read = be.business_event_read(agent_id="recouvrement")
    assert read.rows == []
    assert read.readable is True
    assert read.blind is False


# --- per-fact flip routing -------------------------------------------------------


def test_reads_default_to_the_owned_store(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
    monkeypatch.delenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", raising=False)
    assert isinstance(be._read_store(), ClickHouseBusinessEventStore)


def test_local_override_routes_reads_to_the_in_process_store(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "local")
    assert type(be._read_store()).__name__ == "InMemoryBusinessEventStore"


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
        author=Actor.system("test-fixture"),
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


# --- ADR 0019 §4 · the synthetic mark must cross the owned medium ----------------
#
# `business_events` defaults to `spine` (see `_FACT_DEFAULTS`), so ClickHouse — not the
# in-process store — is the DEFAULT read medium. Between that flip and the `synthetic`
# column, the write dropped the mark and the read rebuilt every row as real: a canary
# turn's events were served to every business surface as genuine. These tests are the
# regression lock on both legs plus the migration that repairs an existing table.


def test_line_carries_the_synthetic_mark_as_uint8() -> None:
    import json

    base = {"timestamp": "2026-07-02T16:01:25+00:00", "event_name": "intent.routed"}
    real = business_event_line(base)
    canary = business_event_line({**base, "synthetic": True})
    assert real is not None and canary is not None
    assert json.loads(real)["synthetic"] == 0
    assert json.loads(canary)["synthetic"] == 1


def test_ch_row_mapper_rebuilds_the_synthetic_mark() -> None:
    ch_row = {
        "occurred_at": "2026-07-02 16:01:25.317",
        "event_name": "business_rule.checked",
        "agent_id": "recouvrement",
        "conversation_id": "conv-1",
        "turn_id": "t1",
    }
    assert ch_mod._business_row_from_ch(ch_row)["synthetic"] is False  # absent → real
    assert ch_mod._business_row_from_ch({**ch_row, "synthetic": 0})["synthetic"] is False
    assert ch_mod._business_row_from_ch({**ch_row, "synthetic": 1})["synthetic"] is True


def test_read_seam_excludes_a_synthetic_row_served_by_the_owned_store(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The whole point: a canary row in the owned table must not reach a business surface."""
    monkeypatch.delenv("TESSERA_SPINE_SOURCE", raising=False)
    monkeypatch.delenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", raising=False)  # default = spine
    with be.synthetic_turn():
        canary = _to_row()
    assert canary["synthetic"] is True  # the emit path stamped it
    monkeypatch.setattr(ch_mod, "ClickHouseAdapter", lambda *_a, **_k: _StubAdapter(rows=[canary]))

    rebuilt = ClickHouseBusinessEventStore().list(agent_id="recouvrement")
    assert [event.synthetic for event in rebuilt] == [True]  # survives the round trip
    assert be.persisted_business_events(agent_id="recouvrement") == []  # and is excluded
    assert len(be.persisted_business_events(agent_id="recouvrement", include_synthetic=True)) == 1


def test_ddl_declares_the_synthetic_column() -> None:
    assert "synthetic        UInt8 DEFAULT 0" in ch_mod.business_events_ddl("tessera")


def test_ensure_business_events_schema_migrates_an_existing_table() -> None:
    """`CREATE TABLE IF NOT EXISTS` cannot add a column — a pre-column table needs the ALTER."""
    adapter = _offline_adapter()
    queries: list[str] = []
    adapter.execute = lambda query, *_a, **_k: queries.append(query) or ""  # type: ignore[method-assign,return-value]
    adapter.ensure_business_events_schema()
    assert queries[0].startswith("CREATE DATABASE IF NOT EXISTS")
    assert queries[1].startswith("CREATE TABLE IF NOT EXISTS")
    assert queries[2] == (
        "ALTER TABLE tessera.business_events ADD COLUMN IF NOT EXISTS synthetic UInt8 DEFAULT 0"
    )
