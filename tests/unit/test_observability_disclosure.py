"""Unit tests for AI Act disclosure UX (ADR 0010, #134)."""

from __future__ import annotations

from tessera.observability.disclosure import DISCLOSURE_TEXT, disclosure_status


def test_all_locales_covered() -> None:
    report = disclosure_status()
    assert report.enabled is True
    assert report.article == "Art. 50"
    assert report.all_covered is True
    assert report.missing_locales == []


def test_texts_present_for_each_locale() -> None:
    report = disclosure_status()
    for locale in ("fr", "de", "en"):
        assert locale in report.texts
        assert len(report.texts[locale]) > 0


def test_missing_locale_detected() -> None:
    report = disclosure_status(["fr", "de", "en", "es"])
    assert report.all_covered is False
    assert "es" in report.missing_locales


def test_disclosure_mentions_ai() -> None:
    assert "IA" in DISCLOSURE_TEXT["fr"] or "ia" in DISCLOSURE_TEXT["fr"].lower()
    assert "KI" in DISCLOSURE_TEXT["de"]
    assert "AI" in DISCLOSURE_TEXT["en"]
