"""Span-contract conformance suite — signal 103, the ADR 0017 §4 L1 gate.

An agent is **L1 (Observable)** iff its turn root spans carry the full Scope
dimension set (ADR 0015 §Migration B) under the GenAI + Tessera semantic
conventions. This is the reusable checker any agent repo runs in CI (ADR 0017 §7
"the SDK ships its testkit"): pass it a span's attribute mapping — the
authoritative attribute keys come from :mod:`tessera.observability.semconv`
(``stamp_turn_dimensions``), never re-listed here (0015 one-canonical-source).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# The required-attribute contract is defined once in semconv (the authoritative home,
# next to stamp_turn_dimensions) so the boundary-scanned control plane can reuse it for
# the coverage descriptor (signal 92) without importing the agent SDK. Re-exported here.
from tessera.observability.semconv import (
    CONDITIONAL_TURN_SPAN_ATTRIBUTES,
    REQUIRED_TURN_SPAN_ATTRIBUTES,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "CONDITIONAL_TURN_SPAN_ATTRIBUTES",
    "REQUIRED_TURN_SPAN_ATTRIBUTES",
    "assert_turn_span",
    "verify_turn_span",
]


def verify_turn_span(attributes: Mapping[str, object]) -> list[str]:
    """Return the L1 span-contract violations for a turn root span (empty ⇒ conforming).

    A required attribute is a violation if it is absent or empty; the model
    attribute, when present, must likewise be non-empty (it is legitimately
    absent when the serving model is unknown).
    """
    violations: list[str] = []
    for key in REQUIRED_TURN_SPAN_ATTRIBUTES:
        if key not in attributes:
            violations.append(f"missing required span attribute {key!r}")
        elif attributes[key] in (None, ""):
            violations.append(f"required span attribute {key!r} is empty")
    for key in CONDITIONAL_TURN_SPAN_ATTRIBUTES:
        if key in attributes and attributes[key] in (None, ""):
            violations.append(f"span attribute {key!r} is present but empty")
    return violations


def assert_turn_span(attributes: Mapping[str, object]) -> None:
    """Raise ``AssertionError`` if the turn span fails the L1 contract (signal 103)."""
    violations = verify_turn_span(attributes)
    assert not violations, "span-contract (signal 103) violations: " + "; ".join(violations)
