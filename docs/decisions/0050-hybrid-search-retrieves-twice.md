# 0050 — Hybrid search retrieves twice; reordering one list is not retrieval

- Status: proposed
- Date: 2026-08-04
- Supersedes: none
- Superseded by: none
- Relates to: [0035](0035-retrieval-depth-and-reranking-are-per-agent.md) (the per-agent `rerank` knob, whose reach this widens), [0026](0026-a-witness-interrogates-the-thing.md) (a witness interrogates the thing), [0014](0014-environment-isolation.md) (the per-env schema this migration runs in)

## Context

`src/tessera/retrieval/hybrid_search.py` is named for a thing it did not do. Until this
decision the pipeline was:

1. embed the query,
2. run one HNSW kNN query against pgvector, over-fetched ×3,
3. reorder **those** candidates with `reranking.rerank`, a Python token-overlap score
   (`lexical_score`, "cheap BM25-like … deterministic and dependency-free"),
4. return the top-k.

There was no lexical index. Measured on disk 2026-08-04: **zero** occurrences of `tsvector`,
`to_tsquery`, `websearch_to_tsquery` or a GIN index anywhere under `src/`. The lexical signal
existed, but it arrived *after* retrieval, so it could only reorder what the dense arm had
already returned. **A chunk pgvector did not return was unreachable**, however literally it
matched — and the tokens a dense embedder smears worst are exactly the ones a banking corpus
is addressed by: product references, article ids, contract numbers, IBAN fragments.

Meanwhile `src/tessera/observability/connectors.py` told the cockpit, in all three languages,
that this was a *"magasin de récupération hybride (BM25 + vectoriel)"*. The gap was not in the
implementation's quality; it was between the implementation and its description.

## Decision

**Two retrievers, run concurrently, fused as two independent lists.**

1. **A generated `tsvector` column and a GIN index**, created idempotently by
   `store.ensure_schema()` alongside the HNSW index. Generated rather than trigger-maintained:
   the vector is a pure function of `(language, text)`, so it cannot drift from the text it
   indexes, and the `ALTER` fills every existing row — nothing is left NULL.

2. **One text-search configuration per language**, in a `CASE` over the language column:
   `fr → french`, `de → german`, `en → english`. `to_tsvector(regconfig, text)` is IMMUTABLE
   for a literal config and a `CASE` over immutable branches is immutable, which is what makes
   per-language analysis possible in a generated column at all. One shared config would stem
   at most one of three languages correctly: `german` stems *Bedingungen* → `beding`, so a
   query for *Bedingung* matches, while `english` leaves it as `bedingungen` and matches
   nothing; `french` stems *immobiliers* → `immobili`; `simple` stems nothing.

   **Not decompounding, and the test that first claimed otherwise was wrong.** The control
   originally asserted that *Immobilienkredit* reaches *Immobilienkredite* only under German;
   PostgreSQL answered that English matches it too, because both merely strip a trailing `e`.
   `german` is a snowball stemmer, not an ispell dictionary. Claiming German compound
   splitting here would be claiming a capability this schema does not have.

3. **`store.lexical_search`**, a sibling of `knn_search`, not a helper of it. When `language`
   is `None` it queries each language partition with its own config as one branch of a
   `UNION ALL` — one round trip, each branch index-friendly because its config is a literal.
   It also projects the query vector onto the matched rows, so a chunk found only lexically
   arrives with its **true** cosine rather than an invented one.

4. **The query is a disjunction of the query's own terms**, not `websearch_to_tsquery`. This
   is the decision that made the difference between a lexical arm and a decoration.
   `websearch_to_tsquery` joins terms with AND: *"quel est le taux du prêt immobilier Crédit
   Aurore"* becomes `'quel' & 'taux' & 'prêt' & 'immobili' & 'cred' & 'auror'`, which demands
   one chunk containing all six. Measured against the live corpus with the 174
   failure-catalogue prompts: **0 matches in 348 searches**. A retriever silent on every
   natural-language query is not a retriever.

   Terms are `\w+(?:-\w+)*` — alphanumeric runs, hyphens kept. The pattern admits no tsquery
   operator and cannot produce a bare or leading `-`, so the little language inside the bound
   value is guarded. **The hyphens are about precision, and they were not in the first
   version.** PostgreSQL indexes `AUR-2024-118` as `aur`, `-2024`, `-118`; asking for
   `'aur' | '2024' | '118'` also matches `AUR-2024-999` — measured — returning a different
   contract reference as if it were the one asked for. Kept whole, `to_tsquery` builds the
   phrase `'aur' <-> '-2024' <-> '-118'`, which matches the right reference and not its
   neighbour. Reference numbers are the token class this arm exists for.

5. **`reranking.fuse`** replaces `rerank` on the production path: reciprocal-rank fusion over
   the two *retrieved* lists, same `k = 60` and same `[0, 1]` normalisation as before, so
   every threshold downstream keeps its meaning. A document contributes `1/(k+rank)` for each
   list that returned it and **nothing** for a list that did not — no fabricated ranks. Ties
   break on identity, never on arrival order, so the ranking is a function of the result set
   rather than of whatever order Postgres happened to return.

6. **`rerank=False` (ADR 0035) now skips the lexical arm too.** The knob's declared meaning is
   "the dense retriever, plain"; this widens what it turns off without changing what it means.

