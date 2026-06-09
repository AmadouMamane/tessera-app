"""Localization completeness (ADR 0010, idea #77; locale routing is ADR 0006).

A trilingual product (FR / DE / EN) silently degrades when a translation key is
missing: next-intl falls back to the default locale, and a German customer is
shown English text without any error firing. This module makes that gap
measurable. It flattens the per-locale message catalogues and, against the
default locale's key set, reports each locale's completeness, the missing keys,
and the resulting fallback rate.

The comparison is pure over already-loaded message dictionaries; the endpoint
reads ``webapp/frontend/messages/{fr,de,en}.json`` and feeds them in. It catches
the regression the moment a key is added to ``en.json`` but not its siblings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["LocaleCompleteness", "LocalizationReport", "assess_localization", "flatten_keys"]

_DEFAULT_LOCALE = "en"
_MISSING_PREVIEW = 12


def flatten_keys(obj: object, prefix: str = "") -> set[str]:
    """Return the set of dotted leaf-key paths in a nested message dict."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                keys |= flatten_keys(value, path)
            else:
                keys.add(path)
    return keys


@dataclass(frozen=True, slots=True)
class LocaleCompleteness:
    """Completeness of one locale against the default."""

    locale: str
    n_keys: int
    n_missing: int
    completeness: float
    fallback_rate: float
    missing_sample: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LocalizationReport:
    """Localization completeness across the non-default locales."""

    default_locale: str
    n_default_keys: int
    locales: list[LocaleCompleteness] = field(default_factory=list)


def assess_localization(
    catalogues: dict[str, dict[str, object]],
    *,
    default_locale: str = _DEFAULT_LOCALE,
) -> LocalizationReport:
    """Assess each locale's completeness against the default locale.

    Args:
        catalogues: ``locale -> message dict`` for each locale.
        default_locale: The reference locale whose keys must all be present.

    Returns:
        A :class:`LocalizationReport`, locales ordered least-complete first.
    """
    default_keys = flatten_keys(catalogues.get(default_locale, {}))
    n_default = len(default_keys)

    locales: list[LocaleCompleteness] = []
    for locale, catalogue in catalogues.items():
        if locale == default_locale:
            continue
        keys = flatten_keys(catalogue)
        missing = sorted(default_keys - keys)
        completeness = (n_default - len(missing)) / n_default if n_default else 1.0
        locales.append(
            LocaleCompleteness(
                locale=locale,
                n_keys=len(keys),
                n_missing=len(missing),
                completeness=completeness,
                fallback_rate=len(missing) / n_default if n_default else 0.0,
                missing_sample=missing[:_MISSING_PREVIEW],
            )
        )

    locales.sort(key=lambda lc: lc.completeness)
    return LocalizationReport(
        default_locale=default_locale, n_default_keys=n_default, locales=locales
    )
