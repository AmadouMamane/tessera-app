"""Unit tests for localization completeness (ADR 0010, #77)."""

from __future__ import annotations

from tessera.observability.localization import assess_localization, flatten_keys


def test_flatten_nested_keys() -> None:
    keys = flatten_keys({"a": 1, "b": {"c": 2, "d": {"e": 3}}})
    assert keys == {"a", "b.c", "b.d.e"}


def test_complete_locale() -> None:
    cat = {
        "en": {"greeting": "hi", "nav": {"home": "Home"}},
        "fr": {"greeting": "salut", "nav": {"home": "Accueil"}},
    }
    report = assess_localization(cat)
    fr = report.locales[0]
    assert fr.locale == "fr"
    assert fr.n_missing == 0
    assert fr.completeness == 1.0
    assert fr.fallback_rate == 0.0


def test_missing_key_detected() -> None:
    cat = {
        "en": {"a": "1", "b": "2", "c": "3", "d": "4"},
        "de": {"a": "1", "b": "2"},
    }
    report = assess_localization(cat)
    de = report.locales[0]
    assert de.n_missing == 2
    assert de.completeness == 0.5
    assert de.fallback_rate == 0.5
    assert "c" in de.missing_sample


def test_default_excluded_from_locales() -> None:
    report = assess_localization({"en": {"a": "1"}, "fr": {"a": "1"}})
    assert {lc.locale for lc in report.locales} == {"fr"}
    assert report.n_default_keys == 1


def test_sorted_least_complete_first() -> None:
    cat = {
        "en": {"a": "1", "b": "2", "c": "3", "d": "4"},
        "fr": {"a": "1", "b": "2", "c": "3"},  # 75%
        "de": {"a": "1"},  # 25%
    }
    report = assess_localization(cat)
    assert report.locales[0].locale == "de"
    assert report.locales[-1].locale == "fr"
