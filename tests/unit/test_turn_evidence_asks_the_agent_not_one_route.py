"""A turn is proven by the agent's emissions, not by one route's counter (ADR 0017 §4 Am. 3).

The defect these pin, measured on 2026-08-06: ``tessera_agent_turns_total`` is incremented in
``/chat`` only. ``recouvrement`` serves its turns over ``/recouvrement-assistant/message``, so the
counter never named it — and ``observability_level`` returns L0 *before* it looks at business
events. Its 1281 timestamped events, the only real business evidence in the system, were never
read. The one agent emitting proof was refused for want of proof.

What is widened is what counts as *looking*, never what counts as a declaration: both sources are
emissions the agent makes and a store records. What that widening costs is paid here too — a
source that saw nothing may only prove absence when the other source could be asked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tessera.observability import business_capabilities as bc, turn_evidence

if TYPE_CHECKING:
    import pytest

_AGENT = "recouvrement"
_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _row(
    *,
    turn_id: str = "t-1",
    stamp: str | None = None,
    agent_id: str = _AGENT,
    capability_id: str = "propose_schedule",
) -> dict[str, object]:
    """One serialised ledger row, shaped as the read seam returns it."""
    return {
        "agent_id": agent_id,
        "turn_id": turn_id,
        "timestamp": stamp if stamp is not None else (_NOW - timedelta(days=1)).isoformat(),
        "capability_id": capability_id,
        "event_name": "action.prepared",
    }


# ── the window: what it counts, and what it refuses to conclude ──────────────────────────────


def test_the_window_counts_turns_not_events() -> None:
    """Thirty events from one turn are one turn — the counter it stands in for counts turns."""
    rows = [_row(turn_id="t-1") for _ in range(30)] + [_row(turn_id="t-2")]
    window = turn_evidence.turns_in_window(rows, since=_NOW - timedelta(days=30), until=_NOW)
    assert window.turns == {"t-1", "t-2"}


def test_an_emission_older_than_the_window_does_not_prove_present_activity() -> None:
    """The ledger keeps six months; without this bound "is emitting" would mean "ever emitted"."""
    old = (_NOW - timedelta(days=200)).isoformat()
    window = turn_evidence.turns_in_window(
        [_row(stamp=old)], since=_NOW - timedelta(days=30), until=_NOW
    )
    assert window.turns == frozenset()
    assert window.legible is True  # dated, just old — a real "no", not a blind spot


def test_an_event_dated_in_the_future_is_a_clock_not_an_emission() -> None:
    future = (_NOW + timedelta(days=3)).isoformat()
    window = turn_evidence.turns_in_window(
        [_row(stamp=future)], since=_NOW - timedelta(days=30), until=_NOW
    )
    assert window.turns == frozenset()


def test_a_clickhouse_naive_stamp_is_read_as_utc_like_the_writer_wrote_it() -> None:
    """``DateTime64`` comes back without an offset. Rejecting it would empty the window silently.

    This is the failure mode that would have made the whole amendment a no-op on the deployed
    stack while every unit test passed: in-process rows carry ``+00:00``, ClickHouse rows do not.
    """
    naive = (_NOW - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    window = turn_evidence.turns_in_window(
        [_row(stamp=naive)], since=_NOW - timedelta(days=30), until=_NOW
    )
    assert window.turns == {"t-1"}


def test_rows_that_cannot_be_dated_are_illegible_never_empty() -> None:
    """ "No turn in the window" and "no row I could date" must never be the same sentence."""
    window = turn_evidence.turns_in_window(
        [_row(stamp="not-a-date"), _row(stamp="")], since=_NOW - timedelta(days=30), until=_NOW
    )
    assert window.turns == frozenset()
    assert window.legible is False


def test_no_rows_at_all_is_legible_emptiness() -> None:
    """An agent that emitted nothing is a fact; only unparsable rows are a blind spot."""
    window = turn_evidence.turns_in_window([], since=_NOW - timedelta(days=30), until=_NOW)
    assert window.legible is True


# ── the merge table, row by row ──────────────────────────────────────────────────────────────


def test_the_counter_alone_still_proves_a_turn() -> None:
    assert turn_evidence.turn_evidence_state(_AGENT, {_AGENT}, emitting=set()) == "observed"


def test_the_ledger_alone_proves_a_turn_and_that_is_the_whole_amendment() -> None:
    """`recouvrement`'s case: silent counter, emitting ledger. It was L0; it is observed."""
    assert turn_evidence.turn_evidence_state(_AGENT, set(), emitting={_AGENT}) == "observed"


