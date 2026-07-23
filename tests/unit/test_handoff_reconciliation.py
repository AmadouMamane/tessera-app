"""A fleet handoff must be a completed transition, not merely a raw ledger label.

Found live on 2026-07-13: the ledger attested **34 handoffs over 34 conversations** while the
conversation store reported **zero** shared conversations — and the org-total footer rendered
"0 dédoublonnées · 0 conversations partagées (handoff = 1)" as though a reconciliation had
happened. It had not. ``OrgRollup.shared`` asks the conversation table about its OWN entities
("which of mine touch two agents?"), which reads 0 with total composure when the handed-off
journeys never share an id there at all — a witness answering about its neighbourhood
(ADR 0026) while the sentence it feeds claims to be about handoffs.

The first correction exposed both halves so the UI could state that gap. The 2026-07-23 root
diagnosis then showed why all 37 live entries failed reconciliation: a brand-new Onboarding
conversation was routed from a technical Support default and logged as a handoff even though
Support never handled it. The fleet business counter now requires a prior source turn and the
persisted target turn; the raw immutable entries remain available as audit evidence. These tests
pin the raw journal seam, the completed-transition seam and both ledger modes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest

from tessera.observability.agent_scope import shared_entities_among
from tessera.observability.fleet import (
    HandoffClaim,
    _handoff_counts,
    _verified_file_handoff_rollup,
    _verified_handoff_rollup,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_ledger(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8"
    )


class TestTheJournalSide:
    """File mode: the scan must surface the journeys, not just the per-agent tallies."""

    def test_events_and_conversation_ids_come_back_with_the_counts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
        path = tmp_path / "audit.log"
        _write_ledger(
            path,
            [
                {"type": "tessera.guard.audit", "outcome": "allowed"},  # noise: not a handoff
                {
                    "type": "tessera.agent.handoff",
                    "from_agent": "support-client",
                    "to_agent": "onboarding",
                    "conversation_id": "conv-1",
                },
                {
                    "type": "tessera.agent.handoff",
                    "from_agent": "support-client",
                    "to_agent": "onboarding",
                    "conversation_id": "conv-1",  # a second transfer on the SAME journey
                },
                {
                    "type": "tessera.agent.handoff",
                    "from_agent": "onboarding",
                    "to_agent": "support-client",
                    "conversation_id": "conv-2",
                },
            ],
        )

        incoming, outgoing, events, conv_ids = _handoff_counts(path)

        assert incoming == {"onboarding": 2, "support-client": 1}
        assert outgoing == {"support-client": 2, "onboarding": 1}
        assert events == 3  # three transfers…
        assert conv_ids == {"conv-1", "conv-2"}  # …over two journeys: ids, never a bare count

    def test_a_handoff_without_a_conversation_id_still_counts_as_an_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An id-less event is a fact about the journal, not a reason to shrink the total."""
        monkeypatch.setenv("TESSERA_LEDGER_SOURCE", "file")
        path = tmp_path / "audit.log"
        _write_ledger(
            path,
            [{"type": "tessera.agent.handoff", "from_agent": "a", "to_agent": "b"}],
        )

        _incoming, _outgoing, events, conv_ids = _handoff_counts(path)

        assert events == 1
        assert conv_ids == set()


class _RecordingCursor:
    """Async-cursor double recording the SQL and its bound parameters."""

    def __init__(self, n: int) -> None:
        self.calls: list[tuple[str, object]] = []
        self._n = n

    async def execute(self, sql: str, params: object = None) -> None:
        self.calls.append((sql, params))

    async def fetchone(self) -> dict[str, Any]:
        return {"n": self._n}


class _RefusingCursor:
    """A cursor that fails the test the moment anybody queries it."""

    async def execute(self, sql: str, params: object = None) -> None:
        raise AssertionError("no query may run for an empty entity set")


