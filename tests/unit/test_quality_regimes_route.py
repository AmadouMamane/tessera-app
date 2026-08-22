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


def test_each_plane_carries_counts_in_its_own_field_and_no_other() -> None:
    # Disjointness at the seam: `business` exists exactly on the business_scored entries,
    # `judged` exactly on the llm_judged ones — so no consumer can even reach for a figure
    # that would mix the two rulers, and both counts stay in their plane's own unit.
    for entry in _entries().values():
        if entry["regime"] == "business_scored":
            assert isinstance(entry["business"], dict)
        else:
            assert entry["business"] is None
        if entry["regime"] == "llm_judged":
            judged = entry["judged"]
            assert isinstance(judged, dict)
            assert isinstance(judged["responses_total"], int)
            # Recency rides the count (ADR 0052): a total without WHEN the ruler last
            # spoke reads as alive when it may be a fossil. Both bounds, or honestly None.
            assert judged["since"] is None or isinstance(judged["since"], str)
            assert judged["last_scored_at"] is None or isinstance(judged["last_scored_at"], str)
        else:
            assert entry["judged"] is None
        if entry["regime"] == "business_scored":
            business = entry["business"]
            assert isinstance(business, dict)
            assert business["since"] is None or isinstance(business["since"], str)
            assert business["last_event_at"] is None or isinstance(business["last_event_at"], str)


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


def test_each_store_is_read_once_for_its_whole_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The scaling ratchet, on BOTH planes: the event ledger costs ONE read whether 1 or 30
    # agents declare business_scored, and the score log costs ONE read for every llm_judged
    # agent. A per-agent read would make the route's cost grow with the fleet — correct at
    # a handful of agents, wrong by construction at 200 (operator requirement, 2026-08-22).
    ledger_calls: list[dict[str, object]] = []
    score_calls: list[tuple[object, ...]] = []

    def _recording_ledger(**kwargs: object) -> list[dict[str, object]]:
        ledger_calls.append(dict(kwargs))
        return []

    def _recording_scores(*args: object, **kwargs: object) -> list[dict[str, object]]:
        score_calls.append((args, kwargs))
        return []

    monkeypatch.setattr(signals.business_events_mod, "business_event_rows", _recording_ledger)
    # `from x import y` copies the name: the route calls ITS module-level `read_scores`.
    monkeypatch.setattr(signals, "read_scores", _recording_scores)
    monkeypatch.setattr(signals, "list_agents", lambda: _fleet_with_business_clones(30))

    payload = observability_quality_regimes()

    assert len(ledger_calls) == 1
    # The one read is the GROUPED one — unscoped, distributed afterwards by the rows' own
    # agent_id — never a scoped read that would have to be repeated per agent.
    assert ledger_calls[0].get("agent_id") is None
    # And the score log: one unscoped FULL-history read (the live ring is a 200-row cut —
    # counting "since the beginning" over it would be a window in name only).
    assert len(score_calls) == 1
    assert score_calls[0][0][1] is None
    assert score_calls[0][1] == {"full": True}
    regimes = payload["regimes"]
    assert isinstance(regimes, list)
    business = [e for e in regimes if e["regime"] == "business_scored"]
    assert len(business) == 30
    assert all(isinstance(e["business"], dict) for e in business)


def test_judged_counts_come_from_each_agents_own_faithfulness_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A judged response is one faithfulness verdict of that agent's own: another metric's
    # row, another agent's row, and the org-only rows (agent_id None — pre-tagging
    # history) must not inflate the count.
    scores = [
        {
            "metric": "faithfulness",
            "agent_id": "support-client",
            "scored_at": "2026-08-10T09:00:00+00:00",
        },
        {
            "metric": "faithfulness",
            "agent_id": "support-client",
            "scored_at": "2026-06-01T09:00:00+00:00",
        },
        {
            "metric": "faithfulness",
            "agent_id": "onboarding",
            "scored_at": "2026-07-15T09:00:00+00:00",
        },
        {
            "metric": "relevancy",
            "agent_id": "support-client",
            "scored_at": "2026-08-20T09:00:00+00:00",
        },
        {"metric": "faithfulness", "agent_id": None, "scored_at": "2026-08-21T09:00:00+00:00"},
        {
            "metric": "faithfulness",
            "agent_id": "recouvrement",
            "scored_at": "2026-08-21T09:00:00+00:00",
        },
    ]
    monkeypatch.setattr(signals, "read_scores", lambda *_a, **_k: list(scores))

    entries = _entries()
    support = entries["support-client"]["judged"]
    onboarding = entries["onboarding"]["judged"]
    assert isinstance(support, dict) and support["responses_total"] == 2
    # First and last are the agent's OWN faithfulness bounds — the later relevancy row and
    # the org-only row must not move them.
    assert support["since"] == "2026-06-01T09:00:00+00:00"
    assert support["last_scored_at"] == "2026-08-10T09:00:00+00:00"
    assert isinstance(onboarding, dict) and onboarding["responses_total"] == 1
    # A business_scored agent has no judged field at all — even with a stray score row.
    assert entries["recouvrement"]["judged"] is None


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
