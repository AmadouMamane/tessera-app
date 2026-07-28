"""Prometheus metrics exposed by the agent.

The metric set is deliberately small; ``docs/runbook.md`` documents what
each one is good for. We expose them via the standard ``/metrics`` endpoint
on a separate port (default ``9090``) so the API process never serves both
business traffic and scraping on the same socket.

**Multi-worker (ADR 0044).** When the agent runs as N uvicorn workers every worker processes
turns, so every worker increments the counters — and the L1/L2 level badges read
``tessera_agent_turns_total`` from Prometheus. A single worker sees only 1/N of the traffic,
so the counters MUST aggregate across the process group. That is what ``prometheus_client``'s
multiprocess mode does: with ``PROMETHEUS_MULTIPROC_DIR`` set (exported by
:func:`tessera.api.main.cli` before the workers spawn) each metric value is written to
per-pid mmap files, and the exposition endpoint reads them all back through a
:class:`~prometheus_client.multiprocess.MultiProcessCollector`, summing counters/histograms
across every worker. Recording needs no coordination; only the exposition HTTP server is
singular — exactly one worker (the advisory-lock leader) binds ``metrics_port``. In the
single-worker default the env var is unset and everything behaves exactly as before.
"""

from __future__ import annotations

import os

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
    # Multi-worker: keep only live workers' values (drop dead-pid files); ignored in the
    # single-process default. Cosmetic gauge, not read by any badge.
    multiprocess_mode="liveall",
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
    # Multi-worker: per-live-worker ratio (drop dead-pid files); ignored single-process.
    multiprocess_mode="liveall",
)

SPINE_SHADOW_DIVERGENCE = Counter(
    "tessera_spine_shadow_divergence_total",
    "Shadow-run reconciliation outcomes per fact type — jsonl (served) vs spine (compared). "
    "A signal graduates jsonl->spine only after parity holds (ADR 0015 §Migration C).",
    labelnames=("fact", "result"),
    registry=registry,
)


_started: bool = False


def _exposition_registry() -> CollectorRegistry:
    """The registry the ``/metrics`` server scrapes.

    Single process: the module registry, exactly as before. Multiprocess
    (``PROMETHEUS_MULTIPROC_DIR`` set): a fresh registry fed by
    :class:`~prometheus_client.multiprocess.MultiProcessCollector`, which reads every
    worker's mmap files and sums counters / aggregates gauges across the process group — so
    ``tessera_agent_turns_total`` reflects ALL workers, not the ``1/N`` a single one saw.
    """
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        aggregated = CollectorRegistry()
        multiprocess.MultiProcessCollector(aggregated)  # type: ignore[no-untyped-call]
        return aggregated
    return registry


def configure(*, serve: bool = True) -> None:
    """Bring metrics up for this process; bind the exposition server on the leader only.

    Every worker RECORDS metrics with no coordination — in multiprocess mode the module-level
    metric objects write their values to per-pid mmap files (see the module docstring). What
    is singular is the exposition HTTP server: exactly one process may bind ``metrics_port``.

    Args:
        serve: Whether THIS process is the one that binds ``metrics_port`` and serves
            ``/metrics``. Pass the advisory-lock leadership flag (the lone worker in the
            single-process default always leads → ``True``, identical to the old behaviour).
            When ``False`` this worker still records; it just does not open the socket, so N
            workers never fight over the port.
    """
    global _started
    if _started:
        return
    settings = get_settings().observability
    if not settings.metrics_enabled:
        return
    if not serve:
        _started = True  # recording happens via the mmap store; nothing to bind here
        return
    start_http_server(settings.metrics_port, registry=_exposition_registry())
    _started = True
