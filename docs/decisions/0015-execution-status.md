# ADR 0015 — execution status (autonomous run)

Single source of truth for **where the ADR 0015 implementation is**. The autonomous loop
(see ADR 0015 §Execution protocol) updates this file after every phase. A resuming session
reads this first, then continues the **next `pending` phase** — no re-work.

- **Protocol**: implement → full gate **twice green** + phase verification → commit + push
  (targeted staging, never `git add -A`) → update this file → auto-advance. No human gate.
- **Halt only** on: 3 failed repair attempts, the **Docker daemon unavailable** (the run starts the
  obs stack itself via `make obs-up-core`/`obs-up`), or an honesty conflict. Otherwise A→F to end.
- **Stop it anytime**: create the file **`docs/decisions/0015-STOP`** — the run finishes its current
  safe step, records state, and exits cleanly (never a half-committed phase).
- **Watch it**: this Log (below, newest first) + `git log origin/feature/redesign`.
- **Branch**: `feature/redesign` · **remote**: `origin/feature/redesign`.

## Phase ledger

| Phase | Scope (short) | Status | Commit | Notes |
|---|---|---|---|---|
| A | Scope object + registry + capabilities + snapshot endpoint + cache/single-flight (reads current stores) | ✅ done | `697106f` | kills the silent-ignore bug class; fast read model in place before any source swap. Perf p95: cold 25ms / warm 2ms / 2 upstream reads for 9 signals |
| B | Complete stamping (EVAL_SCORE / GUARD_DECISIONS labels + span attrs + Langfuse scores) + Prometheus recording rules + "data available since" cutoff | ✅ done | `828016f` | agent_id+model on EVAL_SCORE; agent_id on GUARD_DECISIONS (now wired); turn-span stamping; 5 recording rules loaded; /availability honest per-dimension cutoff |
| C | Read adapters (langfuse / prometheus / ledger) behind read(scope); aggregates→Prom, detail→Langfuse; shadow-run + parity per signal; contract tests; spine creds via Secret Manager | ✅ done | `f6723f5` | real Prom/Langfuse query clients + `SpineStoresReader` (Langfuse detail + local ledger carve-out); `TESSERA_SPINE_SOURCE` = jsonl(default)\|spine\|shadow; `ShadowReader` records `tessera_spine_shadow_divergence_total`; unreachable→`SpineUnavailableError` (honest-empty); 23 unit + 7 live contract tests. Perf p95: cold 2.8ms / warm 1.4ms / 2 upstream reads |
| D | Retire convenience jsonl (scores/bundles) after all signals flipped + baked; keep audit/S1 ledgers; erasure reaches spine + cache | ⬜ pending | — | |
| E | Four cards (traces / inbox / release / audit) + fixtures flagged synthetic / derived from spine | ⬜ pending | — | |
| F | Add language + model dimensions to Scope UI (no route sweep) — prove agent × time × language cube | ⬜ pending | — | |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green + pushed) · ⛔ blocked (see notes).

## Log (newest first)