class _VerifiedRollupCursor:
    """A cursor double for the bounded SQL reconciliation aggregate."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.calls: list[tuple[str, object]] = []
        self._rows = rows

    async def execute(self, sql: str, params: object = None) -> None:
        self.calls.append((sql, params))

    async def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class TestOnlyPersistedAgentTransitionsAreHandoffs:
    """A default route must never become a historical transfer fact."""

    @pytest.mark.asyncio
    async def test_the_aggregate_requires_a_prior_source_turn_and_the_persisted_target_turn(
        self,
    ) -> None:
        cur = _VerifiedRollupCursor(
            [
                {
                    "from_agent": "support-client",
                    "to_agent": "onboarding",
                    "events": 2,
                    "conversations": 1,
                }
            ]
        )

        rollup = await _verified_handoff_rollup(cur)  # type: ignore[arg-type]

        assert rollup.incoming == {"onboarding": 2}
        assert rollup.outgoing == {"support-client": 2}
        assert rollup.events == 2
        assert rollup.conversations == 1

        sql, params = cur.calls[0]
        assert params == ("tessera.agent.handoff",)
        assert "source.agent_id = claim.from_agent" in sql
        assert "source.created_at < claim.occurred_at" in sql
        assert "NOT source.synthetic" in sql
        assert "target.agent_id = claim.to_agent" in sql
        assert "target.turn_id::text = claim.turn_id" in sql
        assert "NOT target.synthetic" in sql

    @pytest.mark.asyncio
    async def test_the_file_escape_rejects_an_initial_route_with_only_a_target_turn(self) -> None:
        claim = HandoffClaim(
            conversation_id=UUID("11111111-1111-4111-8111-111111111111"),
            turn_id="22222222-2222-4222-8222-222222222222",
            from_agent="support-client",
            to_agent="onboarding",
            occurred_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        )
        cur = _VerifiedRollupCursor(
            [
                {
                    "conversation_id": str(claim.conversation_id),
                    "turn_id": claim.turn_id,
                    "agent_id": "onboarding",
                    "created_at": datetime(2026, 7, 23, 8, 0, 1, tzinfo=UTC),
                }
            ]
        )

        rollup = await _verified_file_handoff_rollup(cur, [claim])  # type: ignore[arg-type]

        assert rollup.events == 0
        assert rollup.conversations == 0
        assert rollup.incoming == {}
        assert rollup.outgoing == {}

    @pytest.mark.asyncio
    async def test_the_file_escape_keeps_a_real_transition_between_two_persisted_turns(
        self,
    ) -> None:
        claim = HandoffClaim(
            conversation_id=UUID("11111111-1111-4111-8111-111111111111"),
            turn_id="22222222-2222-4222-8222-222222222222",
            from_agent="support-client",
            to_agent="onboarding",
            occurred_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        )
        cur = _VerifiedRollupCursor(
            [
                {
                    "conversation_id": str(claim.conversation_id),
                    "turn_id": "00000000-0000-4000-8000-000000000000",
                    "agent_id": "support-client",
                    "created_at": datetime(2026, 7, 23, 7, 55, tzinfo=UTC),
                },
                {
                    "conversation_id": str(claim.conversation_id),
                    "turn_id": claim.turn_id,
                    "agent_id": "onboarding",
                    "created_at": datetime(2026, 7, 23, 8, 0, 1, tzinfo=UTC),
                },
            ]
        )

        rollup = await _verified_file_handoff_rollup(cur, [claim])  # type: ignore[arg-type]

        assert rollup.events == 1
        assert rollup.conversations == 1
        assert rollup.incoming == {"onboarding": 1}
        assert rollup.outgoing == {"support-client": 1}


class TestTheStoreSide:
    """`shared_entities_among` asks the table about the JOURNAL's entities — bound, validated."""

    @pytest.mark.asyncio
    async def test_it_reports_how_many_attested_journeys_the_table_sees_shared(self) -> None:
        cur = _RecordingCursor(n=1)

        seen = await shared_entities_among(
            cur,  # type: ignore[arg-type]
            table="conversation_messages",
            entity_col="conversation_id",
            entities={"conv-2", "conv-1", "conv-3"},
        )

        assert seen == 1  # the gap (3 attested, 1 seen) is the caller's sentence to render
        (sql, params) = cur.calls[0]
        assert "ANY(%s)" in sql, "the ids must travel as a bound parameter, never as SQL text"
        assert params == (["conv-1", "conv-2", "conv-3"],)  # sorted: deterministic on the wire
        assert "conv-1" not in sql

    @pytest.mark.asyncio
    async def test_an_empty_entity_set_answers_zero_without_a_query(self) -> None:
        seen = await shared_entities_among(
            _RefusingCursor(),  # type: ignore[arg-type]
            table="conversation_messages",
            entity_col="conversation_id",
            entities=(),
        )

        assert seen == 0

    @pytest.mark.asyncio
    async def test_it_rejects_unsafe_identifiers(self) -> None:
        with pytest.raises(ValueError, match="unsafe SQL identifier"):
            await shared_entities_among(
                _RecordingCursor(n=0),  # type: ignore[arg-type]
                table="conversation_messages; DROP TABLE x",
                entity_col="conversation_id",
                entities={"conv-1"},
            )
