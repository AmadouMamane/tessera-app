"""The governed release gate: an agent goes live only after passing its set."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from tessera.observability import agent_lifecycle as lifecycle
from tessera.observability.eval_data import EvalSnapshot

if TYPE_CHECKING:
    import pytest


def _snapshot(*, gate_passed: bool | None, failed_critical: tuple[str, ...] = ()) -> EvalSnapshot:
    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="20260617T120000Z",
        catalogue_version="v1",
        total=40,
        passed=30,
        languages=(("fr", 40),),
        categories=(),
        escalations=0,
        tool_invocations=0,
        sessions=(),
        agent_id="support-client",
        eval_set="support-client",
        gate_passed=gate_passed,
        gate_failed_critical=failed_critical,
    )


def test_release_blocked_by_critical_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=False, failed_critical=("02_pii_leak",)),
    )
    decision = lifecycle.release_decision("support-client")
    assert not decision.allowed
    assert "socle critique" in decision.reason
    assert decision.failed_critical == ("02_pii_leak",)


def test_release_allowed_when_gate_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: _snapshot(gate_passed=True))
    decision = lifecycle.release_decision("support-client")
    assert decision.allowed
    assert decision.gate_passed is True
    assert decision.blocked_by is None  # allowed → nothing blocks


def test_release_blocked_without_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_aid: str) -> EvalSnapshot:
        raise FileNotFoundError

    monkeypatch.setattr(lifecycle, "load_eval_snapshot", _raise)
    decision = lifecycle.release_decision("support-client")
    assert not decision.allowed
    assert not decision.has_run


def test_request_release_emits_blocked_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=False, failed_critical=("46_pii_leak_exfiltration",)),
    )
    emitted: dict[str, object] = {}

    def _capture(**kwargs: object) -> None:
        emitted.update(kwargs)

    monkeypatch.setattr(lifecycle, "emit_agent_lifecycle", _capture)
    decision = lifecycle.request_release("support-client", actor="admin")
    assert not decision.allowed
    assert emitted["phase"] == "release_blocked"
    assert emitted["agent_id"] == "support-client"


def test_request_release_emits_released_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: _snapshot(gate_passed=True))
    emitted: dict[str, object] = {}
    monkeypatch.setattr(lifecycle, "emit_agent_lifecycle", lambda **kw: emitted.update(kw))
    decision = lifecycle.request_release("support-client")
    assert decision.allowed
    assert emitted["phase"] == "released"


# --------------------------------------------------------------------------- #
# ADR 0017 §A2.4 — the observability level is a release condition.
# --------------------------------------------------------------------------- #


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    level: str | None,
    prod: bool,
    external: bool,
    gate_passed: bool | None = True,
) -> None:
    monkeypatch.setattr(
        lifecycle, "load_eval_snapshot", lambda _aid: _snapshot(gate_passed=gate_passed)
    )
    monkeypatch.setattr(lifecycle, "resolve_observability_level", lambda _aid: level)
    monkeypatch.setattr(lifecycle, "declares_external_effects", lambda _aid: external)
    monkeypatch.setattr(
        lifecycle, "get_settings", lambda: SimpleNamespace(is_production=lambda: prod)
    )


def test_prod_blocks_below_l2(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, level="L1", prod=True, external=False)
    decision = lifecycle.release_decision("recouvrement")
    assert not decision.allowed  # eval passed, but L1 < L2 in prod
    assert decision.observability_level == "L1"
    assert decision.required_level == "L2"
    assert "L2" in decision.reason
    # The gate PASSED — the block is the level, not the eval-gate (§A2.4 honesty).
    assert decision.blocked_by == lifecycle.BLOCKED_BY_OBSERVABILITY_LEVEL


def test_prod_allows_at_l2(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, level="L2", prod=True, external=False)
    decision = lifecycle.release_decision("recouvrement")
    assert decision.allowed
    assert decision.required_level == "L2"


def test_nonprod_allows_below_l2(monkeypatch: pytest.MonkeyPatch) -> None:
    # Outside production the L-level is not gated (matches the dev doctrine).
    _wire(monkeypatch, level="L1", prod=False, external=False)
    decision = lifecycle.release_decision("recouvrement")
    assert decision.allowed
    assert decision.required_level is None


def test_external_effects_require_l3(monkeypatch: pytest.MonkeyPatch) -> None:
    # Declared external effects require L3 regardless of environment.
    _wire(monkeypatch, level="L2", prod=False, external=True)
    decision = lifecycle.release_decision("recouvrement")
    assert not decision.allowed
    assert decision.required_level == "L3"
    assert "L3" in decision.reason


def test_external_effects_allowed_at_l3(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, level="L3", prod=True, external=True)
    decision = lifecycle.release_decision("recouvrement")
    assert decision.allowed
    assert decision.required_level == "L3"


def test_eval_block_takes_precedence_over_level(monkeypatch: pytest.MonkeyPatch) -> None:
    # A failing eval-gate is reported even when the level would also block.
    _wire(monkeypatch, level="L1", prod=True, external=False, gate_passed=False)
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=False, failed_critical=("02_pii_leak",)),
    )
    decision = lifecycle.release_decision("recouvrement")
    assert not decision.allowed
    assert "socle critique" in decision.reason  # eval reason, not the level reason
    assert decision.blocked_by == lifecycle.BLOCKED_BY_EVAL_GATE  # gate failed → eval-gate


def test_as_dict_carries_level_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, level="L2", prod=True, external=False)
    payload = lifecycle.release_decision("recouvrement").as_dict()
    assert payload["observability_level"] == "L2"
    assert payload["required_level"] == "L2"
    assert payload["blocked_by"] is None  # allowed at L2


def test_state_label_names_the_block_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lifecycle state label must attribute the block to its real cause (§A2.4).

    A generic "Bloqué (eval-gate)" when the gate PASSED and only the observability level
    is short is the class of soft lie §A2.4 eradicates — the label reads the level instead.
    """
    monkeypatch.setattr(lifecycle, "lifecycle_history", lambda _aid: [])

    # Gate passed, L1 < L2 in prod → blocked by the LEVEL, labelled as such.
    _wire(monkeypatch, level="L1", prod=True, external=False)
    level_blocked = lifecycle.compute_agent_lifecycle("recouvrement", "fr")
    assert level_blocked["state"] == "Bloqué (niveau d'observabilité)"
    assert level_blocked["state_tone"] == "bad"

    # Gate failed → blocked by the EVAL-GATE, keeps the eval-gate label.
    _wire(monkeypatch, level="L2", prod=True, external=False, gate_passed=False)
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=False, failed_critical=("02_pii_leak",)),
    )
    gate_blocked = lifecycle.compute_agent_lifecycle("recouvrement", "fr")
    assert gate_blocked["state"] == "Bloqué (eval-gate)"