- **Phase C ✅ — `f6723f5`** (twice-green + pushed). Built the read seam over the live spine
  (§Migration C) as **real** query clients, not stubs: `prometheus.py` (PromQL instant/range +
  `Scope.to_labels()` selector — every dashboard *number*) and `langfuse.py` (per-agent scores
  and traces by `metadata.agent_id` + as-of-T `toTimestamp` window — LLM *detail*), with the
  tamper-evident **ledger read locally** (the carve-out — never leaves the process). Source is a
  factory on `TESSERA_SPINE_SOURCE`: **jsonl** (default, unchanged), **spine** (the flip), or
  **shadow** (`ShadowReader` serves jsonl, compares the spine, records
  `tessera_spine_shadow_divergence_total{fact,result}` — a signal graduates jsonl→spine only
  after parity holds). An unreachable spine raises `SpineUnavailableError` → honest-empty, never
  a fabricated zero. **Honest state**: the spine has no dimensioned *history* yet (0 Langfuse
  scores; pre-stamping traces carry `agent_id=None`), so the row-level spine reads are served
  **only in shadow** and are never presented as the real per-agent view — exactly the
  ADR-sanctioned pre-parity posture. Gate twice-green: ruff + ruff-format (baseline 32, none
  mine) + mypy strict (160 obs files) + 23 new spine unit + 9 stamping + 7 live contract
  (Prom/Langfuse reachable) + perf budgets met (cold p95 **2.8 ms**, warm **1.4 ms**, 2 upstream
  reads for 9 signals). Frontend untouched (backend-only diff). **Pre-existing** integration
  failures (firewall auth-seed; two non-hermetic memory Postgres tests) fail *identically on
  pristine HEAD* — proven by stashing this diff and re-running — so they are out of Phase C
  scope, not a regression. **Next: Phase D.**
- **Phase B ✅ — `828016f`** (twice-green + pushed). Completed the dimensioning so Phase C's
  adapters can read per-agent facts: **EVAL_SCORE** gains `agent_id` + `model` labels (model
  threaded through `evaluate_turn`); **GUARD_DECISIONS_TOTAL** gains `agent_id` and is now
  *actually wired* (a helper increments it at the 4 guard-decision sites — it was defined but
  never emitted); `semconv.stamp_turn_dimensions()` stamps {agent, language, model,
  conversation, turn, environment} on the turn root span (the Langfuse per-agent substrate);
  best-effort Langfuse **score mirroring** (`langfuse_scores.py`, daemon thread, no-op without
  a trace, never blocks the turn); **Prometheus recording rules** (`infra/.../rules/`, 5 rules,
  validated by promtool + loaded via rule_files + `--web.enable-lifecycle`); per-dimension
  **"data available since"** (`spine/availability.py` + `/observability/availability`) — honest
  forward-only (agent since 06-25 vs data since 06-24); `scripts/backfill_langfuse_traces.py`.
  Gate twice-green: ruff + ruff-format (baseline 32) + mypy strict (237) + 868 unit (9 new) +
  tsc + biome + 29 vitest + promtool (5 rules) + rules loaded + /availability verified. **Next:
  Phase C.**
- **Phase A ✅ — `697106f`** (twice-green + pushed). Introduced the spine foundations:
  `Scope` value object, capability-declared signal registry (honoured/ignored report → the
  silent-ignore bug class is now unrepresentable), the `SpineReader` adapter seam with an
  in-memory fake, and a batched cached `GET /observability/snapshot` (single-flight +
  immutable-past cache, RBAC via `require_bearer`, self-instrumented). Frontend `lib/scope.ts`
  + `lib/signal-registry.ts`; the overview org-wide badge is registry-driven, not hand-placed.
  Perf budget met and gated by `scripts/perf-probe.mjs`: cold p95 **25 ms** (< 300), warm p95
  **2 ms** (< 150), **2** upstream reads for 9 signals (≤ 4). Parity asserted (snapshot signal ==
  route handler). Gate twice-green: ruff + ruff-format (baseline 32, none mine) + mypy strict
  (235 files) + 859 unit + 36 new spine unit + tsc + biome (my files) + 29 vitest. Ledger-backed
  signals (conformance / tool-validity / governance / audit-integrity) are declared + registered
  + requestable but stay off the default hot path until Phase C's shared ledger adapter (the
  dev ledger is 25 MB; a per-scope full read + O(n) chain verify would blow the compute budget).
  Langfuse/Prometheus adapter files deferred to Phase C (built real there, not empty stubs).
  **Next: Phase B.**
- _(seed)_ ADR 0015 written and pushed (Context → Decision → Architecture → Migration →
  Performance → Testing/migration/security → Execution protocol). Phase 1 per-agent wiring
  (transitional base) is live on the branch. **Next: Phase A.**
