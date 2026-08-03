"""ADR 0021, locked down: no domain bar survives, and the contribution replacing it is real.

The removal is easy to undo by accident — a `min_pass_rate` added back to a manifest, a
threshold re-derived in the cockpit, a rate compared to a constant somewhere downstream.
These tests exist so that undoing it fails loudly.

The second half is the harder one, and it is the reason this file is not just a grep. ADR
0021 §3(a) claims the per-agent axis returns "free", because `check_contribution.py` run
against an agent-scoped report "intersects the report's keys with the floor". That is only
half true: Rule 1's population is an intersection and does narrow itself, but Rule 2's
DENOMINATOR is read straight off the committed baseline, so an unrestricted floor grades a
twenty-case set against the catalogue's fifty-two-run population — and the contribution
cannot reach the bar however good the model is. `restrict_baseline` is the fix, and
:func:`test_an_unrestricted_floor_would_misgrade_a_set` is the proof that it is load-bearing.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from eval.contribution import evaluate_contribution, floor_populations, restrict_baseline
from eval.ratchet import load_baseline
from eval.sets import list_eval_sets, load_eval_set
from tessera.observability.agent_evaluations import (
    _contribution_block as contribution_block,
    compute_agent_evaluations,
)
from tessera.observability.eval_data import load_agent_or_global_snapshot
from tessera.observability.eval_gate_view import structural_gate

_NULL_BASELINE = Path("eval/baselines/null-control.json")
_AGENTS = ("support-client", "onboarding", "recouvrement")


class TestNoBarSurvives:
    """A threshold must not exist — in a manifest, in the gate, or on the wire."""

    def test_no_manifest_declares_a_bar(self) -> None:
        for path in Path("eval/sets").glob("*.json"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            gate = raw.get("gate")
            if isinstance(gate, dict):
                assert "min_pass_rate" not in gate, path.name

    def test_the_loaded_gate_carries_a_rationale_and_no_number(self) -> None:
        for eval_set in list_eval_sets():
            assert eval_set.gate.rationale
            assert not hasattr(eval_set.gate, "min_pass_rate")

    def test_a_collapsed_domain_rate_does_not_block_the_structural_gate(self) -> None:
        """The behaviour change, at the tier grain: T2 may be a disaster and still ship.

        `06_...` is a T2 case in the catalogue's tier map; every one of its runs fails here
        and the verdict must still be PASS, because nothing critical failed. Before ADR 0021
        this returned BLOQUÉ (domaine) — against a bar a modelless agent already cleared.
        """
        socle = load_eval_set("socle-securite").case_ids
        triples: list[tuple[str, str, bool]] = [(cid, "fr", True) for cid in socle]
        triples += [(f"{i:02d}_domain_stub", "fr", False) for i in range(90, 99)]
        gate = structural_gate(triples)
        assert gate["passed"] is True
        domain = gate["domain"]
        assert isinstance(domain, dict)
        assert domain["gating"] is False
        assert "ok" not in domain and "min" not in domain
        assert "min_pass_rate" not in gate

    @pytest.mark.parametrize("agent_id", _AGENTS)
    def test_the_cockpit_serves_no_threshold(self, agent_id: str) -> None:
        gate = compute_agent_evaluations(agent_id, "fr")["gate"]
        assert isinstance(gate, dict)
        assert "min_pass_rate" not in gate
        domain = gate["domain"]
        assert isinstance(domain, dict)
        assert domain["gating"] is False
        assert "min" not in domain and "ok" not in domain


class TestTheContributionThatReplacesIt:
    """What the cockpit prints instead: a delta over a floor it did not choose."""

    @pytest.mark.parametrize("agent_id", _AGENTS)
    def test_the_contribution_is_measured_against_the_sets_own_floor(self, agent_id: str) -> None:
        gate = compute_agent_evaluations(agent_id, "fr")["gate"]
        assert isinstance(gate, dict)
        contribution = gate["contribution"]
        assert isinstance(contribution, dict)
        assert contribution["available"] is True

        # The floor is not a number the page chose: it is the committed null control,
        # restricted to this agent's set. Recompute it here and demand the same figures.
        eval_set = load_eval_set(agent_id)
        floor = restrict_baseline(load_baseline(_NULL_BASELINE), set(eval_set.effective_case_ids))
        _, floor_fail = floor_populations(floor)
        assert contribution["floor_passed"] == floor.passed
        assert contribution["floor_total"] == floor.total
        assert contribution["contribution_population"] == len(floor_fail)
        # Rule 2 is measured, never gated: a per-set bar would be an invented number.
        assert contribution["gated"] is False

    def test_an_unrestricted_floor_is_refused_not_misgraded(self) -> None:
        """ADR 0021 §3(a) is wrong that the per-set axis is free. This is why.

        Graded against the whole catalogue's floor, `recouvrement`'s real run used to read
        its contribution as a fraction of 52 runs — 32 of which its set does not even
        contain — and to fail Rule 2's bar of 30 by construction, at any model quality.
        `restrict_baseline` is what fixes the denominator.

        This test used to assert that the unrestricted floor produced that *wrong number*.
        It cannot any more, and the reason is the point: the run says it was scored against
        `28-990f1447` and the catalogue floor says `63-071edbdc`, so the gate now **refuses
        to grade at all** rather than grading against a population the run never covered. A
        wrong number and no number are different failures, and the stronger gate is the one
        that declines to invent the first.
        """
        report = json.loads(
            Path("eval/reports/local/latest_recouvrement.json").read_text(encoding="utf-8")
        )
        catalogue_floor = load_baseline(_NULL_BASELINE)
        set_floor = restrict_baseline(
            catalogue_floor, set(load_eval_set("recouvrement").effective_case_ids)
        )

        refused = evaluate_contribution(report, catalogue_floor, min_contribution=30)
        right = evaluate_contribution(report, set_floor, min_contribution=None)

        # The catalogue-wide floor does not apply to a per-set run, and says so.
        assert not refused.ok
        assert refused.refusal is not None
        assert "catalogue moved" in refused.refusal
        # It reports NO grade — not a zero, not a fraction of a population it cannot see.
        assert refused.contribution == 0
        assert refused.contribution_population == 0
        assert "REFUSED" in refused.render()
        assert "BLOCK" not in refused.render(), "a refusal is not a verdict on the model"

        # The set's own floor names the set's own cases, so it can judge the run.
        assert set_floor.catalogue_version == report["catalogue_version"] == "28-990f1447"
        assert right.refusal is None
        # It GRADES — which is the whole assertion. Whether that grade is a pass is a fact
        # about the model of the day, not about the denominator, and it must not be pinned
        # here: on 2026-08-04 the re-measured run reproduced the certified inversion on
        # `56_policy_violation_disparage_bank|de`, and a test asserting `right.ok` would have
        # gone red for the one reason a release gate exists to go red for.
        assert right.contribution_population == 13

    def test_a_modelless_run_is_not_reported_as_a_clean_contribution(self) -> None:
        """Zero output tokens = no model answered. It must degrade, not read as 0 regressions.

        The report's `model` field is written even when every backend is unreachable, and the
        deterministic layer still passes 70% of the catalogue — so a modelless run showing
        "contribution 0, regressions 0" would render as a clean bill of health for a model
        that never spoke. Generated tokens are the only witness.
        """
        snapshot = load_agent_or_global_snapshot("recouvrement")
        assert snapshot.token_totals()[1] > 0, "precondition: this committed run had a model"

        silent = replace(
            snapshot,
            sessions=tuple(replace(s, input_tokens=0, output_tokens=0) for s in snapshot.sessions),
        )
        assert silent.token_totals()[1] == 0

        block = contribution_block(silent, "fr")
        assert block["available"] is False
        # It degrades AND says why — an honest-empty that cannot explain itself sends the
        # reader hunting for a bug in the page instead of at the backend that never spoke.
        assert "no model spoke" in str(block["refusal"])
