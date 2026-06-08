"""Observability primitives — logging, tracing, metrics.

Each submodule exposes a small, opinionated configure-once-then-use surface:

* :func:`logging.configure` sets up structlog with JSON or console rendering.
* :func:`traces.configure` wires OpenTelemetry to a Cloud Trace exporter.
* :func:`metrics.configure` starts the Prometheus exporter.

The functions are idempotent so that re-importing in tests does not register
duplicate handlers.
"""

from __future__ import annotations

from tessera.observability import instrument, logging, metrics, semconv, traces

__all__ = ["instrument", "logging", "metrics", "semconv", "traces"]
