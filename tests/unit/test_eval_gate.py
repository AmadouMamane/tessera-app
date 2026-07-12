"""The eval-gate: the critical floor, zero tolerance — and NOTHING else (ADR 0021)."""

from __future__ import annotations

from eval.gate import evaluate_gate

_CRIT = {"01_prompt_injection", "02_pii_leak"}


def test_all_pass_clears_the_gate() -> None:
    results = [("01_prompt_injection", True), ("99_domain", True)]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert verdict.passed
    assert verdict.critical_ok


def test_a_single_critical_failure_blocks_despite_strong_domain() -> None:
    """The whole point: a high domain rate must not mask an existential failure."""
    results = [
        ("01_prompt_injection", False),  # critical fails
        ("90_a", True),
        ("91_b", True),
        ("92_c", True),
        ("93_d", True),  # domain = 100%
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert not verdict.passed
    assert not verdict.critical_ok
    assert verdict.failed_critical == ("01_prompt_injection",)


def test_a_collapsed_domain_rate_does_not_block() -> None:
    """ADR 0021, asserted directly — this is the behaviour change, so it gets a test.

    Every domain bar we ever set (55% / 65% / 55%) sat below the catalogue's measured null
    floor: an agent whose LLM backends all point at a closed port clears them. A condition a
    disconnected system already satisfies cannot deny a release, so it was removed rather
    than raised. A domain rate of 1/3 now passes — and it *should*, because a bar that would
    have caught it would have had to be invented.
    """
    results = [
        ("01_prompt_injection", True),  # critical OK
        ("90_a", True),
        ("91_b", False),
        ("92_c", False),  # domain = 1/3
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert verdict.passed
    assert verdict.critical_ok
    assert verdict.standard_pass_rate < 0.5


def test_the_domain_rate_is_still_measured() -> None:
    """Removing the bar must not remove the measurement — the page still shows the rate."""
    results = [("01_prompt_injection", True), ("90_a", True), ("91_b", False)]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert (verdict.standard_passed, verdict.standard_total) == (1, 2)
    assert verdict.standard_pass_rate == 0.5
    assert "no bar" in verdict.render()


def test_critical_must_pass_in_every_language() -> None:
    """A critical case is one id with several per-language results; all must pass."""
    results = [
        ("02_pii_leak", True),  # fr ok
        ("02_pii_leak", False),  # de fails -> blocks
        ("90_a", True),
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert not verdict.passed
    assert verdict.failed_critical == ("02_pii_leak",)


def test_empty_run_never_passes() -> None:
    """Absence of proof is not proof — an empty run is blocked, not vacuously clean."""
    verdict = evaluate_gate([], critical_ids=_CRIT)
    assert not verdict.passed


def test_only_critical_cases_means_full_domain_rate() -> None:
    results = [("01_prompt_injection", True), ("02_pii_leak", True)]
    verdict = evaluate_gate(results, critical_ids=_CRIT)
    assert verdict.standard_total == 0
    assert verdict.standard_pass_rate == 1.0
    assert verdict.passed
