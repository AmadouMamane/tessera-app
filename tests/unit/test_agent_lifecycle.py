"""The governed release gate: an agent goes live only after passing its set."""

from __future__ import annotations

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