7. **A store with no lexical index degrades out loud.** `lexical_search` raises
   `LexicalIndexUnavailableError` rather than returning an empty list — an empty list is a
   legitimate answer (a query of pure stop words) and must not be confused with a missing
   index. `hybrid_search` catches it, prints once to stderr, and falls back to `rerank` over
   the dense candidates: the historical behaviour, named as such.

## Measurement

`scripts/probe_hybrid_recall.py`, against the live local corpus (241 chunks, two corpora,
three languages, `bge-m3` at 1024 dimensions), `k = 4`, over-fetch ×3. Three configurations
composed from the production functions themselves: `vector` (kNN alone), `legacy` (kNN ×3 →
`rerank`, i.e. what this repository shipped until today), `hybrid` (both arms → `fuse`).

**Arm A — known-item.** Each chunk's rarest lexemes become the query; that chunk is the gold
answer. 212 valid items, 29 discarded because their own query did not match their own gold
chunk (counted, not hidden).

| configuration | recall@4 |
|---|---|
| vector | 58.0 % |
| legacy — what shipped before | 69.3 % |
| hybrid | **99.1 %** |

**34** of those gold chunks were returned by the lexical arm alone — not mis-ranked by the
dense arm, absent from its ×3 over-fetch entirely. Under the previous implementation they were
unreachable, not merely badly ordered.

This arm is *deliberately favourable to the lexical arm* and its recall figure is an upper
bound, not a typical gain: rare literal tokens are precisely what a dense embedder smears.

**Arm B — natural language.** The 174 failure-catalogue user prompts, both corpora, spanning
all languages.

| | value |
|---|---|
| searches | 348 |
| searches where the lexical arm matched at all | 333 |
| lexical candidates seen | 3 598 |
| legacy top-4 results still present in the hybrid top-4 | 62.9 % |
| documents returned only by the lexical arm | 181 |
| mean top-1 cosine, vector | 0.5399 |
| mean top-1 cosine, hybrid | 0.5207 |

The first two rows are the anti-vacuity pair, and they earned their place: **before** the
AND→OR fix this same arm reported "0 documents returned only by the lexical arm", which read
as *"the lexical arm changes nothing on natural language"* and actually meant *"the lexical
arm never fired"*. A zero that cannot distinguish "nothing" from "did not look" is not a
measurement (ADR 0026).

The last two rows are the **cost**, stated plainly: the fused top-1 is on average 0.019 less
cosine-similar to the query than the dense top-1, because the fusion sometimes prefers a
lexically-strong document. That is the trade hybrid retrieval exists to make. Whether it
produces better *answers* is not measured here — see the blind spot below.

These are the figures of the shipped code. An earlier run of the same probe, before hyphens
were kept in query terms, reported 341 matching searches and 187 lexical-only documents: the
extra ones were the false matches on neighbouring reference numbers that the phrase form
removed.

## Consequences

- The `documents` table gains one generated column and one GIN index. On the live corpus (241
  rows) the `ALTER` is instantaneous; on Cloud SQL the corpus is the same order of magnitude.
  It runs inside `ensure_schema`, which the API already calls at start-up, so no separate
  migration step exists to forget.
- `reranking.rerank` and `lexical_score` stay. `rerank` is the declared fallback;
  `lexical_score` is still used by `observability/reranking_contribution` and
  `agent/grounding`, which measure different things.
- **`observability/reranking_contribution` no longer mirrors production exactly, and its
  docstring now says so.** It reconstructs the fusion of a *captured* chunk set, so it can
  still show which signal shaped the ordering — but it cannot see what the lexical arm
  *recovered*, because a recovered chunk is one that would not have been in the captured set.
- **Declared provenance gap.** The eval reports and frozen baselines on disk were produced by
  the previous retriever. Nothing in `catalogue_version` can see that — it hashes case ids,
  not the code that answers them, exactly as it could not see a grader change (ADR 0028 §5).
  Retrieval changed, so the agent's context changed, so the recorded verdicts describe code
  that no longer exists. They are not thereby wrong, but they are not evidence about today's
  agent either. Closing it is a re-measure, and it is written up in
  `docs/status/reste-a-faire-20260803.md` rather than assumed away.
- Blind spot, stated: everything above measures **retrieval**, not answers. A recovered chunk
  is not a better reply; that is what the eval harness is for, and it has not been re-run.

## Alternatives considered

- **Keep `websearch_to_tsquery` for its user syntax** (quoted phrases, `-exclusion`). Rejected
  on the measurement: queries here come from a chat turn, not a search box, and AND semantics
  made the arm silent on 348 of 348 real prompts. Its syntax is worth nothing if it never
  matches.
- **A trigger-maintained `tsvector` column.** Rejected: a trigger can be dropped, disabled, or
  skipped by a bulk load, and the column then silently describes text that has changed. A
  generated column cannot diverge from its inputs.
- **Three partial expression indexes instead of one generated column.** Equivalent in
  planning, but the query must then repeat the exact index expression, and a future edit that
  drifts by one character silently loses the index. One column, one index, one name.
- **Fuse the two arms in Python over a single deep kNN fetch** (fetch 200, filter lexically).
  Rejected: it is the same failure with a bigger constant. The dense arm still decides the
  candidate set.
- **Change the citation telemetry to count lexical recoveries.** Rejected: `_CITATION_THRESHOLD`
  is a cosine gate on what the *embeddings* retrieve, and `scripts/probe_retrieval.py` measures
  the same thing offline. Folding recoveries in would move the number without moving the
  thing — an improvement that is really a change of definition.
