"""Generic ingestion entry point — shared by the seed and regulation scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.observability.logging import get_logger
from tessera.retrieval import embeddings
from tessera.retrieval.chunking import chunk_text
from tessera.retrieval.store import (
    DocumentRecord,
    ensure_schema,
    existing_chunk_ids,
    insert_documents,
)
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from collections.abc import Iterable

LOG = get_logger("tessera.corpus.ingestion")


def _load(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"{path}: expected a JSON list of documents")
    return [item for item in payload if isinstance(item, dict)]


def _iter_data_files(corpus_filter: str | None) -> Iterable[tuple[Path, str, LanguageCode]]:
    package = resources.files("tessera.corpus.data")
    for entry in package.iterdir():
        name = entry.name
        if not name.endswith(".json"):
            continue
        if not name.startswith("regulations_") and corpus_filter == "regulations":
            continue
        if name.startswith("regulations_"):
            corpus = "regulations"
            # Authoritative language per issuing body:
            # DORA / GDPR → EN (EU Official Journal primary text)
            # BaFin        → DE (German national authority)
            # CNIL         → FR (French national authority)
            # Source prefixes in corpus JSON files match the issuing authority:
            # BaFin/* → DE, CNIL/* → FR, DORA/* and GDPR/* → EN
            regulation_languages: dict[str, LanguageCode] = {
                "regulations_dora.json": LanguageCode.EN,
                "regulations_gdpr.json": LanguageCode.EN,
                "regulations_bafin.json": LanguageCode.DE,
                "regulations_cnil.json": LanguageCode.FR,
            }
            language = regulation_languages.get(name, LanguageCode.EN)
        else:
            base = name.removesuffix(".json")
            *_, lang_code = base.rsplit("_", 1)
            corpus = base.removesuffix(f"_{lang_code}")
            try:
                language = LanguageCode(lang_code)
            except ValueError:
                continue
        yield Path(str(entry)), corpus, language


async def ingest_path(path: Path, corpus: str, language: LanguageCode) -> int:
    """Ingest a single JSON file into pgvector."""
    docs = _load(path)
    records: list[DocumentRecord] = []
    for doc in docs:
        source = str(doc["source"])
        text = str(doc["text"])
        raw_meta = doc.get("metadata")
        metadata = {
            str(k): str(v) for k, v in (raw_meta if isinstance(raw_meta, dict) else {}).items()
        }
        chunks = chunk_text(text, language=language)
        if not chunks:
            continue
        chunk_ids = [f"{source}#{idx:04d}" for idx, _ in enumerate(chunks)]
        existing = await existing_chunk_ids(corpus=corpus, source=source, chunk_ids=chunk_ids)
        missing = [
            (idx, chunk, chunk_ids[idx])
            for idx, chunk in enumerate(chunks)
            if chunk_ids[idx] not in existing
        ]
        if not missing:
            continue
        vectors = await embeddings.embed([chunk.text for _, chunk, _ in missing])
        for (_, chunk, chunk_id), vector in zip(missing, vectors, strict=True):
            records.append(
                DocumentRecord(
                    corpus=corpus,
                    source=source,
                    chunk_id=chunk_id,
                    language=language,
                    text=chunk.text,
                    embedding=vector,
                    metadata=metadata,
                )
            )
    inserted = await insert_documents(records)
    LOG.info(
        "corpus.ingest_file",
        path=str(path),
        corpus=corpus,
        language=language.value,
        records=len(records),
        inserted=inserted,
    )
    return inserted


async def ingest_corpus(corpus_filter: str = "regulations") -> int:
    """Create the vector schema and ingest the selected packaged corpus."""
    await ensure_schema()
    total = 0
    for path, corpus, language in _iter_data_files(corpus_filter):
        if corpus_filter and corpus != corpus_filter:
            continue
        total += await ingest_path(path, corpus, language)
    LOG.info("corpus.ingest_done", inserted=total)
    return total


async def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by ``scripts/ingest_regulations.py``."""
    parser = argparse.ArgumentParser(description="Ingest a corpus into pgvector.")
    parser.add_argument(
        "--corpus",
        default="regulations",
        help="Filter to this logical corpus (default: regulations).",
    )
    args = parser.parse_args(argv)
    await ingest_corpus(args.corpus)
    return 0


def cli(argv: list[str] | None = None) -> int:
    """Synchronous console-script entry point."""
    return asyncio.run(main(argv))


if __name__ == "__main__":
    raise SystemExit(cli())
