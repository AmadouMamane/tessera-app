"""Span instrumentation for LangGraph nodes and guarded tool calls (ADR 0010).

This realises idea #4 — the OTel GenAI *agent* span conventions — for Tessera:

* :func:`instrument_node` wraps a LangGraph node ``run`` callable so each node
  emits an ``invoke_agent <name>`` span carrying ``gen_ai.operation.name`` and
  ``gen_ai.agent.name``. Nodes are wrapped once at graph-build time. Both sync
  and async node functions are supported — LangGraph uses a mix of both.
* :func:`tool_span` opens an ``execute_tool <name>`` span around a guarded tool
  invocation, carrying ``gen_ai.tool.name`` plus the guard verdict — used at the
  single chokepoint in :func:`tessera.guard.adapter.guarded_invoke`.

The spans nest under the FastAPI request span, so a single trace shows the whole
turn: request → invoke_agent (per worker) → execute_tool (per guarded call).
"""

from __future__ import annotations

import functools
import inspect
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from tessera.observability import semconv
from tessera.observability.traces import tracer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from opentelemetry.trace import Span

    from tessera.settings import LanguageCode

__all__ = ["instrument_node", "tool_span"]


def _language_value(language: object) -> str:
    """Render a language attribute value, accepting an enum or a string."""
    return str(getattr(language, "value", language))


def _annotate_node(span: Span, name: str, state: object) -> None:
    """Set the invoke_agent attributes, reading the language from state if present."""
    span.set_attribute(semconv.GEN_AI_OPERATION_NAME, semconv.GenAIOperation.INVOKE_AGENT)
    span.set_attribute(semconv.GEN_AI_AGENT_NAME, name)
    language = state.get("language") if isinstance(state, dict) else None
    if language is not None:
        span.set_attribute(semconv.TESSERA_LANGUAGE, _language_value(language))


def _record_node_errors(span: Span, result: object) -> None:
    """Record how many errors a node returned, when it returned any."""
    if isinstance(result, dict):
        errors = result.get("errors")
        if isinstance(errors, list | tuple | set):
            span.set_attribute("tessera.node.error_count", len(errors))


def instrument_node(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a node ``run`` callable in an ``invoke_agent <name>`` span.

    Handles both coroutine and plain functions, returning a wrapper of the same
    kind so LangGraph keeps treating the node as sync or async respectively.

    Args:
        name: The node / worker name (becomes ``gen_ai.agent.name``).
        fn: The node entry point ``run(state) -> partial state`` (sync or async).

    Returns:
        A wrapper with the same calling convention, emitting one span per call.
    """
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def _async(state: Any, *args: Any, **kwargs: Any) -> Any:
            with tracer().start_as_current_span(semconv.agent_span_name(name)) as span:
                _annotate_node(span, name, state)
                result = await fn(state, *args, **kwargs)
                _record_node_errors(span, result)
                return result

        return _async

    @functools.wraps(fn)
    def _sync(state: Any, *args: Any, **kwargs: Any) -> Any:
        with tracer().start_as_current_span(semconv.agent_span_name(name)) as span:
            _annotate_node(span, name, state)
            result = fn(state, *args, **kwargs)
            _record_node_errors(span, result)
            return result

    return _sync


@contextmanager
def tool_span(tool_name: str, language: LanguageCode) -> Iterator[Span]:
    """Open an ``execute_tool <name>`` span around a guarded tool invocation.

    The caller sets the guard verdict on the yielded span via
    :data:`tessera.observability.semconv.TESSERA_GUARD_DECISION`.

    Args:
        tool_name: The tool's policy key (becomes ``gen_ai.tool.name``).
        language: The active conversation language.

    Yields:
        The active span, so the caller can annotate the verdict/outcome.
    """
    with tracer().start_as_current_span(semconv.tool_span_name(tool_name)) as span:
        span.set_attribute(semconv.GEN_AI_OPERATION_NAME, semconv.GenAIOperation.EXECUTE_TOOL)
        span.set_attribute(semconv.GEN_AI_TOOL_NAME, tool_name)
        span.set_attribute(semconv.TESSERA_LANGUAGE, _language_value(language))
        yield span
