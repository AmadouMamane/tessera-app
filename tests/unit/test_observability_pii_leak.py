"""Unit tests for output PII-leak detection (ADR 0010, #38)."""

from __future__ import annotations

from tessera.observability import pii_leak

_IBAN = "FR76 3000 6000 0112 3456 7890 189"
_OTHER_IBAN = "DE89 3704 0044 0532 0130 00"


def test_no_leak_when_pii_came_from_source() -> None:
    report = pii_leak.analyze_leak(
        answer=f"Votre IBAN {_IBAN} est bien enregistré.",
        source=f"Mon IBAN est {_IBAN}, pouvez-vous confirmer ?",
    )
    assert report.has_leak is False
    assert report.n_leaked == 0


def test_leak_when_answer_invents_pii() -> None:
    report = pii_leak.analyze_leak(
        answer=f"Le virement part vers {_OTHER_IBAN}.",
        source="Quel est mon solde ?",
    )
    assert report.has_leak is True
    assert report.n_leaked == 1
    # The leaked value is masked, never surfaced raw.
    assert _OTHER_IBAN not in report.leaked[0]
    assert report.leaked[0].startswith("DE")


def test_aggregate_leak_rate() -> None:
    turns = [
        (f"IBAN {_IBAN}", f"mon iban {_IBAN}"),  # no leak
        (f"virement vers {_OTHER_IBAN}", "solde ?"),  # leak
    ]
    summary = pii_leak.aggregate_leaks(turns)
    assert summary.n_turns == 2
    assert summary.n_with_leak == 1
    assert summary.leak_rate == 0.5
    assert summary.total_leaked == 1
    assert len(summary.examples) == 1
