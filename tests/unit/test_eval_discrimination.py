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
    ALPHA,
    Sample,
    check_power,
    classify,
    dump_power,
    fisher_greater,
    holm_reject,
    load_power,
    load_samples,
)
from eval.ratchet import Baseline

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
        assert power.runs[0].klass == "undecided"
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

    def test_reversed__the_weak_model_separates__an_anomaly_never_a_credit(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": False}, 15)),
            _sample("w", _repeat({"a|fr": True}, 15)),
        )
        assert power.runs[0].klass == "reversed"
        assert not power.runs[0].measures_the_model

    def test_non_discriminating__both_models_always_pass_it(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": True}, 15)),
        )
        assert power.runs[0].klass == "non_discriminating"

    def test_non_discriminating__neither_model_ever_passes_it__unreached(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": False}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        assert power.runs[0].klass == "non_discriminating"

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
        # A refusal is the ABSENCE of a verdict. The ratchet must not read it as a drop
        # to zero and blame the catalogue for a floor that simply no longer applies.
        verdict = check_power(power, None, floor_cases=5, floor_runs=5)
        assert verdict.ok is False
        assert verdict.refusal is not None

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
    def test_it_passes_when_the_power_holds(self) -> None:
        floor = _baseline({"a|fr": False})
        power = classify(
            floor,
            _sample("s", _repeat({"a|fr": True}, 15)),
            _sample("w", _repeat({"a|fr": False}, 15)),
        )
        assert check_power(power, power, floor_cases=1, floor_runs=1).ok

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
        assert verdict.ok is False
        assert any("LOST discriminating power" in r for r in verdict.reasons)

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
        assert verdict.ok is False
        assert verdict.drift == ("a|fr: discriminating -> non_discriminating",)


# --------------------------------------------------------------------------------------
# The committed evidence — the classification must be REPRODUCIBLE from it.
# --------------------------------------------------------------------------------------


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
