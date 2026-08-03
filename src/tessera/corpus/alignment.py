"""Pair the product corpus across languages, and read the figures each version states.

`docs/multilingual.md` said the DE and EN product bundles were *translations* of the French one,
produced by `corpus/translator.py`, "aligned in structure and coverage". They are not
translations, and until 2026-08-04 nothing in the repository could have noticed: the three
bundles did not even share a key. Every document was addressed by a localised slug —
`produits/livret-aurore`, `produkte/sparkonto-aurore`, `products/savings-account` — so there was
no way to ask what the German version of a French document said, let alone whether it agreed.

The divergences are real and they are about money. The French Livret states a statutory ceiling
of 22 950 €; the German account states none. A German customer and a French one are told
different things by the same agent, and **nothing distinguished a deliberate product difference
from a typo** — which is the actual defect, because one of those is a feature and the other is a
bank giving a customer a wrong number.

This module makes the question askable. `metadata.doc_id` pairs the three versions, and
:func:`figures` reads the quantities each states — in that language's own notation, which is the
part that has to be right before anything else can be:

    French     1 500 €    thousands separator is a space (or a non-breaking one)
    German     1.500 €    thousands separator is a full stop
    English    1,500      thousands separator is a comma

Read naively, `1.500 €` is one and a half euros, and a comparison built on that reports twelve
of thirteen documents as divergent — a wall of false positives that hides the eight real ones.
It did, on the first attempt.

What this module does NOT do is decide. Whether the German savings account genuinely has no
ceiling is a product question, and the answer is not in the JSON. The registry in
`tests/unit/test_corpus_facts_across_languages.py` freezes what diverges today so that nothing
new joins it silently, and each entry leaves when somebody says which of the two it is.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["AlignedDocument", "figures", "load_aligned", "misaligned_figures"]

#: Where the product bundles live, one per language.
DATA_DIR: Final[Path] = Path(__file__).resolve().parent / "data"

#: The languages the product corpus is published in.
LANGUAGES: Final[tuple[str, ...]] = ("fr", "de", "en")

#: Every space a European thousands separator is written with, including the two invisible ones
#: (U+00A0 no-break, U+202F narrow no-break) that a French typographer will have used and that a
#: naive `str.split()` will not.
_THOUSANDS_SPACES: Final[str] = " \N{NO-BREAK SPACE}\N{NARROW NO-BREAK SPACE}\N{THIN SPACE}"

#: A quantity as any of the three locales writes one. The trailing guard stops a match from
#: ending inside a longer digit run. The separator class is BUILT from the constant
#: above rather than re-typed: two lists of invisible characters are two lists that
#: drift, and the drift is invisible by eye.
_NUMBER: Final[re.Pattern[str]] = re.compile(
    r"\d+(?:[.," + re.escape(_THOUSANDS_SPACES) + r"]\d{3})*(?:[.,]\d{1,2})?(?!\d)"
)


@dataclass(frozen=True, slots=True)
class AlignedDocument:
    """One product document in every language that publishes it."""

    doc_id: str
    text: dict[str, str]
    """``language -> body``. A language missing from here does not publish this document."""

    @property
    def languages(self) -> tuple[str, ...]:
        """The languages that publish this document, sorted."""
        return tuple(sorted(self.text))


def _parse(token: str, language: str) -> float | None:
    """Read one written quantity in ``language``'s own notation.

    Getting this wrong is not a rounding error, it is an order of magnitude: German `1.500`
    read as English gives 1.5, and every German amount then looks like a divergence.
    """
    for space in _THOUSANDS_SPACES:
        token = token.replace(space, "")
    if language == "en":
        token = token.replace(",", "")
    else:
        if language == "de":
            token = token.replace(".", "")
        token = token.replace(",", ".")
    try:
        return float(token)
    except ValueError:  # pragma: no cover — the pattern only matches parsable shapes
        return None


def figures(text: str, language: str) -> set[float]:
    """Every quantity ``text`` states, read in ``language``'s notation.

    Args:
        text: The document body.
        language: One of :data:`LANGUAGES` — it decides how separators are read.

    Returns:
        The distinct quantities. A set, not a list: a document repeating "2,40 €" twice states
        one fact twice, and counting it twice would make word order look like disagreement.
    """
    found = (_parse(match.group(0), language) for match in _NUMBER.finditer(text))
    return {value for value in found if value is not None}


def load_aligned(data_dir: Path = DATA_DIR) -> dict[str, AlignedDocument]:
    """Pair the product bundles by ``metadata.doc_id``.

    Args:
        data_dir: Where the bundles live.

    Returns:
        ``doc_id -> AlignedDocument``.

    Raises:
        KeyError: If a document carries no ``doc_id``. That is not a missing nicety — without it
            the three bundles are three unrelated corpora again, and no comparison is possible.
    """
    aligned: dict[str, AlignedDocument] = {}
    per_language: dict[str, dict[str, str]] = {}
    for language in LANGUAGES:
        path = data_dir / f"credit_aurore_{language}.json"
        if not path.exists():
            continue
        bundle: dict[str, str] = {}
        for document in json.loads(path.read_text(encoding="utf-8")):
            metadata = document.get("metadata") or {}
            doc_id = metadata.get("doc_id")
            if not doc_id:
                msg = (
                    f"{path.name}: {document.get('source')!r} carries no metadata.doc_id, so it "
                    f"cannot be paired with its other-language versions"
                )
                raise KeyError(msg)
            bundle[str(doc_id)] = str(document.get("text") or "")
        per_language[language] = bundle

    for doc_id in sorted({key for bundle in per_language.values() for key in bundle}):
        aligned[doc_id] = AlignedDocument(
            doc_id=doc_id,
            text={
                lang: bundle[doc_id] for lang, bundle in per_language.items() if doc_id in bundle
            },
        )
    return aligned


def misaligned_figures(
    data_dir: Path = DATA_DIR,
) -> Iterator[tuple[str, dict[str, list[float]]]]:
    """Documents whose language versions state different quantities.

    Yields:
        ``(doc_id, {language: figures that language states and the others do not})``. Only
        documents published in every language are compared: a document one bundle simply does
        not carry is a coverage question, not a contradiction, and conflating the two would hide
        both.
    """
    for doc_id, document in load_aligned(data_dir).items():
        if len(document.languages) < len(LANGUAGES):
            continue
        stated = {lang: figures(body, lang) for lang, body in document.text.items()}
        shared = set.intersection(*stated.values())
        only = {lang: sorted(values - shared) for lang, values in stated.items()}
        if any(only.values()):
            yield doc_id, {lang: values for lang, values in only.items() if values}
