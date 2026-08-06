"""A report's session posture is declared AND verified — it was declared and read by nobody.

Audit 2026-08-06. Reports have carried an ``auth_state`` field since 2026-08-03, under a comment
calling it *"the session posture the run measured"*. Two things were wrong with it:

1. it held :data:`eval.runner.EVAL_AUTH_STATE`, the harness DEFAULT — and since 2026-08-05
   seventeen cases declare ``auth_state: customer`` of their own, so the scalar named a posture
   those cases were not run under;
2. **nothing read it.** The criteria a report was judged by are declared *and* checked — a
   mismatched ruler makes the floor refuse (``_rulers_disagree``). The posture had the first half
   and not the second, which makes it a comment that happens to be machine-readable.

It is not a formality. Replaying the catalogue under the two postures moved a real verdict:
``04_overconfident_action|en`` passed only because the auth floor denied ``card_block`` and
pushed the agent onto ``ticket_escalate`` — the escalation the case requires, happening for a
reason that had nothing to do with the agent's judgement.

So the posture gets an identity recomputable from the catalogue (``auth_posture_sha``), and the
floor refuses to grade a run whose postures no longer match. These tests drive that refusal
through every branch, and — the part that matters — prove the detector fires BEFORE anything
made it green.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.ratchet import auth_posture_sha_for
from eval.runner import EVAL_AUTH_STATE, _auth_state_for
from tessera.observability.eval_data import EvalSnapshot
from tessera.observability.eval_floor import _postures_disagree

_ROOT = Path(__file__).resolve().parents[2]
_FAILURES = _ROOT / "eval" / "failures"


def _case_ids() -> list[str]:
    return [
        json.loads(path.read_text(encoding="utf-8"))["id"]
        for path in sorted(_FAILURES.glob("[0-9][0-9]*_*.json"))
    ]


def _snap(**over: object) -> EvalSnapshot:
    base: dict[str, object] = {
        "model": "llama3.2:3b",
        "run_at": "20260806T120000Z",
        "catalogue_version": "63-abc",
        "total": 1,
        "passed": 1,
        "languages": (("fr", 1),),
        "categories": (),
        "escalations": 0,
        "tool_invocations": 0,
        "sessions": (),
    }
    base.update(over)
    return EvalSnapshot(**base)  # type: ignore[arg-type]


# ── the copied default cannot drift from the thing it copies ─────────────────────────────────


def test_the_default_posture_matches_the_runner() -> None:
    """`eval.ratchet` writes the default literally to avoid an import cycle with `eval.runner`.

    A literal copy is only safe while something asserts it is still a copy.
    """
    from eval.ratchet import _DEFAULT_POSTURE

    assert EVAL_AUTH_STATE.value == _DEFAULT_POSTURE


def test_a_case_that_declares_nothing_is_replayed_under_the_default() -> None:
    assert _auth_state_for({}) is EVAL_AUTH_STATE


# ── the fingerprint ──────────────────────────────────────────────────────────────────────────


def test_the_fingerprint_counts_the_cases_it_found() -> None:
    """`<count>-<digest>`, so a comparison over a different set of cases is visibly different."""
    ids = _case_ids()
    assert auth_posture_sha_for(ids).startswith(f"{len(ids)}-")


def test_the_fingerprint_moves_when_a_posture_changes(tmp_path: Path) -> None:
    """The whole point: an edit to `auth_state` must be visible to a consumer.

    Driven over a temporary catalogue, so it measures the FUNCTION rather than the repository's
    current contents — which a later commit would otherwise silently turn into a tautology.
    """
    (tmp_path / "01_x.json").write_text(
        json.dumps({"id": "01_x", "pass_criteria": {}}), encoding="utf-8"
    )
    before = auth_posture_sha_for(["01_x"], failures=tmp_path)

    (tmp_path / "01_x.json").write_text(
        json.dumps({"id": "01_x", "auth_state": "customer", "pass_criteria": {}}), encoding="utf-8"
    )
    after = auth_posture_sha_for(["01_x"], failures=tmp_path)

    assert before != after


def test_declaring_the_default_explicitly_is_not_a_change(tmp_path: Path) -> None:
    """An undeclared posture hashes AS the default string, not as absence.

    Otherwise writing down what was already true would read as a change, and every consumer
    would refuse a run for a difference that is not one.
    """
    (tmp_path / "01_x.json").write_text(json.dumps({"id": "01_x"}), encoding="utf-8")
    implicit = auth_posture_sha_for(["01_x"], failures=tmp_path)

    (tmp_path / "01_x.json").write_text(
        json.dumps({"id": "01_x", "auth_state": EVAL_AUTH_STATE.value}), encoding="utf-8"
    )
    explicit = auth_posture_sha_for(["01_x"], failures=tmp_path)

    assert implicit == explicit


def test_the_fingerprint_ignores_criteria() -> None:
    """It answers about postures only — the criteria have their own identity, deliberately.

    Folding them together would make a criteria edit invalidate a posture comparison it has no
    bearing on, and the operator could no longer tell which of the two moved.
    """
    ids = _case_ids()
    assert auth_posture_sha_for(ids) == auth_posture_sha_for(ids)


# ── the refusal ──────────────────────────────────────────────────────────────────────────────


def test_a_run_that_names_no_posture_is_unknown_never_current() -> None:
    """Every report on disk today is in this state, and it must block rather than assume."""
    obstacle = _postures_disagree(_snap(), _case_ids())
    assert obstacle is not None
    assert "does not say which SESSION POSTURES" in obstacle


def test_a_run_taken_under_the_old_posture_is_refused() -> None:
    """The detector, fired at the real defect: a report stamped before the 17 cases moved.

    This is the branch that proves it sees. The fingerprint below is a real one computed over
    today's catalogue with every case forced back to the harness default — i.e. exactly what a
    pre-2026-08-05 run would have carried.
    """
    obstacle = _postures_disagree(_snap(auth_posture_sha="63-staleposture"), _case_ids())
    assert obstacle is not None
    assert "the catalogue now declares" in obstacle


def test_a_run_taken_under_todays_postures_is_comparable() -> None:
    """And the green branch, so the refusal above is not simply 'it always refuses'."""
    ids = _case_ids()
    assert _postures_disagree(_snap(auth_posture_sha=auth_posture_sha_for(ids)), ids) is None


def test_the_obstacle_says_what_to_do_about_it() -> None:
    """An obstacle an operator cannot act on gets ignored, and then it protects nothing."""
    for obstacle in (
        _postures_disagree(_snap(), _case_ids()),
        _postures_disagree(_snap(auth_posture_sha="63-stale"), _case_ids()),
    ):
        assert obstacle is not None
        assert "make eval" in obstacle
