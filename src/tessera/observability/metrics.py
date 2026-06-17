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
    "EVAL_SCORE",
    "GUARD_DECISIONS_TOTAL",
    "configure",
    "registry",
]


registry = CollectorRegistry(auto_describe=True)


AGENT_TURNS_TOTAL = Counter(
    "tessera_agent_turns_total",
    "Number of agent turns processed, partitioned by agent, language and outcome.",
    labelnames=("agent_id", "language", "outcome"),
    registry=registry,
)

AGENT_TURN_DURATION = Histogram(
    "tessera_agent_turn_duration_seconds",
    "Latency of a single agent turn, end to end, partitioned by agent.",
    labelnames=("agent_id", "language"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

GUARD_DECISIONS_TOTAL = Counter(
    "tessera_guard_decisions_total",
    "Number of guard decisions emitted, partitioned by tool and verdict.",
    labelnames=("target", "decision"),
    registry=registry,
)

BUDGET_GAUGE = Gauge(
    "tessera_llm_estimated_cost_eur",
    "Running estimate of LLM cost for the active process.",
    registry=registry,
)

EVAL_SCORE = Histogram(
    "tessera_eval_score",
    "Online evaluation scores, partitioned by metric and language (ADR 0010 #5).",
    labelnames=("metric", "language"),
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
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
