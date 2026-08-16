"""Every declared component can say what it is, in every language the cockpit is read in.

The hole this closes was found by walking into it. Adding the thirteenth component
(`public-canonical`, ADR 0052 §Amendment 2) meant adding `health.components.role.public-canonical`
to three catalogues, and **nothing in the repository would have said so**. next-intl does not
throw on a missing key: it renders the KEY PATH, so the observability page would have shown a row
labelled `health.components.role.public-canonical` — in production, in three languages, under a
heading about how trustworthy the monitoring is.

Two directions, because only one of them is the interesting failure:

* a component with no translation — the shipping accident above;
* a translation for a component that no longer exists — dead weight that makes the catalogue
  look more complete than it is, and the reason a translator cannot tell what still matters.

Read from `webapp/frontend/messages/`, which is the ONE copy: `Dockerfile.agent` copies that
directory into `src/tessera/observability/data/messages` at build time precisely so the repo never
holds two (see its COPY line and the comment above it).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessera.observability.stack_components import STACK_COMPONENTS

_MESSAGES = Path(__file__).resolve().parents[2] / "webapp" / "frontend" / "messages"
_LOCALES = ("fr", "de", "en")


def _roles(locale: str) -> dict[str, str]:
    payload = json.loads((_MESSAGES / f"{locale}.json").read_text(encoding="utf-8"))
    roles = payload["health"]["components"]["role"]
    assert isinstance(roles, dict)
    return roles


def test_the_catalogues_are_where_this_test_looks() -> None:
    """The positive control: a moved `messages/` would empty every set below and read green."""
    for locale in _LOCALES:
        assert (_MESSAGES / f"{locale}.json").is_file(), f"no catalogue for {locale}"
    assert len(STACK_COMPONENTS) > 5, "the registry is suspiciously small — is it the right one?"


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_declared_component_has_a_role_in_this_language(locale: str) -> None:
    declared = {c.key for c in STACK_COMPONENTS}
    translated = set(_roles(locale))
    missing = sorted(declared - translated)
    assert not missing, (
        f"{locale}: no role for {missing}. next-intl renders the KEY PATH for a missing key, so "
        f"this ships as a row labelled 'health.components.role.{missing[0]}' on a page about "
        "whether the monitoring can be trusted."
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_role_survives_the_component_it_described(locale: str) -> None:
    declared = {c.key for c in STACK_COMPONENTS}
    orphans = sorted(set(_roles(locale)) - declared)
    assert not orphans, (
        f"{locale}: roles for components nobody declares: {orphans}. Either the component was "
        "removed and this line should go with it, or it was renamed and this row silently "
        "stopped being labelled."
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_a_role_is_a_sentence_not_a_placeholder(locale: str) -> None:
    """An empty or key-shaped value passes the two tests above while saying nothing."""
    for key, text in _roles(locale).items():
        assert text.strip(), f"{locale}: {key} has an empty role"
        assert not text.startswith("health."), f"{locale}: {key} carries a key path, not a role"
        assert key != text, f"{locale}: {key}'s role is just its key"
