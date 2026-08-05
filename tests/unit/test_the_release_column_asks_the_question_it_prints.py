"""The fleet column is headed "Prêt à être mis en ligne". It must answer that question.

Instance №3 of the same disease, and the one that got furthest. The Évaluations page's Release
button learned to read ADR 0021's measured floor; the fleet column learned it on 2026-07-14, one
incident later. Neither ever learned §A2.4 rules 3 and 4 — *no production below L2*, and **L3
when the agent declares external effects** — because the release gate held them privately and no
other surface could see them.

It stayed invisible for as long as a stricter condition failed first. `recouvrement` was blocked
by the floor, so nobody could notice the column ignoring its level. On 2026-08-05 a criteria
correction removed the last certified inversion, the floor stopped blocking, and the column
printed **PRÊT** for an agent the release gate refuses. One condition masking another is how this
survives review: the surface was not "not yet fixed", it was *unfalsifiable* while something else
was red.

So the conditions now have ONE definition — `business_capabilities.required_level_for` — and this
module asserts the two surfaces agree, on the real agents and on constructed ones.

There is also a recursion to keep broken. The computed L-level reads `_governed`, which is "an
eval with a socle has run", which is the eval half of the release state. Wiring the level into
`agent_release_state` therefore closes `resolve_level_state -> _governed -> agent_release_state`
unless `_governed` reads the narrow question. It does, and a test here says so — a stack overflow
is a loud failure, but only if something calls the path.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from tessera.observability import (
    agent_lifecycle as lifecycle,
    agent_release,
    business_capabilities as capabilities,
)

if TYPE_CHECKING:
    import pytest

AGENTS = ("onboarding", "recouvrement", "support-client")


def test_the_two_surfaces_agree_on_every_real_agent() -> None:
    """The claim in one line: what the column prints is what the gate decides.

    Read from the committed reports and manifests, no mocks — the mocked wiring lives below.
    This is the assertion that was false on 2026-08-05, for `recouvrement`, in production.
    """
    disagreements = []
    for agent_id in AGENTS:
        column = agent_release.agent_release_state(agent_id, "fr")
        gate = lifecycle.release_decision(agent_id, "fr")
        if not column.available:
            continue
        if column.passed != gate.allowed:
            disagreements.append(
                f"{agent_id}: column says passed={column.passed} "
                f"({column.verdict_label!r}), gate says allowed={gate.allowed} "
                f"(blocked_by={gate.blocked_by!r})"
            )
    assert not disagreements, (
        "the fleet column and the release gate disagree about who may ship:\n  "
        + "\n  ".join(disagreements)
        + "\nThe column is headed 'Prêt à être mis en ligne'. If a condition belongs to only one "
        + "of them, it belongs to neither — put it in required_level_for and share it."
    )


def test_the_agents_are_actually_there() -> None:
    """Positive control: the comparison above is vacuous if nothing is evaluated."""
    available = [a for a in AGENTS if agent_release.agent_release_state(a, "fr").available]
    assert len(available) == len(AGENTS), f"only {available} have a usable run"


class TestTheConditionIsOneDefinition:
    """Rules 3 and 4, exercised where they now live — and in both directions."""

    def test_external_effects_require_l3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capabilities, "declares_external_effects", lambda _aid: True)
        assert capabilities.required_level_for("x") == "L3"

    def test_production_requires_l2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(capabilities, "declares_external_effects", lambda _aid: False)
        monkeypatch.setattr(
            capabilities, "get_settings", lambda: SimpleNamespace(is_production=lambda: True)
        )
        assert capabilities.required_level_for("x") == "L2"

    def test_outside_production_nothing_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Negative control: a condition that always fires is not a condition."""
        monkeypatch.setattr(capabilities, "declares_external_effects", lambda _aid: False)
        monkeypatch.setattr(
            capabilities, "get_settings", lambda: SimpleNamespace(is_production=lambda: False)
        )
        assert capabilities.required_level_for("x") is None

    def test_the_ladder_orders_the_rungs(self) -> None:
        assert capabilities.level_at_least("L3", "L3")
        assert capabilities.level_at_least("L2", None)
        assert not capabilities.level_at_least("L0", "L3")
        assert not capabilities.level_at_least(None, "L2")


class TestTheColumnAppliesIt:
    """Driven, so the block is proved rather than observed on today's data."""

    def _column(
        self, monkeypatch: pytest.MonkeyPatch, *, level: str | None, required: str | None
    ) -> agent_release.AgentRelease:
        monkeypatch.setattr(capabilities, "resolve_observability_level", lambda _aid: level)
        monkeypatch.setattr(capabilities, "required_level_for", lambda _aid: required)
        return agent_release.agent_release_state("support-client", "fr")

    def test_a_level_short_of_the_requirement_blocks_a_passing_eval(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """THE incident: eval green, floor green, level L0, requirement L3 — the column refuses."""
        eval_half = agent_release.eval_release_state("support-client", "fr")
        assert eval_half.passed, "this fixture needs an agent whose eval half clears"

        blocked = self._column(monkeypatch, level="L0", required="L3")
        assert blocked.passed is False
        assert blocked.verdict_label == "BLOQUÉ : PREUVES DE FONCTIONNEMENT INSUFFISANTES"
        assert blocked.verdict_tone == "bad"

    def test_the_same_agent_at_the_required_rung_ships(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Positive control: the refusal above must not be a function that always says no."""
        allowed = self._column(monkeypatch, level="L3", required="L3")
        assert allowed.passed is True
        assert allowed.verdict_label == "PRÊT"

    def test_the_level_never_rescues_a_failed_eval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A condition added to a conjunction may only ever remove verdicts, never add one."""
        monkeypatch.setattr(agent_release, "load_eval_snapshot", _raise_missing)
        state = self._column(monkeypatch, level="L3", required=None)
        assert state.available is False
        assert state.passed is False


def test_the_narrow_question_is_what_governed_reads() -> None:
    """The recursion, kept broken by construction rather than by care.

    `resolve_level_state` asks `_governed`; if that asked the GOVERNED release state, the level
    would be computed from a value that is computed from the level. Calling the level resolver is
    the whole test: if the loop is ever closed, this raises RecursionError instead of passing.
    """
    import inspect

    source = inspect.getsource(capabilities._governed)
    assert "eval_release_state" in source, (
        "_governed reads the governed release state again — that is the loop "
        "resolve_level_state -> _governed -> agent_release_state, and it will recurse"
    )
    for agent_id in AGENTS:
        capabilities.resolve_observability_level(agent_id)


def _raise_missing(_agent_id: str) -> object:
    raise FileNotFoundError
