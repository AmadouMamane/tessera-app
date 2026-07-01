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
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from tessera.observability import semconv
from tessera.observability.traces import tracer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from opentelemetry.trace import Span

    from tessera.settings import LanguageCode

__all__ = [
    "annotate_retrieval",
    "collect_node_timings",
    "instrument_node",
    "node_start_offsets",
    "retrieval_span",
    "tool_span",
]

# Per-turn node latencies (ms) + start offsets (ms from the collection origin),
# collected via collect_node_timings (idea #48). The start offsets make the
# Console trace a *real* waterfall: a node is positioned by when it actually
# began, so parallel nodes overlap instead of all starting at 0.
_node_timings: ContextVar[dict[str, float] | None] = ContextVar(
    "tessera_node_timings", default=None
)
_node_starts: ContextVar[dict[str, float] | None] = ContextVar("tessera_node_starts", default=None)
_collect_origin: ContextVar[float | None] = ContextVar("tessera_collect_origin", default=None)


@contextmanager
def collect_node_timings() -> Iterator[dict[str, float]]:
    """Collect per-node durations (ms) for the duration of the context.

    The yielded dict is populated as instrumented nodes run within the same
    async task; repeated runs of a node are summed. Per-node *start offsets*
    (ms from the context origin) are collected in parallel and read with
    :func:`node_start_offsets` while still inside the context.
    """
    timings: dict[str, float] = {}
    starts: dict[str, float] = {}
    timings_token = _node_timings.set(timings)
    starts_token = _node_starts.set(starts)
    origin_token = _collect_origin.set(time.perf_counter())
    try:
        yield timings
    finally:
        _node_timings.reset(timings_token)
        _node_starts.reset(starts_token)
        _collect_origin.reset(origin_token)


def node_start_offsets() -> dict[str, float]:
    """Per-node start offsets (ms) measured from the collection origin.

    Real, measured offsets — not a synthetic cascade. Must be read while still
    inside the :func:`collect_node_timings` context (the ContextVar is reset on
    exit). If a node ran more than once the earliest start is kept.
    """
    return dict(_node_starts.get() or {})


def _record_timing(name: str, elapsed_ms: float) -> None:
    current = _node_timings.get()
    if current is not None:
        current[name] = current.get(name, 0.0) + elapsed_ms


def _record_start(name: str, start_perf: float) -> None:
    starts = _node_starts.get()
    origin = _collect_origin.get()
    if starts is None or origin is None:
        return
    offset = max(0.0, (start_perf - origin) * 1000.0)
    prior = starts.get(name)
    starts[name] = offset if prior is None else min(prior, offset)


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
                start = time.perf_counter()
                result = await fn(state, *args, **kwargs)
                _record_timing(name, (time.perf_counter() - start) * 1000.0)
                _record_start(name, start)
                _record_node_errors(span, result)
                return result

        return _async

    @functools.wraps(fn)
    def _sync(state: Any, *args: Any, **kwargs: Any) -> Any:
        with tracer().start_as_current_span(semconv.agent_span_name(name)) as span:
            _annotate_node(span, name, state)
            start = time.perf_counter()
            result = fn(state, *args, **kwargs)
            _record_timing(name, (time.perf_counter() - start) * 1000.0)
            _record_start(name, start)
            _record_node_errors(span, result)
            return result

    return _sync


@contextmanager
def retrieval_span(corpus: str, language: LanguageCode | None) -> Iterator[Span]:
    """Open a ``retrieve <corpus>`` span around a hybrid-search query.

    The span nests under the active ``invoke_agent`` worker span, so a real turn
    shows request -> invoke_agent -> retrieve. The caller annotates which source
    categories the query actually retrieved via :func:`annotate_retrieval`; that
    is what the Phoenix-backed citation telemetry reads back (idea #4).

    Args:
        corpus: The corpus searched (becomes part of the span name + an attr).
        language: The active conversation language, or ``None`` for an
            all-languages search (the regulatory path).

    Yields:
        The active span, so the caller can annotate the retrieved categories.
    """
    with tracer().start_as_current_span(semconv.retrieval_span_name(corpus)) as span:
        span.set_attribute(semconv.OPENINFERENCE_SPAN_KIND, "RETRIEVER")
        span.set_attribute(semconv.TESSERA_RETRIEVAL_CORPUS, corpus)
        if language is not None:
            span.set_attribute(semconv.TESSERA_LANGUAGE, _language_value(language))
        yield span


def annotate_retrieval(
    span: Span,
    *,
    categories: list[str],
    hit_count: int,
    top_score: float | None,
) -> None:
    """Record which source categories a retrieval query cited above threshold.

    Args:
        span: The active retrieval span.
        categories: Sorted source-category ids retrieved above the citation
            threshold (comma-joined onto the span; empty when nothing cited).
        hit_count: Number of candidate chunks above the threshold.
        top_score: The best cosine similarity in the candidate set, if any.
    """
    span.set_attribute(semconv.TESSERA_RETRIEVAL_CATEGORIES, ",".join(categories))
    span.set_attribute(semconv.TESSERA_RETRIEVAL_HIT_COUNT, hit_count)
    if top_score is not None:
        span.set_attribute(semconv.TESSERA_RETRIEVAL_TOP_SCORE, top_score)


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
