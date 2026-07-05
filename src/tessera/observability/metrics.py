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
    "ACTION_BLOCKED_TOTAL",
    "ACTION_PREPARED_TOTAL",
    "ARTIFACT_CREATED_TOTAL",
    "ARTIFACT_STATUS_CHANGED_TOTAL",
    "BUDGET_GAUGE",
    "BUSINESS_EVENTS_TOTAL",
    "BUSINESS_RULE_CHECKED_TOTAL",
    "EVAL_SCORE",
    "GUARD_DECISIONS_TOTAL",
    "POLICY_DECISION_TOTAL",
    "SPINE_CACHE_HIT_RATIO",
    "SPINE_SHADOW_DIVERGENCE",
    "SPINE_SNAPSHOT_LATENCY",
    "SPINE_SNAPSHOT_UPSTREAM_READS",
    "VALIDATION_REQUESTED_TOTAL",
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
    "Number of guard decisions emitted, partitioned by tool, verdict and agent (ADR 0015).",
    labelnames=("target", "decision", "agent_id"),
    registry=registry,
)

BUDGET_GAUGE = Gauge(
    "tessera_llm_estimated_cost_eur",
    "Running estimate of LLM cost for the active process.",
    registry=registry,
)

EVAL_SCORE = Histogram(
    "tessera_eval_score",
    "Online evaluation scores, partitioned by metric, language, agent and model "
    "(ADR 0010 #5; agent_id + model added ADR 0015 §Migration B).",
    labelnames=("metric", "language", "agent_id", "model"),
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=registry,
)

BUSINESS_EVENTS_TOTAL = Counter(
    "tessera_business_events_total",
    "Business workflow events emitted, partitioned by agent, workflow, surface, "
    "event and decision.",
    labelnames=("agent_id", "workflow_id", "surface", "event_name", "decision"),
    registry=registry,
)

BUSINESS_RULE_CHECKED_TOTAL = Counter(
    "tessera_business_rule_checked_total",
    "Business-rule checks emitted by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "decision", "reason_code"),
    registry=registry,
)

POLICY_DECISION_TOTAL = Counter(
    "tessera_policy_decision_total",
    "Policy/compliance decisions emitted by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "decision", "reason_code"),
    registry=registry,
)

ARTIFACT_CREATED_TOTAL = Counter(
    "tessera_artifact_created_total",
    "Business artifacts created by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "artifact_type", "artifact_status"),
    registry=registry,
)

ARTIFACT_STATUS_CHANGED_TOTAL = Counter(
    "tessera_artifact_status_changed_total",
    "Business artifact status changes emitted by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "artifact_type", "artifact_status"),
    registry=registry,
)

VALIDATION_REQUESTED_TOTAL = Counter(
    "tessera_validation_requested_total",
    "Validation requests emitted by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "artifact_type", "artifact_status"),
    registry=registry,
)

ACTION_PREPARED_TOTAL = Counter(
    "tessera_action_prepared_total",
    "Business actions prepared by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "decision", "reason_code"),
    registry=registry,
)

ACTION_BLOCKED_TOTAL = Counter(
    "tessera_action_blocked_total",
    "Business actions blocked by specialised workflows.",
    labelnames=("agent_id", "workflow_id", "surface", "decision", "reason_code"),
    registry=registry,
)

# --- Spine snapshot self-instrumentation (ADR 0015 §Performance — we dogfood the spine) ---

SPINE_SNAPSHOT_LATENCY = Histogram(
    "tessera_spine_snapshot_latency_seconds",
    "Latency of a batched cockpit snapshot compute, partitioned by cache outcome.",
    labelnames=("cache",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0),
    registry=registry,
)

SPINE_SNAPSHOT_UPSTREAM_READS = Histogram(
    "tessera_spine_snapshot_upstream_reads",
    "Distinct upstream store reads per snapshot compute (the anti-fan-out budget).",
    buckets=(0, 1, 2, 3, 4, 5, 8, 13, 21),
    registry=registry,
)

SPINE_CACHE_HIT_RATIO = Gauge(
    "tessera_spine_cache_hit_ratio",
    "Running cache-hit ratio of the snapshot endpoint (served-from-cache / total).",
    registry=registry,
)

SPINE_SHADOW_DIVERGENCE = Counter(
    "tessera_spine_shadow_divergence_total",
    "Shadow-run reconciliation outcomes per fact type — jsonl (served) vs spine (compared). "
    "A signal graduates jsonl->spine only after parity holds (ADR 0015 §Migration C).",
    labelnames=("fact", "result"),
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
