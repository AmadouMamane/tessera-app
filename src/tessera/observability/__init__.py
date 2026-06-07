"""Observability primitives — logging, tracing, metrics.

Each submodule exposes a small, opinionated configure-once-then-use surface:

* :func:`logging.configure` sets up structlog with JSON or console rendering.
* :func:`traces.configure` wires OpenTelemetry to a Cloud Trace exporter.
* :func:`metrics.configure` starts the Prometheus exporter.

The functions are idempotent so that re-importing in tests does not register
duplicate handlers.
"""

from __future__ import annotations

from tessera.observability import (
    actions,
    context,
    digital_twin,
    evidence,
    instrumentation,
    langfuse,
    logging,
    metrics,
    privacy,
    profiles,
    schema,
    traces,
    verifier,
)

__all__ = [
    "context",
    "actions",
    "digital_twin",
    "evidence",
    "instrumentation",
    "langfuse",
    "logging",
    "metrics",
    "privacy",
    "profiles",
    "schema",
    "traces",
    "verifier",
]
