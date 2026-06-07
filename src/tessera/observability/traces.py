"""OpenTelemetry tracing wiring.

The configure helper installs a tracer provider that exports to either:

* Cloud Trace (when ``observability.cloud_logging_project`` is set), or
* an OTLP gRPC collector pointed at ``observability.otel_endpoint``, or
* an in-process console exporter as a last-resort fallback for local dev.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult,
)

from tessera import __version__
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk.trace import ReadableSpan

__all__ = ["configure", "tracer"]

_configured: bool = False


class _NoopSpanExporter(SpanExporter):
    """Span exporter used in CI to avoid writing to closed pytest streams."""

    def export(self, _spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Drop spans successfully."""
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """No-op shutdown."""

    def force_flush(self, _timeout_millis: int = 30_000) -> bool:
        """No-op flush."""
        return True


def _resolve_exporter() -> SpanExporter:
    active = get_settings()
    settings = active.observability
    if active.environment.value == "ci":
        return _NoopSpanExporter()
    if settings.cloud_logging_project:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            return CloudTraceSpanExporter(project_id=settings.cloud_logging_project)  # type: ignore[no-untyped-call]
        except ImportError:
            pass
    if settings.otel_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=settings.otel_endpoint)
    return ConsoleSpanExporter()


def configure() -> None:
    """Install the tracer provider once per process."""
    global _configured
    if _configured:
        return
    settings = get_settings().observability
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": __version__,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_resolve_exporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def tracer(name: str = "tessera") -> trace.Tracer:
    """Return a tracer for ``name``, configuring on first call."""
    if not _configured:
        configure()
    return trace.get_tracer(name, __version__)
