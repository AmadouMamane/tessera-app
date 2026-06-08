"""Seed the local pgvector database with the Credit Aurore demo corpus."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Mapping
from importlib import resources

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

LOG = get_logger("tessera.corpus.seed_demo")

_CORPUS_FILES: dict[str, tuple[str, LanguageCode]] = {
    "credit_aurore_fr.json": ("credit_aurore", LanguageCode.FR),
    "credit_aurore_de.json": ("credit_aurore", LanguageCode.DE),
    "credit_aurore_en.json": ("credit_aurore", LanguageCode.EN),
}


def _metadata(raw: object) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


async def ingest_file(filename: str, corpus: str, language: LanguageCode) -> int:
    """Ingest one packaged demo-corpus JSON file into pgvector."""
    package = resources.files("tessera.corpus.data")
    target = package.joinpath(filename)
    if not target.is_file():
        LOG.warning("seed.skip_missing", filename=filename)
        return 0

    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"{filename}: expected a JSON list of documents")

    records: list[DocumentRecord] = []
    for doc in payload:
        if not isinstance(doc, dict):
            continue
        source = str(doc["source"])
        text = str(doc["text"])
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
                    metadata=_metadata(doc.get("metadata")),
                )
            )

    inserted = await insert_documents(records)
    LOG.info(
        "seed.ingested",
        filename=filename,
        corpus=corpus,
        language=language.value,
        records=len(records),
        inserted=inserted,
    )
    return inserted


async def seed_demo(only: str | None = None) -> int:
    """Create the vector schema and ingest the packaged product corpus."""
    LOG.info("seed.start", filter=only)
    await ensure_schema()
    total = 0
    for filename, (corpus, language) in _CORPUS_FILES.items():
        if only and only not in {corpus, language.value, filename}:
            continue
        total += await ingest_file(filename, corpus, language)
    LOG.info("seed.done", inserted=total)
    return total


async def amain(argv: list[str] | None = None) -> int:
    """Async CLI implementation."""
    parser = argparse.ArgumentParser(description="Seed Tessera's pgvector store.")
    parser.add_argument("--only", help="Restrict to one corpus or language code.")
    args = parser.parse_args(argv)
    await seed_demo(args.only)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
