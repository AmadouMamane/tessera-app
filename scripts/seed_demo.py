"""Seed the local pgvector database with the demo corpora."""

from __future__ import annotations

import sys

from tessera.corpus.seed_demo import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
