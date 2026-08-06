"""The chain says what a flat list of components structurally cannot.

Twenty independent rows can tell an operator that three things are red. They cannot tell them
that ONE thing is red and the other two are its consequence, and that is the sentence somebody
is trying to assemble in their head at 3 a.m. These tests pin the three facts that make the
drawing worth having — each of them the opposite of what a reader would assume, which is exactly
why the picture has to be declared from the configs rather than sketched from intuition:

* metrics reach Prometheus by TWO independent routes, so a dead collector does not blind them;
* business events never touch the collector at all (ADR 0017 §5, direct insert);
* a component nobody could interrogate degrades every capability that needs it to *cannot say*,
  never to *lost* and never to *served* (ADR 0026).
"""

from __future__ import annotations

from tessera.observability.stack_components import STACK_COMPONENTS
from tessera.observability.stack_topology import (
    AGENT_NODE,
    CHAIN_EDGES,
    CHAIN_NODES,
    CONSEQUENCES,
    consequence_states,
    reachable_signals,
)
from tessera.preflight import Verdict

_ALL_OK = {component.key: Verdict.OK for component in STACK_COMPONENTS}


def _with(**overrides: Verdict) -> dict[str, Verdict]:
    """Every component healthy except the named ones."""
    return {**_ALL_OK, **{key.replace("_", "-"): value for key, value in overrides.items()}}


def test_every_drawn_node_is_a_component_somebody_actually_probes() -> None:
    """A node with no probe is a drawing of a system rather than of this one."""
    probed = {component.key for component in STACK_COMPONENTS}
    drawn = {node.key for node in CHAIN_NODES} - {AGENT_NODE}
    assert drawn <= probed, f"drawn but never interrogated: {sorted(drawn - probed)}"


def test_every_edge_joins_two_declared_nodes() -> None:
    """An edge to a node that is not in the picture renders as a line into nothing."""
    known = {node.key for node in CHAIN_NODES}
    for edge in CHAIN_EDGES:
        assert edge.source in known, f"{edge.source} is an edge source but not a node"
        assert edge.target in known, f"{edge.target} is an edge target but not a node"


def test_every_edge_cites_where_it_is_declared() -> None:
    """The drawing is a claim; a claim whose evidence cannot be reached is decoration."""
    for edge in CHAIN_EDGES:
        assert edge.declared_in.strip(), f"{edge.source}->{edge.target} cites nothing"


def test_every_consequence_depends_only_on_probed_components() -> None:
    """A capability hanging off a component nobody probes can never be resolved."""
    probed = {component.key for component in STACK_COMPONENTS}
    for consequence in CONSEQUENCES:
        assert consequence.needs, f"{consequence.key} declares no dependency"
        unknown = set(consequence.needs) - probed
        assert not unknown, f"{consequence.key} needs un-probed {sorted(unknown)}"


def test_a_dead_collector_does_not_blind_the_metrics_it_never_carried() -> None:
    """The fact the flat table cannot express, and the one a reader gets wrong.

    Prometheus scrapes the agent's own ``/metrics`` directly (job ``tessera-agent``); only the
    remote profile's metrics ride the collector. Reporting metrics as lost when the collector
    dies would be false for the in-process profile — and sending an operator to restart the
    wrong thing is worse than saying nothing.
    """
    signals = reachable_signals(_with(otel_collector=Verdict.FAIL))
    assert signals["metrics"] == "served", "the direct scrape path survives the collector"
    assert signals["traces"] == "lost", "…and traces have no second route: they are gone"


def test_business_events_do_not_ride_the_collector() -> None:
    """ADR 0017 §5 decided direct insert; the picture has to agree with the decision."""
    assert consequence_states(_with(otel_collector=Verdict.FAIL))["business-events"] == "served"
    assert consequence_states(_with(clickhouse=Verdict.FAIL))["business-events"] == "lost"


def test_the_two_stores_turn_evidence_needs_are_both_named() -> None:
    """The consequence the operator actually pays for: an agent the door then refuses.

    Turn evidence merges Prometheus and the ledger (ADR 0017 §4 Amendment 3), and loses its
    certainty when EITHER cannot be asked. This is the row that carries ``gates_agents``.
    """
    turn_evidence = next(c for c in CONSEQUENCES if c.key == "turn-evidence")
    assert set(turn_evidence.needs) == {"prometheus", "clickhouse"}
    assert turn_evidence.gates_agents, "losing it can block an agent, not just blank a chart"
    assert consequence_states(_with(prometheus=Verdict.FAIL))["turn-evidence"] == "lost"
    assert consequence_states(_with(clickhouse=Verdict.FAIL))["turn-evidence"] == "lost"


def test_a_blind_probe_yields_cannot_say_and_never_ok() -> None:
    """ADR 0026 as an assertion: a witness that could not look may not report success."""
    states = consequence_states(_with(prometheus=Verdict.BLIND))
    assert states["turn-evidence"] == "cannot_say"
    assert states["aggregates"] == "cannot_say"
    assert states["business-events"] == "served", "an unrelated capability is untouched"


