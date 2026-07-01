# 0015 — Runtime telemetry spine & first-class Scope for multi-dimensional cockpit signals

- Status: **accepted** (decision 2026-07-01) — implementation phased and pending
  (see §Migration plan). Supersedes the Phase-1 per-signal `?agent=` wiring shipped
  in this branch, which is absorbed as the transitional state.
- Date: 2026-07-01
- Deciders: Tessera maintainers
- Branch: `feature/redesign`
- Related: 0007 (agent memory), 0010 (frontier observability), **0011 (temporal
  as-of-T — generalised here into one dimension of `Scope`)**, 0012 (agent registry),
  0014 (environment isolation — `environment` is another `Scope` dimension),
  `docker-compose.obs.claude.yml` (Langfuse / Phoenix / Prometheus / Grafana stack),
  `src/tessera/observability/metrics.py`, `src/tessera/observability/eval/scores.py`,
  `src/tessera/observability/replay.py`, `src/tessera/observability/langfuse_obs.py`.

## Context

### The cockpit reads a bespoke convenience path, not the real telemetry spine

Tessera already emits **properly dimensioned telemetry** at runtime:

- **OTel spans** → Langfuse / Phoenix. Every turn is a trace; spans carry attributes
  (we already stamp `tessera.agent_id` in `emit_score`).
