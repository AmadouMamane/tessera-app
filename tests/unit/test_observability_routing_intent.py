"""Unit tests for intent / router observability (ADR 0010, #63)."""

from __future__ import annotations

from tessera.observability import routing_intent as ri


def test_account_intent() -> None:
    intent, confidence, _ = ri.classify_intent("Quel est le solde de mon compte ?")
    assert intent == "account"
    assert confidence > 0.0


def test_regulation_intent() -> None:
    intent, _confidence, _ = ri.classify_intent("What does DORA article 5 require for compliance?")
    assert intent == "regulation"


def test_unknown_intent() -> None:
    intent, confidence, _ = ri.classify_intent("xyzzy foobar")
    assert intent == "unknown"
    assert confidence == 0.0


def test_aggregate_distribution_and_low_confidence() -> None:
    report = ri.aggregate_intents(
        [
            "Quel est le solde de mon compte ?",  # account
            "xyzzy",  # unknown → low confidence
        ]
    )
    assert report.n == 2
    assert report.distribution.get("account") == 1
    assert report.unknown == 1
    assert report.low_confidence == 1
    assert report.low_confidence_rate == 0.5
