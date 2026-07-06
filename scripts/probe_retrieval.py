"""Measure real retrieval citation / hit-rate per knowledge source.

Embeds the failure-catalogue user prompts (real queries the agent received),
runs knn_search over both corpora, and records, per source category, how often
its chunks are retrieved above a similarity threshold. The result is cached to
``<guard.audit_file.parent>/knowledge_citations.json`` and consumed by
:mod:`tessera.observability.knowledge` to fill the Connaissances citation and
hit-rate figures with real numbers (never fabricated).

Run::

    PYTHONPATH=.:src .venv/bin/python -m scripts.probe_retrieval
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from tessera.observability.knowledge import _SOURCE_META, _probe_path
from tessera.retrieval.embeddings import embed
from tessera.retrieval.store import knn_search

_FAILURES = Path(__file__).resolve().parents[1] / "eval" / "failures"
_CORPORA = ("regulations", "credit_aurore")
_TOP_K = 5
_THRESHOLD = 0.55  # cosine similarity; a chunk below this is not a real "hit"


def _load_queries() -> list[str]:
    queries: list[str] = []
    for path in sorted(_FAILURES.glob("[0-9]*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        prompts = case.get("prompts", {})
        if not isinstance(prompts, dict):
            continue
        for bundle in prompts.values():
            if isinstance(bundle, dict) and bundle.get("user"):
                queries.append(str(bundle["user"]))
    return queries


async def _categories_for(query_vec: list[float]) -> set[str]:
    """Return the source categories retrieved above threshold for one query."""
    hits = []
    for corpus in _CORPORA:
        hits.extend(
            await knn_search(query_embedding=query_vec, corpus=corpus, language=None, top_k=_TOP_K)
        )
    cats: set[str] = set()
    for hit in hits:
        if hit.score < _THRESHOLD:
            continue
        meta = hit.metadata if isinstance(hit.metadata, dict) else {}
        cat = str(meta.get("category", ""))
        if cat in _SOURCE_META:
            cats.add(cat)
    return cats


async def main() -> None:
    queries = _load_queries()
    print(f"probing {len(queries)} catalogue queries over {_CORPORA}...")
    vectors = await embed(queries)

    cited: Counter[str] = Counter()
    queries_with_hit = 0
    for vec in vectors:
        cats = await _categories_for(vec)
        if cats:
            queries_with_hit += 1
        for cat in cats:
            cited[cat] += 1

    n = len(queries) or 1
    categories = {
        cat: {"citation": round(100 * cited[cat] / n, 1), "hits": cited[cat]}
        for cat in _SOURCE_META
    }
    overall = {
        "citation": round(100 * sum(cited.values()) / (n * len(_SOURCE_META)), 1),
        "hitrate": round(100 * queries_with_hit / n, 1),
        "coverage": round(100 * sum(1 for c in cited.values() if c) / len(_SOURCE_META), 1),
    }
    payload = {
        "run_at": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "queries": len(queries),
        "top_k": _TOP_K,
        "threshold": _THRESHOLD,
        "categories": categories,
        "_overall": overall,
    }
    path = _probe_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"overall: {overall}")
    print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
