# Tessera — System Design

This document describes how Tessera is put together: the quality model that
drives the architecture, the LangGraph topology that orchestrates a single
conversational turn, the typed state contract shared by every node, the
retrieval layer, the dual LLM paths, and the guard/audit machinery. It is a
technical reference for contributors, not an overview for newcomers — read the
README first for positioning and [`docs/structure.md`](./structure.md) for the
canonical layout.

## Architecture philosophy: the four quality layers

Tessera is an *assembly*, not an invention. Its design is organised around four
distinct quality layers, each addressing a different failure mode of LLM
agents, each verifiable independently:

1. **Runtime guard** — every tool call passes through a single chokepoint
   (`src/tessera/guard/adapter.py`) that applies allow/deny/transform policy
   before the underlying tool runs. The decision logic is the first-party
   policy engine in `src/tessera/guard/decisions.py`; the adapter is the
   declared seam behind which an alternative guard backend can be plugged
   (ADR 0028). The interface is identical either way.
2. **Offline regression harness** — a catalogue of 63 publicly documented
   agent failures lives under `eval/failures/` and is replayed against the live
   graph nightly in CI and per agent on demand. See `docs/eval.md`.
3. **Structured audit trail** — every guard decision emits a typed,
   JSON-serialisable record to a configurable sink. See "Audit trail design"
   below and `docs/compliance.md`.
4. **Human-in-the-loop escalation** — the reviewer node fuses grounding,
   coverage, and guard-health signals into a single confidence score; below a
   configurable threshold the graph routes to a dedicated escalation worker
   instead of answering.

These layers are deliberately decoupled. The guard does not know about the
harness; the harness asserts on the guard's observable effects; the audit trail
records what the guard did without influencing it; escalation is a routing
decision taken by a side-effect-free reviewer. This decoupling is what lets
each layer be tested and reasoned about in isolation.

## LangGraph topology

The agent is a single `StateGraph` built in `src/tessera/agent/graph.py`. One
turn flows through it as follows:

```
START → router → planner → (fan-out) workers → reviewer → reporter → END
                                                    │
                                                    └─(needs_escalation)→ escalation → END
```

### Router

The entry node (`NodeName.ROUTER`) classifies the user's language (FR/DE/EN)
and intent. Language detection seeds `state["language"]` and
`state["language_confidence"]`; the detected language drives prompt selection
(`src/tessera/agent/prompts/{fr,de,en}.yaml`) and the language of the final
answer.

### Planner

The planner (`NodeName.PLANNER`) decides which workers to run and writes a
`plan: list[WorkerName]` into the state, with an optional `plan_rationale`. The
plan can be empty — when it is, the conditional edge sends the state straight to
the reviewer so it can decline politely or escalate, rather than fabricating an
answer.

### Worker fan-out

`_route_after_planner` is a conditional edge that returns a *list* of node
names. LangGraph interprets a list of next-node names as a fan-out: each named
worker receives the same input state and runs concurrently, and their outputs
are merged back through the state's reducers. The selectable workers are:

- `product_lookup` — retrieval over the Crédit Aurore product corpus.
- `regulation_lookup` — cross-lingual retrieval over the EU regulatory corpora.
- `account_lookup` — account-scoped data via guarded tools.
- `simulator` — loan/repayment simulation via the `loan_simulate` tool.
- `escalation_worker` — produces a human-handoff message.

Workers are deliberately defined as individual callables rather than a generic
`ToolNode`. This makes `add_conditional_edges` decisions deterministic and
replayable, which the regression harness in `eval/runner.py` relies on.

### Reviewer

Every data-fetching worker rejoins at the reviewer (`NodeName.REVIEWER`). The
reviewer (`src/tessera/agent/reviewer.py`) is rule-based and side-effect-free —
intentionally, so the harness can assert on its outputs deterministically. It
fuses three signals:

- **Grounding** (weight 0.5) — does the draft trace to retrieved documents or
  tool results? See "Grounding score semantics" below.
- **Coverage** (weight 0.3) — did the planned workers return anything useful,
  or did every lookup come back empty?
- **Guard health** (weight 0.2) — has the firewall denied repeatedly this turn?
  One or two denies are normal (e.g. PII redaction); a deny-storm drags the
  score down.

The fused confidence is `grounding*0.5 + coverage*0.3 + guard*0.2`. When it
falls below `GuardSettings.escalation_confidence_threshold`, the reviewer sets
`needs_escalation = True` with a structured reason naming the weakest signal.

