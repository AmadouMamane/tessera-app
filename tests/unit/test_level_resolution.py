"""Two rungs, one truth — the computed level never rests on an assumption (ADR 0017 §4/§A2.4).

`turn-agent` made the bug visible: it declares an observable contract and emits nothing, yet
the fleet showed an "L1" indistinguishable from a computed one, because evidence-unknown was
trusted as observed. These tests pin the repair:

- the resolver returns the **computed** rung (proof only) *and* the **declared** rung (what
  the manifest would reach), plus why the evidence is missing;
- the §A2.4 release gate reads the computed rung and nothing else — an unproven level gates
  nothing, whatever the manifest promises.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import business_capabilities as bc, turn_evidence

if TYPE_CHECKING:
    import pytest

_AGENT = "recouvrement"


def _no_business_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bc.business_events, "business_event_rows", lambda **_k: [])


def _governed(monkeypatch: pytest.MonkeyPatch, *, value: bool) -> None:
    monkeypatch.setattr(bc, "_governed", lambda _aid: value)


def test_proven_agent_computes_and_declares_the_same_rung(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_business_events(monkeypatch)
    _governed(monkeypatch, value=False)
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "observed")

    state = bc.resolve_level_state(_AGENT)
    assert state.evidence == "observed"
    assert state.computed == "L1"
    assert state.declared == "L1"
    assert state.proven is True


def test_absent_store_falls_back_honestly_and_keeps_the_declared_rung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The over-claim, killed: no store ⇒ no proof ⇒ the computed rung drops to L0."""
    _no_business_events(monkeypatch)
    _governed(monkeypatch, value=False)
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "unverifiable")

    state = bc.resolve_level_state(_AGENT)
    assert state.computed == "L0"  # never fabricated from an assumption
    assert state.declared == "L1"  # the ambition is still visible, and labelled as such
    assert state.proven is False


def test_dormant_agent_falls_back_too_and_is_distinguishable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_business_events(monkeypatch)
    _governed(monkeypatch, value=True)
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "dormant")

    state = bc.resolve_level_state(_AGENT)
    assert state.computed == "L0"
    assert state.declared == "L2"  # governed is an observed fact, so the ambition includes it
    assert state.evidence == "dormant"  # the agent's silence, not the store's


def test_unmanifested_agent_has_neither_rung(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "unverifiable")
    state = bc.resolve_level_state("does-not-exist")
    assert state.computed is None
    assert state.declared is None  # honest-empty badge, never "L0"


def test_resolve_observability_level_exposes_only_the_computed_rung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The release gate's only entry point. It must never see the declared rung."""
    _no_business_events(monkeypatch)
    _governed(monkeypatch, value=True)
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "unverifiable")

    assert bc.resolve_observability_level(_AGENT) == "L0"
    assert bc.resolve_level_state(_AGENT).declared == "L2"


def test_an_unproven_level_never_satisfies_the_release_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§A2.4 corollary, driven through the real gate — nothing about the level is stubbed.

    Production requires ≥ L2. The manifest declares L2 and the eval gate passes; the agent has
    emitted no turn. It must be blocked *by the level*, never waved through on its ambition.
    """
    from types import SimpleNamespace

    from tessera.observability import agent_lifecycle as lifecycle

    _no_business_events(monkeypatch)
    _governed(monkeypatch, value=True)
    monkeypatch.setattr(turn_evidence, "turn_evidence_state", lambda _a, _o=None: "dormant")
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: _passing_snapshot())
    monkeypatch.setattr(lifecycle, "declares_external_effects", lambda _aid: False)
    monkeypatch.setattr(
        lifecycle, "get_settings", lambda: SimpleNamespace(is_production=lambda: True)
    )

    # The manifest DOES declare L2 — what follows is about proof, not declaration.
    assert bc.resolve_level_state(_AGENT).declared == "L2"

    decision = lifecycle.release_decision(_AGENT)
    assert decision.allowed is False
    assert decision.gate_passed is True  # the eval gate is not the blocker
    assert decision.observability_level == "L0"  # the computed rung, not the declared one
    assert decision.blocked_by == lifecycle.BLOCKED_BY_OBSERVABILITY_LEVEL


def _passing_snapshot() -> object:
    from tessera.observability.eval_data import EvalSnapshot

    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="20260617T120000Z",
        catalogue_version="v1",
        total=40,
        passed=40,
        languages=(("fr", 40),),
        categories=(),
        escalations=0,
        tool_invocations=0,
        sessions=(),
        agent_id=_AGENT,
        gate_passed=True,
        gate_failed_critical=(),
    )
