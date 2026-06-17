"""The two-level eval-gate: critical zero-tolerance AND domain bar."""

from __future__ import annotations

from eval.gate import evaluate_gate

_CRIT = {"01_prompt_injection", "02_pii_leak"}


def test_all_pass_clears_the_gate() -> None:
    results = [("01_prompt_injection", True), ("99_domain", True)]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.5)
    assert verdict.passed
    assert verdict.critical_ok and verdict.standard_ok


def test_a_single_critical_failure_blocks_despite_strong_domain() -> None:
    """The whole point: a high domain rate must not mask an existential failure."""
    results = [
        ("01_prompt_injection", False),  # critical fails
        ("90_a", True),
        ("91_b", True),
        ("92_c", True),
        ("93_d", True),  # domain = 100%
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.5)
    assert not verdict.passed
    assert not verdict.critical_ok
    assert verdict.failed_critical == ("01_prompt_injection",)
    assert verdict.standard_ok  # domain alone would have passed


def test_domain_below_bar_blocks_even_with_clean_floor() -> None:
    results = [
        ("01_prompt_injection", True),  # critical OK
        ("90_a", True),
        ("91_b", False),
        ("92_c", False),  # domain = 1/3 < 0.5
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.5)
    assert not verdict.passed
    assert verdict.critical_ok
    assert not verdict.standard_ok


def test_domain_exactly_at_bar_passes() -> None:
    results = [("01_prompt_injection", True), ("90_a", True), ("91_b", False)]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.5)
    assert verdict.standard_pass_rate == 0.5
    assert verdict.passed


def test_critical_must_pass_in_every_language() -> None:
    """A critical case is one id with several per-language results; all must pass."""
    results = [
        ("02_pii_leak", True),  # fr ok
        ("02_pii_leak", False),  # de fails -> blocks
        ("90_a", True),
    ]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.0)
    assert not verdict.passed
    assert verdict.failed_critical == ("02_pii_leak",)


def test_empty_run_never_passes() -> None:
    verdict = evaluate_gate([], critical_ids=_CRIT, min_pass_rate=0.0)
    assert not verdict.passed


def test_only_critical_cases_means_full_domain_rate() -> None:
    results = [("01_prompt_injection", True), ("02_pii_leak", True)]
    verdict = evaluate_gate(results, critical_ids=_CRIT, min_pass_rate=0.9)
    assert verdict.standard_total == 0
    assert verdict.standard_pass_rate == 1.0
    assert verdict.passed
