"""Per-agent evaluation sets: manifests are valid, curated, and bound to agents."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.sets import (
    SECURITY_FLOOR_SLUG,
    critical_case_ids,
    list_eval_sets,
    load_eval_set,
    load_security_floor,
    resolve_case_ids,
)
from tessera.agent.registry import list_agents

_FAILURES_DIR = Path(__file__).resolve().parents[2] / "eval" / "failures"


def _catalogue_ids() -> set[str]:
    return {p.stem for p in _FAILURES_DIR.glob("[0-9][0-9]*_*.json")}


def test_every_set_references_only_real_cases() -> None:
    known = _catalogue_ids()
    for eval_set in list_eval_sets():
        missing = [cid for cid in eval_set.case_ids if cid not in known]
        assert not missing, f"{eval_set.slug} references unknown cases: {missing}"


def test_catalogue_set_is_the_full_catalogue() -> None:
    full = load_eval_set("catalogue-echecs")
    assert set(full.case_ids) == _catalogue_ids()


def test_per_agent_sets_are_genuinely_different() -> None:
    """The whole point of Phase 4: each agent is judged on a distinct set."""
    sc = set(resolve_case_ids("support-client"))
    onb = set(resolve_case_ids("onboarding"))
    rec = set(resolve_case_ids("recouvrement"))
    # No two agent sets are identical.
    assert sc != onb
    assert sc != rec
    assert onb != rec
    # Each carries cases the others do not (domain-specific differentiation).
    assert sc - onb - rec, "support-client has no exclusive cases"
    assert onb - sc - rec, "onboarding has no exclusive cases"
    assert rec - sc - onb, "recouvrement has no exclusive cases"


def test_no_set_declares_a_threshold() -> None:
    """ADR 0021: a manifest states WHY its bar is what it is, and never a number.

    The `gate` object is `additionalProperties: false`, so reintroducing `min_pass_rate`
    (or any other bar) fails schema validation on load. This asserts the ban holds where it
    is enforceable — the loaded object carries a rationale and nothing to compare against.
    """
    for eval_set in list_eval_sets():
        assert not hasattr(eval_set.gate, "min_pass_rate"), eval_set.slug
        assert eval_set.gate.rationale, f"{eval_set.slug}: a gate must say why"


def test_every_agent_binds_a_loadable_set() -> None:
    for agent in list_agents():
        if not agent.eval_set:
            continue  # an ungoverned L1 agent (hello-agent, ADR 0017 §F) binds no eval set
        eval_set = load_eval_set(agent.eval_set)
        # The manifest's agent_id, when set, agrees with the binding agent.
        if eval_set.agent_id:
            assert eval_set.agent_id == agent.id


def test_unknown_slug_raises() -> None:
    with pytest.raises(KeyError):
        load_eval_set("does-not-exist")


def test_security_floor_is_all_critical() -> None:
    """Every case in the shared floor must be flagged critical in the catalogue."""
    floor = set(load_security_floor().case_ids)
    assert floor, "the security floor must not be empty"
    assert floor <= critical_case_ids()


def test_critical_cases_exist_and_are_marked() -> None:
    crit = critical_case_ids()
    assert crit <= _catalogue_ids()
    # The floor defines the universal critical surface; it is a subset of all
    # critical cases (an agent may carry additional domain-critical cases).
    assert set(load_security_floor().case_ids) <= crit


def test_floor_is_injected_into_every_agent_set() -> None:
    floor = set(load_security_floor().case_ids)
    for agent in list_agents():
        if not agent.eval_set:
            continue  # no eval set → no floor injection (eval-gating is L2, not L1)
        effective = set(resolve_case_ids(agent.eval_set))
        assert floor <= effective, f"{agent.eval_set} is missing floor cases"


def test_floor_does_not_recurse_into_itself() -> None:
    floor = load_security_floor()
    # The floor (no agent_id) is not re-injected with itself.
    assert floor.effective_case_ids == floor.case_ids


def test_full_catalogue_has_no_floor_injection() -> None:
    full = load_eval_set("catalogue-echecs")
    assert full.effective_case_ids == full.case_ids


def test_agent_sets_still_differ_after_floor_injection() -> None:
    sc = set(resolve_case_ids("support-client"))
    onb = set(resolve_case_ids("onboarding"))
    rec = set(resolve_case_ids("recouvrement"))
    assert sc != onb != rec != sc
    # The floor is the common core shared by all three.
    floor = set(load_security_floor().case_ids)
    assert floor <= (sc & onb & rec)


def test_floor_slug_constant_matches_a_real_set() -> None:
    assert load_eval_set(SECURITY_FLOOR_SLUG).slug == SECURITY_FLOOR_SLUG
