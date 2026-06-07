"""LangGraph wiring for the Tessera agent.

The graph flows:

.. code-block:: text

    START
      │
      ▼
    router        ─── classify language + intent
      │
      ▼
    planner       ─── decide which workers to run
      │
      ▼
    dispatch      ─── fan-out to selected workers (parallel)
      │   │   │
      │   │   └── account_lookup
      │   └────── regulation_lookup
      └────────── product_lookup, simulator, escalation_worker
      │
      ▼
    reviewer      ─── score grounding + safety; may set needs_escalation
      │
      ├── (needs_escalation) ──▶ escalation ──▶ END
      │
      ▼
    reporter      ─── render the final answer in the user's language
      │
      ▼
    END

Workers are deliberately defined as separate callables rather than a generic
``ToolNode`` because LangGraph's ``add_conditional_edges`` lets us
deterministically replay decisions during the regression harness — see
``eval/runner.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from tessera.agent import (
    planner as planner_module,
    reporter as reporter_module,
    reviewer as reviewer_module,
    router as router_module,
)
from tessera.agent.state import AgentState, NodeName, WorkerName
from tessera.agent.workers import (
    account_lookup as account_lookup_worker,
    escalation as escalation_worker,
    product_lookup as product_lookup_worker,
    regulation_lookup as regulation_lookup_worker,
    simulator as simulator_worker,
)
from tessera.observability.instrumentation import instrument_node
from tessera.observability.schema import TelemetrySpan

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

__all__ = ["build_graph", "compile_graph"]


# ---------------------------------------------------------------------------
# Worker dispatch table — each WorkerName maps to its node function.
# ---------------------------------------------------------------------------

_WORKER_NODES: dict[WorkerName, str] = {
    WorkerName.PRODUCT_LOOKUP: product_lookup_worker.NODE_NAME,
    WorkerName.REGULATION_LOOKUP: regulation_lookup_worker.NODE_NAME,
    WorkerName.ACCOUNT_LOOKUP: account_lookup_worker.NODE_NAME,
    WorkerName.SIMULATOR: simulator_worker.NODE_NAME,
    WorkerName.ESCALATION: escalation_worker.NODE_NAME,
}

_NODE_SPANS: dict[str, TelemetrySpan] = {
    NodeName.ROUTER.value: TelemetrySpan.ROUTER,
    NodeName.PLANNER.value: TelemetrySpan.PLANNER,
    NodeName.REVIEWER.value: TelemetrySpan.REVIEWER,
    NodeName.REPORTER.value: TelemetrySpan.REPORTER,
    product_lookup_worker.NODE_NAME: TelemetrySpan.PRODUCT_LOOKUP,
    regulation_lookup_worker.NODE_NAME: TelemetrySpan.REGULATION_LOOKUP,
    account_lookup_worker.NODE_NAME: TelemetrySpan.ACCOUNT_LOOKUP,
    simulator_worker.NODE_NAME: TelemetrySpan.SIMULATOR,
    escalation_worker.NODE_NAME: TelemetrySpan.ESCALATION,
}


def _route_after_router(state: AgentState) -> str:
    """Conditional edge: short-circuit to END when the injection guard blocked the input.

    The router writes a ``final_response`` and an empty ``plan`` when it
    detects a prompt-injection attempt. In that case we skip the LLM entirely.
    """
    if state.get("final_response") and state.get("plan") == []:
        return END
    return NodeName.PLANNER.value


def _route_after_planner(state: AgentState) -> list[str]:
    """Conditional edge: send the state to every worker selected by the plan.

    LangGraph treats a list of next-node names as a fan-out: each named node
    receives the same input state and their outputs are merged through the
    state's reducers.
    """
    plan = state.get("plan") or []
    if not plan:
        # Empty plan → nothing useful to do; jump straight to the reviewer so
        # it can decide whether to escalate or politely decline.
        return [NodeName.REVIEWER.value]
    return [_WORKER_NODES[name] for name in plan]


def _route_after_reviewer(state: AgentState) -> str:
    """Conditional edge: escalate to a human if the reviewer flagged it."""
    if state.get("needs_escalation", False):
        return NodeName.ESCALATION.value
    return NodeName.REPORTER.value


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph[AgentState]:
    """Construct (but do not compile) the agent's StateGraph.

    Returning the uncompiled graph lets tests inspect the topology and lets
    callers register custom checkpointers before compilation.
    """
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # Top-level nodes
    graph.add_node(
        NodeName.ROUTER.value,
        instrument_node(
            node=NodeName.ROUTER.value,
            span_name=_NODE_SPANS[NodeName.ROUTER.value],
            handler=router_module.run,
        ),
    )
    graph.add_node(
        NodeName.PLANNER.value,
        instrument_node(
            node=NodeName.PLANNER.value,
            span_name=_NODE_SPANS[NodeName.PLANNER.value],
            handler=planner_module.run,
        ),
    )
    graph.add_node(
        NodeName.REVIEWER.value,
        instrument_node(
            node=NodeName.REVIEWER.value,
            span_name=_NODE_SPANS[NodeName.REVIEWER.value],
            handler=reviewer_module.run,
        ),
    )
    graph.add_node(
        NodeName.REPORTER.value,
        instrument_node(
            node=NodeName.REPORTER.value,
            span_name=_NODE_SPANS[NodeName.REPORTER.value],
            handler=reporter_module.run,
        ),
    )

    # Workers — registered under the names declared in their modules so that
    # _route_after_planner's return values are valid node identifiers.
    graph.add_node(
        product_lookup_worker.NODE_NAME,
        instrument_node(
            node=product_lookup_worker.NODE_NAME,
            span_name=_NODE_SPANS[product_lookup_worker.NODE_NAME],
            handler=product_lookup_worker.run,
        ),
    )
    graph.add_node(
        regulation_lookup_worker.NODE_NAME,
        instrument_node(
            node=regulation_lookup_worker.NODE_NAME,
            span_name=_NODE_SPANS[regulation_lookup_worker.NODE_NAME],
            handler=regulation_lookup_worker.run,
        ),
    )
    graph.add_node(
        account_lookup_worker.NODE_NAME,
        instrument_node(
            node=account_lookup_worker.NODE_NAME,
            span_name=_NODE_SPANS[account_lookup_worker.NODE_NAME],
            handler=account_lookup_worker.run,
        ),
    )
    graph.add_node(
        simulator_worker.NODE_NAME,
        instrument_node(
            node=simulator_worker.NODE_NAME,
            span_name=_NODE_SPANS[simulator_worker.NODE_NAME],
            handler=simulator_worker.run,
        ),
    )
    graph.add_node(
        escalation_worker.NODE_NAME,
        instrument_node(
            node=escalation_worker.NODE_NAME,
            span_name=_NODE_SPANS[escalation_worker.NODE_NAME],
            handler=escalation_worker.run,
        ),
    )

    # Linear backbone
    graph.add_edge(START, NodeName.ROUTER.value)

    # After the router, either proceed to the planner or short-circuit to END
    # when the router's prompt-injection check blocked the input (final_response
    # is already written; no LLM call needed).
    graph.add_conditional_edges(
        NodeName.ROUTER.value,
        _route_after_router,
        path_map={
            NodeName.PLANNER.value: NodeName.PLANNER.value,
            END: END,
        },
    )

    # Planner → workers fan-out
    worker_targets = [*_WORKER_NODES.values(), NodeName.REVIEWER.value]
    graph.add_conditional_edges(
        NodeName.PLANNER.value,
        _route_after_planner,
        path_map={name: name for name in worker_targets},
    )

    # Every data-fetching worker rejoins at the reviewer.
    # escalation_worker is terminal (→ END only) and must be excluded here;
    # adding it to this loop would create a second edge to reviewer and cause
    # an infinite cycle when the reviewer routes back to escalation.
    for worker_name, worker_node in _WORKER_NODES.items():
        if worker_name is WorkerName.ESCALATION:
            continue
        graph.add_edge(worker_node, NodeName.REVIEWER.value)

    # Reviewer → escalation or reporter
    graph.add_conditional_edges(
        NodeName.REVIEWER.value,
        _route_after_reviewer,
        path_map={
            NodeName.ESCALATION.value: escalation_worker.NODE_NAME,
            NodeName.REPORTER.value: NodeName.REPORTER.value,
        },
    )

    graph.add_edge(NodeName.REPORTER.value, END)
    # Escalation produces a brief human-handoff message then terminates.
    graph.add_edge(escalation_worker.NODE_NAME, END)

    return graph


def compile_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Return a compiled, immediately invokable graph.

    Callers needing a checkpointer (persistent conversations) should build the
    graph manually with :func:`build_graph` and compile it themselves with the
    checkpointer of their choice.
    """
    return build_graph().compile()
