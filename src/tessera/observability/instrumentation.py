"""OpenTelemetry helpers for Tessera's assurance instrumentation."""

from __future__ import annotations

import inspect
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from tessera import __version__
from tessera.observability.context import (
    current_conversation_hash,
    current_request_id,
    current_turn_id,
)
from tessera.observability.metrics import LANGGRAPH_NODE_DURATION
from tessera.observability.privacy import sanitize_attributes
from tessera.observability.profiles import resolve_profile
from tessera.observability.traces import tracer
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from opentelemetry.util.types import AttributeValue

    from tessera.observability.schema import TelemetryEvent, TelemetrySpan

__all__ = [
    "current_trace_id",
    "emit_event",
    "instrument_node",
    "span_attributes",
    "start_span",
]


def _coerce_attribute(value: object) -> AttributeValue | None:
    """Coerce sanitized values into OpenTelemetry-compatible attributes."""
    if isinstance(value, str | bool | int | float):
        return value
    if value is None:
        return None
    if (
        isinstance(value, Sequence)
        and not isinstance(value, bytes | bytearray | str)
        and all(isinstance(item, str | bool | int | float) for item in value)
    ):
        return cast("AttributeValue", list(value))
    return str(value)


def span_attributes(attributes: Mapping[str, object] | None = None) -> dict[str, AttributeValue]:
    """Return privacy-gated attributes plus active profile/correlation metadata."""
    profile = resolve_profile()
    settings = get_settings()
    raw: dict[str, object] = {
        "deployment.target": settings.deployment_mode.value,
        "observability.profile": profile.name.value,
        "assurance.level": profile.assurance_level.value,
        "prompt_family": settings.observability.prompt_family,
        "prompt_version": settings.observability.prompt_version,
        "langfuse.trace.name": "tessera.chat.turn",
        "langfuse.trace.tags": [
            "tessera",
            profile.name.value,
            profile.assurance_level.value,
            settings.observability.langfuse_project,
        ],
        "langfuse.version": __version__,
        "langfuse.environment": settings.environment.value,
        "langfuse.trace.metadata.observability_profile": profile.name.value,
        "langfuse.trace.metadata.assurance_level": profile.assurance_level.value,
        "langfuse.trace.metadata.langfuse_project": settings.observability.langfuse_project,
    }
    request_id = current_request_id.get()
    conversation_hash = current_conversation_hash.get()
    turn_id = current_turn_id.get()
    trace_id = current_trace_id()
    if request_id is not None:
        raw["request_id"] = request_id
    if conversation_hash is not None:
        raw["conversation_id_hash"] = conversation_hash
        raw["langfuse.session.id"] = conversation_hash
        raw["langfuse.user.id"] = conversation_hash
    if turn_id is not None:
        raw["turn_id"] = turn_id
    if trace_id is not None:
        raw["trace_id"] = trace_id
    if attributes is not None:
        raw.update(attributes)
    sanitized = sanitize_attributes(raw)
    coerced: dict[str, AttributeValue] = {}
    for key, value in sanitized.items():
        attribute = _coerce_attribute(value)
        if attribute is not None:
            coerced[key] = attribute
    return coerced


def current_trace_id() -> str | None:
    """Return the current OpenTelemetry trace id as lowercase hex, when valid."""
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return f"{context.trace_id:032x}"


def start_span(name: TelemetrySpan | str, attributes: Mapping[str, object] | None = None) -> Any:
    """Start a current span with privacy-gated Tessera attributes."""
    return tracer().start_as_current_span(str(name), attributes=span_attributes(attributes))


def emit_event(
    event: TelemetryEvent | str,
    attributes: Mapping[str, object] | None = None,
    *,
    span: Span | None = None,
) -> None:
    """Add a privacy-gated event to ``span`` or the current span."""
    target = span or trace.get_current_span()
    if not target.get_span_context().is_valid:
        return
    target.add_event(str(event), attributes=span_attributes(attributes))


def instrument_node(
    *,
    node: str,
    span_name: TelemetrySpan,
    handler: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a LangGraph node with a span and duration metric."""
    if inspect.iscoroutinefunction(handler):

        async def _async_wrapped(state: Any) -> Any:
            outcome = "ok"
            started = time.perf_counter()
            with start_span(span_name, {"node": node}) as span:
                try:
                    result = await handler(state)
                except Exception as exc:
                    outcome = "error"
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                finally:
                    LANGGRAPH_NODE_DURATION.labels(node=node, outcome=outcome).observe(
                        time.perf_counter() - started
                    )
                    span.set_attributes(span_attributes({"node": node, "outcome": outcome}))
            return result

        return _async_wrapped

    def _sync_wrapped(state: Any) -> Any:
        outcome = "ok"
        started = time.perf_counter()
        with start_span(span_name, {"node": node}) as span:
            try:
                return handler(state)
            except Exception as exc:
                outcome = "error"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            finally:
                LANGGRAPH_NODE_DURATION.labels(node=node, outcome=outcome).observe(
                    time.perf_counter() - started
                )
                span.set_attributes(span_attributes({"node": node, "outcome": outcome}))

    return _sync_wrapped
