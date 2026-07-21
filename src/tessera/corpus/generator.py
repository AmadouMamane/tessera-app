"""Synthetic Crédit Aurore product corpus updater.

The in-code catalogue contains deterministic bootstrap pages.  The JSON files
also contain editorial pages built after that bootstrap, so generation is a
conservative upsert: managed sources are refreshed and every other valid page
is preserved.  Writes are atomic and malformed existing corpora are refused,
never replaced.

The catalogue text is editorial — it is *not* drawn from any real bank's
materials. Keep it that way.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from tessera.settings import LanguageCode


@dataclass(frozen=True, slots=True)
class ProductPage:
    """One product page in one language."""

    source: str
    language: LanguageCode
    text: str
    metadata: dict[str, str]


class CorpusGenerationError(ValueError):
    """Raised when replacing an existing corpus would be unsafe."""


_CATALOGUE: dict[LanguageCode, tuple[ProductPage, ...]] = {
    LanguageCode.FR: (
        ProductPage(
            source="credit-aurore-livret-aurore",
            language=LanguageCode.FR,
            text=(
                "Le Livret Aurore est un livret d'épargne réglementé proposé par "
                "Crédit Aurore. Le taux d'intérêt en vigueur est de 3,00% net, "
                "révisé deux fois par an. Le plafond de versement est fixé à "
                "22 950 € hors capitalisation des intérêts. Les retraits sont "
                "libres et sans frais."
            ),
            metadata={"product": "savings", "locator": "livret-aurore"},
        ),
        ProductPage(
            source="credit-aurore-pret-immobilier-classique",
            language=LanguageCode.FR,
            text=(
                "Le Prêt Immobilier Aurore est un prêt à taux fixe ou variable "
                "destiné à financer l'acquisition d'une résidence principale, "
                "secondaire, ou un investissement locatif. La durée maximale "
                "est de 25 ans. Une assurance emprunteur conforme à la loi "
                "Lemoine est requise. Les frais de dossier s'élèvent à 1% du "
                "montant emprunté, plafonnés à 1 500 €."
            ),
            metadata={"product": "mortgage", "locator": "pret-immobilier"},
        ),
    ),
    LanguageCode.DE: (
        ProductPage(
            source="credit-aurore-aurore-sparen",
            language=LanguageCode.DE,
            text=(
                "Das Aurore-Sparbuch ist ein reguliertes Sparprodukt der "
                "Crédit Aurore. Der aktuelle Zinssatz beträgt 3,00% p.a. und "
                "wird halbjährlich überprüft. Die Einzahlungsobergrenze liegt "
                "bei 22 950 EUR ohne Zinskapitalisierung. Abhebungen sind "
                "jederzeit gebührenfrei möglich."
            ),
            metadata={"product": "savings", "locator": "aurore-sparen"},
        ),
        ProductPage(
            source="credit-aurore-baufinanzierung",
            language=LanguageCode.DE,
            text=(
                "Die Aurore-Baufinanzierung ist ein Hypothekendarlehen mit "
                "fester oder variabler Verzinsung zur Finanzierung von "
                "selbstgenutztem oder vermietetem Wohneigentum. Die maximale "
                "Laufzeit beträgt 25 Jahre. Eine konforme Restschuld- bzw. "
                "Risikolebensversicherung ist erforderlich. Die Bearbeitungs"
                "gebühr beträgt 1% der Darlehenssumme, höchstens 1 500 EUR."
            ),
            metadata={"product": "mortgage", "locator": "baufinanzierung"},
        ),
    ),
    LanguageCode.EN: (
        ProductPage(
            source="credit-aurore-aurore-savings",
            language=LanguageCode.EN,
            text=(
                "The Aurore Savings Account is a regulated savings product "
                "offered by Crédit Aurore. The current interest rate is 3.00% "
                "net, reviewed twice a year. The deposit cap is EUR 22,950 "
                "excluding capitalised interest. Withdrawals are free and "
                "available on demand."
            ),
            metadata={"product": "savings", "locator": "aurore-savings"},
        ),
        ProductPage(
            source="credit-aurore-aurore-mortgage",
            language=LanguageCode.EN,
            text=(
                "The Aurore Mortgage is a fixed- or variable-rate home loan "
                "designed for the purchase of a primary or secondary "
                "residence, or for buy-to-let investment. The maximum term "
                "is 25 years. A compliant loan-protection insurance policy "
                "is required. The arrangement fee is 1% of the loan amount, "
                "capped at EUR 1,500."
            ),
            metadata={"product": "mortgage", "locator": "aurore-mortgage"},
        ),
    ),
}


def _resolve_data_dir() -> Path:
    package = resources.files("tessera.corpus.data")
    return Path(str(package))


def _serialise_page(page: ProductPage) -> dict[str, object]:
    return {
        "source": page.source,
        "language": page.language.value,
        "text": page.text,
        "metadata": page.metadata,
    }


def _validated_existing(target: Path, language: LanguageCode) -> list[dict[str, object]]:
    """Load a valid existing corpus or fail before opening a replacement file."""
    if not target.exists():
        return []
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusGenerationError(
            f"refusing to replace unreadable corpus {target}: {exc}"
        ) from exc
    if not isinstance(raw, list):
        raise CorpusGenerationError(f"refusing to replace {target}: top level must be a list")

    seen: set[str] = set()
    validated: list[dict[str, object]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise CorpusGenerationError(f"{target}[{index}] must be an object")
        source = item.get("source")
        text = item.get("text")
        metadata = item.get("metadata")
        page_language = item.get("language")
        if not isinstance(source, str) or not source:
            raise CorpusGenerationError(f"{target}[{index}].source must be non-empty")
        if source in seen:
            raise CorpusGenerationError(f"{target} contains duplicate source {source!r}")
        if page_language is not None and page_language != language.value:
            raise CorpusGenerationError(
                f"{target}[{index}] has language {page_language!r}, expected {language.value!r}"
            )
        if not isinstance(text, str) or not text.strip():
            raise CorpusGenerationError(f"{target}[{index}].text must be non-empty")
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
        ):
            raise CorpusGenerationError(f"{target}[{index}].metadata must map strings to strings")
        metadata_language = metadata.get("language")
        if metadata_language is not None and metadata_language != language.value:
            raise CorpusGenerationError(
                f"{target}[{index}].metadata.language has {metadata_language!r}, "
                f"expected {language.value!r}"
            )
        seen.add(source)
        validated.append(dict(item))
    return validated


def _merge_pages(
    existing: list[dict[str, object]], pages: tuple[ProductPage, ...]
) -> list[dict[str, object]]:
    """Upsert managed pages without injecting bootstrap sources into editorial corpora."""
    managed = {page.source: _serialise_page(page) for page in pages}
    if not existing:
        return list(managed.values())
    return [managed.get(str(item["source"]), item) for item in existing]


def _atomic_write(target: Path, payload: list[dict[str, object]]) -> None:
    """Replace ``target`` atomically after bytes are flushed to disk."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_corpus(language: LanguageCode, pages: tuple[ProductPage, ...]) -> Path:
    target = _resolve_data_dir() / f"credit_aurore_{language.value}.json"
    existing = _validated_existing(target, language)
    payload = _merge_pages(existing, pages)
    _atomic_write(target, payload)
    return target


async def main(argv: list[str] | None = None) -> int:
    """CLI entry point — writes one JSON file per language."""
    parser = argparse.ArgumentParser(description="Generate the demo product corpus.")
    parser.add_argument(
        "--language",
        choices=[lang.value for lang in LanguageCode],
        help="Generate only one language; default is all three.",
    )
    args = parser.parse_args(argv)
    targets = [LanguageCode(args.language)] if args.language else list(LanguageCode)
    for language in targets:
        path = _write_corpus(language, _CATALOGUE[language])
        print(f"wrote {path}")
    return 0
