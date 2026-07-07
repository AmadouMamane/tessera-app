"""Conformance testkit shipped with the agent SDK (ADR 0017 §7, ADR 0018 §D).

The L-level gates are a ``pip install``, not a bespoke setup: any agent repo runs
these reusable suites in CI over its own emissions.

* :mod:`span_contract` — signal 103, the L1 gate: turn spans carry the full Scope
  dimension set under the GenAI + Tessera semantic conventions.
* :mod:`grammar_conformance` — signal 104, the L3 gate: business events conform to
  the versioned workflow grammar (names, versions, strict PII-free payloads).

Each suite exposes ``verify_*`` functions returning a list of violation strings
(empty ⇒ conforming) plus ``assert_*`` wrappers for direct use under any test
runner. The authoritative contract is imported from the observability modules,
never re-listed here (0015 one-canonical-source rule).
"""

from __future__ import annotations

from tessera.agent.sdk.testkit.grammar_conformance import (
    GRAMMAR_EVENT_NAMES,
    assert_business_event,
    verify_business_event,
    verify_event_stream,
)
from tessera.agent.sdk.testkit.span_contract import (
    CONDITIONAL_TURN_SPAN_ATTRIBUTES,
    REQUIRED_TURN_SPAN_ATTRIBUTES,
    assert_turn_span,
    verify_turn_span,
)

__all__ = [
    "CONDITIONAL_TURN_SPAN_ATTRIBUTES",
    "GRAMMAR_EVENT_NAMES",
    "REQUIRED_TURN_SPAN_ATTRIBUTES",
    "assert_business_event",
    "assert_turn_span",
    "verify_business_event",
    "verify_event_stream",
    "verify_turn_span",
]