### Reviewer routing, reporter, escalation

`_route_after_reviewer` reads `needs_escalation`: if set, it routes to the
escalation worker (terminal → `END`); otherwise to the reporter, which renders
the final answer in the user's language and terminates. The escalation worker is
deliberately excluded from the worker→reviewer rejoin loop in `build_graph`;
adding it would create a second edge into the reviewer and an infinite cycle.

## State design

The contract between the graph and every node is a single `TypedDict`,
`AgentState`, defined in `src/tessera/agent/state.py`. LangGraph identifies how
to merge concurrent node outputs by the reducer annotations on each field.

Scalar fields representing the agent's current best answer (`plan`,
`draft_response`, `final_response`, `confidence`, `needs_escalation`) use
LangGraph's default last-write-wins behaviour. Fields that accumulate across the
parallel fan-out are explicitly annotated:

- `messages`, `tool_calls`, `guard_decisions`, `errors` use
  `Annotated[..., operator.add]` so concurrent workers can each append without
  conflict. The `errors` reducer in particular means a worker can record a
  failure without clobbering another worker's error written in the same
  superstep.
- `retrieved_documents` and `citations` use a custom `_dedup_concat` reducer
  that concatenates while removing duplicates by equality, since two parallel
  workers may legitimately return the same document or citation. First
  occurrence wins to keep ordering deterministic for replay.

`new_state()` constructs a fresh state with every accumulator initialised to an
empty list, ensuring reducers never see a missing key. New fields require a
mention in the relevant ADR — the state schema is load-bearing and stable by
policy.

## Retrieval design

Retrieval is PostgreSQL with the `pgvector` extension. The store
(`src/tessera/retrieval/store.py`) owns one process-wide async connection pool
and creates its schema idempotently in `ensure_schema()`: a `documents` table
keyed by `(corpus, source, chunk_id)`, with a `vector(dim)` embedding column,
an HNSW index using `vector_cosine_ops`, and a secondary `(corpus, language)`
index.

### Hybrid search

The public entry point is `search()` in
`src/tessera/retrieval/hybrid_search.py`. The pipeline is:

1. Embed the query with the active embedding backend.
2. Run an HNSW kNN query against pgvector via `store.knn_search`,
   over-fetching by a factor of `_VECTOR_OVERFETCH` (3) so the reranker has
   enough candidates to meaningfully reorder.
3. Rerank candidates with RRF (reciprocal-rank fusion) in
   `src/tessera/retrieval/reranking.py`, blending the vector ranking with a
   lexical (BM25-style) signal.
4. Materialise `RetrievedDocument` records carrying the fused score for the
   agent state.

Empty queries short-circuit to an empty list; empty kNN results short-circuit
before reranking.

### Cross-lingual regulation search

`knn_search` accepts `language: LanguageCode | None`. When a concrete language
is passed, the query is scoped with `WHERE corpus = %s AND language = %s`. When
`language` is `None`, the language filter is dropped and the search spans all
languages. This is used by `regulation_lookup`: EU regulatory texts (DORA,
CNIL, BaFin, GDPR) are stored in their source language regardless of the
conversation language, so a French-speaking user's question must be able to
match a German BaFin circular. Cosine similarity in a multilingual embedding
space carries the cross-lingual matching; the active conversation language is
restored later, at the reporter, which renders the answer in the user's locale.

### Chunking

Corpus documents are split into chunks before embedding
(`src/tessera/retrieval/chunking.py`) and ingested with stable `chunk_id`s so
that the `(corpus, source, chunk_id)` uniqueness constraint makes re-ingestion
idempotent (`INSERT ... ON CONFLICT DO NOTHING`).

## LLM layer

Two interchangeable backends sit behind one narrow `ChatBackend` Protocol
(`src/tessera/llm/router.py`): `chat(messages, *, temperature, max_output_tokens)
-> ChatResponse`. The selector `get_chat_backend()` is `lru_cache`d for the
process lifetime and resolves the backend from the active `LLMProfile`:

- **Frontier path** — `LLMProfile.FRONTIER` selects `VertexAIBackend`
  (`src/tessera/llm/frontier.py`), reaching a Gemini model through Vertex AI.
  Embeddings on this path also come from Vertex AI.
