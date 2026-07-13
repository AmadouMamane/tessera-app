"""The governed release gate: an agent goes live only after passing its set.

The snapshot fixture below reproduces the agent's **real null floor** rather than stubbing
an empty run. That is not decoration: the release decision now grades the model against
that floor (ADR 0021, Rule 1), so a fixture with no sessions would either have to patch the
floor away — leaving the wiring free to be deleted without a test noticing — or block for a
reason the test is not about. A run that reproduces the floor exactly breaks nothing and
contributes nothing, which is precisely the neutral baseline every other condition wants.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from eval.contribution import restrict_baseline
from eval.ratchet import load_baseline
from eval.sets import load_eval_set
from tessera.observability import agent_lifecycle as lifecycle
from tessera.observability.eval_data import EvalSnapshot, SessionRow

if TYPE_CHECKING:
    import pytest

_NULL_BASELINE = Path("eval/baselines/null-control.json")


def _floor_of(eval_set: str) -> dict[str, bool]:
    """The committed null control, restricted to one agent's set — its own measured floor."""
    floor = restrict_baseline(
        load_baseline(_NULL_BASELINE), set(load_eval_set(eval_set).effective_case_ids)
    )
    return dict(floor.verdicts)


def _sessions(verdicts: dict[str, bool]) -> tuple[SessionRow, ...]:
    """Sessions for a run with those verdicts. Non-zero tokens = a model actually spoke."""
    return tuple(
        SessionRow(
            case_id=key.split("|", 1)[0],
            language=key.split("|", 1)[1],
            category="",
            title="",
            passed=passed,
            needs_escalation=False,
            tools=(),
            duration_ms=1.0,
            input_tokens=3,
            output_tokens=1,
            response="…",
            started_at="20260617T120000Z",
        )
        for key, passed in verdicts.items()
    )


def _snapshot(
    *,
    gate_passed: bool | None,
    failed_critical: tuple[str, ...] = (),
    verdicts: dict[str, bool] | None = None,
    eval_set: str = "support-client",
) -> EvalSnapshot:
    """A run of ``eval_set``. Defaults to reproducing its null floor exactly.

    Reproducing the floor means: breaks nothing the agent already passes with no model at
    all (Rule 1 holds) and closes none of what it fails (contribution 0, which is measured
    and not gated per-set). Neutral on the floor axis, so each test varies one condition.
    """
    run = _floor_of(eval_set) if verdicts is None else verdicts
    sessions = _sessions(run)
    return EvalSnapshot(
        model="llama3.2:3b",
        run_at="20260617T120000Z",
        # The identity of the case set this run was scored against. It must be the SET's,
        # not a placeholder: the floor refuses to grade a run it cannot show it applies to.
        catalogue_version=restrict_baseline(
            load_baseline(_NULL_BASELINE), set(load_eval_set(eval_set).effective_case_ids)
        ).catalogue_version,
        total=len(sessions),
        passed=sum(1 for s in sessions if s.passed),
        languages=(("fr", len(sessions)),),
        categories=(),
        escalations=0,
        tool_invocations=0,
        sessions=sessions,
        agent_id=eval_set,
        eval_set=eval_set,
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


# --------------------------------------------------------------------------- #
# ADR 0021 Rule 1 — the null floor is a RELEASE CONDITION, not a dashboard tile.
#
# The critical floor structurally CANNOT see a model that is worse than no model at all:
# 122 of the catalogue's 174 runs pass with every LLM backend pointed at a closed port, so
# an agent can clear every critical case while having BROKEN a run its own guard/router
# layer closes unaided. These are the tests that would have caught the release button
# ignoring the very tile rendered beside it.
# --------------------------------------------------------------------------- #


def test_release_blocked_when_the_model_is_worse_than_no_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation: break ONE run the floor passes, and a passing gate must not release.

    This is the whole thesis in a single assertion. The critical gate still says PASS — it
    has no idea the deterministic layer used to handle this case — and the release is
    refused anyway, because a model that degrades what worked without it is not shippable
    at any score.
    """
    floor = _floor_of("support-client")
    broken = next(k for k, ok in floor.items() if ok)  # a run the agent passes with NO model
    run = {**floor, broken: False}

    monkeypatch.setattr(
        lifecycle, "load_eval_snapshot", lambda _aid: _snapshot(gate_passed=True, verdicts=run)
    )
    decision = lifecycle.release_decision("support-client")

    assert decision.gate_passed is True, "the critical floor still passes — it cannot see this"
    assert not decision.allowed, "and the release is refused anyway: worse than nothing"
    assert decision.blocked_by == lifecycle.BLOCKED_BY_FLOOR
    assert decision.floor_regressions == (broken,)
    assert "worse than nothing" in decision.reason
    assert "eval-contribution" in decision.reason, "the reason carries the command that settles it"


def test_a_clean_run_on_the_floor_still_releases(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control for the test above: same gate, same level, floor intact → allowed.

    Without this, a floor condition that blocked *everything* would pass the test above and
    look like a working gate.
    """
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: _snapshot(gate_passed=True))
    decision = lifecycle.release_decision("support-client")
    assert decision.allowed
    assert decision.blocked_by is None
    assert decision.floor_graded is True
    assert decision.floor_regressions == ()


