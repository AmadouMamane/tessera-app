# 0011 — Temporal "as-of T" dimension for the cockpit

- Status: **accepted** (2026-06-12) — layered architecture: durable event store →
  snapshots (B) for read perf → `?at=` recompute (A) for exactness → traces/replay
  (C) for the Replay workbench (§4)
- Date: 2026-06-12
- Deciders: Tessera maintainers
- Branch: `feature/redesign`
- Related: 0006 (locale routing), 0009 (dashboard auth/RBAC), 0010 (frontier
  observability), `docs/observability-ideas.md` (#201 temporal timeline, #1
  trace replay, #15 SLO, #17 what-changed), `docs/prototypes/cockpit-time-control.html`,
  `docs/images/cockpit_temporal_integration.svg`, `docs/ui-reference/`
  (`00`/`01`/`02`/`11`).

## Context

The cockpit time picker is **not a per-chart filter**. The reference design
(`cockpit-time-control.html`, `cockpit_temporal_integration.svg`, image `11`)
defines it as a **global temporal context applied to the whole page**:

> `vue = Registre(état + actions) × Backend(valeurs à T)` — T is just a query
> parameter; the model absorbs time like it absorbs identity.

Two states of the **same** screen (no separate route):

- **Live** (default, folded): `T = maintenant`, comparison off. The *Tendance
  (7j)* column and sparklines are "already time, in the background".
- **Time-travel** (unfolded on "Relire à T"): **every block re-reads "à T"** —
  KPIs become `Score global 58/100 à T ▼ −4 vs baseline`, the critical-controls
  table headers become `ÉTAT À T / VALEUR À T / OBJECTIF / VS BASELINE / CASE`,
  the footer shows `preuves lisibles as-of T (bi-temporalité)`.

Three modes are named in image `11` (Agir / Replay, shadow & time travel):
`live` (current), `history` (state reconstructed as-of T, read-only), `replay`
(re-execute captured traces against a model/prompt and compare — the deep
workbench, backed by `POST /observability/replay` + shadow + what-changed).

The temporal context is meant to thread through **all** COCKPIT pages (Vue
d'ensemble, Qualité IA, Sécurité & Privacy, Conformité, Fiabilité & coût,
Amélioration), with the overview as the entry point and the Replay page as the
deep workbench.

### What exists today (`feature/redesign`)

- An interactive time rail on the overview: period, scrubber over the real
  `/observability/timeline` (#201), play/pause, compare-to-baseline.
- **But** `mode`/`selectedAt`/`compare` are **local to the `TemporalRail`
  component**. No other block reacts to T; the KPIs/controls/cases/footer all
  poll the **live** backend.
- **No backend endpoint accepts a T.** Aggregates (`slo`, `toxicity`, `cost`,
  `funnel`…) are computed "now" from an **in-process ring buffer** (volatile)
  and the audit log. There is no time-indexed store, no snapshots, no
  bi-temporality.

So the canonical design assumes a backend that can answer "valeur à T"
everywhere — which does not exist. Wiring the frontend "à T" before that exists
would **fabricate history**, the exact mock this redesign removed.

## Decision

### 1. `TemporalState` as a page-level context (frontend, backend-agnostic)

```ts
type TimeMode = "live" | "history" | "replay";
type Period = "24h" | "7d" | "30d";

interface TemporalState {
  mode: TimeMode;
  period: Period;
  asOf: string | null;        // ISO instant T; null = live / now
  compareTo: "target" | "now" | "previousPeriod" | "baselineRelease" | "none";
  baselineRelease?: string;
}
```

Exposed via a local React context (`useTemporal()`), set by the rail, consumed
by `KpiSection`, `CriticalControlsTable`, `ControlCasesSection`, `RightColumn`
(incidents/release/actions/activities), `AnalyticsSection`, `FooterTrustBar`.
Each data hook **keys its react-query on `(signal, asOf)`** so changing T
refetches. This shape is stable regardless of the backend strategy below.

### 2. Component contract (honest by construction)

Each section is a pure function of `(TemporalState, data)`. The data layer
exposes `fetchX(asOf?)`. **When `asOf` is set and the backend cannot answer at
T, the section renders an explicit "as-of indisponible" state — never a
fabricated value.** Labels carry the verb: `… à T` + `vs baseline` in
history/replay, current in live.

### 3. Action governance under time ("risk governs execution")

In `history`/`replay`, write/dangerous actions are disabled or transformed; the
time picker **never writes**:

- *Geler release* → **Comparer avec le Live** (read-only).
- *Rollback* → **Voir le point de rollback**.
- *Ouvrir playbook* → **Créer un replay depuis T**.
- *Générer evidence pack* → allowed, **scoped to `(period, asOf)`**.

### 4. Backend strategy — **decision: combine them, each at its layer**

No single strategy wins on both *business quality* (exactness, audit
defensibility, bi-temporal evidence) and *performance* (interactive read
latency, write overhead, storage). They serve different layers, so we **layer
them on one durable event log** (event-sourcing + snapshots / CQRS-lite):

| Criterion | **A · `?at=` recompute** | **B · Timestamped snapshots** | **C · Traces / replay** |
|---|---|---|---|
| Principle | recompute the aggregate at T over raw events ≤ T | persist computed aggregates periodically; read nearest snapshot ≤ T | reconstruct/replay state from a captured trace |
| Signal coverage | any recomputable aggregate | whatever is snapshotted (fixed ahead) | only trace-backed (one turn), not global aggregates |
| Exactness | **exact** (true value at T) | nearest snapshot ≤ T (approx.) | exact for a replayed turn (≠ system state at T) |
| Time granularity | **continuous** (any T) | discrete (= snapshot interval) | per event/turn (irregular) |
| Prerequisite | **raw history persisted** (today's buffer is volatile) | a small snapshot table + periodic job | full, replayable trace capture (#1) |
| Read latency | high/variable (recompute) | **very low** (one read) | high (re-execution) |
| Write/runtime cost | low (append events) | low–med (snapshot job, cold path) | med–high (trace storage) |
| Storage | medium (raw events) | **low** (sampled aggregates) | high (full traces) |
| Bi-temporal evidence | free via audit | free via audit | native (the trace *is* the as-of-T state) |
| Honesty risk | none (real recompute) | low (real point, labelled "nearest snapshot") | none, but wrong frame for global aggregates |
| Ideal use | audit/compliance, exact T | **overview KPIs/controls at T** (fast scrub) | **Replay/shadow/what-changed page** |

**Decision.** Build a **durable, append-only, time-stamped event log** as the
single source of truth (foundation, non-negotiable — today's in-process score
buffer is volatile and replays nothing). On top of it:

- **A (`?at=` recompute)** is the **exactness path** — exact value at any T,
  audit-defensible. The aggregation functions already exist; they just take a
  `≤ T` filter. **At Tessera's current scale (hundreds of events) A is also
  fast**, so it ships first as the primary as-of-T mechanism.
- **B (snapshots)** is the **read-optimisation** for the hot scrub path, added
  **when data volume makes A's recompute latency matter** (a materialised view
  derived from the same log — no contract change). Deferred until then to avoid
  premature optimisation (CLAUDE.md: prefer cutting).
- **C (traces/replay)** is reserved for the **Replay/shadow workbench** (image
  11), via `POST /observability/replay` + shadow + what-changed — orthogonal to
  the aggregate "as-of T".
- **Bi-temporality** of evidence is free now: the audit log is append-only and
  hash-chained, so "entries with `occurred_at ≤ T`" is exact at no cost.

Layering A+B on one event log removes the quality↔performance trade-off:
snapshots serve the interactive scrub; recompute serves the rare exact-T/audit
query; both derive from the same log, so they never drift.

### 4bis. Honest coverage at each step

A signal can be shown "à T" **only if its source is persisted/append-only**;
otherwise the section shows an explicit **"as-of indisponible (live)"** badge —
never a fabricated value. Initial honest set: **quality scores / SLO** (once the
scores log lands), **`/timeline`** (#201), **`/trend`**, and **audit evidence**.
Aggregates still computed "now" from volatile buffers (toxicity, cost, funnel…)
stay **live-badged** in history mode until they too are logged.

### 5. Bi-temporality for evidence

Evidence/audit must be readable "as known at T": the audit log is
append-only/hash-chained, so "entries with `occurred_at ≤ T`" is exact and free.
The evidence pack is scoped to `(period, asOf)`.

## Implementation status (2026-06-12)

**Phase 0 and Phase 1 are shipped** on `feature/redesign`, plus more of the page
than Phase 1 originally scoped:

- Durable append-only stores `scores.jsonl` and `bundles.jsonl` next to the
  audit log; `recent_bundles()` warms from its store after a restart so history
  survives (idea #202).
- **A (`?at=` recompute)** ships as the primary mechanism across the score-,
  bundle- and audit-backed endpoints (`/scores`, `/slo`, `/trend`, `/timeline`,
  `/toxicity`, `/pii-leak`, `/anomalies`, `/cost`, `/what-changed`, `/funnel`,
  `/playbooks`, `/roadmap`, `/conformance`, `/tool-validity`, `/ai-act`), via the
  shared `occurred_before` comparator.
- Frontend: global `TemporalState` (mode/period/asOf), every capable block reads
  "à T" with honest `à T` / `live` chips, action governance (§3), and the
  evidence pack/report scoped to `(period, asOf)` (§5).
- **Stays live by nature:** firewall-efficacy + refusal (fixed-corpus probes),
  the structural audit-chain integrity check, system health.

**Left for Phase 2:** snapshots (**B**) only when recompute latency matters
(A is fast at current scale); extend `TemporalState` to the other cockpit pages;
the dedicated Replay / shadow / time-travel workbench (**C**, image 11).

## Sequencing (answers "must point 1 be settled first?")

**Decide** the strategy (this ADR) before wiring **any** block "à T". You need
not **build** the whole backend first — the contract (§1–§2) is backend-agnostic
and a thin honest slice ships now:

- **Phase 0** (no backend change): lift `TemporalState` to context; in `live`,
  unchanged; in `history`, only append-only-sourced blocks show real "à T"
  (`/timeline`, audit evidence, and `/trend` + SLO if scores are read as-of T),
  the rest show "as-of indisponible"; apply action transformation (§3).
- **Phase 1**: persist scores/aggregates to a time-indexed store + chosen
  strategy (**B** recommended) → real "à T" for KPIs and the controls table.
- **Phase 2**: extend to the other cockpit pages and the dedicated Replay /
  shadow / time-travel workbench (image 11) on `POST /observability/replay`,
  shadow, what-changed.

## Consequences & honest limits

- ~1.6 day of real traffic + in-memory buffers → little history until
  persistence lands; 7d/30d "as-of T" will be **sparse** (a "data starts here"
  marker already states this).
- Until Phase 1, KPIs/controls stay **live even in history mode**, clearly
  **badged**, not fabricated.
- No new heavy dependency: snapshots = a small time-indexed table; recompute
  reuses the existing aggregation functions.

## Non-goals

- Not a separate route (same page, two states).
- The time picker is **read-only** — it never mutates real data.
- Not a generic BI/time-series explorer; it is the cockpit's "as-of T" lens.
