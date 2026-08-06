"""The observability CHAIN — who feeds whom, and what each link's silence costs.

:mod:`tessera.observability.stack_components` answers *is each component alive?* and the page
built on it renders twenty independent rows. Twenty independent rows is structurally unable to
express the fact an operator most needs at 3 a.m.: **the collector is one node and it carries
two signals**, so its death takes traces *and* remote-profile metrics with it, while business
events — inserted straight into ClickHouse (ADR 0017 §5) — keep flowing. A flat list shows
three red dots and no reason; a chain shows one dead node and two consequences.

**Declared from the configs that actually wire it, never guessed.** Every edge below cites the
file that establishes it, and the citation travels to the screen. This is ADR 0026 applied to a
drawing: a diagram is a claim about the system, and a claim whose evidence a reader cannot
reach is decoration. Three of these edges are the opposite of what a reader would assume:

* ``agent → prometheus`` is **direct** — Prometheus scrapes the agent's own ``/metrics`` on the
  ``tessera-agent`` job. The in-process profile's metrics do **not** cross the collector, so a
  dead collector does not blind them. The remote profile's do (job ``remote-agent-metrics``,
  the collector's ``:8889`` exporter), and that is a second, separate edge.
* ``agent → clickhouse`` is **direct insert**, no collector, no OTLP. ADR 0017 §5 decided this.
* ``clickhouse`` is shared: Tessera's business events **and** Langfuse's own storage live in
  it, so its loss is felt in two unrelated places on the page.

**Consequences are declared here and resolved from the live probe.** The mapping
"store → what the cockpit can no longer answer" is a fact about *this codebase* — it comes from
reading which module queries which store — so it is written down and cited. The *verdict* on
each consequence is computed from the component's own probe, never declared: a page that states
a consequence it did not measure is the over-claim this project forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from tessera.preflight import Verdict

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = [
    "AGENT_NODE",
    "CHAIN_EDGES",
    "CHAIN_NODES",
    "CONSEQUENCES",
    "ChainEdge",
    "ChainNode",
    "Consequence",
    "ConsequenceState",
    "Signal",
    "Stage",
    "consequence_states",
    "reachable_signals",
]

#: Where a node sits in the chain, left to right. The stage is the layout, and it is declared
#: rather than inferred from the edges: a node with no live edge (``langfuse-worker``, which
#: publishes no host port) still has a place in the picture, and a graph layout computed from
#: edges alone would drop it exactly when it is the thing that broke.
Stage = Literal["emitter", "pipeline", "store", "viewer"]

#: What travels an edge. Four kinds, because they fail independently and an operator acts on
#: them differently: ``traces`` (per-turn spans), ``metrics`` (aggregates), ``events`` (the
#: business-event ledger), ``state`` (a component's own working storage).
Signal = Literal["traces", "metrics", "events", "state"]

#: The emitter. Not a member of ``STACK_COMPONENTS`` — nothing probes it from outside, because
#: the answer to this very request IS the probe: an agent that did not serve it could not report
#: on anything. Its verdict is therefore ``ok`` by construction, which is stated on the node
#: rather than left for the reader to infer.
AGENT_NODE: Final = "agent"


@dataclass(frozen=True, slots=True)
class ChainNode:
    """One node of the observability chain, and where it sits."""

    key: str
    stage: Stage
    #: The signals this node handles at all — used to grey a node out for a signal it never
    #: carries, rather than drawing it as a healthy participant in a pipeline it is not in.
    carries: tuple[Signal, ...]


@dataclass(frozen=True, slots=True)
class ChainEdge:
    """One declared link, and the file that establishes it."""

    source: str
    target: str
    signal: Signal
    #: The configuration that wires this edge, repo-relative. Travels to the UI so a reader can
    #: check the drawing against the system instead of trusting it.
    declared_in: str
    #: ``None`` when the edge exists in every deployment; a profile name when it exists only in
    #: one. An edge that is absent by design must not read as an edge that is broken.
    profile: str | None = None


#: The nodes. Ordered emitter → pipeline → stores → viewers, which is also the reading order.
CHAIN_NODES: Final[tuple[ChainNode, ...]] = (
    ChainNode(AGENT_NODE, "emitter", ("traces", "metrics", "events", "state")),
    ChainNode("otel-collector", "pipeline", ("traces", "metrics")),
    ChainNode("prometheus", "store", ("metrics",)),
    ChainNode("clickhouse", "store", ("events", "traces")),
    ChainNode("postgres", "store", ("state",)),
    ChainNode("redis", "store", ("state",)),
    ChainNode("minio", "store", ("traces",)),
    ChainNode("langfuse-db", "store", ("state",)),
    ChainNode("langfuse-redis", "store", ("state",)),
    ChainNode("phoenix", "viewer", ("traces",)),
    ChainNode("langfuse-web", "viewer", ("traces",)),
    ChainNode("langfuse-worker", "pipeline", ("traces",)),
    ChainNode("grafana", "viewer", ("metrics",)),
)

_COLLECTOR_CONF: Final = "infra/observability/otel-collector/collector.onprem.yaml"
_PROM_CONF: Final = "infra/observability/prometheus/prometheus.yml"
_OBS_COMPOSE: Final = "docker-compose.obs.claude.yml"

#: The edges, each citing the file that wires it.
CHAIN_EDGES: Final[tuple[ChainEdge, ...]] = (
    # ── traces: OTLP into the collector, redacted, fanned out to two backends ──────────────
    ChainEdge(AGENT_NODE, "otel-collector", "traces", f"{_COLLECTOR_CONF} · receivers.otlp"),
    ChainEdge(
        "otel-collector", "phoenix", "traces", f"{_COLLECTOR_CONF} · exporters.otlphttp/phoenix"
    ),
    ChainEdge(
        "otel-collector",
        "langfuse-web",
        "traces",
        f"{_COLLECTOR_CONF} · exporters.otlphttp/langfuse",
    ),
    ChainEdge("langfuse-web", "langfuse-worker", "traces", f"{_OBS_COMPOSE} · langfuse-worker"),
    ChainEdge("langfuse-worker", "clickhouse", "traces", f"{_OBS_COMPOSE} · CLICKHOUSE_URL"),
    ChainEdge(
        "langfuse-worker", "minio", "traces", f"{_OBS_COMPOSE} · LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT"
    ),
    ChainEdge("langfuse-web", "langfuse-db", "state", f"{_OBS_COMPOSE} · DATABASE_URL"),
    ChainEdge("langfuse-web", "langfuse-redis", "state", f"{_OBS_COMPOSE} · REDIS_HOST"),
    # ── metrics: TWO paths into Prometheus, and only one of them crosses the collector ─────
    ChainEdge(AGENT_NODE, "prometheus", "metrics", f"{_PROM_CONF} · job tessera-agent"),
    ChainEdge(
        AGENT_NODE,
        "otel-collector",
        "metrics",
        f"{_COLLECTOR_CONF} · pipelines.metrics",
        profile="remote",
    ),
    ChainEdge(
        "otel-collector",
        "prometheus",
        "metrics",
        f"{_PROM_CONF} · job remote-agent-metrics",
        profile="remote",
    ),
    ChainEdge("prometheus", "grafana", "metrics", "infra/observability/grafana/provisioning"),
    # ── events and working state: straight from the agent, no pipeline in between ──────────
    ChainEdge(
        AGENT_NODE,
        "clickhouse",
        "events",
        "src/tessera/observability/clickhouse_business_events.py (ADR 0017 §5)",
    ),
    ChainEdge(AGENT_NODE, "postgres", "state", "src/tessera/ledger — the ledger's own connect"),
    ChainEdge(AGENT_NODE, "redis", "state", "src/tessera/settings.py · redis"),
)


@dataclass(frozen=True, slots=True)
class Consequence:
    """What the cockpit stops being able to answer when a component goes quiet.

    The mapping is a fact about this repository — read off the module that queries the store —
    so ``reads`` names that module and the screen shows it. What is *not* declared is the
    verdict: :func:`consequence_states` computes it from the live probe.
    """

    key: str
    #: Every component the answer needs. Silence in ANY of them costs the capability, which is
    #: why this is a tuple and not a single key: turn evidence has two sources and loses its
    #: certainty when either one cannot be asked (ADR 0017 §4 Amendment 3).
    needs: tuple[str, ...]
    #: The module that actually performs the read. The citation, so the claim is checkable.
    reads: str
    #: True when losing this capability can *block an agent* rather than merely blank a chart.
    #: An operator triages on this and on nothing else.
    gates_agents: bool = False


#: What each store underwrites. Ordered by what it costs to lose it.
CONSEQUENCES: Final[tuple[Consequence, ...]] = (
    Consequence(
        "turn-evidence",
        ("prometheus", "clickhouse"),
        "src/tessera/observability/turn_evidence.py",
        gates_agents=True,
    ),
    Consequence(
        "business-events",
        ("clickhouse",),
        "src/tessera/observability/business_events.py",
        gates_agents=True,
    ),
    Consequence(
        "aggregates",
        ("prometheus",),
        "src/tessera/observability/spine/adapters/prometheus.py",
    ),
    Consequence(
        "ledger",
        ("postgres",),
        "src/tessera/ledger",
        gates_agents=True,
    ),
    Consequence(
        "traces",
        ("otel-collector", "phoenix"),
        f"{_COLLECTOR_CONF} · pipelines.traces",
    ),
    Consequence(
        "llm-observability",
        ("langfuse-web", "clickhouse"),
        "src/tessera/observability/langfuse_obs.py",
    ),
    Consequence(
        "dashboards",
        ("grafana", "prometheus"),
        "infra/observability/grafana/provisioning",
    ),
)

#: A capability's standing. Deliberately the same three-valued alphabet the probe speaks, and
#: for the same reason: ``cannot_say`` is not ``lost``. An operator restarts a component for the
#: first and investigates their own vantage point for the second.
ConsequenceState = Literal["served", "lost", "cannot_say"]

#: Verdict → what it does to a capability that needs that component. ``skip`` (a precondition
#: deliberately not applicable here) never reaches this map: only stack components do.
_FROM_VERDICT: Final[dict[Verdict, ConsequenceState]] = {
    Verdict.OK: "served",
    Verdict.FAIL: "lost",
    Verdict.BLIND: "cannot_say",
    Verdict.SKIP: "cannot_say",
}


def _worst(states: Iterable[ConsequenceState]) -> ConsequenceState:
    """The state a capability actually has, given each component's contribution.

    ``lost`` outranks ``cannot_say`` outranks ``served``: knowing one dependency is down is a
    stronger fact than not being able to see another, and both outrank the good news. A
    capability with no dependency at all could only arise from a mis-declaration, and answering
    ``cannot_say`` for it is the honest degradation.
    """
    ranked = list(states)
    if not ranked:
        return "cannot_say"
    if "lost" in ranked:
        return "lost"
    return "cannot_say" if "cannot_say" in ranked else "served"


def consequence_states(verdicts: Mapping[str, Verdict]) -> dict[str, ConsequenceState]:
    """Resolve every declared consequence against what the probe actually observed.

    Args:
        verdicts: Component key → the verdict its own probe returned, as
            :func:`tessera.observability.stack_components.probe_stack` produced it.

    Returns:
        Consequence key → its state. A dependency the probe never reported on yields
        ``cannot_say`` for the whole capability rather than being skipped: a missing witness is
        a blind spot, never a pass (ADR 0026).
    """
    return {
        consequence.key: _worst(
            _FROM_VERDICT.get(verdicts[need], "cannot_say") if need in verdicts else "cannot_say"
            for need in consequence.needs
        )
        for consequence in CONSEQUENCES
    }


def _node_state(key: str, verdicts: Mapping[str, Verdict]) -> ConsequenceState:
    """One node's contribution to any path through it.

    The emitter is ``served`` by construction: this code is running inside it, so an agent that
    could not emit could not be answering. Stating that is honest; probing ourselves from
    ourselves and calling it evidence would not be.
    """
    if key == AGENT_NODE:
        return "served"
    return _FROM_VERDICT.get(verdicts[key], "cannot_say") if key in verdicts else "cannot_say"


def reachable_signals(verdicts: Mapping[str, Verdict]) -> dict[Signal, ConsequenceState]:
    """Per signal, whether it still gets from the agent to somewhere it is kept.

    Walked as a PATH from the emitter, not tallied edge by edge — and the difference is the
    whole point of drawing a chain. Edge-by-edge, ``langfuse-worker → minio`` between two
    healthy nodes reads as traces flowing, while upstream the collector is dead and nothing has
    arrived for an hour. Two healthy nodes downstream of a break are not a working pipeline;
    they are two healthy nodes with nothing to do.

    A signal is ``served`` when at least one unbroken path reaches a sink (metrics reach
    Prometheus by two independent routes, so a dead collector does not lose them), ``lost`` when
    every path is severed, and ``cannot_say`` when the best surviving path runs through a node
    nobody could interrogate.

    ``state`` is excluded — a component's private storage is not a signal travelling the
    observability chain, and folding it in would answer a different question.
    """
    signals: dict[Signal, ConsequenceState] = {}
    for signal in {edge.signal for edge in CHAIN_EDGES} - {"state"}:
        edges = [edge for edge in CHAIN_EDGES if edge.signal == signal]
        sources = {edge.source for edge in edges}
        # Best state achievable on a path from the emitter to each node, relaxed until stable.
        # The chain is a handful of nodes deep; a fixed point costs nothing and needs no
        # assumption that the declaration happens to be topologically ordered.
        best: dict[str, ConsequenceState] = {AGENT_NODE: _node_state(AGENT_NODE, verdicts)}
        for _ in range(len(CHAIN_NODES)):
            changed = False
            for edge in edges:
                upstream = best.get(edge.source)
                if upstream is None:
                    continue
                candidate = _worst((upstream, _node_state(edge.target, verdicts)))
                if _best((candidate, best.get(edge.target, "lost"))) != best.get(edge.target):
                    best[edge.target] = _best((candidate, best.get(edge.target, "lost")))
                    changed = True
            if not changed:
                break
        # Only where the signal comes to REST: a healthy hop halfway down a severed chain is
        # not delivery, and counting it as one is the edge-by-edge error above.
        sinks = [node for node in best if node != AGENT_NODE and node not in sources]
        signals[signal] = _best(best[node] for node in sinks) if sinks else "cannot_say"
    return signals


def _best(states: Iterable[ConsequenceState]) -> ConsequenceState:
    """The best of several independent paths — one working route is enough to carry a signal."""
    ranked = list(states)
    if not ranked:
        return "cannot_say"
    if "served" in ranked:
        return "served"
    return "cannot_say" if "cannot_say" in ranked else "lost"
