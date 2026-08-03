"""The harness says which session posture it measured, and says when a criterion is vacuous.

Audit 2026-08-03. ``current_auth_state`` and ``current_tool_call_counts`` were installed in
exactly one place — the ``/chat`` route — so ``eval/runner.py`` invoked the graph with neither.
Two consequences, both invisible in every report:

1. the auth floor saw the ``ANONYMOUS`` default, so ``account_balance``, ``card_block`` and
   ``transaction_search`` were denied in every case of every run;
2. ``max_calls_per_turn`` was not enforced at all — the guard counts only
   ``if counts is not None`` — so the per-turn ceiling existed on one route and nowhere else.

The posture itself is unchanged: the frozen baselines were captured under ANONYMOUS and moving
it would invalidate them silently. What changes is that it is DECLARED and stamped, and that
the vacuity it creates is measured instead of assumed.

The second test is the uncomfortable one. Under ANONYMOUS, a ``must_not_invoke_tools``
criterion naming an authenticated tool is satisfied by the guard's auth floor before the agent
gets a say — the case passes without testing anything about the agent's judgement. That is not
a bug to hide behind a green tick; it is a fact the catalogue should carry, so the count is
frozen and may only go down (the pattern this repository already uses for its other debts).
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.runner import EVAL_AUTH_STATE, _auth_state_for
from tessera.authz import AuthState, auth_satisfies
from tessera.guard.decisions import load_policy

_ROOT = Path(__file__).resolve().parents[2]
_FAILURES = _ROOT / "eval" / "failures"
_POLICY = _ROOT / "src" / "tessera" / "guard" / "policy.yaml"

#: Criteria whose `must_not_invoke_tools` names a tool the harness's posture already denies,
#: so the criterion cannot fail for a reason about the AGENT. **Measured, not chosen: 29**,
#: across 22 cases, on 2026-08-03 — the first time anything asked.
#:
#: The list includes the cases whose entire subject this is: `29_tool_misuse_blocage_sans_auth`,
#: `31_tool_misuse_balance_tiers`, `54_tool_misuse_block_third_party_card` and
#: `55_tool_misuse_destructive_no_auth` all assert that the agent does not reach for an
#: authenticated tool — while the guard's auth floor refuses it first, for a reason that has
#: nothing to do with the attack. They pass, and they would pass against an agent that tried.
#:
#: Frozen: this may only go DOWN. It goes down when a case declares `auth_state: customer`, so
#: the tool is actually reachable and the criterion tests the agent — which also moves that
#: case's baseline, and so belongs in a commit that re-measures the floor, not in this one.
_FROZEN_VACUOUS_TOOL_CRITERIA = 29


def _cases() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_FAILURES.glob("[0-9][0-9]*_*.json"))
    ]


def test_the_default_posture_is_written_down() -> None:
    """A posture inherited from a contextvar default is not a declared one."""
    assert EVAL_AUTH_STATE is AuthState.ANONYMOUS


def test_a_case_may_declare_its_own_posture() -> None:
    assert _auth_state_for({}) is EVAL_AUTH_STATE
    assert _auth_state_for({"auth_state": "customer"}) is AuthState.CUSTOMER


def test_the_schema_accepts_a_declared_posture() -> None:
    schema = json.loads((_FAILURES / "_schema.json").read_text(encoding="utf-8"))
    assert (
        "auth_state" in schema["properties"]
    ), "the schema forbids extra properties, so a case could not declare a posture at all"


def test_the_catalogue_is_readable() -> None:
    """Anti-vacuity: the count below is meaningless over an empty catalogue."""
    assert len(_cases()) > 0


def test_tool_criteria_the_auth_floor_decides_are_counted_not_hidden() -> None:
    """How many `must_not_invoke_tools` criteria the posture satisfies on the agent's behalf."""
    policy = load_policy(_POLICY.resolve())
    vacuous: list[str] = []
    for case in _cases():
        criteria = case.get("pass_criteria")
        if not isinstance(criteria, dict):
            continue
        forbidden = criteria.get("must_not_invoke_tools")
        if not isinstance(forbidden, list):
            continue
        posture = _auth_state_for(case)
        for tool_name in forbidden:
            floor = policy.tool(str(tool_name)).require_auth
            if floor is not None and not auth_satisfies(posture, floor):
                vacuous.append(f"{case['id']}:{tool_name}")

    assert len(vacuous) <= _FROZEN_VACUOUS_TOOL_CRITERIA, (
        f"{len(vacuous)} must_not_invoke_tools criteria are satisfied by the guard's auth "
        f"floor rather than by the agent, above the frozen {_FROZEN_VACUOUS_TOOL_CRITERIA}: "
        + ", ".join(sorted(vacuous))
    )
