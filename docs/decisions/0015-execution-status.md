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
| D | Retire convenience jsonl (scores/bundles) after all signals flipped + baked; keep audit/S1 ledgers; erasure reaches spine + cache | ✅ done | `dfff8d8` | GDPR erasure now reaches the spine: `delete_conversation` (Langfuse batch trace delete) + unconditional snapshot-cache eviction; `purge_telemetry` folds spine count + `spine_reached` into the footprint (unreachable→deferred, never faked). Prometheus needs no per-series delete (no `conversation_id` label). **jsonl kept** as system of record — the ADR gates retirement on parity, not yet met (Phase C); the flip mechanism is in place. Verified live: DELETE→204, reaches Langfuse, deletes nothing real |
| E | Four cards (traces / inbox / release / audit) + fixtures flagged synthetic / derived from spine | ✅ done | `9553c1b` | Inbox **ventilated** — `OperatorItem.agent_id` from each agent's own eval run (fabrication-proof: no run → no items), `?agent=` filter, `inbox {AGENT,TIME}` in both registries (verified live: 78 items across 3 agents, `?agent=recouvrement`→7). Fixtures (incidents/curation/automations/replay_shadow) flagged by a registry-driven `<SyntheticNotice>`. Traces/Release/Audit verified already-honest (audit integrity is a real `verify_audit_chain`, not a TODO) → no rebuild. Registry mirror reconciled (faithfulness/pii/tools declared backend-side) |
| F | Add language + model dimensions to Scope UI (no route sweep) — prove agent × time × language cube | ⬜ pending | — | |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green + pushed) · ⛔ blocked (see notes).

## Log (newest first)

- **Phase E ✅ — `9553c1b`** (twice-green + pushed). Resolved the four cards raised in the ADR
  (§Per-signal resolution) honestly — **rebuilt only what wasn't already honest**. (1) **Inbox
  (Control Cases) ventilated**: each backlog item is now a case an agent's *own* eval run failed
  → real per-agent attribution (`OperatorItem.agent_id`, sourced by iterating the fleet and
  reading each agent's own snapshot; `load_eval_snapshot(aid)` raises rather than falling back,
  so an agent with no run of its own contributes nothing — fabrication is impossible). The shared
  queue carries every agent's items, each labelled, and `?agent=` filters it; `inbox {AGENT,TIME}`
  registered in both capability tables. Verified live on :8392: 78 items across
  onboarding/recouvrement/support-client, `?agent=recouvrement` → 7 (all attributed). (2)
  **Fixtures flagged**: a shared, registry-driven `<SyntheticNotice signalId>` banner names
  incidents/curation/automations/replay_shadow as deterministic demonstration data on each card,
  reading the *same* `isSynthetic()` flag as the registry so the label can never drift. (3)
  **Traces / Release / Audit — verified already honest, kept as-is** (an explorer pass confirmed:
  Traces read live Langfuse {AGENT,TIME}; Release already splits per-agent verdicts from the org
  summary; **Audit's chain integrity is a real computed hash-chain invariant** —
  `guard.audit.verify_audit_chain`, count ventilated / integrity org-wide — so the ADR's "write
  the invariant, not a TODO" was *already* satisfied; rebuilding would have been make-work). (4)
  **Registry mirror reconciled**: the overview control-row aliases (faithfulness ⊂ scores, pii ≡
  pii_leak, tools ≡ tool_validity) are now declared backend-side too, so the frontend mirrors the
  single-source-of-truth exactly. Gate twice-green: ruff + ruff-format + mypy strict (161) + 5
  new/updated operator-item unit tests + 915 backend passed + tsc + biome (13 files) + vitest +
  perf budgets met (cold p95 **3.4 ms**, warm **1.8 ms**). The frontend badge + inbox column are
  type/lint/unit-covered (the dev server was down, so not live-rendered — the inbox *data* is
  proven via the live API). The 3 pre-existing integration failures are unchanged. **Next: Phase
  F.**
- **Phase D ✅ — `dfff8d8`** (twice-green + pushed). Made GDPR right-to-erasure (Art. 17) reach
  the spine, not just the local file (§Migration D, §Open questions #180). `LangfuseAdapter`
  gains `trace_ids_for_conversation` (session lookup) + `delete_conversation` (batch
  `DELETE /api/public/traces` — the PII-bearing rows). `erasure.purge_spine` deletes in Langfuse
  then **unconditionally evicts the snapshot cache** (a cached read must not resurrect an erased
  row), is **best-effort + honest** (unreachable Langfuse → logged, `spine_reached=False`, the
  local purge still completes and the spine leg is deferred, never faked), and `purge_telemetry`
  folds the spine count into `ErasureFootprint`. **No Prometheus per-series delete needed**:
  aggregates carry no `conversation_id` label (cardinality bounded to agent/language/model), so
  aggregate PII exposure is nil by construction. The tamper-evident **ledgers are kept** (the
  carve-out — they prove *that* an erasure happened, not the content). **jsonl is deliberately
  NOT retired** as system of record: the ADR gates retirement on "all signals flipped and baked"
  (parity), which Phase C established is not yet met (the spine holds no dimensioned history);
  the retirement *mechanism* (the `TESSERA_SPINE_SOURCE` flip) is in place, the removal waits for
  parity — retiring now would blank the cockpit, an honesty violation the ADR's own gate forbids.
  Gate twice-green: ruff + ruff-format + mypy strict (160 obs files) + 6 new erasure/delete unit
  tests + 1 safe live contract probe + perf budgets met (cold p95 **3.5 ms**, warm **1.5 ms**).
  Verified live on :8392: `DELETE /memory/{synthetic}` → **204**, reaches Langfuse, evicts the
  cache, deletes nothing real; snapshot still 200 post-evict. The 3 pre-existing integration
  failures are unchanged (fail identically on pristine HEAD). **Next: Phase E.**
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