- **On-prem path** — otherwise `OllamaBackend` (`src/tessera/llm/local.py`)
  serves Llama 3.3 70B via Ollama, running locally on Apple Silicon, with
  embeddings from a local Ollama setup.

Imports are deferred inside `get_chat_backend()` so on-prem hosts need no Vertex
AI credentials and frontier hosts need no Ollama install.

### Budget control

`ChatResponse` carries `input_tokens` / `output_tokens`. The process-wide
`BudgetTracker` (`src/tessera/llm/budget.py`) accumulates token usage per
`(backend, model)` pair under a lock and converts it to an indicative EUR cost
from a small in-memory price table. On-prem inference is priced at zero marginal
LLM cost — hardware amortisation is out of scope for per-call accounting. Prices
are indicative only; the project makes no production-grade FinOps claim. The API
layer queries the tracker once per request to enforce per-conversation caps.

## Tool versus worker separation (ADR 0005)

Tessera draws a hard line between two kinds of callable, documented in
`docs/decisions/0005-tools-vs-workers-separation.md`:

- **Workers** (`src/tessera/agent/workers/`) are LangGraph nodes. They are
  *orchestration*: the graph decides when they run, they read and write
  `AgentState`, and the planner selects them. They are never exposed to the LLM
  as function-call targets.
- **Tools** (`src/tessera/agent/tools/`) are LLM-callable function-call targets
  (`account_balance`, `card_block`, `transaction_search`, `loan_simulate`,
  `ticket_escalate`). They have narrow typed signatures and side effects on
  banking systems.

A worker may invoke a tool; a tool never invokes a worker. Keeping the two
distinct is what lets the guard sit at exactly one boundary.

## Why guardrails at the tool-call boundary, not the HTTP layer

The guard is placed at the tool-call boundary (`guarded_invoke` in
`src/tessera/guard/adapter.py`), the single chokepoint between every worker and
every tool — not at the FastAPI HTTP layer. The reasons are concrete:

- **Semantic context.** At the tool boundary the guard sees the resolved tool
  name, the typed arguments, and the active language, so it can apply
  per-tool allow/deny, language restrictions, and argument validation (e.g.
  mask an IBAN argument). At the HTTP layer it would see only an opaque chat
  payload.
- **Internal calls are covered too.** A worker that decides on its own to call
  a tool is guarded identically to one driven by an LLM function call. An
  HTTP-layer guard would miss everything the agent originates internally.
- **One auditable point.** Every guarded invocation produces exactly one audit
  entry tied to a specific tool and its arguments, which is what
  `docs/compliance.md` requires for regulatory replay.

`guarded_invoke` does three things: a pre-flight policy check (refusing to
invoke if it fails), the actual invocation through a caller-supplied closure (so
the guard never needs to know tool signatures), and a post-flight audit emission.

## Audit trail design

Each guard decision is captured as a frozen `GuardDecisionRecord` in the agent
state (`target`, `decision` ∈ {allow, deny, transform}, `policy_rule`,
`rationale`, `redactions`, `occurred_at`). The audit emitter
(`src/tessera/guard/audit.py`) wraps these into a versioned envelope
(`type: tessera.guard.audit`, `version: 1`) with the target, outcome,
JSON-coerced arguments, the list of decisions, and any error.

**The sink is a transport; the ledger is the store** (ADR 0023). The opposable hash chain is
persisted upstream of the sink, into the append-only Postgres ledger, for **every** sink —
the chain is not a configuration option. The sink only selects where an extra copy is
carried:

- `stdout` — JSON-Lines on stdout, for local dev and tests.
- `file` — appended JSON-Lines to a configured path, parent dirs created as
  needed. Pre-cut, this file is itself the chain.
- `cloud_logging` — Google Cloud Logging via `logger.log_struct`; the observability copy in
  staging and prod. Lazily imported, and if the client library is absent it **raises**. It
  used to "degrade gracefully" to stdout, which meant an operator's chosen sink was silently
  empty while every dashboard built on it read zero (audit F-6).
- `postgres` — no separate copy: the Postgres persistence of an entry *is* the ledger,
  upstream. It never writes a stdout line pretending to be a table.

Emission of the *copy* is fire-and-forget: a transport failure is named on stderr and does
not block the agent's main path — and since ADR 0023 it costs no ledger entry either, which
is precisely what makes failing loudly affordable. Argument values are
coerced to JSON primitives, with non-primitive values rendered via `repr` so an
audit entry is always serialisable.
