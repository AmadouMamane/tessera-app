"""Prometheus metrics exposed by the agent.

The metric set is deliberately small; ``docs/runbook.md`` documents what
each one is good for. We expose them via the standard ``/metrics`` endpoint
on a separate port (default ``9090``) so the API process never serves both
business traffic and scraping on the same socket.
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

from tessera.settings import get_settings

__all__ = [
    "AGENT_TURN_DURATION",
    "AGENT_TURNS_TOTAL",
    "BUDGET_GAUGE",
    "CITATIONS_TOTAL",
    "ESCALATIONS_TOTAL",
    "GUARD_DECISIONS_TOTAL",
    "LANGGRAPH_NODE_DURATION",
    "LANGUAGE_MISMATCHES_TOTAL",
    "LLM_COST_EUR_TOTAL",
    "LLM_TOKENS_TOTAL",
    "MEMORY_DEGRADATIONS_TOTAL",
    "OBSERVABILITY_COMPLETENESS",
    "PROOF_CONSENSUS",
    "RETRIEVAL_DOCUMENTS_TOTAL",
    "SENSITIVE_ACTION_TRANSACTIONS_TOTAL",
    "configure",
    "registry",
]


registry = CollectorRegistry(auto_describe=True)


AGENT_TURNS_TOTAL = Counter(
    "tessera_agent_turns_total",
    "Number of agent turns processed, partitioned by language and outcome.",
    labelnames=("language", "outcome"),
    registry=registry,
)

AGENT_TURN_DURATION = Histogram(
    "tessera_agent_turn_duration_seconds",
    "Latency of a single agent turn, end to end.",
    labelnames=("language",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

GUARD_DECISIONS_TOTAL = Counter(
    "tessera_guard_decisions_total",
    "Number of guard decisions emitted, partitioned by tool and verdict.",
    labelnames=("target", "decision"),
    registry=registry,
)

ESCALATIONS_TOTAL = Counter(
    "tessera_escalations_total",
    "Number of human escalations created by the agent.",
    labelnames=("language", "outcome"),
    registry=registry,
)

RETRIEVAL_DOCUMENTS_TOTAL = Counter(
    "tessera_retrieval_documents_total",
    "Number of retrieved documents returned to agent workers.",
    labelnames=("target", "language"),
    registry=registry,
)

CITATIONS_TOTAL = Counter(
    "tessera_citations_total",
    "Number of citations surfaced to the reporter.",
    labelnames=("target", "language"),
    registry=registry,
)

LLM_TOKENS_TOTAL = Counter(
    "tessera_llm_tokens_total",
    "Number of LLM tokens consumed by direction.",
    labelnames=("backend", "model", "direction"),
    registry=registry,
)

LLM_COST_EUR_TOTAL = Counter(
    "tessera_llm_cost_eur_total",
    "Estimated LLM cost in EUR.",
    labelnames=("backend", "model"),
    registry=registry,
)

MEMORY_DEGRADATIONS_TOTAL = Counter(
    "tessera_memory_degradations_total",
    "Number of memory operations that degraded gracefully.",
    labelnames=("operation", "reason"),
    registry=registry,
)

LANGUAGE_MISMATCHES_TOTAL = Counter(
    "tessera_language_mismatches_total",
    "Number of turns whose resolved language differed from the pinned hint.",
    labelnames=("expected", "actual"),
    registry=registry,
)

SENSITIVE_ACTION_TRANSACTIONS_TOTAL = Counter(
    "tessera_sensitive_action_transactions_total",
    "Sensitive action transactions by target and state.",
    labelnames=("target", "state"),
    registry=registry,
)

BUDGET_GAUGE = Gauge(
    "tessera_llm_estimated_cost_eur",
    "Running estimate of LLM cost for the active process.",
    registry=registry,
)

LANGGRAPH_NODE_DURATION = Histogram(
    "tessera_langgraph_node_duration_seconds",
    "Latency of a single LangGraph node.",
    labelnames=("node", "outcome"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

OBSERVABILITY_COMPLETENESS = Gauge(
    "tessera_observability_completeness",
    "Current process-level observability completeness score from 0.0 to 1.0.",
    labelnames=("profile", "assurance_level"),
    registry=registry,
)

PROOF_CONSENSUS = Gauge(
    "tessera_proof_consensus",
    "Current process-level proof consensus score from 0.0 to 1.0.",
    labelnames=("profile", "assurance_level"),
    registry=registry,
)


_started: bool = False


def configure() -> None:
    """Start the Prometheus HTTP server once per process."""
    global _started
    if _started:
        return
    settings = get_settings().observability
    if not settings.metrics_enabled:
        return
    start_http_server(settings.metrics_port, registry=registry)
    _started = True
