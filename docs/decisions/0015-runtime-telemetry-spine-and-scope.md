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

## Consequences

**Positive.** One source of truth (the runtime spine); dimensions are declarative and
adding one is O(1); the "filter shown but ignored" bug class is *unrepresentable*; fixtures
cannot masquerade as real; honesty markers are data-driven, not hand-maintained; the
"two parallel telemetry paths" smell is gone; genuinely world-class and OTel-native.

**Negative / costs.** The cockpit gains a **hard runtime dependency** on the obs stack
(Langfuse/Prometheus must be up); we lose offline simplicity (mitigated by honest-empty
degradation, not fabrication). Query latency shifts from in-process reads to Langfuse API /
PromQL — needs caching + range discipline. Coupling to the Langfuse query API. Multi-day,
multi-signal migration; must land phased with green gates each step.

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

- **Langfuse query performance** for high-cardinality metadata filters + time windows;
  needs a caching layer and sane default ranges.
- **Score model in Langfuse**: confirm per-trace scores support the metadata filters we need
  (agent_id, language) at the volume we run.
- **GDPR erasure across the spine** (ADR 0007, #180): deletion must reach Langfuse + drop
  the corresponding metric series, not just a local file — design the erasure path in Phase D.
- **Prometheus retention** vs the as-of-T (ADR 0011) horizon: PromQL range must cover the
  cockpit's history window, or long-horizon reads fall back to Langfuse.