def test_a_failure_outranks_a_blind_spot_within_one_capability() -> None:
    """Knowing a dependency is down is a stronger fact than not being able to see another."""
    states = consequence_states(_with(prometheus=Verdict.BLIND, clickhouse=Verdict.FAIL))
    assert states["turn-evidence"] == "lost"


def test_a_component_missing_from_the_probe_is_a_blind_spot_not_a_pass() -> None:
    """The failure mode of a registry that iterates what it found, not what it declared."""
    states = consequence_states({})
    assert set(states.values()) == {"cannot_say"}


def test_a_dead_dashboard_does_not_mean_the_metrics_stopped_arriving() -> None:
    """Shipped wrong, found by re-auditing rather than by a report. Grafana is a VIEWER.

    ``reachable_signals`` treated "a node with no outgoing edge" as delivery — a fact about the
    drawing, not about the system. The only metrics leaf is Grafana, so a dead dashboard put
    *metrics no longer arrive* in the page's headline while Prometheus was storing them
    perfectly. Delivery is arrival at a node that KEEPS the signal, which is why `keeps` is a
    declared field and not `stage == "store"`.
    """
    assert reachable_signals(_with(grafana=Verdict.FAIL)) == {
        "traces": "served",
        "metrics": "served",
        "events": "served",
    }, "losing a dashboard costs a dashboard"
    assert (
        reachable_signals(_with(prometheus=Verdict.FAIL))["metrics"] == "lost"
    ), "…while losing the store that keeps them really does lose them"


def test_one_surviving_trace_store_is_enough() -> None:
    """Phoenix and Langfuse's ClickHouse both keep traces; either alone is still delivery."""
    assert reachable_signals(_with(phoenix=Verdict.FAIL))["traces"] == "served"
    assert (
        reachable_signals(_with(phoenix=Verdict.FAIL, clickhouse=Verdict.FAIL, minio=Verdict.FAIL))[
            "traces"
        ]
        == "lost"
    ), "only when every keeper is gone are the traces actually lost"


def test_every_signal_has_somewhere_to_be_kept() -> None:
    """A signal whose declaration names no keeper could only ever answer 'cannot say'.

    The negative control for the field above: adding a signal and forgetting to mark a keeper
    would make it permanently unreadable, which reads as a broken stack forever.
    """
    keepers = {node.key for node in CHAIN_NODES if node.keeps}
    carried = {edge.signal for edge in CHAIN_EDGES} - {"state"}
    for signal in carried:
        reachable = {
            node.key for node in CHAIN_NODES if signal in node.carries and node.key in keepers
        }
        assert reachable, f"{signal} travels the chain and no node declares that it keeps it"


def test_a_healthy_stack_serves_every_capability() -> None:
    """The negative control: the rules above must not be red on a system that is fine."""
    assert set(consequence_states(_ALL_OK).values()) == {"served"}
    assert set(reachable_signals(_ALL_OK).values()) == {"served"}


def test_a_components_own_read_can_only_degrade_its_capabilities() -> None:
    """ADR 0052 §Amendment 1.3 — the socket is the neighbourhood, the read is the thing.

    Three directions, one rule (`_worst` over both witnesses):

    * socket OK + read FAIL ⇒ lost — the 2026-08-06 Langfuse case, where a 200 on `/health`
      dressed an unreadable store as « assurée »;
    * socket OK + read BLIND ⇒ cannot_say — an unreachable read is a blind spot, not a pass;
    * socket FAIL + read OK ⇒ still lost — a stale green read must never resurrect a dead
      component, because the merge would otherwise be a way to launder a failure.
    """
    states = consequence_states(_ALL_OK, {"langfuse-web": Verdict.FAIL})
    assert states["llm-observability"] == "lost"

    states = consequence_states(_ALL_OK, {"clickhouse": Verdict.BLIND})
    assert states["business-events"] == "cannot_say"
    assert states["turn-evidence"] == "cannot_say", "both of its sources must be readable"

    states = consequence_states(_with(postgres=Verdict.FAIL), {"postgres": Verdict.OK})
    assert states["ledger"] == "lost"


def test_because_and_state_come_from_the_same_merge() -> None:
    """Two derivations of one verdict is how a column and a gate once came to disagree."""
    from tessera.observability.stack_topology import consequence_because

    reads = {"langfuse-web": Verdict.FAIL}
    states = consequence_states(_ALL_OK, reads)
    because = consequence_because(_ALL_OK, reads)
    for key, state in states.items():
        if state == "served":
            assert because[key] == [], f"{key} is served yet blames {because[key]}"
        else:
            assert because[key], f"{key} is {state} and names nobody to fix"


def test_a_read_witness_for_an_unprobed_component_is_still_not_a_pass() -> None:
    """A component the socket probe never saw stays cannot_say even with a green read.

    `_worst(cannot_say, served)` is `cannot_say`: half a witness is not a witness. The socket
    leg missing means the probe registry and the read map disagree about what exists, and the
    honest answer to a disagreement is that nothing may be claimed.
    """
    verdicts = {key: verdict for key, verdict in _ALL_OK.items() if key != "postgres"}
    states = consequence_states(verdicts, {"postgres": Verdict.OK})
    assert states["ledger"] == "cannot_say"
