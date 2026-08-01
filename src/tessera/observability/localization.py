"""Localization completeness (ADR 0010, idea #77; locale routing is ADR 0006).

A trilingual product (FR / DE / EN) silently degrades when a translation key is
missing: next-intl falls back to the default locale, and a German customer is
shown English text without any error firing. This module makes that gap
measurable. It flattens the per-locale message catalogues and, against the
default locale's key set, reports each locale's completeness, the missing keys,
and the resulting fallback rate.

The comparison is pure over already-loaded message dictionaries;
:mod:`tessera.observability.message_catalogues` finds and reads them.

**Two things this used to get wrong.**

*It compared against ``en`` alone.* A key present in ``fr`` and ``de`` and missing from ``en``
was invisible, and the German operator's missing key was the one it could not see — the exact
direction the product's own French-first authoring makes most likely. The reference is now the
UNION of every locale's keys: a key that exists anywhere is a key the product uses, and a
locale lacking it falls back.

*It reported completeness over an empty reference.* ``(n - 0) / n if n else 1.0`` returns
**1.0** when the reference is empty, which is what the endpoint served in production for its
whole life: the catalogues live under ``webapp/``, the container ships only ``src`` and
``eval``, all three reads failed into ``{}``, and a compliance surface said 100 %. The report
now carries ``measured``, and a caller that could read nothing may not render a number.
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
    """Localization completeness across the locales."""

    default_locale: str
    n_default_keys: int
    locales: list[LocaleCompleteness] = field(default_factory=list)
    #: False when there was no reference to compare against. A report with
    #: ``measured=False`` carries no completeness worth rendering — the numbers below it are
    #: arithmetic over an empty set, and 100 % is what that arithmetic produces.
    measured: bool = True
    #: How many locales were actually compared. Zero is a blind spot, not a clean bill.
    n_locales: int = 0


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
        A :class:`LocalizationReport`, locales ordered least-complete first. When no catalogue
        could be read the report is ``measured=False`` with no locales — never 100 %.
    """
    per_locale = {locale: flatten_keys(catalogue) for locale, catalogue in catalogues.items()}

    # The UNION, not the default locale's set. A key authored in `fr` and never back-ported to
    # `en` is a key the product renders and one locale cannot answer; measuring against `en`
    # alone declared that case perfect. Which is worse than missing it: it reports on it.
    reference: set[str] = set()
    for keys in per_locale.values():
        reference |= keys
    n_reference = len(reference)

    if n_reference == 0:
        return LocalizationReport(
            default_locale=default_locale,
            n_default_keys=0,
            locales=[],
            measured=False,
            n_locales=0,
        )

    locales: list[LocaleCompleteness] = []
    for locale, keys in per_locale.items():
        missing = sorted(reference - keys)
        locales.append(
            LocaleCompleteness(
                locale=locale,
                n_keys=len(keys),
                n_missing=len(missing),
                completeness=(n_reference - len(missing)) / n_reference,
                fallback_rate=len(missing) / n_reference,
                missing_sample=missing[:_MISSING_PREVIEW],
            )
        )

    locales.sort(key=lambda lc: lc.completeness)
    return LocalizationReport(
        default_locale=default_locale,
        n_default_keys=n_reference,
        locales=locales,
        measured=True,
        n_locales=len(locales),
    )
