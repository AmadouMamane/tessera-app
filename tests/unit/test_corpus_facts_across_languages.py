"""The three product bundles are not translations, and nothing could tell that from a typo.

`docs/multilingual.md` claimed the DE and EN product corpora were produced from the French one
by `corpus/translator.py`, "aligned in structure and coverage". They are not, and until
2026-08-04 the repository could not have noticed: the three bundles shared no key at all. Each
document was addressed by a localised slug — `produits/livret-aurore`,
`produkte/sparkonto-aurore`, `products/savings-account` — so there was no way to ask what the
German version of a French document said.

The divergences are about money. The French Livret states the statutory 22 950 € ceiling; the
German savings account states none. Both may well be correct — a French *livret réglementé* and
a German *Sparkonto* are not the same product — but **nothing said so**, and that is the defect:
a deliberate product difference and a mistyped amount were indistinguishable, and one of them is
a bank telling a customer a wrong number.

So this file does two things and refuses to do a third:

* it **pairs** the bundles by `metadata.doc_id`, and asserts the pairing stays possible;
* it **freezes** what disagrees today, so nothing new joins the list in silence;
* it does **not** decide. Whether each divergence is a product fact or an error is a question
  for somebody who knows the products. Every entry below is undeclared until then, and leaves
  the registry when it is triaged — the count may only go down.

A first attempt at this comparison reported twelve of thirteen documents as divergent, because
it read German `1.500 €` as one and a half euros. A witness that cries wolf on a locale
convention hides the eight real findings behind five false ones, so the notation handling in
:mod:`tessera.corpus.alignment` is asserted here before anything else is.
"""

from __future__ import annotations

from typing import Final

import pytest

from tessera.corpus.alignment import (
    LANGUAGES,
    figures,
    load_aligned,
    misaligned_figures,
)

#: What disagrees today, measured — never hand-typed. **Undeclared**: nobody has yet said, for
#: any of these, whether it is a product difference or a mistake. The list may only shrink, and
#: an entry leaves it by being triaged, never by being deleted to make a test pass.
#:
#: The one worth reading first is `savings-account`: 22 950 € is the French Livret A ceiling,
#: written into French law. The German version states no ceiling at all. If that is deliberate
#: it is worth a sentence in the corpus; if it is not, a German customer is being told they may
#: deposit without limit.
_FROZEN_DIVERGENCES: Final[dict[str, dict[str, list[float]]]] = {
    "card-blocking": {"fr": [19.0, 133.0]},
    "current-account": {"fr": [76.0]},
    "customer-service": {"de": [17.0, 20.0], "en": [5.0], "fr": [17.0, 20.0]},
    "general-account-terms": {
        "de": [3.0, 100000.0],
        "en": [100000.0],
        "fr": [4.0, 8.0, 20.0, 30.0, 50.0, 80.0],
    },
    "mortgage": {
        "de": [30.0],
        "en": [7.0, 15.0, 20.0, 25.0, 27.0],
        "fr": [3.0, 7.0, 15.0, 20.0, 25.0, 27.0],
    },
    "savings-account": {"de": [25.0, 1000.0, 2000.0], "fr": [1.0, 15.0, 16.0, 2025.0, 22950.0]},
    "visa-classic": {"fr": [24.0]},
    "visa-premier": {"fr": [24.0]},
}


class TestTheNotationIsReadBeforeAnythingIsCompared:
    """1 500 · 1.500 · 1,500 are the same amount written three ways. Read one wrong and the
    comparison below produces a wall of false positives that hides every real one."""

    @pytest.mark.parametrize(
        ("text", "language", "expected"),
        [
            ("un plafond de 22 950 € par personne", "fr", 22950.0),
            ("ein Rahmen von 1.500 €", "de", 1500.0),
            ("a limit of 1,500 EUR", "en", 1500.0),
            ("le taux est de 3,00 % net", "fr", 3.0),
            ("der Satz liegt bei 3,00 %", "de", 3.0),
            ("the rate is 3.00%", "en", 3.0),
        ],
    )
    def test_a_quantity_is_read_in_its_own_locale(
        self, text: str, language: str, expected: float
    ) -> None:
        assert expected in figures(text, language), (
            f"{text!r} read as {language} did not yield {expected}. Reading a thousands "
            f"separator as a decimal point is an error of three orders of magnitude, and it "
            f"makes every foreign amount look like a divergence."
        )

    def test_the_invisible_french_separator_is_handled(self) -> None:
        """A French typographer writes a narrow no-break space. It is not U+0020."""
        narrow = "plafond de 22\N{NARROW NO-BREAK SPACE}950 €"
        nbsp = "plafond de 22\N{NO-BREAK SPACE}950 €"
        assert 22950.0 in figures(narrow, "fr")
        assert 22950.0 in figures(nbsp, "fr")

    def test_a_repeated_amount_is_one_fact(self) -> None:
        assert figures("2,40 € par mois, soit 2,40 € mensuels", "fr") == {2.4}


class TestTheBundlesCanStillBePaired:
    """Without `doc_id` these are three unrelated corpora and no comparison exists at all."""

    def test_every_document_carries_a_pairing_key(self) -> None:
        aligned = load_aligned()

        assert aligned, "no product document could be loaded"

    def test_the_three_bundles_cover_the_same_documents(self) -> None:
        aligned = load_aligned()
        partial = {
            doc_id: document.languages
            for doc_id, document in aligned.items()
            if len(document.languages) < len(LANGUAGES)
        }

        assert partial == {}, (
            f"{partial} is published in some languages and not others. That is a coverage gap, "
            f"not a contradiction — but it means a customer in one language is answered from a "
            f"document a customer in another has no equivalent of."
        )


class TestNothingNewDivergesInSilence:
    """The ratchet. Undeclared divergences may only go down."""

    def test_the_set_of_divergent_documents_has_not_grown(self) -> None:
        found = dict(misaligned_figures())
        new = sorted(set(found) - set(_FROZEN_DIVERGENCES))

        assert new == [], (
            f"{new} now state different figures across languages and are not in the frozen "
            f"registry. Either an amount was mistyped in one language, or a genuine product "
            f"difference was introduced without saying so. Both need a sentence; neither may "
            f"pass silently."
        )

    def test_a_document_that_stops_diverging_is_removed_from_the_registry(self) -> None:
        found = dict(misaligned_figures())
        stale = sorted(set(_FROZEN_DIVERGENCES) - set(found))

        assert stale == [], (
            f"{stale} agree across languages now and are still frozen as divergent. A registry "
            f"of debts that keeps paid ones is a registry nobody trusts — remove them."
        )

    def test_the_frozen_figures_are_still_what_is_measured(self) -> None:
        """Freezing the document ids alone would let the AMOUNTS drift underneath the freeze."""
        found = dict(misaligned_figures())
        drifted = {
            doc_id: (frozen, found.get(doc_id))
            for doc_id, frozen in _FROZEN_DIVERGENCES.items()
            if found.get(doc_id) != frozen
        }

        assert drifted == {}, (
            f"{drifted}: the divergence is frozen under this document id but the figures behind "
            f"it changed. A frozen id with moving contents freezes nothing."
        )

    def test_the_registry_is_a_debt_and_not_a_target(self) -> None:
        """It exists to shrink. Stating the number here is what makes the next reader ask why."""
        assert len(_FROZEN_DIVERGENCES) <= 8, (
            "the undeclared-divergence registry has grown. Each entry is a place where a French "
            "and a German customer are told different amounts and nobody has said which is right."
        )
