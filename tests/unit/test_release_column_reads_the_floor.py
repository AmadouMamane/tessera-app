"""The fleet's "état de release" column reads the measured floor — not `gate.passed` alone.

Instance №2 of the disease `eval-gate-reads-the-floor` closed on the Évaluations page: the
Release button there learned to consult ADR 0021 Rule 1, and the FLEET column plus
AGIR/Release Control — the surfaces an operator actually scans — kept reading the gate view's
one bit. On 2026-07-14 they rendered **PASSE** for two agents whose models are CERTIFIED worse
than silence on runs those very agents execute (support-client on
``48_hallucination_retroactive_refund|fr``, recouvrement on
``56_policy_violation_disparage_bank|de``), measured over 15 passes each. (The 2026-07-15
re-measurement under the fixed grader kept recouvrement's inversion and dropped support-client's,
which did not reproduce; this mocked wiring test is unaffected — it drives the floor verdict
directly.)

``agent_release_state`` now grades against the same floor (``grade_against_own_floor``), and
these tests pin the wiring: only an ``Ok`` releases; a ``NotOk`` renders the Rule 1 block; a
``CannotSay`` renders as the distinct blind-spot label (never dressed as a measured block, never
as a pass); and the floor's one-line reason travels on the wire where the cockpit can show it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.observability import agent_release
from tessera.verdict import CannotSay, NotOk, Ok, Verdict

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


@dataclass(frozen=True)
class _Snap:
    """The EvalSnapshot fields `agent_release_state` actually reads."""

    eval_set: str = "support-client"
    run_at: str = "2026-07-12T14:52:31Z"
    catalogue_version: str = "43-abcd1234"
    passed: int = 40
    total: int = 43
    model: str = "llama3.2:3b"


@dataclass(frozen=True)
class _Gate:
    """The gate-view fields `agent_release_state` actually reads."""

    passed: bool = True
    verdict_label: str = "PASSE"
    verdict_tone: str = "good"
    candidate_version: str = "0.3.1"
    executions: int = 5
    socle_ok: bool = True
    blocking_socle: int = 0
    blocking_t1: int = 0
    waived_active: int = 0
    socle_passed: int = 18
    socle_total: int = 18


@dataclass(frozen=True)
class _Floor:
    """The FloorGrade members `agent_release_state` consults (the grade has its own tests)."""

    releasable: Verdict = field(default_factory=lambda: Ok("graded; nothing held against it"))

    def block_reason(self) -> str | None:
        if isinstance(self.releasable, NotOk):
            return self.releasable.reason
        if isinstance(self.releasable, CannotSay):
            return self.releasable.blind_spot
        return None


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gate: _Gate,
    floor: _Floor,
) -> Callable[[str], agent_release.AgentRelease]:
    monkeypatch.setattr(agent_release, "load_eval_snapshot", lambda _aid: _Snap())
    monkeypatch.setattr(agent_release, "build_gate_view", lambda _snap: gate)
    monkeypatch.setattr(agent_release, "grade_against_own_floor", lambda _snap: floor)
    monkeypatch.setattr(agent_release, "_current_catalogue_version", lambda _slug: "43-abcd1234")
    return lambda lang: agent_release.agent_release_state("support-client", lang)


class TestOnlyAnOkReleases:
    def test_a_certified_inversion_blocks_a_gate_that_passed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """THE incident: gate green, model certified worse than silence — the column must refuse."""
        refusal = NotOk("the model is CERTIFIED worse than silence on 1 run(s) …")
        state = _wire(monkeypatch, gate=_Gate(passed=True), floor=_Floor(releasable=refusal))("fr")

        assert state.passed is False
        assert state.verdict_label == "BLOQUÉ (règle 1)"
        assert state.verdict_tone == "crit"
        assert state.floor_ok is False
        assert state.floor_block == refusal.reason  # the WHY travels, not just the bit

    def test_a_blind_spot_is_not_a_pass_and_not_a_measured_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CannotSay ships nothing — under its own label, never dressed as Rule 1."""
        blind = CannotSay("no floor with the power to clear this run")
        state = _wire(monkeypatch, gate=_Gate(passed=True), floor=_Floor(releasable=blind))("fr")

        assert state.passed is False
        assert state.verdict_label == "NE PEUT PAS DIRE (plancher)"
        assert state.verdict_tone == "bad"
        assert state.floor_block == blind.blind_spot

    def test_an_ok_floor_leaves_a_passing_gate_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        state = _wire(monkeypatch, gate=_Gate(passed=True), floor=_Floor())("fr")

        assert state.passed is True
        assert state.verdict_label == "PASSE"
        assert state.floor_ok is True
        assert state.floor_block is None

    def test_a_gate_block_keeps_its_own_label_and_still_carries_the_floor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A socle block is not rewritten into a Rule 1 block — but the floor facts still travel."""
        refusal = NotOk("certified inversion")
        gate = _Gate(passed=False, verdict_label="BLOQUÉ par le socle", verdict_tone="crit")
        state = _wire(monkeypatch, gate=gate, floor=_Floor(releasable=refusal))("fr")

        assert state.passed is False
        assert state.verdict_label == "BLOQUÉ par le socle"
        assert state.floor_ok is False
        assert state.floor_block == refusal.reason

    def test_the_rule1_label_localizes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        run = _wire(
            monkeypatch, gate=_Gate(passed=True), floor=_Floor(releasable=NotOk("certified"))
        )

        assert run("en").verdict_label == "BLOCKED (rule 1)"
        assert run("de").verdict_label == "BLOCKIERT (Regel 1)"

    def test_the_wire_carries_the_floor_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`as_dict` feeds the fleet AND Release Control — the fields must survive it."""
        refusal = NotOk("certified inversion on 48_…|fr")
        state = _wire(monkeypatch, gate=_Gate(passed=True), floor=_Floor(releasable=refusal))("fr")
        wire = state.as_dict()

        assert wire["floor_ok"] is False
        assert wire["floor_block"] == refusal.reason
        assert wire["passed"] is False
