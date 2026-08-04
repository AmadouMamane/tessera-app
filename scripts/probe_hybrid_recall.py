"""Measure what the lexical arm actually recovers — before and after ADR 0050.

Three retrieval configurations are run over the **same** live corpus, the same embedder and
the same queries, and compared:

``vector``
    ``knn_search`` alone, cut at ``top_k``. The dense retriever, plain.
``legacy``
    ``knn_search`` over-fetched x3, reordered by :func:`tessera.retrieval.reranking.rerank`
    — the Python token-overlap score. **This is what "hybrid search" meant in this repository
    until 2026-08-04.** It reorders the dense candidates; it cannot reach past them.
``hybrid``
    ``knn_search`` and ``lexical_search`` over-fetched x3 **independently**, fused by
    :func:`tessera.retrieval.reranking.fuse`. A chunk the dense arm never returned can win.

Each configuration is composed from the production functions themselves, never re-implemented,
so a change to fusion changes this probe's answer too.

Two arms, because one of them would flatter the change:

**Arm A — known-item.** For every chunk, the rarest lexemes it contains (lowest document
frequency in its own corpus+language partition, as computed by PostgreSQL's own analyser)
become the query; that chunk is the gold answer. This is *deliberately favourable to the
lexical arm* — rare literal tokens are exactly what a dense embedder smears — and it is the
failure mode the audit named: reference numbers, article ids, product codes. Recall@k here is
an upper bound on the gain, not a typical one. Items whose query does not match their own gold
chunk are discarded and counted, so no item is scored on a query that could not have worked.

**Arm B — natural language.** The user prompts from the failure catalogue: real questions, the
kind arm A is not. Here the lexical arm is not expected to help, and the number that matters is
whether it *hurts* — the mean top-1 cosine, and how much of the legacy answer set survives.

Run::

    uv run python -m scripts.probe_hybrid_recall            # JSON under the env's state dir
    uv run python -m scripts.probe_hybrid_recall --out /some/where.json

The report never lands in ``eval/reports/``: that directory *means* "the eval runs for this
environment", and the preflight computes a seed floor from it (see :func:`_default_out`).

Blind spots, stated: this measures retrieval, not answers. A recovered chunk is not a better
reply — that is what the eval harness is for. And arm A's gold labels are derived from the
corpus itself, so they inherit every chunking decision the corpus already made.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tessera.retrieval import reranking, store
from tessera.retrieval.embeddings import embed
from tessera.settings import LanguageCode, get_settings
from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import Sequence

_REPO = Path(__file__).resolve().parents[1]
_FAILURES = _REPO / "eval" / "failures"
_CORPORA = ("credit_aurore", "regulations")
_TOP_K = 4
_OVERFETCH = 3
#: How many rare lexemes make one known-item query. Three is enough to identify a chunk in a
#: corpus this size while staying short enough to be a plausible thing a person would type.
_QUERY_LEXEMES = 3
#: A lexeme in more than this many chunks is not distinctive enough to identify one.
_MAX_DOC_FREQUENCY = 2


@dataclass(frozen=True, slots=True)
class KnownItem:
    """One known-item probe: a query built from a chunk, and the chunk it came from."""

    corpus: str
    language: LanguageCode
    query: str
    gold_source: str
    gold_chunk_id: str


def _key(source: str, chunk_id: str) -> tuple[str, str]:
    return (source, chunk_id)


async def _known_items(corpus: str, language: LanguageCode) -> tuple[list[KnownItem], int]:
    """Build one known-item probe per chunk; return the valid ones and how many were dropped.

    An item is valid only when its own query matches its own gold chunk — asked of PostgreSQL,
    with the same ``websearch_to_tsquery`` production uses. The queries are built from stemmed
    lexemes, and re-stemming a stem is a fixed point for most but not all inputs; rather than
    assume it, every item is verified and the failures are counted rather than hidden.
    """
    table = safe_identifier(get_settings().postgres.vector_table)
    config = store.TEXT_SEARCH_CONFIG[language]
    async with store._connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            WITH lex AS (
                SELECT d.source, d.chunk_id, l.lexeme
                  FROM {table} AS d, LATERAL unnest(d.text_search) AS l
                 WHERE d.corpus = %s AND d.language = %s
            ),
            df AS (
                SELECT lexeme, count(*) AS ndoc FROM lex GROUP BY lexeme
            )
            SELECT lex.source, lex.chunk_id, lex.lexeme, df.ndoc
              FROM lex JOIN df USING (lexeme)
             WHERE df.ndoc <= %s
             ORDER BY lex.source, lex.chunk_id, df.ndoc ASC, lex.lexeme ASC;
            """,  # noqa: S608 — validated identifier; every value is bound
            (corpus, language.value, _MAX_DOC_FREQUENCY),
        )
        rows = await cur.fetchall()

        by_chunk: dict[tuple[str, str], list[str]] = defaultdict(list)
        for source, chunk_id, lexeme, _ndoc in rows:
            bucket = by_chunk[_key(str(source), str(chunk_id))]
            if len(bucket) < _QUERY_LEXEMES:
                bucket.append(str(lexeme))

        items: list[KnownItem] = []
        dropped = 0
        for (source, chunk_id), lexemes in sorted(by_chunk.items()):
            query = " ".join(lexemes)
            await cur.execute(
                f"""
                SELECT count(*)::int
                  FROM {table}, websearch_to_tsquery(%s::regconfig, %s) AS q
                 WHERE corpus = %s AND source = %s AND chunk_id = %s AND text_search @@ q;
                """,  # noqa: S608 — validated identifier; every value is bound
                (config, query, corpus, source, chunk_id),
            )
            matched = await cur.fetchone()
            if matched is None or int(matched[0]) == 0:
                dropped += 1
                continue
            items.append(
                KnownItem(
                    corpus=corpus,
                    language=language,
                    query=query,
                    gold_source=source,
                    gold_chunk_id=chunk_id,
                )
            )
    return items, dropped


