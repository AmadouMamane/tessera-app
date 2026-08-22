"""/observability/quality-regimes — the declared regime of every agent (ADR 0017 A4).

The route is the read seam between the manifest declaration and the quality band. These
tests pin its two promises: every registry agent appears with the regime it DECLARED
(never one inferred from wiring), and the two rulers' populations never share a field —
business counts exist exactly on the ``business_scored`` entries, and no figure in the
response aggregates across regimes.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from tessera.agent.registry import get_agent, list_agents
from tessera.api.routes.observability import observability_quality_regimes, signals
from tessera.observability.agentspec_projection import (
    declares_telemetry,
    quality_regime_descriptor,
)

if TYPE_CHECKING:
    import pytest


def _entries() -> dict[str, dict[str, object]]:
    payload = observability_quality_regimes()
    regimes = payload["regimes"]
    assert isinstance(regimes, list)
    return {str(entry["agent_id"]): entry for entry in regimes}


def test_every_registry_agent_appears_with_its_declared_regime() -> None:
    entries = _entries()
    agents = list_agents()
    assert set(entries) == {a.id for a in agents}
    for agent in agents:
        declared = quality_regime_descriptor(agent)
        assert declared is not None
        entry = entries[agent.id]
        assert entry["regime"] == declared["regime"]
        assert entry["reason_key"] == declared["reason_key"]
        assert entry["name"] == agent.name
        # An unrated agent can still be a watched one: `observable` is the same declared
        # publish-activity contract the fleet card reads, riding along so the band can say
        # "not rated, still observed" instead of implying absence from the cockpit.
        assert entry["observable"] == declares_telemetry(agent)


def test_business_counts_exist_exactly_on_the_business_scored_plane() -> None:
    # Disjointness at the seam: an llm_judged or unscored entry carries NO business
    # counts, and a business_scored entry always carries them — so no consumer can even
    # reach for a figure that would mix the two rulers.
    for entry in _entries().values():
        if entry["regime"] == "business_scored":
            assert isinstance(entry["business"], dict)
        else:
            assert entry["business"] is None


def test_business_signal_counts_partition_the_declared_set() -> None:
    # scored/unknown/not_applicable is the scorer's closed vocabulary (ADR 0017 §A2.2):
    # the three counts must partition the declared signals, so a fourth status can never
    # leak in silently and make the counts stop summing to what was declared.
    entries = _entries()
    business = entries["recouvrement"]["business"]
    assert isinstance(business, dict)
    assert business["signals_declared"] == 10
    total = (
        int(business["signals_scored"])  # type: ignore[call-overload]
        + int(business["signals_unknown"])  # type: ignore[call-overload]
        + int(business["signals_not_applicable"])  # type: ignore[call-overload]
    )
    assert total == business["signals_declared"]
    assert isinstance(business["runs_total"], int)


def test_the_window_names_itself_as_all_history() -> None:
    # Instrumentation trap 2: an absent window reads as "some period". The response says
    # period_days: null out loud — all history, chosen, not assumed.
    payload = observability_quality_regimes()
    assert payload["window"] == {"period_days": None}


def _fleet_with_business_clones(count: int) -> list[object]:
    # A fleet where `count` agents declare business_scored: the real recouvrement plus
    # clones of it under fresh ids. `replace` keeps the declared manifest (and with it the
    # regime), so the route sees `count` distinct business-scored declarations.
    recouvrement = get_agent("recouvrement")
    assert recouvrement is not None
    clones = [
        replace(recouvrement, id=f"recouvrement-clone-{i}", name=f"Recouvrement {i}")
        for i in range(1, count)
    ]
    return [*list_agents(), *clones]


def test_the_ledger_is_read_once_for_the_whole_business_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The scaling ratchet: the ledger costs ONE read whether 1 or 30 agents declare
    # business_scored. A per-agent read would make the route's cost grow with the fleet —
    # correct at 1 agent, wrong by construction at 200 (operator requirement, 2026-08-22).
    calls: list[dict[str, object]] = []

    def _recording_read(**kwargs: object) -> list[dict[str, object]]:
        calls.append(dict(kwargs))
        return []

    monkeypatch.setattr(signals.business_events_mod, "business_event_rows", _recording_read)
    monkeypatch.setattr(signals, "list_agents", lambda: _fleet_with_business_clones(30))

    payload = observability_quality_regimes()

    assert len(calls) == 1
    # The one read is the GROUPED one — unscoped, distributed afterwards by the rows' own
    # agent_id — never a scoped read that would have to be repeated per agent.
    assert calls[0].get("agent_id") is None
    regimes = payload["regimes"]
    assert isinstance(regimes, list)
    business = [e for e in regimes if e["regime"] == "business_scored"]
    assert len(business) == 30
    assert all(isinstance(e["business"], dict) for e in business)


def test_the_grouped_read_distributes_rows_to_their_own_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Parity with the scoped read: each agent's counts must cover exactly ITS rows. Two
    # clones with distinct run counts prove the grouping key is the row's own agent_id —
    # a mis-grouped bucket would show up as a swapped or doubled runs_total.
    def _row(agent_id: str, conversation: str) -> dict[str, object]:
        return {
            "agent_id": agent_id,
            "conversation_id": conversation,
            "turn_id": f"{conversation}-t1",
            "event_name": "case.context_loaded",
            "timestamp": "2026-08-22T00:00:00+00:00",
        }

    ledger = [
        _row("recouvrement-clone-1", "c1"),
        _row("recouvrement-clone-1", "c2"),
        _row("recouvrement-clone-2", "c3"),
        _row("someone-else-entirely", "c4"),
    ]
    monkeypatch.setattr(
        signals.business_events_mod, "business_event_rows", lambda **_: list(ledger)
    )
    monkeypatch.setattr(signals, "list_agents", lambda: _fleet_with_business_clones(3))

    payload = observability_quality_regimes()
    regimes = payload["regimes"]
    assert isinstance(regimes, list)
    by_id = {str(e["agent_id"]): e for e in regimes}
    runs_of = {
        agent_id: by_id[agent_id]["business"]["runs_total"]  # type: ignore[index]
        for agent_id in ("recouvrement", "recouvrement-clone-1", "recouvrement-clone-2")
    }
    assert runs_of == {
        "recouvrement": 0,
        "recouvrement-clone-1": 2,
        "recouvrement-clone-2": 1,
    }
