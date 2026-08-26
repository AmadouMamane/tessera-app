"""The checker column over the labeled reformulation set is PINNED (ADR 0054 §4).

Same discipline as the intent regex ratchet: a pin, not a one-way ratchet. The
deterministic checker is layer 3's compliance floor — a reformulation ships only
where it beats "send the template as-is" WITHOUT losing a single check — so a
checker that silently stops catching a violation kind, or silently starts
failing faithful rewrites, corrupts every shadow number built on it. Both
directions must arrive as a visible re-measure.

To re-pin after a deliberate change (to the checker's rules, the templates, or
the set): run ``uv run python -m eval.reformulation_bench``, read the printed
counts, update the constants below with the new figures and set sha, and say so
in the commit. The pin is keyed to the set's content sha AND exercised over the
LIVE template renderers: a template wording change moves the rendered referent
and therefore re-opens the measurement by construction.
"""

from __future__ import annotations

from eval.reformulation_bench import (
    build_report,
    load_reformulation_set,
    score_checker_column,
)

#: Measured 2026-08-26 (uv run python -m eval.reformulation_bench), set 2026-08-26.1.
_PINNED_SET_SHA = "ff9fa63ca80be3e5f64df20b29210f948619347eab375c35b186da3e8ee46b84"
_PINNED_OVERALL = {
    "candidates": 46,
    "label_agreement": 46,
    "faithful_n": 9,
    "faithful_pass": 9,
    "violations_n": 37,
    "violations_caught": 37,
}
_PINNED_GATE = {"n": 15, "agreement": 15, "refused": 6}


def test_the_referent_is_the_one_the_pin_was_measured_on() -> None:
    """A changed set invalidates the pinned numbers by construction — re-measure, re-pin."""
    referent = load_reformulation_set()
    assert referent.sha256 == _PINNED_SET_SHA, (
        "the labeled set changed (sha "
        f"{referent.sha256[:12]}… vs pinned {_PINNED_SET_SHA[:12]}…) — the measurement is a "
        "property of the (set, checker, templates) triple: run "
        "`uv run python -m eval.reformulation_bench`, then update this pin"
    )


def test_checker_column_is_pinned_in_both_directions() -> None:
    """Every label agreed, every violation caught, every faithful rewrite passed — exactly."""
    referent = load_reformulation_set()
    candidate_verdicts, gate_verdicts = score_checker_column(referent.cases)
    report = build_report(referent, candidate_verdicts, gate_verdicts)
    checker = report["columns"]["checker"]  # type: ignore[index]
    assert checker["overall"] == _PINNED_OVERALL, (
        f"checker column moved: {checker['overall']} != {_PINNED_OVERALL} — a deliberate "
        "change re-pins with its measurement; anything else is a regression "
        f"(disagreements: {checker['disagreements']})"
    )
    assert checker["gate"] == _PINNED_GATE, (
        f"gate column moved: {checker['gate']} != {_PINNED_GATE} — the adversarial "
        "instructions must be refused BEFORE any model call (ADR 0054), and a widened "
        "vocabulary is a compliance decision, not a drift"
    )


def test_every_violation_kind_is_exercised_and_caught() -> None:
    """The referent covers each must-survive rule — a rule no case exercises polices nothing."""
    referent = load_reformulation_set()
    candidate_verdicts, _ = score_checker_column(referent.cases)
    report = build_report(referent, candidate_verdicts, [])
    by_violation = report["columns"]["checker"]["by_violation"]  # type: ignore[index]
    expected_kinds = {
        "amount_changed",
        "number_invented",
        "number_missing",
        "clause_missing",
        "signature_missing",
        "forbidden_term",
    }
    assert (
        set(by_violation) == expected_kinds
    ), f"violation coverage moved: {sorted(by_violation)} != {sorted(expected_kinds)}"
    for kind, bucket in by_violation.items():
        assert bucket["caught"] == bucket["n"], f"{kind}: {bucket['caught']}/{bucket['n']} caught"


def test_the_pin_has_teeth() -> None:
    """A checker made blind must turn this file red — otherwise the pin proves nothing."""
    referent = load_reformulation_set()
    generate_cases = [c for c in referent.cases if c.expected_gate == "generate"]
    assert generate_cases and any(
        c.candidates for c in generate_cases
    ), "the referent lost its generate-gated candidates — the pin would be vacuous"
    # A candidate that keeps NOTHING of the template must never pass the checker.
    from eval.reformulation_bench import render_case_template
    from tessera.recouvrement.reformulation import check_must_survive

    case = next(c for c in generate_cases if c.candidates)
    verdict = check_must_survive(
        render_case_template(case), "Bonjour, merci, cordialement.", language=case.language
    )
    assert not verdict.ok and verdict.failures
