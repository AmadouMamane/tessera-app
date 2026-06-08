"""Bootstrap all packaged corpora into the local pgvector database."""

from __future__ import annotations

import asyncio

from tessera.corpus import ingestion
from tessera.corpus.seed_demo import seed_demo
from tessera.observability.logging import get_logger

LOG = get_logger("tessera.corpus.bootstrap")


async def bootstrap() -> int:
    """Ingest regulations and demo product documents idempotently."""
    LOG.info("corpus.bootstrap_start")
    regulations = await ingestion.ingest_corpus("regulations")
    products = await seed_demo()
    LOG.info("corpus.bootstrap_done", regulations=regulations, products=products)
    return 0


def main() -> int:
    """CLI entry point."""
    return asyncio.run(bootstrap())


if __name__ == "__main__":
    raise SystemExit(main())
