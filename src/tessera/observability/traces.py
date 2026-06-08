"""OpenTelemetry tracing wiring (ADR 0010 backbone).

The configure helper installs a tracer provider whose exporter is chosen by the
observability *profile*, so the same instrumentation ships traces to either
deployment without a code change:

* ``profile = "gcp"`` with ``cloud_logging_project`` set → Cloud Trace.
* otherwise, an OTLP/HTTP endpoint (``otel_collector_endpoint`` or the legacy
  ``otel_endpoint``) → the OpenTelemetry Collector, which fans out to Phoenix /
  Langfuse on-prem.
* failing both, an in-process console exporter as a last-resort dev fallback.

Every span carries resource attributes — service, environment, profile, and the
data-residency tag the Collector uses to route EU-only (idea #3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from tessera import __version__
from tessera.observability.semconv import TESSERA_DATA_RESIDENCY, TESSERA_PROFILE
from tessera.settings import get_settings

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export import SpanExporter

__all__ = ["configure", "tracer"]

_configured: bool = False


def _resolve_exporter() -> SpanExporter:
    """Pick the span exporter for the active observability profile."""
    settings = get_settings().observability
    if settings.profile == "gcp" and settings.cloud_logging_project:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            return CloudTraceSpanExporter(project_id=settings.cloud_logging_project)  # type: ignore[no-untyped-call]
        except ImportError:
            pass
    endpoint = settings.otel_collector_endpoint or settings.otel_endpoint
    if endpoint:
        from urllib.parse import urlsplit

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        # The OTLP/HTTP exporter does not append the signal path to an explicit
        # endpoint, so a bare base URL (host:port, no path) is normalised to the
        # traces signal — the natural mental model for a "collector endpoint".
        if not urlsplit(endpoint).path.strip("/"):
            endpoint = endpoint.rstrip("/") + "/v1/traces"
        return OTLPSpanExporter(endpoint=endpoint)
    return ConsoleSpanExporter()


def configure() -> None:
    """Install the tracer provider once per process."""
    global _configured
    if _configured:
        return
    settings = get_settings()
    obs = settings.observability
    resource = Resource.create(
        {
            "service.name": obs.otel_service_name,
            "service.version": __version__,
            "deployment.environment": settings.environment.value,
            TESSERA_PROFILE: obs.profile,
            TESSERA_DATA_RESIDENCY: obs.data_residency,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = _resolve_exporter()
    # The console fallback is a dev convenience: export synchronously so spans
    # appear immediately and nothing is flushed to a closed stream at exit.
    processor = (
        SimpleSpanProcessor(exporter)
        if isinstance(exporter, ConsoleSpanExporter)
        else BatchSpanProcessor(exporter)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _configured = True


def tracer(name: str = "tessera") -> trace.Tracer:
    """Return a tracer for ``name``, configuring on first call."""
    if not _configured:
        configure()
    return trace.get_tracer(name, __version__)
