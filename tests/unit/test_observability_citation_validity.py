"""Unit tests for regulatory citation validity (ADR 0010, #49)."""

from __future__ import annotations

from tessera.observability import citation_validity as cv


def test_supported_citation_is_valid() -> None:
    report = cv.analyze_citations(
        answer="Selon l'article 5 de DORA, le management body est responsable.",
        context="Article 5 of the Digital Operational Resilience Act requires governance.",
    )
    assert report.n_citations == 1
    assert report.n_unsupported == 0
    assert report.validity_rate == 1.0


def test_fabricated_citation_is_flagged() -> None:
    report = cv.analyze_citations(
        answer="DORA Article 28(3) requires a 4-hour incident report.",
        context="Article 5 of DORA covers governance. Article 17 covers incident reporting.",
    )
    assert report.n_citations == 1
    assert report.n_unsupported == 1
    assert report.unsupported == ["Art. 28"]
    assert report.validity_rate == 0.0


def test_no_citations_is_vacuously_valid() -> None:
    report = cv.analyze_citations(answer="Votre solde est de 1 200 EUR.", context="solde 1200")
    assert report.n_citations == 0
    assert report.validity_rate == 1.0


def test_aggregate_validity() -> None:
    turns = [
        ("article 5 applies", "Article 5 of DORA"),  # supported
        ("article 99 applies", "Article 5 of DORA"),  # fabricated
    ]
    summary = cv.aggregate_citations(turns)
    assert summary.n_turns == 2
    assert summary.n_citations == 2
    assert summary.n_unsupported == 1
    assert summary.validity_rate == 0.5
    assert summary.unsupported_examples == ["Art. 99"]
