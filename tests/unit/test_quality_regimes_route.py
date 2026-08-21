"""/observability/quality-regimes — the declared regime of every agent (ADR 0017 A4).

The route is the read seam between the manifest declaration and the quality band. These
tests pin its two promises: every registry agent appears with the regime it DECLARED
(never one inferred from wiring), and the two rulers' populations never share a field —
business counts exist exactly on the ``business_scored`` entries, and no figure in the
response aggregates across regimes.
"""

from __future__ import annotations

from tessera.agent.registry import list_agents
from tessera.api.routes.observability import observability_quality_regimes
from tessera.observability.agentspec_projection import (
    declares_telemetry,
    quality_regime_descriptor,
)


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