def test_a_run_no_model_answered_is_not_released(monkeypatch: pytest.MonkeyPatch) -> None:
    """0 output tokens = the deterministic layer scored alone. It is not a model verdict.

    The report's `model` field is written even when every backend was unreachable, so it
    proves nothing; generated tokens do. Such a run has no contribution to grade, and an
    ungraded model is not a cleared one.
    """
    snap = _snapshot(gate_passed=True)
    silent = replace(
        snap,
        sessions=tuple(replace(s, output_tokens=0) for s in snap.sessions),
    )
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: silent)
    decision = lifecycle.release_decision("support-client")

    assert not decision.allowed
    assert decision.blocked_by == lifecycle.BLOCKED_BY_FLOOR
    assert decision.floor_graded is False
    assert "no model spoke" in decision.reason


def test_a_floor_that_no_longer_applies_refuses_rather_than_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run scored against a case set the floor was not captured on is NOT graded.

    Fail-closed: the gate refuses to rule rather than grading against a population that no
    longer exists. A refusal is not a pass.
    """
    moved = replace(_snapshot(gate_passed=True), catalogue_version="999-deadbeef")
    monkeypatch.setattr(lifecycle, "load_eval_snapshot", lambda _aid: moved)
    decision = lifecycle.release_decision("support-client")

    assert not decision.allowed
    assert decision.blocked_by == lifecycle.BLOCKED_BY_FLOOR
    assert decision.floor_graded is False
    assert "catalogue moved" in decision.reason


def test_the_state_label_says_worse_than_no_model_not_eval_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A floor block must not be labelled "Bloqué (eval-gate)".

    The critical gate PASSED. Attributing this block to it would send the operator to look
    for a failing critical case that does not exist — the §A2.4 soft lie, in a new place.
    The label mapping is exhaustive so a new reason cannot silently inherit the gate's.
    """
    monkeypatch.setattr(lifecycle, "lifecycle_history", lambda _aid: [])
    floor = _floor_of("support-client")
    broken = next(k for k, ok in floor.items() if ok)
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=True, verdicts={**floor, broken: False}),
    )
    payload = lifecycle.compute_agent_lifecycle("support-client", "fr")
    assert payload["state"] == "Bloqué (pire que sans modèle)"
    assert payload["state_tone"] == "bad"


def test_every_block_reason_has_its_own_label() -> None:
    """No block reason may fall back to the eval-gate label.

    The mapping this asserts replaced an `if/else` that defaulted anything it did not
    recognise to "Bloqué (eval-gate)" — so adding a reason (as this lot did) would have
    silently mislabelled it as a critical-gate failure.
    """
    reasons = {
        lifecycle.BLOCKED_BY_EVAL_GATE,
        lifecycle.BLOCKED_BY_FLOOR,
        lifecycle.BLOCKED_BY_OBSERVABILITY_LEVEL,
    }
    assert reasons == set(lifecycle._BLOCK_LABEL), "every block reason needs its own label"
    assert len({lifecycle._BLOCK_LABEL[r] for r in reasons}) == len(reasons), "labels must differ"


def test_the_release_event_records_which_floor_judged_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The durable S1 event must carry the floor verdict, not merely the outcome.

    A verdict that cannot name what it judged is unfalsifiable — the audit trail has to say
    the floor was applied and what it found, or a later reader cannot tell a clean release
    from one where the floor was never consulted.
    """
    floor = _floor_of("support-client")
    broken = next(k for k, ok in floor.items() if ok)
    monkeypatch.setattr(
        lifecycle,
        "load_eval_snapshot",
        lambda _aid: _snapshot(gate_passed=True, verdicts={**floor, broken: False}),
    )
    emitted: dict[str, object] = {}
    monkeypatch.setattr(lifecycle, "emit_agent_lifecycle", lambda **kw: emitted.update(kw))

    lifecycle.request_release("support-client", actor="admin")

    assert emitted["phase"] == "release_blocked"
    detail = emitted["detail"]
    assert isinstance(detail, dict)
    assert detail["blocked_by"] == lifecycle.BLOCKED_BY_FLOOR
    assert detail["floor_regressions"] == [broken]
    assert detail["floor_graded"] is True
