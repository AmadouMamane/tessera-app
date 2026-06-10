"""Span propagation under async / parallel fan-out (ADR 0010, idea #85).

The agent fans out to several workers in parallel (planner → product/regulation/
account/… ). Under asyncio, a span opened inside one coroutine must still nest
under the request span that was active when the coroutine was scheduled — if the
OTel context is lost across the ``await``/``gather`` boundary, those worker spans
become *orphans* and the trace tree breaks.

This module ships two things:

* :func:`analyze_propagation` — a pure checker over ``(name, span_id, parent_id)``
  triples that reports the root, any orphaned spans (parent not present), and the
  fan-out width (max siblings under one parent);
* :func:`probe_propagation` — a live, **isolated** probe that opens a parent span
  and a parallel fan-out of child spans on a private TracerProvider (no export to
  Phoenix/Langfuse, mirroring the cost-of-obs benchmark), then checks the result.

The probe proves async context actually propagates with the same OTel primitive
the agent instrumentation uses; the analyzer makes the property assertable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

__all__ = [
    "PropagationReport",
    "SpanRef",
    "analyze_propagation",
    "probe_propagation",
]

_DEFAULT_FANOUT = 4


@dataclass(frozen=True, slots=True)
class SpanRef:
    """A minimal span reference for parentage analysis."""

    name: str
    span_id: str
    parent_id: str | None


@dataclass(frozen=True, slots=True)
class PropagationReport:
    """The structural health of a parallel trace tree."""

    n_spans: int
    n_roots: int
    n_orphans: int
    max_fanout: int
    propagated_ok: bool
    orphan_names: list[str] = field(default_factory=list)


def analyze_propagation(spans: list[SpanRef]) -> PropagationReport:
    """Check a set of spans for orphans and a single coherent root.

    Args:
        spans: The spans of one trace as ``(name, span_id, parent_id)`` triples.

    Returns:
        A :class:`PropagationReport`. ``propagated_ok`` is true when there are no
        orphaned spans and exactly one root (no broken context across ``await``).
    """
    ids = {s.span_id for s in spans}
    roots = [s for s in spans if s.parent_id is None]
    orphans = [s for s in spans if s.parent_id is not None and s.parent_id not in ids]

    fanout: dict[str, int] = {}
    for s in spans:
        if s.parent_id is not None:
            fanout[s.parent_id] = fanout.get(s.parent_id, 0) + 1

    return PropagationReport(
        n_spans=len(spans),
        n_roots=len(roots),
        n_orphans=len(orphans),
        max_fanout=max(fanout.values(), default=0),
        propagated_ok=len(orphans) == 0 and len(roots) == 1 and len(spans) > 0,
        orphan_names=[s.name for s in orphans],
    )


async def probe_propagation(*, fanout: int = _DEFAULT_FANOUT) -> PropagationReport:
    """Run a parallel span fan-out on an isolated provider and analyse it.

    Opens a ``request`` parent span and ``fanout`` child ``invoke_agent`` spans
    concurrently via :func:`asyncio.gather`. The spans are created on a private
    :class:`~opentelemetry.sdk.trace.TracerProvider` with an in-memory exporter,
    so nothing is exported to the real backends.

    Args:
        fanout: The number of parallel child spans to open.

    Returns:
        A :class:`PropagationReport`; ``propagated_ok`` proves async context
        survived the parallel fan-out.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("tessera.span_propagation.probe")

    async def _child(index: int) -> None:
        with tracer.start_as_current_span(f"invoke_agent worker_{index}"):
            await asyncio.sleep(0)  # force a real await/scheduling boundary

    with tracer.start_as_current_span("request"):
        await asyncio.gather(*(_child(i) for i in range(fanout)))

    refs = [
        SpanRef(
            name=span.name,
            span_id=format(span.context.span_id, "016x"),
            parent_id=format(span.parent.span_id, "016x") if span.parent else None,
        )
        for span in exporter.get_finished_spans()
    ]
    return analyze_propagation(refs)
