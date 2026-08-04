#!/usr/bin/env python
"""Repair missing corpus embedding provenance through a reviewed atomic reindex.

Dry-run is the default and performs no model call and no write. Applying requires both the exact
row count and the content-bound SHA-256 digest printed by that dry run, so a changed target cannot
ride an earlier approval. Fresh vectors are computed first, staged in PostgreSQL, reconciled
against the exact stored texts, and switched in one transaction.

Usage:
    uv run python scripts/reindex_embeddings.py
    uv run python scripts/reindex_embeddings.py --apply --expect-rows 241 \
      --expect-plan-digest <sha256>

Exit codes: 0 inspected/applied, 2 precondition or visibility failure, 3 repair failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from tessera.retrieval.reindex import (
    ReindexPreconditionError,
    inspect_embedding_reindex,
    repair_unfingerprinted_embeddings,
)


async def _run(args: argparse.Namespace) -> int:
    """Inspect the target, then apply only when the reviewed preconditions are supplied."""
    try:
        plan = await inspect_embedding_reindex()
    except Exception as exc:
        sys.stderr.write(f"CANNOT SAY — embedding repair target is unreadable: {exc}\n")
        return 2

    sys.stdout.write(json.dumps({"mode": "plan", **asdict(plan)}, sort_keys=True) + "\n")
    if not args.apply:
        sys.stdout.write("DRY RUN — no embedding computed and no row changed\n")
        return 0
    if args.expect_rows is None or args.expect_plan_digest is None:
        sys.stderr.write(
            "REFUSED — --apply requires --expect-rows and --expect-plan-digest from this plan\n"
        )
        return 2

    try:
        result = await repair_unfingerprinted_embeddings(
            expected_rows=args.expect_rows,
            expected_digest=args.expect_plan_digest,
            batch_size=args.batch_size,
        )
    except ReindexPreconditionError as exc:
        sys.stderr.write(f"REFUSED — {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"FAILED — no successful repair verdict: {exc}\n")
        return 3
    sys.stdout.write(json.dumps({"mode": "applied", **asdict(result)}, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the asynchronous repair workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the atomic replacement")
    parser.add_argument("--expect-rows", type=int, help="exact row count from the dry-run plan")
    parser.add_argument(
        "--expect-plan-digest", help="exact content-bound SHA-256 from the dry-run plan"
    )
    parser.add_argument("--batch-size", type=int, default=32, help="embedding batch size (1-128)")
    return asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
