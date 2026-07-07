"""Tessera agent SDK (ADR 0017 §7) — the in-process instrumentation surface.

An agent runtime becomes *cockpit-observable* by emitting the ADR 0017 §1
telemetry: OTel GenAI spans (:mod:`instrument`) and a graph-topology fingerprint
(:mod:`graph_topology`). Those emitters, plus the conformance :mod:`testkit`,
live here — on the **agent side** of the ADR 0017 §1 boundary — so the control
plane (``tessera.observability`` + the cockpit routes) never imports them.
LangGraph is the reference adapter, not a cockpit dependency (§7 "two profiles,
one wire"). This is signal 107 (`tessera-otel-genai` extraction) begun in-repo.
"""

from __future__ import annotations

from tessera.agent.sdk import instrument
from tessera.agent.sdk.instrument import (
    annotate_retrieval,
    collect_node_timings,
    instrument_node,
    node_start_offsets,
    retrieval_span,
    tool_span,
)

__all__ = [
    "annotate_retrieval",
    "collect_node_timings",
    "instrument",
    "instrument_node",
    "node_start_offsets",
    "retrieval_span",
    "tool_span",
]
