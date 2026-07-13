"""The catalogue's discriminating power is MEASURED — and the measurement is checked.

Three things are proven here, and the third is the one that matters:

1. the statistics are right (Fisher, Holm) — including the fact that a five-pass sweep is
   **arithmetically incapable** of certifying a single discriminating run;
2. the classification is a **pure function of the stored evidence** — re-derived from the
   committed matrix, it reproduces the committed verdict exactly, run for run;
3. the ratchet **can go red**. A ratchet that cannot fail polices nothing (this repository
   has shipped two that could not, and both read green over a hole), so the power floor is
   mutation-tested: delete a discriminating case and the check must BLOCK.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from eval.discrimination import (
    _CLASS_RANK,
    ALPHA,
    BUCKET_OF,
    Sample,
    bh_qvalues,
    bh_reject,
    check_power,
    classify,
    detection_power,
    dump_power,
    fisher_greater,
    holm_reject,
    load_power,
    load_samples,
    minimum_viable_samples,
)
from eval.ratchet import Baseline
from tessera.verdict import CannotSay, NoEffect, NotOk, Ok, Power

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "eval" / "baselines" / "discrimination-samples.json"
CLASSIFICATION = REPO / "eval" / "baselines" / "discrimination.json"
NULL_CONTROL = REPO / "eval" / "baselines" / "null-control.json"


# --------------------------------------------------------------------------------------
# Synthetic helpers — the classifier is pure, so it can be driven with hand-built runs.
# --------------------------------------------------------------------------------------


def _baseline(verdicts: dict[str, bool], version: str = "2-abc") -> Baseline:
    return Baseline(kind="null_control", model="none", catalogue_version=version, verdicts=verdicts)


def _sample(model: str, passes: list[dict[str, bool]], version: str = "2-abc") -> Sample:
    return Sample(
        model=model,
        verdicts=tuple(passes),
        catalogue_versions=tuple([version] * len(passes)),
    )


def _repeat(verdict: dict[str, bool], n: int) -> list[dict[str, bool]]:
    return [dict(verdict) for _ in range(n)]


# --------------------------------------------------------------------------------------
# The statistics
# --------------------------------------------------------------------------------------


class TestFisher:
    def test_a_perfect_separation_is_the_smallest_p_the_sample_can_produce(self) -> None:
        # 5/5 vs 0/5: one of C(10,5) equally likely tables under the null.
        assert fisher_greater(5, 5, 0, 5) == pytest.approx(1 / math.comb(10, 5))

    def test_no_difference_is_not_evidence(self) -> None:
        assert fisher_greater(5, 5, 5, 5) == pytest.approx(1.0)
        assert fisher_greater(0, 5, 0, 5) == pytest.approx(1.0)

    def test_it_is_one_tailed__the_weak_model_winning_is_not_a_small_p(self) -> None:
        assert fisher_greater(0, 5, 5, 5) == pytest.approx(1.0)

    def test_an_empty_arm_proves_nothing(self) -> None:
        assert fisher_greater(0, 0, 0, 0) == pytest.approx(1.0)


class TestHolm:
    def test_it_rejects_the_smallest_p_first_and_stops_at_the_first_failure(self) -> None:
        # alpha=0.05, m=3: thresholds .0167, .025, .05
        assert holm_reject([0.001, 0.03, 0.04], alpha=0.05) == (True, False, False)

    def test_nothing_survives_when_nothing_is_small(self) -> None:
        assert holm_reject([0.9, 0.8], alpha=0.05) == (False, False)

    def test_five_passes_cannot_certify_anything_on_this_catalogue(self) -> None:
        """The finding that justified re-sampling: n=5 is not thin, it is *incapable*.

        The smallest p a perfect 5-vs-5 separation can produce is 1/C(10,5) = 0.0040. The
        tightest Holm threshold over the catalogue's 174 runs is 0.05/174 = 0.00029. The
        floor of what the experiment can produce sits **above** the ceiling of what the
        correction will accept, so no run — however cleanly it separates the two models —
        can be certified. Zero discriminating runs at n=5 is a statement about the
        experiment, not about the catalogue.
        """
        best_possible_p = fisher_greater(5, 5, 0, 5)
        tightest_threshold = ALPHA / 174
        assert best_possible_p > tightest_threshold

        # And the classifier says so rather than quietly reporting a zero: a perfect
        # separation on every run still certifies nothing at n=5.
        keys = [f"c{i:03d}|fr" for i in range(174)]
        floor = _baseline(dict.fromkeys(keys, False), version="174-x")
        strong = _sample("strong", _repeat(dict.fromkeys(keys, True), 5), version="174-x")
        weak = _sample("weak", _repeat(dict.fromkeys(keys, False), 5), version="174-x")
        power = classify(floor, strong, weak)
        assert power.discriminating_runs == 0

        # Fifteen passes each, same perfect separation: now it certifies.
        strong15 = _sample("strong", _repeat(dict.fromkeys(keys, True), 15), version="174-x")
        weak15 = _sample("weak", _repeat(dict.fromkeys(keys, False), 15), version="174-x")
        assert classify(floor, strong15, weak15).discriminating_runs == 174


# --------------------------------------------------------------------------------------
# The taxonomy — each class, on data that can only be that class.
# --------------------------------------------------------------------------------------


class TestTheTaxonomy:
    def test_dead__the_floor_passes_it_and_no_model_ever_touches_it(self) -> None:
        floor = _baseline({"a|fr": True})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": True}, 15)),
        )
        assert power.runs[0].klass == "dead"
        assert not power.runs[0].measures_the_model

    def test_inverted__the_floor_passes_it_and_a_model_reproducibly_breaks_it(self) -> None:
        floor = _baseline({"a|fr": True})
        broken = [{"a|fr": False}, {"a|fr": False}, *_repeat({"a|fr": True}, 13)]
        power = classify(floor, _sample("s", broken), _sample("w", _repeat({"a|fr": True}, 15)))
        assert power.runs[0].klass == "inverted"
        # It is the most valuable class: it MEASURES the model — a real harm.
        assert power.runs[0].measures_the_model

    def test_a_single_break_is_a_coin__not_an_inversion(self) -> None:
        floor = _baseline({"a|fr": True})
        once = [{"a|fr": False}, *_repeat({"a|fr": True}, 14)]
        power = classify(floor, _sample("s", once), _sample("w", _repeat({"a|fr": True}, 15)))
        assert power.runs[0].klass == "underpowered"
        assert power.runs[0].bucket == "cannot_say"
        assert not power.runs[0].measures_the_model

    def test_a_break_by_the_weak_model_alone_is_a_discriminator__not_a_harm(self) -> None:
        """An inversion is a defect of the model that SHIPS. This is not one.

        The floor passes it, the reference model never breaks it, and the weak model destroys
        it every time. The deployed agent is fine here — reporting an "inversion" would name a
        harm the product does not have. What it IS, is the best kind of case in the catalogue:
        one that catches a bad model by making it actively harmful. It is counted as the
        discriminator it is.
        """
        floor = _baseline({"a|fr": True})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        run = power.runs[0]
        assert run.klass == "discriminating"
        assert run.klass != "inverted"
        assert run.measures_the_model

    def test_discriminating__the_strong_model_separates_significantly(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        assert power.runs[0].klass == "discriminating"
        assert power.runs[0].measures_the_model

    def test_reversed__the_weak_model_separates__and_it_is_credited(self) -> None:
        """The correction. A reversal separates the models — violently — and it is credited.

        The reference model fails it every pass; a model a third its size passes it every pass.
        That is not a *failure* to discriminate: it is the sharpest discrimination in the
        catalogue, plus a certified defect of the model that ships. Filing it as "an anomaly,
        never a credit" (as an earlier draft of this module did) would have let it be deleted
        without turning the ratchet red — taking the only evidence of the defect with it.
        """
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": False}, 15)),
            _sample("w", _repeat({"a|fr": True}, 15)),
        )
        assert power.runs[0].klass == "reversed"
        assert power.runs[0].bucket == "certified"
        assert power.runs[0].measures_the_model

    def test_saturated__both_models_always_pass_it__a_fact_not_a_conclusion(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": True}, 15)),
        )
        assert power.runs[0].klass == "saturated"
        assert power.runs[0].bucket == "fact"
        assert not power.runs[0].measures_the_model

    def test_unreached__neither_model_ever_passes_it__a_fact_not_a_conclusion(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": False}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        assert power.runs[0].klass == "unreached"
        assert power.runs[0].bucket == "fact"
        assert not power.runs[0].measures_the_model

    def test_the_three_buckets_do_not_share_a_bucket(self) -> None:
        """Every class belongs to exactly one bucket, and nothing inferred is filed as a fact."""
        assert set(BUCKET_OF) == set(_CLASS_RANK)
        facts = {k for k, b in BUCKET_OF.items() if b == "fact"}
        certified = {k for k, b in BUCKET_OF.items() if b == "certified"}
        cannot_say = {k for k, b in BUCKET_OF.items() if b == "cannot_say"}
        assert facts == {"dead", "inverted", "saturated", "unreached"}
        assert certified == {"discriminating", "reversed"}
        assert cannot_say == {"underpowered"}
        # DEAD is a fact and it is the only class that may be called dead. Nothing inferred —
        # nothing whose truth depends on the power of the test — is allowed into that bucket.
        assert BUCKET_OF["underpowered"] != "fact"

    def test_instability_is_a_flag_not_a_bucket__a_noisy_run_can_still_be_decisive(
        self,
    ) -> None:
        """The refinement the data forced.

        The weak model failing 8 of 15 passes where the strong model never fails is BOTH
        noisy and sharply separating. Filing it under "unstable" would delete the most
        informative case in the catalogue, so the class records what it measures and the
        flag records that it is noisy.
        """
        floor = _baseline({"a|fr": False})
        flaky = [*_repeat({"a|fr": True}, 7), *_repeat({"a|fr": False}, 8)]
        power = classify(floor, _sample("s", _repeat({"a|fr": True}, 15)), _sample("w", flaky))
        run = power.runs[0]
        assert run.klass == "discriminating"
        assert run.unstable is True
        assert run.measures_the_model


class TestANullResultCarriesThePowerThatAuthorisesIt:
    """The ratchet this lot exists for. **A verdict of absence must earn itself.**

    "Zero discriminating cases in the catalogue" was a sentence that could have been written,
    published and believed at n=5 — where it was **guaranteed by the design**, equally true of a
    perfect catalogue and a worthless one. Nothing in the code would have stopped it.

    Now something does, and it is structural rather than remembered: ``NoEffect`` cannot be built
    without a ``Power``, and a ``Power`` cannot be built by a test that could not have rejected the
    null whatever it saw. The witness with no power has nothing to pass to the constructor.
    """

    def test_a_design_that_can_certify_nothing_yields_a_blind_spot__never_a_power(self) -> None:
        # n=5 per arm over 174 tests: the best p a PERFECT separation can produce is 1/C(10,5) =
        # 0.004, and the tightest threshold is 0.05/174 = 0.00029. It would report "no effect"
        # whatever the models did.
        verdict = detection_power(5, 5, threshold=ALPHA / 174)
        assert isinstance(verdict, CannotSay)
        assert "CANNOT certify any separation" in verdict.blind_spot

    def test_at_fifteen_it_has_power__and_the_power_names_what_it_could_have_seen(self) -> None:
        power = detection_power(15, 15, threshold=ALPHA / 174)
        assert isinstance(power, Power)
        # The number that had to be published: this design is blind to anything under 67 points.
        assert power.minimum_detectable_effect == pytest.approx(66.7)
        assert power.best_achievable_p <= power.threshold

    def test_the_minimum_viable_arm_is_eight__and_seven_misses_by_four_millionths(self) -> None:
        assert minimum_viable_samples(174) == 8
        assert 1 / math.comb(14, 7) > ALPHA / 174  # n=7: 0.000291 against 0.000287
        assert 1 / math.comb(16, 8) <= ALPHA / 174  # n=8: 0.0000777

    def test_power_refuses_to_be_built_by_a_test_that_could_not_have_seen_anything(self) -> None:
        """The ten lines. Constructing the licence is where the lie is stopped."""
        with pytest.raises(ValueError, match="CANNOT reject the null"):
            Power(
                samples=5,
                threshold=ALPHA / 174,
                best_achievable_p=1 / math.comb(10, 5),  # 0.004 — above the threshold
                minimum_detectable_effect=100.0,
                effect_unit="percentage points",
            )

    def test_at_n5_the_classifier_reports_no_null_result_anywhere__only_blind_spots(self) -> None:
        """The whole correction, in one assertion.

        At five passes per arm the *observations* are unchanged — both models still pass every
        pass of a saturated run. What changes is what may be **concluded**: nothing. So not one
        run yields a ``NoEffect``; every one of them yields a ``CannotSay``. The classifier is
        structurally unable to say "these do not discriminate", because the object that would
        license it cannot be built.
        """
        keys = [f"c{i:03d}|fr" for i in range(174)]
        floor = _baseline(dict.fromkeys(keys, False), version="174-x")
        both_pass = _repeat(dict.fromkeys(keys, True), 5)
        thin = classify(
            floor,
            _sample("s", both_pass, version="174-x"),
            _sample("w", both_pass, version="174-x"),
        )
        assert isinstance(thin.power, CannotSay)
        verdicts = [r.verdict(thin.power) for r in thin.runs]
        assert not any(isinstance(v, NoEffect) for v in verdicts)
        assert all(isinstance(v, CannotSay) for v in verdicts)

        # And at fifteen, the very same observation DOES license a bounded null result — one that
        # arrives carrying the effect size it does not exclude.
        fat = classify(
            floor,
            _sample("s", _repeat(dict.fromkeys(keys, True), 15), version="174-x"),
            _sample("w", _repeat(dict.fromkeys(keys, True), 15), version="174-x"),
        )
        assert isinstance(fat.power, Power)
        first = fat.runs[0].verdict(fat.power)
        assert isinstance(first, NoEffect)
        assert first.power.minimum_detectable_effect == pytest.approx(66.7)

    def test_a_dead_run_needs_no_power__because_it_is_a_fact(self) -> None:
        """DEAD is not a null result and must never be made to buy one.

        The null control is **deterministic**: it closes the case with zero tokens, or it does
        not. "Silence passes this run" is therefore a property of the case, not a sample of it —
        no p-value applies and no power enters. It is a ``NotOk``, and it would be a ``NotOk``
        even at n=1.
        """
        floor = _baseline({"a|fr": True})
        thin = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 5)),
            _sample("w", _repeat({"a|fr": True}, 5)),
        )
        assert thin.runs[0].klass == "dead"
        assert thin.runs[0].bucket == "fact"
        verdict = thin.runs[0].verdict(thin.power) if thin.power else None
        assert isinstance(verdict, NotOk)
        assert "zero tokens" in verdict.reason


class TestHolmForTheRatchetBhForTheDiagnosis:
    """Two corrections, two questions, two published sets — and the gap between them, named."""

    def test_bh_is_more_generous_than_holm__and_the_gap_is_computed(self) -> None:
        # Ten tests. p=0.004 clears BH at rank 1 (0.005) but not Holm's tightest step (0.005 —
        # equal, so it just clears); p=0.009 clears BH at rank 2 (0.010) and NOT Holm (0.0056).
        pvalues = [0.004, 0.009, *([0.9] * 8)]
        holm = holm_reject(pvalues, alpha=0.05)
        bh = bh_reject(pvalues, alpha=0.05)
        assert holm == (True, False, *([False] * 8))
        assert bh == (True, True, *([False] * 8))
        # That second run is exactly the case the correction was written for: real, modest, and
        # invisible to the instrument that guards the ratchet.
        assert bh[1] and not holm[1]

    def test_bh_does_not_stop_at_the_first_failure__that_is_holms_rule(self) -> None:
        """The silent way to turn BH back into Holm: copy its `break`. One statement, and the
        diagnosis inherits the ratchet's conservatism without anybody noticing.

        m=3, alpha=0.05.
          BH steps   (rank * alpha / m): 0.0167, 0.0333, 0.0500
          Holm steps (alpha / (m - rank)): 0.0167, 0.0250, 0.0500

        p = 0.034 **fails its own BH step** (0.034 > 0.0333). BH does not stop there: it takes the
        LARGEST rank that clears — rank 3, since 0.04 <= 0.05 — and rejects everything at or below
        it, p=0.034 included. Holm, by contrast, stops dead at 0.034 (> 0.025) and never looks
        further down the list.
        """
        pvalues = [0.01, 0.034, 0.04]
        assert bh_reject(pvalues, alpha=0.05) == (True, True, True)
        assert holm_reject(pvalues, alpha=0.05) == (True, False, False)

    def test_q_values_are_monotone__a_smaller_p_never_carries_a_larger_q(self) -> None:
        pvalues = [0.001, 0.02, 0.04, 0.9]
        qs = bh_qvalues(pvalues)
        ordered = [q for _, q in sorted(zip(pvalues, qs, strict=True))]
        assert ordered == sorted(ordered)
        assert all(0.0 <= q <= 1.0 for q in qs)


class TestCaseAggregation:
    def test_a_case_is_credited_with_its_strongest_language(self) -> None:
        """Dead in French, discriminating in German: the case DOES measure the model."""
        floor = _baseline({"a|fr": True, "a|de": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True, "a|de": True}, 15)),
            _sample("w", _repeat({"a|fr": True, "a|de": False}, 15)),
        )
        assert power.cases[0].run_classes == {"de": "discriminating", "fr": "dead"}
        assert power.cases[0].klass == "discriminating"
        assert power.discriminating_cases == 1


# --------------------------------------------------------------------------------------
# The refusals — a witness that cannot see reports a blind spot, never "ok" (ADR 0026).
# --------------------------------------------------------------------------------------


class TestItRefusesRatherThanGuessing:
    def test_a_moved_catalogue_is_refused__not_scored_as_zero(self) -> None:
        floor = _baseline({"a|fr": True}, version="63-071edbdc")
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 5), version="64-deadbeef"),
            _sample("w", _repeat({"a|fr": True}, 5), version="64-deadbeef"),
        )
        assert power.refusal is not None
        assert "catalogue moved" in power.refusal
        assert power.runs == ()
        # A refusal is the ABSENCE of a verdict. The ratchet must not read it as a drop to zero
        # and blame the catalogue for a floor that simply no longer applies — so it is a
        # CannotSay, which is neither an Ok nor a NotOk, and exits 3 (unusable != failed).
        verdict = check_power(power, None, floor_cases=5, floor_runs=5)
        assert isinstance(verdict, CannotSay)
        assert not isinstance(verdict, Ok | NotOk)

    def test_an_unknown_version_is_not_a_matching_one(self) -> None:
        floor = _baseline({"a|fr": True}, version="63-071edbdc")
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 5), version=""),
            _sample("w", _repeat({"a|fr": True}, 5), version=""),
        )
        assert power.refusal is not None

    def test_passes_spanning_two_catalogues_cannot_be_pooled(self) -> None:
        floor = _baseline({"a|fr": True}, version="63-071edbdc")
        mixed = Sample(
            model="s",
            verdicts=({"a|fr": True}, {"a|fr": True}),
            catalogue_versions=("63-071edbdc", "64-deadbeef"),
        )
        power = classify(floor, mixed, _sample("w", _repeat({"a|fr": True}, 2)))
        assert power.refusal is not None
        assert "more than one catalogue" in power.refusal

    def test_a_modelless_pass_is_refused__the_witness_is_tokens(self) -> None:
        """A dead backend does not crash the runner: it completes every case, still writes
        ``model: "llama3.2:3b"``, and scores a clean 70%. Pooling such a pass into a
        model's sample would drag every count toward the floor and read as a measurement.
        """
        report: dict[str, Any] = {
            "model": "llama3.2:3b",
            "catalogue_version": "2-abc",
            "cost": {"output_tokens": 0},
            "results": [{"case_id": "a", "language": "fr", "passed": True}],
        }
        with pytest.raises(ValueError, match="0 output tokens"):
            Sample.from_reports("llama3.2:3b", [report])


# --------------------------------------------------------------------------------------
# The ratchet — and the mutation that proves it can go red.
# --------------------------------------------------------------------------------------


class TestThePowerRatchet:
    def test_it_passes_when_the_power_holds__and_the_ok_carries_what_it_examined(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        verdict = check_power(power, power, floor_cases=1, floor_runs=1)
        assert isinstance(verdict, Ok)
        # Not a bare True. It says what it looked at — the whole point of the type.
        assert "re-derived from the committed matrix" in verdict.evidence
        assert "minimum detectable effect" in verdict.evidence

    def test_removing_a_discriminating_case_turns_it_red(self) -> None:
        """The mutation the whole ratchet exists for.

        A case that separates a good model from a bad one is the scarcest thing in this
        repository. Deleting one must be loud.
        """
        floor = _baseline({"a|fr": False, "b|fr": False})
        strong = _sample("s", _repeat({"a|fr": True, "b|fr": True}, 15))
        weak = _sample("w", _repeat({"a|fr": False, "b|fr": False}, 15))
        full = classify(floor, strong, weak)
        assert full.discriminating_cases == 2

        # Now delete case "b" from the catalogue and re-measure.
        cut = _baseline({"a|fr": False})
        cut_power = classify(
            cut,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        assert cut_power.discriminating_cases == 1

        verdict = check_power(cut_power, None, floor_cases=2, floor_runs=2)
        assert isinstance(verdict, NotOk)
        assert "LOST discriminating power" in verdict.reason

    def test_removing_the_reversed_case_turns_it_red_too(self) -> None:
        """The correction, ratcheted.

        ``08_prompt_injection_beneficiaire|en`` is the catalogue's only certified evidence that
        the model which ships resists a prompt injection *worse* than a model a third its size.
        Under the earlier taxonomy — "reversed: an anomaly, never a credit" — deleting it would
        have cost the ratchet nothing, and the finding would have left with it.
        """
        floor = _baseline({"a|fr": False, "rev|fr": False})
        strong = _sample("s", _repeat({"a|fr": True, "rev|fr": False}, 15))
        weak = _sample("w", _repeat({"a|fr": False, "rev|fr": True}, 15))
        full = classify(floor, strong, weak)
        assert {r.key: r.klass for r in full.runs} == {
            "a|fr": "discriminating",
            "rev|fr": "reversed",
        }
        assert full.discriminating_runs == 2  # BOTH are credited.

        cut = classify(
            _baseline({"a|fr": False}),
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        verdict = check_power(cut, None, floor_cases=2, floor_runs=2)
        assert isinstance(verdict, NotOk)
        assert "LOST discriminating power" in verdict.reason

    def test_adding_a_dead_case_cannot_hide__it_moves_the_catalogue_version(self) -> None:
        """A dead case does not lower the count, so the floor alone cannot catch it.

        What catches it is the pin: the classification names the catalogue it describes, and
        a catalogue that gains a case is a different catalogue. The frozen classification is
        then REFUSED (never silently reinterpreted) until someone re-measures — at which
        point the density drop is in the diff, for a human to argue with.
        """
        floor = _baseline({"a|fr": False}, version="1-aaa")
        strong = _sample("s", _repeat({"a|fr": True}, 15), version="1-aaa")
        weak = _sample("w", _repeat({"a|fr": False}, 15), version="1-aaa")
        power = classify(floor, strong, weak)
        assert power.discriminating_cases == 1

        # Someone adds a dead case. The runs are now scored against a 2-case catalogue.
        floor2 = _baseline({"a|fr": False, "dead|fr": True}, version="1-aaa")
        strong2 = _sample("s", _repeat({"a|fr": True, "dead|fr": True}, 15), version="2-bbb")
        weak2 = _sample("w", _repeat({"a|fr": False, "dead|fr": True}, 15), version="2-bbb")
        power2 = classify(floor2, strong2, weak2)
        assert power2.refusal is not None  # NOT graded, and not a green either.

    def test_a_drifted_classification_is_caught_run_by_run(self) -> None:
        floor = _baseline({"a|fr": False})
        frozen = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        # The evidence changed: the strong model no longer separates.
        now = classify(
            floor,
            _sample("s", _repeat({"a|fr": False}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        verdict = check_power(now, frozen, floor_cases=0, floor_runs=0)
        assert isinstance(verdict, NotOk)
        assert "classification drifted: a|fr: discriminating -> unreached" in verdict.reason


# --------------------------------------------------------------------------------------
# The committed evidence — the classification must be REPRODUCIBLE from it.
# --------------------------------------------------------------------------------------


class TestTheCheckAsksTheCatalogueNotItsOwnArtefacts:
    """The hole this ratchet fell into, and the guard that keeps it out.

    ``make eval-power`` was **green with two of its three certified discriminators deleted from
    disk**. It re-derived a 63-case classification from a 63-column matrix against a 63-case null
    floor — three committed artefacts, in perfect agreement with one another, all three describing
    a catalogue that no longer existed. Not one of them had ever opened ``eval/failures/``.

    That is ADR 0026 exactly: *a witness interrogates the thing, never its neighbourhood* — and it
    is the fourth time in this repository. So the CLI now derives the catalogue's identity from the
    **case files**, with the same function the runner stamps reports with, and refuses the moment
    it disagrees with the floor everything else is pinned to.
    """

    def test_the_cli_derives_the_catalogue_identity_from_the_case_files(self) -> None:
        from eval.ratchet import catalogue_on_disk, catalogue_version

        ids = [
            p.stem
            for p in sorted((REPO / "eval" / "failures").glob("*.json"))
            if not p.stem.startswith("_")
        ]
        assert catalogue_on_disk(REPO / "eval" / "failures") == catalogue_version(ids)

    def test_a_catalogue_that_is_not_there_is_a_blind_spot__never_an_empty_one(
        self, tmp_path: Path
    ) -> None:
        """An unreadable catalogue must not read as a catalogue of zero cases.

        ``catalogue_version([])`` is a perfectly good string — ``"0-e3b0c442"`` — and a check that
        computed it would have compared two hashes, found them different, and refused for the
        *wrong reason*, or worse, matched an equally empty floor and passed. The absence of the
        thing is not a property of the thing.
        """
        from eval.ratchet import catalogue_on_disk

        assert catalogue_on_disk(tmp_path / "does-not-exist") is None
        assert catalogue_on_disk(tmp_path) is None  # exists, but empty

    def test_deleting_a_case_makes_the_committed_evidence_describe_a_dead_catalogue(
        self, tmp_path: Path
    ) -> None:
        """The mutation, at the level the CLI reads it.

        The committed artefacts do not change when a case file is deleted — that is the whole
        point, and the whole danger. What changes is the catalogue, and only something that looks
        at the catalogue can see it.
        """
        from eval.ratchet import catalogue_on_disk, catalogue_version

        cut = tmp_path / "failures"
        cut.mkdir()
        kept = [
            p
            for p in sorted((REPO / "eval" / "failures").glob("*.json"))
            if not p.stem.startswith("_") and p.stem != "26_citation_fabrication_cjue"
        ]
        for p in kept:
            (cut / p.name).write_bytes(p.read_bytes())

        frozen = load_power(CLASSIFICATION)
        mutated = catalogue_on_disk(cut)
        assert mutated is not None
        assert (
            mutated != frozen.catalogue_version
        ), "deleting a case did not change the catalogue's identity — the pin is not a pin"
        assert mutated == catalogue_version([p.stem for p in kept])


class TestTheCommittedMeasurement:
    """These read the real artefacts. If the evidence is gone, this is RED, never skipped:
    a test that cannot see must report a blind spot, not a pass (ADR 0026)."""

    def test_the_evidence_and_the_classification_are_both_committed(self) -> None:
        assert SAMPLES.exists(), f"the evidence is missing: {SAMPLES}"
        assert CLASSIFICATION.exists(), f"the classification is missing: {CLASSIFICATION}"

    def test_the_classification_is_reproducible_from_the_stored_runs(self) -> None:
        """Re-derived from the committed matrix, it reproduces the committed verdict —
        run for run, class for class. This is what makes it a measurement and not a claim.
        """
        from eval.ratchet import load_baseline

        _keys, strong, weak = load_samples(SAMPLES)
        power = classify(load_baseline(NULL_CONTROL), strong, weak)
        assert power.refusal is None

        frozen = load_power(CLASSIFICATION)
        assert {r.key: r.klass for r in power.runs} == {r.key: r.klass for r in frozen.runs}
        assert power.discriminating_cases == frozen.discriminating_cases
        assert power.discriminating_runs == frozen.discriminating_runs

    def test_it_is_a_pure_function__classifying_twice_gives_the_same_verdict(self) -> None:
        from eval.ratchet import load_baseline

        _keys, strong, weak = load_samples(SAMPLES)
        floor = load_baseline(NULL_CONTROL)
        first = dump_power(classify(floor, strong, weak))
        second = dump_power(classify(floor, strong, weak))
        assert first == second

    def test_every_committed_pass_carries_a_liveness_witness(self) -> None:
        payload = json.loads(SAMPLES.read_text(encoding="utf-8"))
        for side in ("strong", "weak"):
            passes = payload[side]["passes"]
            assert passes, f"{side} has no passes"
            for p in passes:
                assert p["output_tokens"] > 0, f"{side} {p['source']}: no model spoke"
                assert len(p["sha256"]) == 64, f"{side} {p['source']}: no hash of the raw run"

    def test_the_committed_floor_matches_what_the_evidence_measures(self) -> None:
        """The frozen number in the CLI must be the number the evidence produces.

        A floor that drifted below the measurement would read green while the catalogue
        silently lost power — the ratchet would be policing a number nobody measured.
        """
        from scripts.check_discrimination import POWER_FLOOR_CASES, POWER_FLOOR_RUNS

        frozen = load_power(CLASSIFICATION)
        assert frozen.discriminating_cases == POWER_FLOOR_CASES
        assert frozen.discriminating_runs == POWER_FLOOR_RUNS

    def test_the_classification_describes_the_current_catalogue(self) -> None:
        """The pin. A classification is only true of the case set it was measured on.

        Add a case, delete one, rename one — and every count in the committed
        classification is about runs that no longer exist. This asks the catalogue itself
        (the case files on disk), not the artefact's own say-so: an artefact that asserted
        its own currency would be a witness interrogating its neighbourhood (ADR 0026).

        When this goes red the remedy is `make eval-power-write`, never editing the pin.
        """
        from eval.ratchet import catalogue_version

        case_ids = [
            p.stem
            for p in sorted((REPO / "eval" / "failures").glob("*.json"))
            if not p.stem.startswith("_")
        ]
        current = catalogue_version(case_ids)
        frozen = load_power(CLASSIFICATION)
        assert frozen.catalogue_version == current, (
            f"the catalogue moved: the classification was measured on "
            f"{frozen.catalogue_version!r}, the case files now say {current!r}. Every count "
            f"in it describes runs that no longer exist. Re-measure (`make eval-power-write`)."
        )
