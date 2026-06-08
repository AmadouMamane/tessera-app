"""Lookup helpers for source documents shipped in the Tessera corpus."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from tessera.settings import LanguageCode

__all__ = ["CorpusSourceDocument", "find_source_document", "source_documents"]


@dataclass(frozen=True, slots=True)
class CorpusSourceDocument:
    """One user-visible document backing a retrieved citation."""

    source: str
    text: str
    metadata: dict[str, str]
    corpus: str
    language: LanguageCode

    @property
    def locator(self) -> str:
        """Return the human locator for the document."""
        return self.metadata.get("locator") or self.source

    @property
    def category(self) -> str:
        """Return the corpus category when present."""
        return self.metadata.get("category", "unknown")


def _corpus_name(filename: str) -> str:
    if filename.startswith("credit_aurore_"):
        return "credit_aurore"
    if filename.startswith("regulations_"):
        return "regulations"
    return filename.removesuffix(".json")


def _language_from_record(record: dict[str, Any], filename: str) -> LanguageCode:
    raw = record.get("language")
    metadata = record.get("metadata")
    if raw is None and isinstance(metadata, dict):
        raw = metadata.get("language")
    if raw is None:
        raw = filename.removesuffix(".json").rsplit("_", maxsplit=1)[-1]
    return LanguageCode(str(raw))


def _metadata(record: dict[str, Any]) -> dict[str, str]:
    raw = record.get("metadata")
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


@lru_cache(maxsize=1)
def source_documents() -> tuple[CorpusSourceDocument, ...]:
    """Return all packaged source documents in deterministic order."""
    package = resources.files("tessera.corpus.data")
    documents: list[CorpusSourceDocument] = []
    for path in sorted(package.iterdir(), key=lambda item: item.name):
        if not path.name.endswith(".json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            text = item.get("text")
            if not isinstance(source, str) or not isinstance(text, str):
                continue
            documents.append(
                CorpusSourceDocument(
                    source=source,
                    text=text,
                    metadata=_metadata(item),
                    corpus=_corpus_name(path.name),
                    language=_language_from_record(item, path.name),
                )
            )
    return tuple(documents)


def find_source_document(
    source: str,
    *,
    language: LanguageCode | None = None,
) -> CorpusSourceDocument | None:
    """Find one packaged source document by canonical source id."""
    candidates = [document for document in source_documents() if document.source == source]
    if not candidates:
        return None
    if language is not None:
        for document in candidates:
            if document.language == language:
                return document
    return candidates[0]
