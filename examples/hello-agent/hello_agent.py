"""hello-agent — the ADR 0017 §F acceptance test (second-runtime proof).

A minimal agent that reaches observability **L1** with a **zero tessera import**: it speaks
only OTLP to the collector — turn **spans** carrying the full L1 Scope-dimension contract, and
a turn **counter** that becomes the cockpit's L1 turn-evidence in Prometheus. No LangGraph, no
cockpit code, no shared runtime. Onboarding it is a manifest entry + this process + config.

Run (obs stack up, collector on :4418):

    uv run python examples/hello-agent/hello_agent.py

Env: ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://localhost:4418``), ``HELLO_TURNS``
(default 12), ``DEPLOYMENT_ENVIRONMENT`` (default ``demo``).
"""

from __future__ import annotations

import os
import time
import uuid

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

AGENT_ID = "hello-agent"
ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4418").rstrip("/")
ENVIRONMENT = os.environ.get("DEPLOYMENT_ENVIRONMENT", "demo")
_LANGUAGES = ("fr", "de", "en")

# The L1 turn-span Scope-dimension contract — the exact semconv keys
# tessera.observability.semconv.REQUIRED_TURN_SPAN_ATTRIBUTES declares. We hard-code the
# strings (not import them) precisely to prove a remote agent needs no tessera import.
_ATTR_AGENT_ID = "tessera.agent_id"
_ATTR_LANGUAGE = "tessera.language"
_ATTR_CONVERSATION_ID = "gen_ai.conversation.id"
_ATTR_TURN_ID = "tessera.turn_id"
_ATTR_ENVIRONMENT = "deployment.environment"
_ATTR_MODEL = "gen_ai.request.model"  # conditional dimension


def _build_providers() -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({"service.name": AGENT_ID, "deployment.environment": ENVIRONMENT})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{ENDPOINT}/v1/traces"))
    )
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{ENDPOINT}/v1/metrics"), export_interval_millis=2000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    return tracer_provider, meter_provider


def run_turn(tracer: trace.Tracer, turns_counter: metrics.Counter, language: str) -> None:
    """Process one turn: emit a contract-conformant turn span + increment the turn counter."""
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    turn_id = f"turn-{uuid.uuid4().hex[:8]}"
    with tracer.start_as_current_span("invoke_agent") as span:
        span.set_attribute(_ATTR_AGENT_ID, AGENT_ID)
        span.set_attribute(_ATTR_LANGUAGE, language)
        span.set_attribute(_ATTR_CONVERSATION_ID, conversation_id)
        span.set_attribute(_ATTR_TURN_ID, turn_id)
        span.set_attribute(_ATTR_ENVIRONMENT, ENVIRONMENT)
        span.set_attribute(_ATTR_MODEL, "hello-echo-v1")
        time.sleep(0.02)  # "process" the turn
    # The counter the collector re-exports as tessera_agent_turns_total{agent_id=…} —
    # the exact fact the cockpit resolver reads to award L1 (ADR 0017 §F).
    turns_counter.add(1, {"agent_id": AGENT_ID, "language": language, "outcome": "answered"})


def main() -> None:
    """Emit turns to the collector.

    One-shot batch (``HELLO_TURNS`` turns then exit) by default; a **continuous** profile — a
    turn every ``HELLO_INTERVAL_S`` seconds, forever — when that env is set, so a long-running
    agent keeps its turn metric fresh (a real agent does exactly this).
    """
    tracer_provider, meter_provider = _build_providers()
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    tracer = trace.get_tracer(AGENT_ID)
    turns_counter = meter_provider.get_meter(AGENT_ID).create_counter(
        "tessera_agent_turns", description="Agent turns processed.", unit="1"
    )

    interval = os.environ.get("HELLO_INTERVAL_S")
    if interval:
        step = float(interval)
        print(f"hello-agent: continuous — one turn every {step}s to {ENDPOINT} (SIGTERM to stop)")
        i = 0
        while True:
            run_turn(tracer, turns_counter, _LANGUAGES[i % len(_LANGUAGES)])
            i += 1
            time.sleep(step)

    n = int(os.environ.get("HELLO_TURNS", "12"))
    for i in range(n):
        run_turn(tracer, turns_counter, _LANGUAGES[i % len(_LANGUAGES)])

    tracer_provider.force_flush()
    meter_provider.force_flush()
    tracer_provider.shutdown()
    meter_provider.shutdown()
    print(f"hello-agent: emitted {n} turns (spans + tessera_agent_turns) to {ENDPOINT}")


if __name__ == "__main__":
    main()