@dataclass(frozen=True, slots=True)
class Orderings:
    """What each configuration returned for one query, plus the two comparison signals."""

    vector: list[tuple[str, str]]
    legacy: list[tuple[str, str]]
    hybrid: list[tuple[str, str]]
    lexical_only: list[tuple[str, str]]
    vector_top1_cosine: float | None
    hybrid_top1_cosine: float | None
    #: How many candidates the lexical arm returned for this query — BEFORE fusion. Without
    #: it, "the lexical arm added nothing" and "the lexical arm was never consulted" are the
    #: same zero, and a probe that cannot tell them apart is not a witness.
    lexical_candidates: int

    def by_name(self, name: str) -> list[tuple[str, str]]:
        return {"vector": self.vector, "legacy": self.legacy, "hybrid": self.hybrid}[name]


async def _three_orderings(
    *, query: str, query_vec: list[float], corpus: str, language: LanguageCode | None
) -> Orderings:
    """The top-k keys each configuration returns, from one embedding and two DB queries."""
    deep = _TOP_K * _OVERFETCH
    dense_deep, lexical = await asyncio.gather(
        store.knn_search(query_embedding=query_vec, corpus=corpus, language=language, top_k=deep),
        store.lexical_search(
            query=query,
            query_embedding=query_vec,
            corpus=corpus,
            language=language,
            top_k=deep,
        ),
    )
    # The dense arm's top-k is its top-k whatever the over-fetch: kNN order is monotone, so
    # truncating a deeper fetch gives exactly the shallow fetch. No separate query needed, and
    # no candidate-budget confound between the configurations.
    fused = reranking.fuse(dense_deep, lexical, top_k=_TOP_K)
    return Orderings(
        vector=[_key(h.source, h.chunk_id) for h in dense_deep[:_TOP_K]],
        legacy=[
            _key(item.hit.source, item.hit.chunk_id)
            for item in reranking.rerank(query=query, hits=dense_deep, top_k=_TOP_K)
        ],
        hybrid=[_key(item.source, item.chunk_id) for item in fused],
        lexical_only=[_key(i.source, i.chunk_id) for i in fused if i.found_by == "lexical"],
        vector_top1_cosine=dense_deep[0].score if dense_deep else None,
        hybrid_top1_cosine=fused[0].vector_score if fused else None,
        lexical_candidates=len(lexical),
    )


async def _arm_a() -> dict[str, Any]:
    """Known-item recall@k for the three configurations."""
    per_config: dict[str, int] = {"vector": 0, "legacy": 0, "hybrid": 0}
    recovered_by_lexical = 0
    lexical_candidates = 0
    total = 0
    dropped_total = 0
    per_partition: list[dict[str, Any]] = []

    for corpus in _CORPORA:
        for language in LanguageCode:
            items, dropped = await _known_items(corpus, language)
            dropped_total += dropped
            if not items:
                continue
            vectors = await embed([item.query for item in items])
            hits = {"vector": 0, "legacy": 0, "hybrid": 0}
            for item, vec in zip(items, vectors, strict=True):
                orderings = await _three_orderings(
                    query=item.query, query_vec=vec, corpus=corpus, language=language
                )
                gold = _key(item.gold_source, item.gold_chunk_id)
                lexical_candidates += orderings.lexical_candidates
                for config in hits:
                    if gold in orderings.by_name(config):
                        hits[config] += 1
                if gold in orderings.lexical_only:
                    recovered_by_lexical += 1
            total += len(items)
            for config, n in hits.items():
                per_config[config] += n
            per_partition.append(
                {
                    "corpus": corpus,
                    "language": language.value,
                    "items": len(items),
                    "dropped": dropped,
                    **{f"recall_{c}": round(100 * n / len(items), 1) for c, n in hits.items()},
                }
            )

    return {
        "items": total,
        "dropped_unmatched": dropped_total,
        "top_k": _TOP_K,
        "recall": {c: round(100 * n / total, 1) if total else 0.0 for c, n in per_config.items()},
        # Strictly: the gold chunk was in the fused top-k AND the dense arm had not returned it
        # even in its x3 over-fetch. Under the previous implementation these were not
        # mis-ranked, they were unreachable. The rest of the gain is the lexical arm out-ranking
        # a dense candidate it did see, which the previous implementation also attempted.
        "recovered_only_by_the_lexical_arm": recovered_by_lexical,
        "lexical_candidates_seen": lexical_candidates,
        "partitions": per_partition,
    }


