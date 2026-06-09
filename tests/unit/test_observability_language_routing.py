"""Unit tests for language routing / code-switch (ADR 0010, #37)."""

from __future__ import annotations

from tessera.observability import language_routing as lr


def test_detect_language_picks_dominant() -> None:
    lang, confidence, _counts = lr.detect_language("Quel est le solde de mon compte ?")
    assert lang == "fr"
    assert confidence > 0.0


def test_detect_language_unknown_when_no_markers() -> None:
    lang, confidence, _ = lr.detect_language("xyzzy 123 ###")
    assert lang == "unknown"
    assert confidence == 0.0


def test_analyze_routing_flags_mismatch() -> None:
    analysis = lr.analyze_routing(text="What is my account balance?", served_language="fr")
    assert analysis.detected == "en"
    assert analysis.mismatch is True


def test_analyze_routing_no_mismatch_when_aligned() -> None:
    analysis = lr.analyze_routing(text="Wie kann ich mein Konto sehen?", served_language="de")
    assert analysis.mismatch is False


def test_aggregate_routing_rates() -> None:
    turns = [
        ("Quel est le solde de mon compte ?", "fr"),  # aligned
        ("What is my account balance?", "fr"),  # mismatch (en served as fr)
    ]
    report = lr.aggregate_routing(turns)
    assert report.n == 2
    assert report.mismatches == 1
    assert report.mismatch_rate == 0.5
