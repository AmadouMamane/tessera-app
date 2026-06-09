"""Cost of observability itself (ADR 0010, idea #84).

Instrumentation is not free: every span allocates, sets attributes, and is
queued for export. If observing a turn costs a meaningful slice of the turn's own
latency budget, the telemetry has become part of the problem. This module makes
that overhead a *measured number* rather than an act of faith.

:func:`measure_overhead` micro-benchmarks the real OpenTelemetry SDK span
lifecycle (start, set a few ``gen_ai.*`` attributes, end) against an isolated
no-export tracer, then projects it onto a whole turn (a handful of node and tool
spans) and compares it to the turn's latency budget. It also estimates the
telemetry *volume* a turn emits. The honest framing: this is the cost of *making*
the spans in-process — wire/export cost lives in the Collector, off the hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns

from opentelemetry.sdk.trace import TracerProvider

__all__ = ["ObsCostReport", "measure_overhead"]

# A grounded turn emits roughly this many spans: router + planner + a few worker
# nodes (invoke_agent) + tool calls (execute_tool) + the chat span + reviewer.
_SPANS_PER_TURN = 8
# Rough on-wire size of one span with a dozen attributes (OTLP/protobuf).
_BYTES_PER_SPAN = 512
# The end-to-end latency budget we hold a turn to (see metrics histogram buckets).
_TURN_BUDGET_MS = 2000.0
# Overhead under this fraction of the budget is comfortably within budget.
_BUDGET_FRACTION_OK = 0.01  # 1 %
_DEFAULT_ITERATIONS = 2000
_DEFAULT_WARMUP = 200


@dataclass(frozen=True, slots=True)
class ObsCostReport:
    """Measured instrumentation overhead projected onto a turn."""

    iterations: int
    span_overhead_us: float  # mean wall-time to create+end one instrumented span
    spans_per_turn: int
    overhead_per_turn_ms: float
    turn_budget_ms: float
    overhead_pct_of_budget: float  # overhead as a % of the turn budget
    est_bytes_per_span: int
    est_bytes_per_turn: int
    within_budget: bool


def measure_overhead(
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    warmup: int = _DEFAULT_WARMUP,
    spans_per_turn: int = _SPANS_PER_TURN,
) -> ObsCostReport:
    """Micro-benchmark span overhead and project it onto a turn.

    Uses an isolated :class:`TracerProvider` with no span processors, so the
    benchmark measures span *creation* cost only (no export), and never touches
    the process's real telemetry pipeline.

    Args:
        iterations: Number of timed span lifecycles.
        warmup: Untimed iterations first, to settle caches/JIT-like effects.
        spans_per_turn: Spans a representative turn emits.

    Returns:
        An :class:`ObsCostReport` with the per-span overhead and its projection.
    """
    iterations = max(1, iterations)
    provider = TracerProvider()  # no processors → spans are created but not exported
    tracer = provider.get_tracer("tessera.obs-cost-benchmark")

    def _emit() -> None:
        with tracer.start_as_current_span("benchmark") as span:
            span.set_attribute("gen_ai.system", "tessera")
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("tessera.profile", "on_prem")

    for _ in range(max(0, warmup)):
        _emit()

    start = perf_counter_ns()
    for _ in range(iterations):
        _emit()
    elapsed_ns = perf_counter_ns() - start

    span_overhead_us = elapsed_ns / iterations / 1000.0
    overhead_per_turn_ms = span_overhead_us * spans_per_turn / 1000.0
    overhead_pct = (overhead_per_turn_ms / _TURN_BUDGET_MS * 100.0) if _TURN_BUDGET_MS > 0 else 0.0

    return ObsCostReport(
        iterations=iterations,
        span_overhead_us=span_overhead_us,
        spans_per_turn=spans_per_turn,
        overhead_per_turn_ms=overhead_per_turn_ms,
        turn_budget_ms=_TURN_BUDGET_MS,
        overhead_pct_of_budget=overhead_pct,
        est_bytes_per_span=_BYTES_PER_SPAN,
        est_bytes_per_turn=_BYTES_PER_SPAN * spans_per_turn,
        within_budget=overhead_pct < _BUDGET_FRACTION_OK * 100.0,
    )
