"""hello-agent (ADR 0017 §F) emits L1-contract turn spans — the SDK testkit gate.

ADR 0017 §7: "the L1/L3 gates are a ``pip install``, not a bespoke setup" — an agent repo runs
the SDK's span-contract suite against its own emission. Here the cockpit repo pins it for the
reference second-runtime agent: the exact attribute set ``hello_agent.run_turn`` stamps on each
turn span must satisfy ``verify_turn_span`` (the L1 signal-103 contract).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tessera.agent.sdk.testkit.span_contract import assert_turn_span, verify_turn_span

_HELLO_PATH = Path(__file__).resolve().parents[2] / "examples" / "hello-agent" / "hello_agent.py"


def _hello_agent() -> object:
    spec = importlib.util.spec_from_file_location("hello_agent", _HELLO_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _emitted_turn_attributes(mod: object) -> dict[str, str]:
    """The exact attribute set ``hello_agent.run_turn`` stamps — read from the agent's own
    constants so this gate fails if the agent ever drops a dimension."""
    return {
        mod._ATTR_AGENT_ID: mod.AGENT_ID,
        mod._ATTR_LANGUAGE: "fr",
        mod._ATTR_CONVERSATION_ID: "conv-abc123",
        mod._ATTR_TURN_ID: "turn-xyz789",
        mod._ATTR_ENVIRONMENT: mod.ENVIRONMENT,
        mod._ATTR_MODEL: "hello-echo-v1",
    }


def test_hello_agent_turn_span_meets_the_l1_contract() -> None:
    attributes = _emitted_turn_attributes(_hello_agent())
    assert verify_turn_span(attributes, synthetic=False) == []
    assert_turn_span(attributes, synthetic=False)  # raises on any violation


def test_hello_agent_missing_a_dimension_is_caught() -> None:
    # Drift guard: drop one required dimension → the testkit flags it (the gate has teeth).
    attributes = _emitted_turn_attributes(_hello_agent())
    del attributes["tessera.turn_id"]
    assert verify_turn_span(attributes, synthetic=False)  # non-empty violations
    with pytest.raises(AssertionError):
        assert_turn_span(attributes, synthetic=False)
