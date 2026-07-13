"""The dedup's "0 shared" must be reconciled against the journeys the S1 journal attests.

Found live on 2026-07-13: the ledger attested **34 handoffs over 34 conversations** while the
conversation store reported **zero** shared conversations — and the org-total footer rendered
"0 dédoublonnées · 0 conversations partagées (handoff = 1)" as though a reconciliation had
happened. It had not. ``OrgRollup.shared`` asks the conversation table about its OWN entities
("which of mine touch two agents?"), which reads 0 with total composure when the handed-off
journeys never share an id there at all — a witness answering about its neighbourhood
(ADR 0026) while the sentence it feeds claims to be about handoffs.

The fleet payload now carries both halves so the UI can state a gap instead of implying a
completed dedup: the journal side (``handoff_events`` + the exact conversation ids) and the
store side (how many of THOSE ids it can see under more than one agent). These tests pin each
half, and the seam between them.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tessera.observability.agent_scope import shared_entities_among
from tessera.observability.fleet import _handoff_counts

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
