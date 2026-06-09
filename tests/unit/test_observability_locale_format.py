"""Unit tests for locale-aware formatting correctness (ADR 0010, #51)."""

from __future__ import annotations

from tessera.observability import locale_format as lf


def test_classify_styles() -> None:
    assert lf.classify_number("4.567,89") == "de"
    assert lf.classify_number("4,567.89") == "en"
    assert lf.classify_number("4 567,89") == "fr"
    assert lf.classify_number("1234") == "ambiguous"


def test_correct_locale_no_violation() -> None:
    report = lf.analyze_formatting(answer="Le solde est de 4 567,89 €.", locale="fr")
    assert report.n_amounts == 1
    assert report.n_violations == 0


def test_wrong_locale_flagged() -> None:
    # English-formatted amount served in a French turn.
    report = lf.analyze_formatting(answer="Votre solde est de 4,567.89 €.", locale="fr")
    assert report.n_amounts == 1
    assert report.n_violations == 1
    assert report.violations == ["4,567.89"]


def test_dates_are_not_flagged() -> None:
    # A German date must not be mistaken for a misformatted amount.
    report = lf.analyze_formatting(answer="Der Vorfall war am 09.06.2026 gemeldet.", locale="de")
    assert report.n_violations == 0


def test_aggregate_rate() -> None:
    turns = [
        ("solde 4 567,89 €", "fr"),  # correct
        ("Kontostand 4,567.89 €", "de"),  # wrong (en style in de turn)
    ]
    summary = lf.aggregate_formatting(turns)
    assert summary.n_amounts == 2
    assert summary.n_violations == 1
    assert summary.correctness_rate == 0.5
