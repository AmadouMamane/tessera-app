"""ADR 0019 §Amendment 1 A1.2 — the integration witness, and the platform capital it forced.

`duplex-agent` is the only example that both serves a turn and publishes telemetry for it. That
composition is the claim; these tests hold it, plus the two pieces of platform the claim needed:
the capability-schema loader (a form is generated, never guessed) and the propagation duty
(§A1.1) honoured across a process boundary.

The witness is loaded **by path**, never imported as a package — importing it would install OTLP
providers into the test process, and the file is meant to be read the way an operator reads a
foreign runtime: from the outside.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tessera.agent.capability_schema import (
    CapabilitySchemaError,
    load_input_schema,
    validate_params,
)
from tessera.agent.registry import get_agent
from tessera.agent.sdk.testkit import verify_business_event, verify_turn_result
from tessera.agent.turn_contract import TURN_RESULT_KEYS
from tessera.observability.agent_console import capability_forms, compute_agent_console
from tessera.observability.business_events import (
    UNATTRIBUTED_PRINCIPAL,
    UNATTRIBUTED_ROLE,
    BusinessEvent,
)

if TYPE_CHECKING:
    from types import ModuleType

_DUPLEX_PY = Path(__file__).resolve().parents[2] / "examples" / "duplex-agent" / "duplex_agent.py"
_CAPABILITY = "propose_schedule"


@pytest.fixture(scope="module")
def duplex() -> ModuleType:
    """Load the witness from its path, without touching global tracer/meter providers."""
    spec = importlib.util.spec_from_file_location("_duplex_agent_under_test", _DUPLEX_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _params() -> dict[str, Any]:
    return {
        "outstanding_amount_eur": 1200.0,
        "installments": 4,
        "first_due_date": "2026-08-01",
        "channel": "email",
        "notify_customer": True,
    }


def _turn_input(*, synthetic: bool) -> dict[str, Any]:
    return {
        "conversation_id": "conv-1",
        "turn_id": "turn-1",
        "language": "fr",
        "surface": "console",
        "synthetic": synthetic,
        "action": {"type": _CAPABILITY, "params": _params()},
    }


# --------------------------------------------------------------------------- #
# The manifest declaration
# --------------------------------------------------------------------------- #


def test_duplex_declares_one_capability_with_an_input_schema() -> None:
    spec = get_agent("duplex-agent").observability
    assert spec is not None
    assert [c.id for c in spec.capabilities] == [_CAPABILITY]
    assert spec.capabilities[0].input_schema == "schemas/propose_schedule.json"


def test_the_declared_schema_loads_and_is_renderable() -> None:
    schema = load_input_schema("schemas/propose_schedule.json")
    assert schema["type"] == "object"
    properties = schema["properties"]
    assert isinstance(properties, dict)
    # One property of each supported primitive — the generated form's whole vocabulary.
    kinds = {name: prop["type"] for name, prop in properties.items()}
    assert set(kinds.values()) == {"number", "integer", "string", "boolean"}


def test_the_console_generates_a_form_from_the_declaration() -> None:
    """The forcing function: the declaration alone produces the bench, with no per-agent code."""
    payload = compute_agent_console("fr", "duplex-agent")
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    assert len(capabilities) == 1
    entry = capabilities[0]
    assert entry["id"] == _CAPABILITY
    # The label travels as a KEY, never a resolved string: that is what keeps the projection
    # agent-agnostic and the locale catalogue the frontend's business.
    assert entry["label_key"] == "capability.propose_schedule"
    assert isinstance(entry["schema"], dict)


def test_an_agent_without_input_schemas_has_no_forms_rather_than_an_empty_one() -> None:
    assert capability_forms(get_agent("turn-agent")) == []
    assert capability_forms(get_agent("support-client")) == []


# --------------------------------------------------------------------------- #
# The schema loader refuses what it cannot honour
# --------------------------------------------------------------------------- #


class TestSchemaLoader:
    def test_absent_schema_raises_rather_than_degrading(self) -> None:
        with pytest.raises(CapabilitySchemaError, match="absent"):
            load_input_schema("schemas/does_not_exist.json")

    def test_a_path_escaping_the_schemas_directory_is_refused(self) -> None:
        with pytest.raises(CapabilitySchemaError, match="directly under schemas/"):
            load_input_schema("schemas/../../../etc/passwd")

    def test_a_nested_path_is_refused(self) -> None:
        with pytest.raises(CapabilitySchemaError, match="directly under schemas/"):
            load_input_schema("schemas/nested/thing.json")


class TestParamValidation:
    def test_valid_params_pass(self) -> None:
        schema = load_input_schema("schemas/propose_schedule.json")
        assert validate_params(schema, _params()) == []

    def test_a_missing_required_parameter_is_named(self) -> None:
        schema = load_input_schema("schemas/propose_schedule.json")
        params = _params()
        del params["installments"]
        assert validate_params(schema, params) == ["missing required parameter 'installments'"]

    def test_an_unknown_parameter_is_refused(self) -> None:
        schema = load_input_schema("schemas/propose_schedule.json")
        violations = validate_params(schema, {**_params(), "sneaky": 1})
        assert "unknown parameter 'sneaky'" in violations

    def test_a_bool_is_not_an_integer(self) -> None:
        """`bool` is an `int` in Python; a checkbox is not a count."""
        schema = load_input_schema("schemas/propose_schedule.json")
        violations = validate_params(schema, {**_params(), "installments": True})
        assert any("expects integer" in v for v in violations)


# --------------------------------------------------------------------------- #
# The witness serves a conformant turn
# --------------------------------------------------------------------------- #


def test_the_turn_result_conforms_to_the_declared_wire_contract(duplex: ModuleType) -> None:
    result = duplex.handle_turn(_turn_input(synthetic=True))
    assert set(result) == TURN_RESULT_KEYS
    assert verify_turn_result(result) == []


def test_the_capability_actually_computes_the_schedule(duplex: ModuleType) -> None:
    result = duplex.handle_turn(_turn_input(synthetic=True))
    artifact = result["artifact"]
    assert artifact["installments"] == 4
    # 1200 / 4 = 300, and the last instalment absorbs the rounding rather than being dropped.
    assert artifact["monthly_amount_eur"] == 300.0
    assert artifact["final_amount_eur"] == 300.0


def test_a_free_message_is_answered_without_an_action(duplex: ModuleType) -> None:
    result = duplex.handle_turn({"user_message": "bonjour", "synthetic": False})
    assert set(result) == TURN_RESULT_KEYS
    assert _CAPABILITY in result["visibleReply"]


def test_an_impossible_schedule_is_an_honest_error_not_a_fabricated_answer(
    duplex: ModuleType,
) -> None:
    bad = _turn_input(synthetic=True)
    bad["action"]["params"]["installments"] = 99
    with pytest.raises(ValueError, match="installments must be between"):
        duplex.handle_turn(bad)


# --------------------------------------------------------------------------- #
# §A1.1 — the propagation duty, checked with the real conformance suite
# --------------------------------------------------------------------------- #


def _emitted_event(duplex: ModuleType, *, synthetic: bool) -> BusinessEvent:
    result = duplex.handle_turn(_turn_input(synthetic=synthetic))
    events = result["businessEvents"]
    assert len(events) == 1
    # The example agent is FORBIDDEN from importing tessera (test_example_agents), so its
    # events cross the wire without an author. Tessera does not ingest them today (ADR 0019
    # §A1.2 (b) holds only for that reason); rebuilding one here must therefore SAY that the
    # author is unknown rather than quietly invent one.
    return BusinessEvent(
        **events[0],
        author_principal=UNATTRIBUTED_PRINCIPAL,
        author_role=UNATTRIBUTED_ROLE,
    )


def test_a_synthetic_turns_events_are_stamped_across_the_wire(duplex: ModuleType) -> None:
    """The end-to-end proof of A1.1: the flag arrived as data and left as a stamped event."""
    event = _emitted_event(duplex, synthetic=True)
    assert event.synthetic is True
    assert verify_business_event(event, synthetic=True) == []


def test_a_product_turns_events_are_not_stamped(duplex: ModuleType) -> None:
    event = _emitted_event(duplex, synthetic=False)
    assert event.synthetic is False
    assert verify_business_event(event, synthetic=False) == []


def test_an_absent_synthetic_key_means_product_traffic(duplex: ModuleType) -> None:
    """Absent ⇒ false: an agent must never infer 'test turn' from silence."""
    result = duplex.handle_turn({"user_message": "bonjour"})
    assert result["businessEvents"][0]["synthetic"] is False


class _Span:
    """Records what the witness stamps, without a tracer provider."""

    def __init__(self, attrs: dict[str, object]) -> None:
        self._attrs = attrs

    def set_attribute(self, key: str, value: object) -> None:
        self._attrs[key] = value

    def __enter__(self) -> _Span:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


class _Tracer:
    def __init__(self, attrs: dict[str, object]) -> None:
        self._attrs = attrs

    def start_as_current_span(self, _name: str) -> _Span:
        return _Span(self._attrs)


class _Counter:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def add(self, _amount: int, attributes: dict[str, object]) -> None:
        self.attributes = attributes


@pytest.mark.parametrize("synthetic", [True, False], ids=["synthetic", "product"])
def test_the_witness_stamps_the_span_only_when_the_turn_is_synthetic(
    duplex: ModuleType, *, synthetic: bool
) -> None:
    """The span half of the duty, read through the same testkit gate an http agent must pass."""
    from tessera.agent.sdk.testkit import verify_turn_span

    attrs: dict[str, object] = {}
    counter = _Counter()
    duplex.emit_turn_telemetry(
        _Tracer(attrs), counter, _turn_input(synthetic=synthetic), outcome="answered"
    )
    assert (
        verify_turn_span(attrs, synthetic=synthetic) == []
    ), f"duplex-agent's span fails the L1 contract for synthetic={synthetic}"
    # The counter the collector re-exports as `tessera_agent_turns_total{agent_id=…}` —
    # serving a turn is what produces the evidence that raises the computed level.
    assert counter.attributes["agent_id"] == "duplex-agent"
    assert counter.attributes["synthetic"] == str(synthetic).lower()


def test_the_witness_declares_its_schema_by_hand_rather_than_importing_it() -> None:
    """The duplication is the proof, so it must stay true: what it hard-codes must be correct."""
    source = _DUPLEX_PY.read_text(encoding="utf-8")
    for key in TURN_RESULT_KEYS:
        assert f'"{key}"' in source, f"duplex-agent no longer names the wire key {key!r}"
    # The schema it serves is the one the manifest declares — checked, never assumed.
    declared = json.loads(
        (
            Path(__file__).resolve().parents[2] / "src/tessera/agent/schemas/propose_schedule.json"
        ).read_text(encoding="utf-8")
    )
    for name in declared["required"]:
        assert name in source, f"duplex-agent ignores the required parameter {name!r}"
