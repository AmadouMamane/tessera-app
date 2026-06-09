"""Unit tests for clickable/verifiable citations (ADR 0010, #132)."""

from __future__ import annotations

from tessera.observability.citation_resolver import resolve_citations

_SOURCES = {"DORA/art-5", "DORA/art-6", "GDPR/art-17", "CNIL/recommendation-2024"}


def test_empty_resolvable_rate_one() -> None:
    report = resolve_citations([], _SOURCES)
    assert report.n_citations == 0
    assert report.resolvable_rate == 1.0


def test_resolves_real_citation() -> None:
    report = resolve_citations(["DORA Article 5"], _SOURCES)
    assert report.n_resolved == 1
    assert report.links[0].resolved is True
    assert report.links[0].source == "DORA/art-5"


def test_dangling_citation() -> None:
    report = resolve_citations(["DORA Article 99"], _SOURCES)
    assert report.n_resolved == 0
    assert report.links[0].resolved is False
    assert report.links[0].source is None


def test_mixed() -> None:
    report = resolve_citations(["GDPR Article 17", "MiFID Article 2"], _SOURCES)
    assert report.n_citations == 2
    assert report.n_resolved == 1
    assert report.resolvable_rate == 0.5


def test_order_free_match() -> None:
    report = resolve_citations(["article 5 of DORA"], _SOURCES)
    assert report.links[0].resolved is True
