"""The ratchet: the null floor is non-derogable, and no bar may be set beneath it.

Amadou's product thesis is, word for word, "an eval gate with a non-derogable floor". The
floor exists, it is measured, and it is committed (``eval/baselines/null-control.json``:
122 of the catalogue's 174 runs pass with every LLM backend pointed at a closed port). What
was missing is that nothing *enforced* it where a release is decided.

These tests make the configuration that produced that bug INEXPRESSIBLE. Each one has been
mutation-tested — a ratchet nobody has seen go red polices nothing:

1. **No bar below the floor.** A threshold a disconnected system already clears cannot fail,
   and a gate that cannot fail is a decoration. The `gate` object in `eval/sets/_schema.json`
   is `additionalProperties: false`, so no manifest can even *name* a bar — and this test
   proves that guard is load-bearing rather than assumed.
2. **A stale floor is refused, never guessed.** A floor captured on another case set grades
   against a population that no longer exists; every lift computed on it is a lie.
3. **The floor binds the RELEASE decision**, not merely a dashboard tile.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from eval.contribution import evaluate_contribution, floor_populations, restrict_baseline
from eval.ratchet import Baseline, catalogue_version, load_baseline
from eval.sets import list_eval_sets, load_eval_set

_NULL_BASELINE = Path("eval/baselines/null-control.json")
_SETS_SCHEMA = Path("eval/sets/_schema.json")


def _floor() -> Baseline:
    return load_baseline(_NULL_BASELINE)


# ── 1. No bar may be configured below the null floor ─────────────────────────


def test_the_measured_floor_is_what_the_removed_bars_sat_under() -> None:
    """The finding, pinned as arithmetic: 70% with no model, against bars of 55/65/55.

    If this ever fails, the floor moved and every claim built on it — the ADR, the gate, the
    docs — needs re-reading. It is not a decorative assertion: it is the premise.
    """
    floor = _floor()
    assert floor.passed == 122
    assert floor.total == 174
    rate = floor.passed / floor.total
    assert 0.70 <= rate < 0.71
    # The three bars ADR 0021 removed. Every one of them sat BELOW this floor, which is why
    # none of them could ever deny a release.
    for removed_bar in (0.55, 0.65, 0.55):
        assert removed_bar < rate, "a bar under the floor cannot fail — that is the bug"


def test_a_gate_bar_is_structurally_inexpressible() -> None:
    """A manifest CANNOT declare a threshold: the schema forbids unknown keys in `gate`.

    Mutation-tested: flip `additionalProperties` to true in the schema and a manifest with
    `min_pass_rate: 0.55` validates again — which is exactly the configuration that produced
    a gate a disconnected agent could clear.
    """
    schema = json.loads(_SETS_SCHEMA.read_text(encoding="utf-8"))
    gate = schema["properties"]["gate"]
    assert gate.get("additionalProperties") is False, (
        "the `gate` object must reject unknown keys — this is what makes a re-added "
        "`min_pass_rate` fail validation rather than sit there being ignored"
    )
    assert "min_pass_rate" not in gate.get("properties", {})

    # And the guard actually bites: a bar is rejected by the schema, not merely absent.
    import jsonschema

    bad = {"rationale": "…", "min_pass_rate": 0.55}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, gate)


def test_no_eval_set_smuggles_a_bar_past_the_schema() -> None:
    """Belt and braces: no loaded set carries a threshold under any name."""
    for eval_set in list_eval_sets():
        gate = eval_set.gate
        assert not hasattr(gate, "min_pass_rate")
        for field in gate.__dataclass_fields__:
            value = getattr(gate, field)
            if isinstance(value, float | int) and not isinstance(value, bool):
                pytest.fail(
                    f"{eval_set.slug}: gate.{field} = {value} — a bare number in the gate is a "
                    f"threshold by another name. The bar is the MEASURED floor, never a number."
                )


# ── 2. A stale floor is refused, never guessed ───────────────────────────────


def _report(floor: Baseline, *, catalogue: str, tokens: int = 999) -> dict[str, object]:
    """A run that reproduces the floor exactly, stamped with a given catalogue identity."""
    return {
        "model": "llama3.2:3b",
        "catalogue_version": catalogue,
        "cost": {"input_tokens": tokens, "output_tokens": tokens},
        "results": [
            {"case_id": k.split("|", 1)[0], "language": k.split("|", 1)[1], "passed": ok}
            for k, ok in floor.verdicts.items()
        ],
    }


def test_a_moved_catalogue_is_refused_not_graded() -> None:
    """The floor expires. A lift computed on an expired floor is a lie, so none is computed."""
    floor = _floor()
    verdict = evaluate_contribution(
        _report(floor, catalogue="64-deadbeef"), floor, min_contribution=30
    )
    assert not verdict.ok
    assert verdict.refusal is not None
    assert "catalogue moved" in verdict.refusal
    # NOT GRADED — no number is produced, because any number would count against a
    # population that no longer exists.
    assert verdict.contribution == 0
    assert verdict.contribution_population == 0
    assert "REFUSED" in verdict.render()


def test_an_unknown_catalogue_version_is_refused_too() -> None:
    """An unknown version is not a matching one — absence of proof is not proof.

    The first version of this check read `if baseline.version and run.version and they
    differ`, so an EMPTY version on either side skipped the comparison and the gate read
    green: it compared a floor of unknown provenance against a run from an unknown catalogue
    and called them equal. That is the "interrogate the neighbourhood of the truth" class,
    and it is closed here from both sides.
    """
    floor = _floor()
    no_version_on_the_run = evaluate_contribution(
        _report(floor, catalogue=""), floor, min_contribution=30
    )
    assert no_version_on_the_run.refusal is not None
    assert "does not name the catalogue" in no_version_on_the_run.refusal

    anonymous_floor = replace(floor, catalogue_version="")
    no_version_on_the_floor = evaluate_contribution(
        _report(floor, catalogue="63-071edbdc"), anonymous_floor, min_contribution=30
    )
    assert no_version_on_the_floor.refusal is not None
    assert "baseline does not name the catalogue" in no_version_on_the_floor.refusal


def test_a_matching_catalogue_still_grades() -> None:
    """The control: without this, a gate that refused EVERYTHING would pass the tests above."""
    floor = _floor()
    verdict = evaluate_contribution(
        _report(floor, catalogue=floor.catalogue_version), floor, min_contribution=0
    )
    assert verdict.refusal is None
    assert verdict.ok
    assert verdict.contribution_population == 52


def test_a_restricted_floor_names_the_cases_it_actually_holds() -> None:
    """A floor cut down to one set is a floor OVER THAT SET, and must say so.

    `restrict_baseline` used to inherit the parent's `63-071edbdc` while holding as few as 6
    cases — so it claimed to be the whole catalogue and matched no per-set run at all. The
    identity is now DERIVED from the cases held, which is the only way the check above can
    tell a legitimate per-set grading from a floor that expired.
    """
    floor = _floor()
    for eval_set in list_eval_sets():
        restricted = restrict_baseline(floor, set(load_eval_set(eval_set.slug).effective_case_ids))
        cases = {k.split("|", 1)[0] for k in restricted.verdicts}
        assert restricted.catalogue_version == catalogue_version(cases)
        if len(cases) < len(
            {k.split("|", 1)[0] for k in floor.verdicts}
        ):  # a strict subset must NOT claim the parent's identity
            assert restricted.catalogue_version != floor.catalogue_version


# ── 3. The floor binds the RELEASE, not just a tile ──────────────────────────


def test_rule_1_cannot_be_bought_off_by_a_perfect_contribution() -> None:
    """No score buys back "worse than no model at all". That is what non-derogable means."""
    floor = _floor()
    floor_pass, floor_fail = floor_populations(floor)
    broken = next(iter(sorted(floor_pass)))
    # Closes EVERY run the floor fails (a perfect 52/52) and breaks exactly one it passes.
    run = {**dict.fromkeys(floor_fail, True), **dict.fromkeys(floor_pass, True), broken: False}
    report = {
        "model": "m",
        "catalogue_version": floor.catalogue_version,
        "cost": {"output_tokens": 999},
        "results": [
            {"case_id": k.split("|", 1)[0], "language": k.split("|", 1)[1], "passed": ok}
            for k, ok in run.items()
        ],
    }
    verdict = evaluate_contribution(report, floor, min_contribution=30)
    assert verdict.contribution == 52, "a perfect contribution…"
    assert not verdict.ok, "…and it is still blocked, because it broke the floor"
    assert verdict.confirmed_breaks == (broken,)


def test_the_release_decision_reads_the_floor() -> None:
    """The wiring itself, asserted at the seam.

    `agent_lifecycle` must call the shared grader. If someone deletes that call, the tile
    keeps rendering the contribution and the button silently stops reading it — which is the
    exact bug this lot closed, and it would leave every other test green.
    """
    import inspect

    from tessera.observability import agent_lifecycle

    source = inspect.getsource(agent_lifecycle.release_decision)
    assert "grade_against_own_floor" in source, (
        "release_decision must grade the model against its own null floor — a model worse "
        "than no model at all is not releasable at any score (ADR 0021, Rule 1)"
    )
    assert "floor_ok" in inspect.getsource(agent_lifecycle._blocked_by)