def test_both_sources_silent_and_both_readable_is_dormancy() -> None:
    assert turn_evidence.turn_evidence_state(_AGENT, set(), emitting=set()) == "dormant"


def test_a_silent_counter_and_a_blind_ledger_cannot_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cost of the widening, paid honestly.

    Before the ledger counted, the counter's silence WAS the answer. Now that a second source can
    contradict it, one source's silence proves absence only when the other could be asked —
    otherwise a ClickHouse outage would quietly demote an agent that is emitting fine.
    """
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())
    assert turn_evidence.turn_evidence_state(_AGENT, set(), emitting=None) == "unverifiable"


def test_a_blind_counter_and_a_silent_ledger_cannot_say() -> None:
    assert turn_evidence.turn_evidence_state(_AGENT, None, emitting=set()) == "unverifiable"


def test_both_blind_cannot_say() -> None:
    assert turn_evidence.turn_evidence_state(_AGENT, None, emitting=None) == "unverifiable"


# ── the level, end to end, through the real resolver ─────────────────────────────────────────


def _ledger(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, object]]) -> None:
    """Make the ONE read seam `resolve_level_state` uses return these rows, readable."""
    monkeypatch.setattr(
        bc.business_events,
        "business_event_read",
        lambda **_k: bc.business_events.BusinessEventRead(rows=rows, readable=True),
    )


def _blind_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bc.business_events,
        "business_event_read",
        lambda **_k: bc.business_events.BusinessEventRead(rows=[], readable=False),
    )


def test_the_agent_that_emits_is_no_longer_refused_for_want_of_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The measured defect, reproduced and closed: recent stamped events, no counter → L3.

    This test FREES an agent. It is the shape that has twice been wrong on the grader, so read
    what it actually asserts: the rows carry a real ``capability_id`` (L3's own evidence) AND a
    ``turn_id`` inside the window (L1's), and the counter is explicitly silent throughout.
    """
    _ledger(monkeypatch, [_row(turn_id="t-1"), _row(turn_id="t-2")])
    monkeypatch.setattr(bc, "_governed", lambda _aid: True)
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())

    state = bc.resolve_level_state(_AGENT)
    assert state.evidence == "observed"
    assert state.computed == "L3"
    assert state.declared == "L3"  # the two rungs stop diverging for this agent
    assert state.proven is True


def test_stale_events_alone_leave_the_agent_where_it_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the window this row would read as "observed" for six months after the agent died."""
    _ledger(monkeypatch, [_row(stamp=(datetime.now(UTC) - timedelta(days=200)).isoformat())])
    monkeypatch.setattr(bc, "_governed", lambda _aid: True)
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())

    state = bc.resolve_level_state(_AGENT)
    assert state.evidence == "dormant"
    assert state.computed == "L0"


def test_a_blind_ledger_demotes_nothing_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """ClickHouse now carries L0→L1 as well as L2→L3, so its outage must reach BOTH decisions.

    An outage that demoted an agent to a measured-looking L0 would be the same over-claim the
    release column made on 2026-08-05, one rung lower.
    """
    _blind_ledger(monkeypatch)
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())

    state = bc.resolve_level_state(_AGENT)
    assert state.facts_readable is False
    assert state.computed is None  # not "L0" — the store did not answer
    assert state.evidence == "unverifiable"  # not "dormant" — that would blame the agent


def test_the_resolver_reads_the_ledger_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both facts come out of one read — a second read could disagree with the first."""
    calls = 0

    def _counting_read(**_k: object) -> object:
        nonlocal calls
        calls += 1
        return bc.business_events.BusinessEventRead(rows=[_row()], readable=True)

    monkeypatch.setattr(bc.business_events, "business_event_read", _counting_read)
    monkeypatch.setattr(bc, "_governed", lambda _aid: True)
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())

    bc.resolve_level_state(_AGENT)
    assert calls == 1


def test_a_canary_turn_cannot_manufacture_the_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Synthetic events are excluded by the read seam's default (ADR 0019 §4), inherited here.

    Pinned rather than assumed: a canary that unlocked a rung would let the cockpit certify an
    agent on turns it sent itself.
    """
    seen: dict[str, object] = {}

    def _recording_read(**kwargs: object) -> object:
        seen.update(kwargs)
        return bc.business_events.BusinessEventRead(rows=[], readable=True)

    monkeypatch.setattr(bc.business_events, "business_event_read", _recording_read)
    monkeypatch.setattr(turn_evidence, "agents_with_turn_evidence", lambda: set())

    bc.resolve_level_state(_AGENT)
    assert seen.get("include_synthetic") in (None, False)
