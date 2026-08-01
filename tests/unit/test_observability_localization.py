"""Unit tests for localization completeness (ADR 0010, #77).

The reference key set is the **union** of every locale, not the default locale's. That is a
deliberate reversal, and the tests below carry the reason: measuring against `en` alone made a
key authored in `fr` and never back-ported invisible — `fr` had it, `en` did not, `en` was the
reference, so nothing was missing from anything. Two such keys existed in this repo
(`product.apercu.widget.minimize` / `.maximize`, an `aria-label` at `chat-widget.tsx:226`), and
the endpoint reported 100 % over both for as long as they had been there.

The default locale therefore APPEARS in the report now. It can be the incomplete one, and a
report that structurally cannot say so is not measuring the default locale — it is defining it
as correct.
"""

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

    assert report.measured is True
    assert report.n_locales == 2
    assert all(lc.n_missing == 0 and lc.completeness == 1.0 for lc in report.locales)
    assert all(lc.fallback_rate == 0.0 for lc in report.locales)


def test_missing_key_detected() -> None:
    cat = {
        "en": {"a": "1", "b": "2", "c": "3", "d": "4"},
        "de": {"a": "1", "b": "2"},
    }
    report = assess_localization(cat)
    de = report.locales[0]

    assert de.locale == "de"
    assert de.n_missing == 2
    assert de.completeness == 0.5
    assert de.fallback_rate == 0.5
    assert "c" in de.missing_sample


def test_the_default_locale_can_itself_be_the_incomplete_one() -> None:
    """The reversal, asserted. `en` is missing a key `fr` declares, and the report says so."""
    report = assess_localization({"en": {"a": "1"}, "fr": {"a": "1", "b": "2"}})

    assert report.n_default_keys == 2, "the reference is the UNION, not the default's key set"
    by_locale = {lc.locale: lc for lc in report.locales}
    assert set(by_locale) == {"en", "fr"}, "the default locale must be measured, not assumed"
    assert by_locale["en"].n_missing == 1
    assert by_locale["en"].missing_sample == ["b"]
    assert by_locale["fr"].n_missing == 0


def test_sorted_least_complete_first() -> None:
    cat = {
        "en": {"a": "1", "b": "2", "c": "3", "d": "4"},
        "fr": {"a": "1", "b": "2", "c": "3"},  # 75%
        "de": {"a": "1"},  # 25%
    }
    report = assess_localization(cat)

    assert [lc.locale for lc in report.locales] == ["de", "fr", "en"]


def test_nothing_readable_is_a_blind_spot_not_a_hundred_percent() -> None:
    """The production bug, as an assertion.

    The route resolved the catalogues under `webapp/`, which the agent image does not ship, and
    swallowed all three failures into `{}`. The reference was empty, and
    `(n - 0) / n if n else 1.0` returned **1.0** — a hundred percent over nothing, served on a
    compliance surface for the endpoint's entire life. ADR 0026: a witness that cannot see
    reports a blind spot; it may never report "ok".
    """
    report = assess_localization({"en": {}, "fr": {}, "de": {}})

    assert report.measured is False
    assert report.locales == []
    assert report.n_locales == 0
    assert report.n_default_keys == 0
