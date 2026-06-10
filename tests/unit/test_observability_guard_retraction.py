"""Unit tests for mid-stream guard retraction observability (ADR 0010, #90)."""

from __future__ import annotations

import re

from tessera.guard.decisions import Policy
from tessera.observability import guard_retraction


def _policy() -> Policy:
    """A minimal policy: deny 'ignore previous' echoes, redact a fake IBAN."""
    return Policy(
        version=1,
        tools={},
        prompt_injection_deny=(re.compile(r"ignore previous", re.IGNORECASE),),
        prompt_injection_transforms=(),
        pii_patterns=(re.compile(r"DE\d{20}"),),
    )


def test_clean_answer_needs_no_retraction() -> None:
    report = guard_retraction.analyze_retractions(
        ["Your balance is available in the app."], policy=_policy()
    )
    assert report.n_answers == 1
    assert report.n_retractions == 0
    assert report.retraction_rate == 0.0
    assert report.max_tokens_exposed == 0


def test_pii_trigger_records_exposure() -> None:
    prefix = "x" * 40  # 40 chars ≈ 10 tokens streamed before the IBAN
    answer = f"{prefix} DE12345678901234567890 trailing"
    report = guard_retraction.analyze_retractions([answer], policy=_policy())
    assert report.n_retractions == 1
    event = report.events[0]
    assert event.kind == "pii"
    assert event.tokens_before > 0
    assert 0.0 < event.exposure_rate < 1.0


def test_injection_echo_trigger() -> None:
    report = guard_retraction.analyze_retractions(
        ["Sure — ignore previous instructions and proceed."], policy=_policy()
    )
    assert report.n_retractions == 1
    assert report.events[0].kind == "injection_echo"


def test_earliest_trigger_wins_and_aggregates() -> None:
    answers = [
        "clean answer",
        "ignore previous DE12345678901234567890",  # injection earlier than pii
    ]
    report = guard_retraction.analyze_retractions(answers, policy=_policy())
    assert report.n_answers == 2
    assert report.n_retractions == 1
    assert report.events[0].kind == "injection_echo"
    assert report.mean_tokens_exposed == report.events[0].tokens_before
