"""Tests for the policy-correct eval-gate view, three-tier map and waiver store.

These lock in the binding invariants of ``docs/design/eval-gate-policy.md``:
the verdict is the headline, the gate grain is (case, langue), Tier 0 is never
waivable (T0 inter derog = empty), the structural Venn sums to the totals, and
every counter reconciles across the payload.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eval.sets import load_security_floor
from tessera.observability.agent_evaluations import compute_agent_evaluations
from tessera.observability.eval_data import load_agent_or_global_snapshot
from tessera.observability.eval_gate_view import build_gate_view, structural_gate
from tessera.observability.eval_tiers import is_waivable, load_tier_map, tier_for
from tessera.observability.eval_waivers import effective_waivers, verify_waiver_chain


def test_tiers_partition_the_catalogue_without_overlap() -> None:
    tm = load_tier_map()
    # T0 is exactly the curated socle; T0 and T1 are disjoint (no waivable socle).
    assert tm.t0_cases == frozenset(load_security_floor().case_ids)
    assert not (tm.t0_cases & tm.t1_cases)
    # T0 is never waivable; T1 always is; T2 is graded (not waivable).
    for cid in tm.t0_cases:
        assert tier_for(cid) == "T0"
        assert not is_waivable(cid)
    for cid in tm.t1_cases:
        assert tier_for(cid) == "T1"
        assert is_waivable(cid)


def test_waiver_chain_verifies() -> None:
    # The seeded store is tamper-evident end to end.
    assert verify_waiver_chain()


def test_tier0_is_never_effectively_waived() -> None:
    snap = load_agent_or_global_snapshot("support-client")
    for ew in effective_waivers(snap.run_at):
        if ew.tier == "T0":
            # A waiver request on the socle is recorded but never active.
            assert not ew.active
            assert ew.status == "sans_effet_socle"


def test_expired_waiver_auto_re_blocks() -> None:
    snap = load_agent_or_global_snapshot("support-client")
    # Far in the future, every grant has lapsed -> none active (auto re-block).
    far = datetime.now(UTC) + timedelta(days=3650)
    assert all(not ew.active for ew in effective_waivers(snap.run_at, now=far))


def test_gate_view_counters_reconcile_at_case_language_grain() -> None:
    snap = load_agent_or_global_snapshot("support-client")
    gv = build_gate_view(snap)
    # Executions split exactly into passed + failed.
    assert gv.passed_exec + gv.failed_exec == gv.executions
    # The tier partition sums to the executions (structural Venn property).
    assert sum(gv.tier_counts.values()) == gv.executions
    # Critical breakdown reconciles: every T1 failure is either blocking or waived.
    t1_fail = sum(1 for s in gv.statuses if s.tier == "T1" and not s.passed and s.executed)
    assert gv.blocking_t1 + gv.waived_active == t1_fail
    # Every socle (T0) failure is a hard block (none can be waived).
    t0_fail = sum(1 for s in gv.statuses if s.tier == "T0" and not s.passed and s.executed)
    assert gv.blocking_socle == t0_fail


def test_structural_gate_carried_by_the_run_matches_the_render() -> None:
    # The run-carried structural gate (no waivers) must share the render's tier
    # classification; the only difference is the dynamic waiver delta layered at
    # render: structural.blocking_t1 == render.blocking_t1 + render.waived_active.
    snap = load_agent_or_global_snapshot("support-client")
    triples = [(s.case_id, s.language, s.passed) for s in snap.sessions]
    sg = structural_gate(triples)
    gv = build_gate_view(snap)
    assert sg["tier_counts"] == gv.tier_counts
    bd = sg["breakdown"]
    assert isinstance(bd, dict)
    assert bd["blocking_socle"] == gv.blocking_socle
    assert bd["blocking_t1"] == gv.blocking_t1 + gv.waived_active


def test_verdict_is_the_headline_and_tied_to_conformity() -> None:
    payload = compute_agent_evaluations("support-client")
    gate = payload["gate"]
    assert isinstance(gate, dict)
    # The verdict label is one of the policy's worded verdicts.
    assert gate["label"] in {
        "PASSE",
        "BLOQUÉ par le socle",
        "BLOQUÉ (critiques non dérogés)",
        "BLOQUÉ (domaine)",
    }
    # Colour/tone is tied to conformity: a block is never toned "good".
    if gate["passed"] is False:
        assert gate["tone"] != "good"
    # The structural Venn reconciles to the executions grain.
    venn = gate["venn"]
    assert isinstance(venn, dict)
    assert venn["socle"] + venn["t1"] + venn["domaine"] == venn["universe"]
    assert venn["reconciles"] is True
    # The critical-cases table and the breakdown agree.
    bd = gate["breakdown_grain"]
    cc = gate["critical_cases"]
    assert isinstance(bd, dict)
    assert isinstance(cc, dict)
    non_exec = bd["non_executed_critical"]
    assert bd["blocking_socle"] + bd["blocking_t1"] + bd["waived_active"] == cc["total"] - non_exec