- **Prometheus** (`prom/prometheus:v2.55.1`, `:19090`, scraping the agent's `/metrics`):
  `AGENT_TURNS_TOTAL{agent_id,language,outcome}`, `AGENT_TURN_DURATION{agent_id,language}`
  are already sliceable by agent. (Gaps: `EVAL_SCORE{metric,language}` and
  `GUARD_DECISIONS_TOTAL{target,decision}` carry **no** `agent_id` yet.)
- **Grafana** dashboards over Prometheus.

But the **cockpit dashboards do not read any of this**. They read a *parallel,
bespoke path*: in-process ring buffers + append-only convenience files
(`scores.jsonl`, `bundles.jsonl`) plus the tamper-evident ledgers (`audit.log`, the
S1 governance journal). The convenience files were a deliberate shortcut — the docstring
in `eval/scores.py` says so: "so the dashboard can show live eval-as-telemetry without
standing up Prometheus/BigQuery locally". That shortcut is now the **architectural smell**:
two parallel telemetry paths, one of which (the real, dimensioned one) the product ignores.

### Consequence: dimensioning is implicit and per-signal → a whole bug class

Because a signal is defined by *which store it reads* and filters are bolted on
store-by-store, "can this signal be sliced by agent?" is an **emergent property of the
implementation**, discovered case by case. The Phase-1 work in this branch made
online-eval scores + replay bundles carry `agent_id`, added `?agent=` to ~14 routes,
and hand-placed honest "org-wide" badges. It works, but it exposed the deeper problem:

- Adding a dimension is **O(signals × dimensions)**: agent touched ~14 routes + 3 stores;
  the next dimension (language, model, tenant, channel) would repeat all of it.
- The state **"a filter is shown but silently ignored"** is *representable* — and it
  happened (Vue d'ensemble's Activité gouvernée / Incidents / Actions recommandées cards
  ignored `?agent=` while the filter was on screen). Every new signal risks re-introducing
  it. Honesty markers are placed by hand, so they drift.
- Deterministic **fixtures** (incidents / curation / automations / replay-shadow) have no
  real per-agent data; ventilating them would fabricate a per-agent split of a fixture —
  a direct violation of the project rule "never call a deterministic fixture real".

### The offline trade-off we are choosing to give up

The convenience jsonl let the demo run **without** the obs stack. The maintainers have
decided (2026-07-01) to trade that offline simplicity for a runtime-connected, world-class
architecture: **the cockpit reads the live telemetry spine, not jsonl.**

## Decision

Adopt a **single, runtime-connected telemetry spine** as the source of truth for
dimensioned facts, and make **Scope** (the set of dimension filters) a **first-class,
declared** concept end to end. Concretely:

1. **The spine is the runtime telemetry that already exists** — OTel spans in
   Langfuse/Phoenix for per-turn facts/traces/scores; Prometheus for metric time-series.
   This is **adoption of OTel semantic conventions**, not a new framework — squarely
   within Tessera's "reuse, don't reinvent" thesis. **No warehouse is added.**

2. **Every fact-emitting path stamps the full dimension set** on its span/metric:
   `agent_id`, `language`, `model`, `conversation_id`, `turn_id`, `environment`
   (ADR 0014). One helper stamps them at turn start; scores/guard/tool spans and the
   Prometheus label sets are completed (§Migration B).

3. **`Scope` is a first-class value object** — `{at?, agent?, language?, model?, environment?}`
   — parsed **once** on each side (server: from `searchParams`; client: from the URL),
   replacing the scattered `readAgentScope` / `withAsOf` / `withScope` / `_agent_or_none`.
   **This generalises ADR 0011**: the temporal `at` becomes one dimension of `Scope`, not a
   separate mechanism. Adding a dimension later is a field on `Scope`, not a route sweep.

4. **A signal registry with declared capabilities.** Each signal declares
   `{id, dimensions: Set<Dimension>, synthetic: boolean, read(scope): Data}`. The read
   layer applies `Scope` uniformly and **reports** which dimensions it honoured.

5. **The UI is generated from the declarations.** Filters and the "org-wide" / "synthetic"
   badges are rendered from each signal's capability descriptor — **not hand-placed**. A
   signal either declares a dimension (the filter works) or does not (the UI badges it
   automatically). This makes the illegal state *"filter shown but ignored"*
   **unrepresentable** (make illegal states unrepresentable).

6. **Retire the convenience jsonl** (`scores.jsonl`, `bundles.jsonl`) as system of record;
   the cockpit reads the spine instead.

### Non-negotiable carve-out: the tamper-evident ledgers stay local

"No jsonl" targets the **convenience** stores that *duplicate* Langfuse/Prometheus. It does
**not** apply to `audit.log` and the S1 governance journal. Those are **append-only,
hash-chained tamper-evident ledgers** — their local, sequential hash chain **is** the
security property (DORA/BaFin evidence). Exporting them to Langfuse would **break
tamper-evidence** (Langfuse is not an append-only hash chain). They already carry
`agent_id` (they are dimensioned), and reading them directly, filtered by `agent_id` +
`occurred_at`, is correct. **They are not the smell; they are the compliance ledger.**
Removing them would degrade security in the name of purity — explicitly rejected.

## Architecture

### The dimensioned fact model

The atomic fact is a **turn**. A turn emits a trace (Langfuse) and metric observations
(Prometheus), each carrying the dimension set:

```
dimensions = { agent_id, language, model, conversation_id, turn_id, environment }
time       = the span/observation timestamp  (the `at` dimension is a window end)
```

Every cockpit signal is a **derivation over turns**, parameterised by `Scope`:
`signal(scope) = aggregate(facts where facts.dimensions ⊇ scope.filters and facts.time ≤ scope.at)`.

### Physical backends behind the spine (per fact type)

| Fact type | Today (retire / keep) | Spine home | Read adapter |
|---|---|---|---|
| Eval scores (faithfulness/grounding/hallucination) | `scores.jsonl` → **retire** | Langfuse **scores on the trace** + Prometheus `EVAL_SCORE` | Langfuse (per-trace, metadata filter) + Prometheus (SLO/quantile series) |
| Captured turns (cost / toxicity / pii / replay) | `bundles.jsonl` → **retire** | Langfuse **trace** (holds input/context/output) | Langfuse (filter by `agent_id`, time window); derived signals computed over trace payloads |
| Metric series (turns, duration, budget) | Prometheus (partial) | Prometheus | PromQL with label selectors + range |
| Guard decisions (conformance, tool-validity) | `audit.log` → **keep (ledger)** | `audit.log` (hash-chained, `agent_id`) | Ledger adapter, filtered by `agent_id` + `occurred_at` |
| Governance (routing/handoff/proposed/release/deploy) | S1 journal → **keep (ledger)** | S1 journal (hash-chained, `agent_id`) | Ledger adapter, filtered |
| Fixtures (incidents/curation/automations/replay-shadow) | deterministic fixture | derive from spine where a real fact exists; else `synthetic:true` | registry marks `synthetic` |

### The `Scope` value object

- Backend: `src/tessera/observability/spine/scope.py` — `Scope(at, agent_id, language,
  model, environment)`, plus `Scope.from_query(params)` and `Scope.to_labels()` (→ a
  Prometheus/Langfuse selector). `agent_id in {None, "<id>"}` (`"all"`→`None`).
- Frontend: `lib/scope.ts` — `parseScope(searchParams) → Scope`, `withScope(path, scope)`
  (absorbs `withAsOf` + the current `withScope`), and `scopeKey(scope)` for React-Query
  keys. `lib/agent-scope.ts`, `lib/temporal-url.ts` are folded into it.

### The signal registry & capability descriptor

`src/tessera/observability/spine/registry.py`:

```python
@dataclass(frozen=True)
class SignalSpec:
    id: str
    dimensions: frozenset[Dimension]   # subset of {AGENT, TIME, LANGUAGE, MODEL}
    synthetic: bool = False            # fixture / not-yet-real → UI labels it honestly
    read: Callable[[Scope], Awaitable[object]]
```

- The read layer intersects `scope` with `spec.dimensions`; unsupported dimensions are
  ignored **and returned in a `honoured/ignored` report** so the UI can badge them.
- Domain-global invariants are expressed by *omitting* a dimension from `dimensions`
  (e.g. audit-chain integrity omits `AGENT`) — the UI then shows "org-wide" automatically
  and truthfully.
- Frontend mirror: `lib/signal-registry.ts` maps `signalId → {dimensions, synthetic}` so a
  `<SignalCard signalId>` renders the filter affordance + org-wide/synthetic badges with no
  hand-written notes. The current hand-placed `orgSignalsNote` / `orgWide` / `orgPostureNote`
  strings and the `ORG_WIDE_CONTROL_IDS` set are replaced by registry-driven rendering.

### Honest degradation (replaces the offline guarantee)

The spine (Langfuse/Prometheus) runs in `docker-compose.obs.claude.yml`. If a backend is
unreachable, a signal returns an **honest empty** state and the read report marks it
`unavailable` → the UI shows "spine indisponible", **never a fabricated zero**. This keeps
the "never fake data" rule intact while accepting the runtime dependency.

## Per-signal resolution (including the four cards raised)

| Signal / card | Verdict | Rationale |
|---|---|---|
| **Preuves d'audit** | Ventilate the **count**; keep **integrity global** | The hash chain links entry N to N-1 across all agents; a per-agent sub-chain is a *weaker* security guarantee. Global integrity is a **domain/crypto invariant**, not an arch limit. `dimensions` omits `AGENT` for the integrity sub-signal; the event **count** declares `AGENT`. |
| **Observabilité · traces** | **Ventilate** — purest spine win | Traces already live in Langfuse with `tessera.agent_id`. Per-agent = a Langfuse `metadata.agent_id` filter. Zero bespoke. |
| **Control Cases (inbox)** | **Ventilate** — data-model gap | A control case is intrinsically about one agent's turn. Case = a **view/annotation over a trace** → `agent_id` derives from the source turn. Add `agent_id` to the case model (or derive it) . |
| **Release / changements** | **Finish** — already per-agent by nature | The release gate *is* per-agent (Support 50 % / Onboarding 54 % / Recouvrement 74 %). Card is ~85 % scoped; only the AI-Act sub-signal is org (same crypto caveat: oversight **count** ventilable, chain part global). |
| Quality / SLO / trend / funnel / scores | already `AGENT`+`TIME` (Phase 1) → move source to spine | Langfuse scores + Prometheus `EVAL_SCORE` (after label completion). |
| Cost / toxicity / pii / what-changed | already `AGENT`+`TIME` (Phase 1) → move source to spine | Langfuse traces. |
| Conformance / tool-validity / governance | `AGENT`+`TIME` via ledger (keep) | Read `audit.log` / S1 journal filtered — already correct. |
| refusal / firewall efficacy | `TIME`-none, `AGENT`-none (org) | Fixed-corpus probes of the **current shared policy** — identical per agent, no substrate to slice. `dimensions` empty → UI badges org-wide. |
| incidents / curation / automations / replay-shadow | `synthetic:true` until real | Deterministic fixtures. Derive from spine where a real fact exists (e.g. incidents from guard-deny clusters + low-score turns, all in the spine); otherwise keep flagged so they can never be silently ventilated. |
| reliability / compliance / improvement | composite → declare the **intersection** of sub-signal dimensions | Reliability & improvement read scores+bundles (→ `AGENT`+`TIME`); compliance mixes per-agent (conformance/pii) and org (refusal/firewall/ai-act) → declare `AGENT` only if *every* rendered sub-metric supports it, else org with per-metric badges. |

## Canonical tree changes

Adds (supersedes the ad-hoc Phase-1 helpers `_agent_or_none` / `withScope` / `_by_agent`,
which are absorbed):

```
src/tessera/observability/spine/
├── __init__.py
├── scope.py            # Scope value object + from_query/to_labels
├── registry.py         # SignalSpec + registry + read(scope) with honoured/ignored report
├── capabilities.py     # per-signal dimension declarations (single source of honesty truth)
└── adapters/
    ├── __init__.py
    ├── langfuse.py     # traces/scores by metadata + time window
    ├── prometheus.py   # PromQL label-selector + range
    └── ledger.py       # audit.log / S1 journal, filtered (tamper-evident, stays local)
webapp/frontend/lib/
├── scope.ts            # parseScope / withScope / scopeKey  (folds agent-scope + temporal-url)
└── signal-registry.ts  # signalId → {dimensions, synthetic}  (drives UI badges/filters)
```

## Migration plan (ordered, each phase independently shippable)

**A — Foundations (no behaviour change, kills the bug class).**
Introduce `Scope` + the registry + `capabilities.py`, and migrate the existing Phase-1
wiring to *declare* its capabilities. Replace hand-placed `orgSignalsNote` / `orgWide` /
`ORG_WIDE_CONTROL_IDS` with registry-driven badges. Storage unchanged. Gate: parity with
today's render, no silent-ignore possible.

**B — Complete the stamping (make the spine fully dimensioned).**
Add `agent_id` (+ `language`, `model`) labels to `EVAL_SCORE` and `GUARD_DECISIONS_TOTAL`.
Add a turn-start span-attribute helper stamping the full dimension set on every span. Emit
each eval verdict as a **Langfuse score on the trace** (in addition to the metric).

**C — Read adapters (connect cockpit to spine).**
Build `langfuse.py` + `prometheus.py` + `ledger.py` behind `read(scope)`. Migrate signals
column by column: quality/SLO/trend/funnel/scores → Prometheus/Langfuse; cost/toxicity/pii/
what-changed/replay → Langfuse traces; conformance/tool-validity/governance → ledger (already).

**D — Retire the convenience jsonl.**
Remove `scores.jsonl` + `bundles.jsonl` as system of record (optionally keep a thin,
clearly-labelled local cache *only* for a degraded-offline mode). **Keep `audit.log` + S1
journal** (ledgers). Update `purge_conversation` (GDPR erasure) to erase in the spine
(Langfuse deletion API + metric relabel drop) instead of rewriting jsonl.

**E — The four cards + fixtures.**
Traces (Langfuse `metadata.agent_id`); inbox (`agent_id` from source turn); release (finish
AI-Act count-ventilated / chain-global); audit (count ventilated, integrity global — write
the invariant, not a TODO). Flag the four fixture composites `synthetic:true`; derive from
the spine where a real fact exists.

**F — Multi-dimensional generalisation (proves the payoff).**
Add `language` + `model` to the `Scope` UI. Because signals *declare* dimensions, this is a
field on `Scope` + registry entries — **no route sweep**. Prove the cube agent × time ×
language end to end.

## Performance budget & caching (first-class — designed and built from Phase A)

The current cockpit is fast for exactly one reason: it reads in-process files. Moving to
the spine replaces the per-page fan-out with network + query round-trips — **Qualité IA
fires 37 `useQuery`, Vue d'ensemble 24, Sécurité 16**, each re-fired on every poll (5–30 s),
every agent switch, and every temporal scrub. Done naïvely that regresses the UI from
"instant" to seconds. **Performance is therefore a first-class requirement of this ADR, not
a follow-up: the caching and batching below ship in Phase A, before any source swap.** The
risk is **data-load latency, not React render** (rendering is unchanged).

Framed positively: today's 37 separate HTTP calls that each re-parse whole jsonl files on
every poll are themselves wasteful. Done right, the spine is **as fast or faster** — the
migration is the moment to fix the fan-out, not just a risk to absorb.

### Budget (the contract — measured, and a gate on each phase)

| Interaction | Target (p95) | How it is met |
|---|---|---|
| Cold dashboard TTI (all KPIs populated) | **< 500 ms** | one batched snapshot query; Prometheus aggregates |
| Warm reload / poll refresh | **< 150 ms** | served from cache (stale-while-revalidate) |
| Agent switch (scope change) | **< 200 ms** | cache hit for warm scopes; ≤ 1 upstream query |
| Temporal scrub step | **< 100 ms perceived** | debounce + `keepPreviousData` + immutable past-instant cache |
| Backend snapshot compute (1 scope, all signals) | **< 300 ms** | shared spine reads, no per-signal fan-out |
| Upstream spine queries **per snapshot** | **≤ 1 PromQL + ≤ 1 Langfuse** | not 24–37; Langfuse only for trace-detail signals |
| Concurrent viewers of one scope | **1 upstream query / TTL** | request coalescing (single-flight) |

A snapshot that misses budget **fails the phase gate**. The endpoint instruments its own p95
latency + cache-hit-rate as Prometheus metrics — we dogfood the spine.

### Mandatory patterns (in order of leverage)

1. **Read-model split — aggregates on Prometheus, detail on Langfuse.** Every dashboard
   *number* (SLO, rate, quantile, cost, count, trend) comes from **Prometheus** — a
   pre-aggregated TSDB built for range + label queries. **Langfuse is queried only for detail**
   (opening a trace, the Traces card, drill-downs), never to compute an aggregate on the hot
   path. *Rule: the hot path never pulls raw traces to sum a number.*
2. **Batched snapshot endpoint (the anti-fan-out).** `GET /observability/snapshot?scope=…`
   returns **all** signals for a scope in one backend pass that shares the underlying reads
   (one multi-metric PromQL query; at most one Langfuse query for the trace-summary card). The
   frontend fires **one** React-Query; each card `select`s its slice, so cards still render
   independently with **one** network round-trip. Collapses 37 → 1 — the single biggest lever.
3. **Read-through cache with single-flight + stale-while-revalidate.** Server-side cache keyed
   by `(scope, time-bucket)`, TTL = poll cadence (~10 s live). Concurrent requests for the same
   key **coalesce onto one** in-flight upstream query; the cached value is served instantly and
   revalidated in the background, so a poll never blocks on the network.
4. **Immutable past instants (the temporal super-power).** An as-of-T read of a *past* instant
   can never change → **cache it forever**. Scrubbing back to any visited instant is a cache
   hit (~0 ms). With scrub debounce (~200 ms after drag stops) and `keepPreviousData` (already
   used), temporal navigation stays smooth even on a cold instant.
5. **Pre-aggregation (recording rules) + bounded, adaptive ranges.** Per-agent aggregates (SLO
   over 5m/1h, cost, error rate) are **Prometheus recording rules** computed at scrape time →
   O(1) reads, not heavy on-read PromQL. The as-of-T window has a max default range, and the
   PromQL `step` scales with the window (coarser step for wider windows) so a query never
   returns 10k points to draw a 200 px sparkline.
6. **Langfuse cardinality discipline.** `agent_id` / `language` / `model` land as **indexed**
   trace metadata/tags so filters are index scans, not full scans; trace-detail queries are
   always `limit`- and time-bounded — never "fetch all, then aggregate".
7. **Honest degradation is also a latency guard.** Each signal has an upstream **timeout**
   (~800 ms); on a slow/unreachable spine the snapshot returns that signal `unavailable`
   (honest empty) rather than blocking the page. The dashboard paints what is ready and badges
   the rest — never held hostage by one slow query.

### Folded into the phases (so it is built from day one, not bolted on)

- **Phase A** ships the **snapshot endpoint + `(scope, time-bucket)` cache key + single-flight**,
  initially reading the *current* stores. Batching and caching therefore exist **before** any
  source swap; Phase C only changes what the adapter reads underneath — the fast read model is
  already in place and gated by the budget table.
- **Phase B** adds the **Prometheus recording rules** for per-agent aggregates alongside the
  metric-label completion.
- **Phase C** adapters honor the cache + single-flight and enforce the aggregates-on-Prometheus
  / detail-on-Langfuse split; the budget table gates the phase.

## Testing, migration safety & security (first-class — designed from Phase A)

Performance is not the only cross-cutting requirement a runtime-connected cockpit needs
before it swaps a live source. Testing, data migration, safe rollback and security are peers
of §Performance and are **decided here, not deferred**.

### 1. Testing strategy — keep the 823 tests offline and green

- **Adapter seam.** The `read(scope)` adapters (`langfuse.py` / `prometheus.py` / `ledger.py`)
  sit behind one interface. Tests inject an **in-memory fake adapter** seeded with canned facts,
  so unit tests stay **offline, deterministic and fast** — no Langfuse/Prometheus required. The
  existing jsonl fixtures become the fake adapter's seed data during migration, so the current
  823 tests carry over unchanged.
- **What unit tests cover.** `Scope` parsing/serialisation, the registry's dimension
  intersection + `honoured/ignored` report, `synthetic` flagging, and the snapshot endpoint's
  shape (golden test). The registry-driven UI is tested by asserting badges/filters render from
  the capability descriptors (not hand-placed).
- **Contract tests (integration tier).** A throwaway spine (a `docker-compose` test profile
  with ephemeral Langfuse + Prometheus) verifies the adapters actually speak Langfuse queries /
  PromQL correctly. Tagged `pytest.mark.integration`, gated separately like today's integration
  suite — never in the fast loop.
- **Frontend.** MSW (or fixtures) for the single snapshot endpoint; assert cards `select` their
  slice and render org-wide/synthetic badges from the registry.

### 2. Historical backfill — honest per-dimension "data available since"

Stamping is forward-only (spans carry `agent_id` from now; §Migration B). History therefore
needs an explicit stance, never fabrication:

- **Langfuse traces**: backfill `agent_id` (+ language/model) onto existing traces via the
  update API by joining `trace → conversation_id → transcript responder` — the exact mirror of
  `scripts/backfill_agent_attribution.py`. Where the join resolves, history becomes per-agent;
  where it does not, the trace stays org-only.
- **Prometheus**: a TSDB **cannot** be cleanly backfilled with new historical labels → per-agent
  metric series start at the label-completion deploy. Older per-agent aggregates come from the
  Langfuse trace backfill, or are honestly org-only before the cutoff.
- **The contract**: each dimension exposes a **"data available since" boundary** (extends ADR
  0011's `data-range`), and an as-of-T read before that boundary reads org-wide (or empty),
  clearly marked in the UI — the cockpit never pretends a dimension existed before it was stamped.

### 3. Migration safety — per-signal source flag + shadow, so every step is reversible

- **`source` per signal** in the registry: `jsonl | spine | shadow`. A signal is flipped
  spine→jsonl **instantly via config/env, no deploy**, if a spine read is wrong or slow.
- **Shadow mode** (dark launch): run *both* sources for a signal, **serve jsonl**, and log the
  divergence. A signal graduates to `spine` only after it holds **parity** over a bake period.
  This is how a live signal migrates without a user-visible regression.
- **Global kill-switch**: "spine off" → every signal falls back to jsonl / honest-empty for
  incident response. jsonl is retired (§Migration D) only once **all** signals have flipped and
  held parity — the transitional dual-run is the safety net, not a smell.

### 4. Security & privacy

- **Authz.** The snapshot endpoint enforces the **same RBAC as today's routes (ADR 0009)**:
  scope is a *filter*, never a privilege escalation — an operator sees only what their role
  allows, and choosing an agent scope can never widen access.
- **Credentials.** Langfuse API keys + Prometheus auth live in **Secret Manager / env, never in
  the repo** (CLAUDE.md). Only the FastAPI backend talks to Langfuse/Prometheus; **the browser
  never holds a spine key** — it calls the snapshot endpoint only.
- **PII.** Langfuse traces hold conversation content (PII). The snapshot returns **aggregates,
  not raw payloads**; trace drill-down is authz-gated **and** audit-logged; GDPR erasure reaches
  Langfuse + evicts the read-through cache (§Open questions, §Migration D).

### 5. Prometheus ↔ Langfuse consistency

- They can disagree — Prometheus counts every scrape; Langfuse may **sample** traces. Rule: a
  **canonical source per fact** — aggregates are canonical on **Prometheus**, trace detail is
  canonical on **Langfuse**; the two are never mixed for the *same* number.
- Where a card shows a Prometheus aggregate next to a linked Langfuse detail list, the expected
  skew (sampling) is documented and the UI reconciles by using the same time window; a periodic
  **consistency probe** compares a known aggregate from both and alerts on drift beyond a
  threshold — we dogfood the reconciliation.

### Folded into the phases

- **Phase A**: adapter seam + fake adapter (tests stay green); registry `source` flag +
  shadow-mode scaffolding; snapshot-endpoint RBAC.
- **Phase B**: record the stamping cutoff → per-dimension "available since"; the Langfuse trace
  backfill script.
- **Phase C**: shadow-run each signal, flip on parity; contract tests vs the ephemeral spine;
  wire spine credentials via Secret Manager.
- **Phase D**: erasure reaches spine + cache; retire jsonl only after all signals flipped and
  the bake period passed.

## Execution protocol (autonomous — run Phases A→F without human gates)

This ADR is implemented **autonomously**: the executing agent advances from one phase to the
next **without waiting for human validation**, self-verifying at each step. Human involvement is
reserved for genuine blockers, never for routine progression.

### The loop (per phase)

1. **Implement** the phase per §Migration + its §Performance and §Testing requirements.
2. **Verify — multiple times.** Run the **full gate** — `ruff check` + `ruff format --check` +
   `mypy` (strict) + `tsc --noEmit` + `biome check` + `pytest -m "not integration"` — **plus the
   phase-specific verification** (the Performance budget probe on a snapshot; a capture / curl
   proving the render; the contract test for a new adapter). Require it **green twice
   consecutively** — a second clean run catches flakiness / non-determinism — before proceeding.
3. **Commit + push (targeted).** Commit the phase with a Conventional-Commits message, staging
   **only that phase's files by path** — **never `git add -A`** (the working tree is shared with a
   concurrent workstream; a blanket add sweeps in unrelated WIP). If a file shows changes outside
   the phase's scope, surface it — do not silently blend workstreams. Push to
   `origin/feature/redesign`.
4. **Record state, then auto-advance.** Update the execution status file (below) with the phase,
   result and commit sha, and **immediately start the next phase** — no pause, no ask.

### Stop conditions (the only times it halts instead of advancing)

Halt and write a clear status report **only** when:
- a phase cannot reach a **green gate after 3 repair attempts** → do **not** commit/push a broken
  phase; report the failing check;
- a **genuine external blocker** it cannot self-provide is hit — a missing credential (Langfuse
  API key, Prometheus auth), an unrunnable service, or a decision needing business/human input →
  state **exactly** what is needed to proceed;
- honesty would be violated — **never** weaken a test, fabricate data, or mark a fixture real to
  force green (§Decision, project rule).

Otherwise it runs **A → B → C → D → E → F to completion**.

### Resumability (survives context compaction and a fresh session)

A→F spans context windows. The protocol is **resumable**: the current phase + last green commit
are tracked in **`docs/decisions/0015-execution-status.md`** (seeded now, updated each phase). A
resuming session reads that file + this ADR and continues the **next** phase — no re-work, no lost
progress. That file is the single source of truth for "where are we".

### Non-negotiables during the run
- The gate is **hard**: a phase is not "done" until it is **twice-green**.
- **Secrets never enter the repo** (spine creds via env / Secret Manager).
- **Shadow before flip** (§Testing #3): a live signal switches jsonl→spine only after it holds
  parity — so an autonomous flip can never regress the UI.
- **Targeted staging only** — never `git add -A`.

## Consequences

**Positive.** One source of truth (the runtime spine); dimensions are declarative and
adding one is O(1); the "filter shown but ignored" bug class is *unrepresentable*; fixtures
cannot masquerade as real; honesty markers are data-driven, not hand-maintained; the
"two parallel telemetry paths" smell is gone; genuinely world-class and OTel-native.

**Negative / costs.** The cockpit gains a **hard runtime dependency** on the obs stack
(Langfuse/Prometheus must be up); we lose offline simplicity (mitigated by honest-empty
degradation, not fabrication). Query latency shifts from in-process reads to Langfuse API /
PromQL — **addressed by design** in §Performance (batched snapshot + read-through cache +
Prometheus-for-aggregates), which is built from Phase A and gated by a budget, not deferred.
Coupling to the Langfuse query API. Multi-day, multi-signal migration; must land phased with
green gates each step.

**Neutral.** The tamper-evident ledgers (`audit.log`, S1 journal) are unchanged — correctly.

## Alternatives considered

- **Scope object only, keep jsonl (Phase A alone).** The minimal honest fix: kills the bug
  class without the runtime dependency. Rejected by the maintainers, who want the runtime
  spine — but it is the safe fallback if the migration must pause.
- **External warehouse (BigQuery / ClickHouse) as the fact spine.** More textbook OLAP, but
  it *adds* infrastructure the stack does not need — the framework-invention the thesis
  forbids. Rejected: Langfuse + Prometheus already are the dimensioned spine.
- **Continue per-signal `?agent=` wiring (status quo).** Rejected: O(signals × dimensions),
  and the silent-ignore bug class persists.

## Open questions / risks

_Performance, testing, migration safety and security are no longer open — they are decided
in §Performance and §Testing, migration safety & security (built from Phase A). What remains
open is implementation detail:_

- **Score model in Langfuse**: confirm per-trace scores support the metadata filters we need
  (agent_id, language) at our volume, and that indexed-tag filtering meets the budget.
- **GDPR erasure across the spine** (ADR 0007, #180): deletion must reach Langfuse + drop the
  corresponding metric series (and evict the read-through cache), not just a local file —
  design the erasure path in Phase D.
- **Prometheus retention vs the as-of-T horizon** (ADR 0011): scrape retention must cover the
  cockpit's history window; beyond it, long-horizon reads fall back to Langfuse (slower path,
  outside the hot budget — acceptable for deep history, flagged in the UI).
- **Recording-rule cardinality**: per-agent × per-language × per-model recording rules must
  stay within a sane series budget; cap the pre-aggregated dimension combinations.