def _catalogue_prompts() -> list[str]:
    prompts: list[str] = []
    for path in sorted(_FAILURES.glob("[0-9]*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        bundles = case.get("prompts", {})
        if not isinstance(bundles, dict):
            continue
        for bundle in bundles.values():
            if isinstance(bundle, dict) and bundle.get("user"):
                prompts.append(str(bundle["user"]))
    return prompts


async def _arm_b(prompts: Sequence[str]) -> dict[str, Any]:
    """Natural-language queries: does the lexical arm cost anything?"""
    vectors = await embed(list(prompts))
    kept = 0
    considered = 0
    lexical_only_returned = 0
    lexical_candidates = 0
    searches_with_a_lexical_match = 0
    searches = 0
    dense_top1: list[float] = []
    hybrid_top1: list[float] = []

    for prompt, vec in zip(prompts, vectors, strict=True):
        for corpus in _CORPORA:
            orderings = await _three_orderings(
                query=prompt, query_vec=vec, corpus=corpus, language=None
            )
            if not orderings.legacy:
                continue
            searches += 1
            considered += len(orderings.legacy)
            kept += sum(1 for key in orderings.legacy if key in orderings.hybrid)
            lexical_only_returned += len(orderings.lexical_only)
            lexical_candidates += orderings.lexical_candidates
            searches_with_a_lexical_match += 1 if orderings.lexical_candidates else 0
            if orderings.vector_top1_cosine is not None:
                dense_top1.append(orderings.vector_top1_cosine)
            if orderings.hybrid_top1_cosine is not None:
                hybrid_top1.append(orderings.hybrid_top1_cosine)

    def _mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    return {
        "queries": len(prompts),
        "searches": searches,
        # The anti-vacuity pair. A zero in `documents_returned_only_by_the_lexical_arm` means
        # "the lexical arm added nothing" ONLY if these two say it was consulted and matched.
        "searches_with_a_lexical_match": searches_with_a_lexical_match,
        "lexical_candidates_seen": lexical_candidates,
        "legacy_results_kept_pct": round(100 * kept / considered, 1) if considered else 0.0,
        "documents_returned_only_by_the_lexical_arm": lexical_only_returned,
        "mean_top1_cosine_vector": _mean(dense_top1),
        "mean_top1_cosine_hybrid": _mean(hybrid_top1),
    }


def _default_out() -> Path:
    """Under the env's state dir, and deliberately **not** under ``eval/reports/``.

    `eval/reports/*.json` is an archive with a meaning: the preflight reads that directory as
    the set of eval runs for this environment and computes a seed floor from it. Dropping a
    probe artifact there made a file that is not an eval run look like the only one — which is
    how the preflight's own tests found it, red, within minutes of the first write.
    """
    return Path(get_settings().state_dir) / "hybrid_recall.json"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"write the JSON report here (default: {_default_out()})",
    )
    args = parser.parse_args()

    settings = get_settings()
    print(f"corpus: schema={settings.pg_schema} table={settings.postgres.vector_table}")
    print("arm A — known-item (rare lexemes; favourable to the lexical arm by construction)")
    arm_a = await _arm_a()
    print(f"  items={arm_a['items']} dropped={arm_a['dropped_unmatched']} k={_TOP_K}")
    for config, value in arm_a["recall"].items():
        print(f"    recall@{_TOP_K} {config:<7} {value:>5} %")
    print(f"    recovered ONLY by the lexical arm: {arm_a['recovered_only_by_the_lexical_arm']}")

    prompts = _catalogue_prompts()
    print(f"arm B — natural language ({len(prompts)} catalogue prompts)")
    arm_b = await _arm_b(prompts)
    for label, value in arm_b.items():
        print(f"    {label:<45} {value}")

    payload = {
        "run_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": settings.pg_schema,
        "table": settings.postgres.vector_table,
        "top_k": _TOP_K,
        "overfetch": _OVERFETCH,
        "arm_a_known_item": arm_a,
        "arm_b_natural_language": arm_b,
    }
    out = args.out if args.out is not None else _default_out()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
