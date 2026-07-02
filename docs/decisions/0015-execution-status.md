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
| F | Add language + model dimensions to Scope UI (no route sweep) — prove agent × time × language cube | ✅ done | `98ddf13` | The 9 store-derived signals + traces declare the full `_CUBE` {agent,time,language,model}; readers (current/fake/spine) filter by language/model; the registry narrows unsupported dims away (a language filter can't reach conformance/audit). Adding the dimension was a Scope field + registry entry + reader filter — **no route sweep** (the snapshot serves the cube for free). Proven 3 ways: hermetic (4 tests), live wire (`snapshot?language=fr` → honoured=['language']), live data-level over REAL ci data (de:21/en:21, exhaustive partition; model honestly sparse) |
| G1 | Owned stores: Postgres `eval_gating_scores` (porteur) + owned ClickHouse `eval_online_scores` (§Amend.2 + §Corr.2b) | ✅ done | `fea97e9` | `ensure_eval_gating_schema()` at lifespan (env-schema isolated, unique re-ingest key) + `ClickHouseAdapter.ensure_schema()` (MergeTree, `PARTITION BY toYYYYMM`, native `TTL` 6 mo; best-effort at boot — monitoring telemetry never blocks boot). Live-proven: `SHOW CREATE TABLE` + `pg_indexes` match the amendments byte-for-byte; 3 live contract tests |
| G2 | Write path: gating → durable Postgres + best-effort Langfuse SDK mirror; online → direct ClickHouse insert (never Langfuse Scores ingestion) | ✅ done | `f82fb33` | `emit_score` → direct owned-CH insert (no online score mirror — the trace IS the drill-down); eval runner → per-case Postgres rows (unique-key idempotent) + SDK mirror **session-anchored on run_id** (anchorless proven rejected 400), stable UUID5 score_id, flushed at CLI exit. Live-proven both legs; suite hermetic via env kill-switches |
| G3 | Spine reads owned stores: gating → `adapters/postgres.py`, online → `adapters/clickhouse.py` (as-of-T by `scored_at`); Langfuse ceases to be a spine source | ✅ done | `f28fd08` | `SpineStoresReader.scores` → owned CH (server-side bound params; live = ring semantics for parity); new `PostgresGatingAdapter`; `gating` = first-class spine fact (protocol + 4 readers + shadow `fact=gating` + memoised context + cube-declared snapshot signal, FE mirror). Live: gating 211 rows/4 real runs; perf p95 cold 5.6ms / 3 upstream reads |
| G4 | Backfill (jsonl→CH, reports→PG) → shadow parity `{fact=scores}` → flip per-fact → owned-store erasure | ✅ done | `b9b532c` | Backfill idempotent (2nd run = 0); boot sweep; shadow bake **28/28 match scores + 28/28 gating, 0 diverge** across a live turn (dual-write 9=9); **flipped per-fact live** (`TESSERA_SPINE_SOURCE_SCORES/_GATING=spine`) — values identical, `source` badge resolved at read time; `DELETE /memory` purges the owned CH store (probe-proven). Retirement gated → G5 |
| G5 | Retire scores.jsonl: route the 17 direct `persisted_scores`/`recent_scores` call expressions through the reader seam → sustained bake → stop the jsonl write → per-fact defaults flip to `spine` → delete the dev file | ✅ done | `3f970f7` | `read_scores(at, agent, full=)` seam helper (ring / as-of / full-history semantics preserved site-by-site); suite pinned `TESSERA_SPINE_SOURCE=jsonl` (hermetic; sources contract-tested); write-stop + defaults gated on the 75-min bake (see log) |
| H | Ledger promotion (§Amend.3, SEPARATE): audit/S1 → owned append-only hash-chained Postgres; dual-write → backfill (verify) → shadow-verify → cut | ✅ done | `df1ee67` | One journal, one chain (S1 flows through `emit_audit`). `audit_ledger` append-only **enforced by trigger**; verification = chain WALK from genesis (order-independent); backfill refuses a broken file chain; dual-write FIFO + boot reconcile. Live: 649 real entries promoted, shadow-verify OK, turn → 652=652, **cut proven** (`TESSERA_LEDGER_SOURCE=postgres`, integrity over rows identical, medium visible). Flat-file retirement + direct-reader sweep = H2, after operating time |
| H2 | Retire the flat audit file: route the **18 true ledger-reader files** through `ledger_store` (each has a bespoke parse loop: system_profile ×7, etat_a_date ×5, routes/audit ×4, agent_garde_fous ×3, integrations/governance_feed/agent_synthese/routes-observability ×2, tool_validity/sources/session_detail/proofs/guardrail_catalogue/guard_explain/fleet/conformance/agent_lifecycle ×1; `audit_file.parent` anchors are NOT ledger reads and stay), implement the real `postgres` sink (synchronous durable insert + file-spool fallback; chain seed from the table head), hold `shadow_verify_ledger` over operating time, then stop the file write | 🟡 in progress | `20346a7` (step 2/5) | **Step 1/5 ✅** — 17 reader files (the "18" here miscounts its own list; re-derived from the code: every `verify_audit_chain` call + every audit-file `open`) routed through the source-aware seam (`read_ledger_entries`/`verify_active_ledger`/`ledger_available`); file mode byte-identical, no reader left on the flat file. **Step 2/5 ✅** — durable spool→Postgres sink (fsync before ack; drain in chain order; `ON CONFLICT` + whole-batch txn; boot replays the spool), **zero loss / zero dup / order preserved** through a Postgres outage — hermetic failure-path test + **live-proven on real Postgres** (ci schema, real connection failure). Remaining: chain continuity at cut (3), sustained bake (4), cut+retire (5). Compliance-sensitive — the file stays canonical-written + boot-reconciled until step 5 |

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green + pushed) · ⛔ blocked (see notes).

## Log (newest first)

- **H2 step 2/5 ✅ — `20346a7`** (twice-green + failure-path test + live proof + pushed). **The
  durable spool sink** — acceptance criterion #1 for retiring the flat file. The best-effort FIFO
  dual-write is replaced: `enqueue_ledger_entry` fsyncs each chained entry to a per-env spool
  (`audit_spool.jsonl`) BEFORE returning, then a background writer `drain_spool()`s it into the
  append-only table in chain order (one transaction: whole-batch commit or nothing; `ON CONFLICT
  (hash) DO NOTHING`). A Postgres outage leaves entries spooled and replays them on recovery —
  the boot reconcile now calls `drain_spool()` too, so a restart mid-outage loses nothing.
  **Zero loss** (fsync before ack), **zero duplicate** (txn + ON CONFLICT), **chain order
  preserved** (FIFO spool). `TESSERA_LEDGER_DUAL_WRITE=0` still disables the leg (suite hermetic).
  Proven two ways: (a) **hermetic failure-path test** (`test_ledger_spool.py`, Postgres simulated) —
  cut mid-stream → 2 audits spool, nothing lands → restore → replay in order, chain verifies,
  re-drain is a no-op; whole-batch-never-half-commits; enqueue durably spools; dual-write-off spools
  nothing. (b) **live on REAL Postgres** (throwaway `ci` schema, dropped after — append-only forbids
  DML cleanup): up→2 rows; a **real connection failure** (dead host)→2 deferred, none lost;
  restore→4 rows in order, chain verified len 4; re-drain→still 4 (no dup). Gate twice-green: 992
  unit, mypy --strict, ruff+format clean. **Next: step 3 — chain continuity at the cut (seed the
  chain head from the table, not the file, so `verify` passes THROUGH the cut boundary).**

- **H2 step 1/5 ✅ — `40628de`** (twice-green + pushed). **Every direct ledger reader now
  routes through the source-aware seam** — no reader is left on the flat file for the cut.
  New in `guard/ledger_store.py`: `read_ledger_entries(path=None)` (all entries oldest→newest
  from the ACTIVE source; file mode parses `path`/the settings file, postgres reads the promoted
  table in `seq` order and raises→honest-empty when unreachable), `verify_active_ledger(path=None)`
  (path-aware), `ledger_available(path=None)` (source-aware health). **17 reader files** rerouted
  (guard-decision aggregation, chain integrity, handoff/routing/lifecycle history, as-of-T scans,
  System-profile health/count, the two API routes incl. the stat-keyed cache which is bypassed in
  postgres mode) — the note's "18" miscounts its own enumeration; the real set was re-derived from
  the code (every `verify_audit_chain` call + every audit-file `open`; `audit_file.parent` sibling-
  state anchors and `bundles.jsonl`/`scores.jsonl` are NOT ledger reads and stay; `spine/current.py`
  was already on the seam from H). **File mode is byte-identical**, so the whole sweep is a
  behaviour-preserving refactor: 988 unit twice-green, mypy --strict 247, ruff+format clean, 10
  new hermetic seam tests (file==raw-parse; postgres reads the table ignoring the path). Backend-
  only diff (tsc/biome unaffected). Isolated from a parallel codex frontend WIP (recouvrement logo)
  via targeted staging (19 files, never `git add -A`). **Next: step 2 — durable synchronous sink +
  spool fallback (zero-loss on a Postgres blip), with the dedicated failure-path test.**

- **G5 ✅ — `3f970f7`** (twice-green + pushed) — **scores.jsonl retired, on a genuinely met gate.**
  The bake (V3): **77 minutes** of per-fact shadow over REAL traffic (12-scope snapshot sweeps every
  60s + a real `/chat` turn every ~4 min; 15 checkpoints in `/tmp/tessera-bake.log`):
  `tessera_spine_shadow_divergence_total` → **scores 900/900 match, gating 900/900 match, ZERO
  diverge/unavailable over the whole window**; dual-write lockstep held throughout (jsonl 67 = CH 67
  at window end; ledger 889=889, both chains verified). Then the activation: `read_scores(at, agent,
  full=)` seam helper (ring / as-of / full-history semantics preserved site-by-site) now serves the
  **17 former direct call expressions**; per-fact defaults flip to `spine` (explicit env = the
  operator escape hatch; the unit suite pins the legacy source and stays hermetic — 978 unit tests
  twice-green); `emit_score` no longer writes the file (durable home = the owned CH table; a
  pre-retirement file stays READ-only: degraded reader, backfill source, erasure surface); the dev
  file was moved aside after the final 67=67 parity. **Live-proven on code defaults (no spine
  env)**: scores/slo/gating serve `source=spine`; the live view returns **67 rows from ClickHouse
  after a restart** (the old ring came back empty — retirement made live views restart-proof);
  as-of 16:15 still exactly 6 rows; gating 211/4; `score-series` n=22 with populated buckets through
  the rerouted full-history read; audit integrity over the Postgres rows (889, chain valid,
  medium=postgres).
- **V2 (ledger consolidation RATIFIED, ADR amended — §Correction 3b) ✅** (docs, 2026-07-02). The H
  implementation consolidated the "two ledgers" into one — a deviation from the ADR's prose that is
  now examined and **ratified, docs aligned to code**. Facts (live table): ONE chain, families
  `tessera.guard.audit` (726 `user_input` + tool targets + **9 governance `memory.*` events**,
  emitted by `governance.audit_memory` through the same `emit_audit`) + `tessera.agent.*`; **no
  second journal file exists** in the state dir — the "S1 journal" was always a logical family
  within `audit.log`. Soundness: (1) one chain = **total order across families** (consent-before-
  action is a provable chain fact; two ledgers would have no provable inter-order) + one head to
  seal; (2) **no distinction lost** — families separable by closed vocabularies (`type`; within
  guard.audit, `target ∈ {memory.write,read,forget}` + `policy_rule "*.governance"`, `Literal`-typed
  at the single emitter); (3) same retention/access class (DORA ICT evidence + GDPR Art. 7(1)/17
  accountability — "keep, never mutate", same RBAC); (4) the named duty: pure-guard consumers
  exclude `memory.*` targets, union views (audit_count) present as the whole S1 journal. ADR
  edited: §Amendment 3 point 4 + new §Correction 3b + §Non-negotiable carve-out note + the two
  §Physical-backends rows + the home map + the header status line.
- **V1 (as-of-T / SR-01) ✅ — `1b57e5a`** (twice-green + pushed). The à-un-instant / Historique
  contract is now PROVEN on the owned stores, not assumed from live mode. **Determinism hardening
  first** (fix-the-adapter-before-trusting-live): both reads impose a **total order** — ClickHouse
  `ORDER BY (scored_at, metric, trace_id, conversation_id)` (+ DESC twin for the live newest-200
  cut, so boundary ties can't float with part-merge order), Postgres gating `(scored_at, id)`.
  **Hermetic**: total-order clauses unit-locked; the seam contract "a read at past T ignores rows
  landing after T" locked over the fake. **Contracts** (live stores, self-cleaning, 3× green):
  frozen-and-reproducible despite later writes on BOTH stores (CH view at T unchanged after a
  post-T insert; the porteur's view at T unchanged after a LATER release run lands). **Live on real
  data**: `snapshot?at=` serves the frozen view from the owned stores (T=02T00:00 → exactly the 3
  July-1 rows / slo n=1; T=16:15 → 6 rows / slo n=2; gating 211/4; `honoured=['time']`,
  `source=spine`; immutable-past cache hit = identical body hash); **fresh-process
  reproducibility** — two separate processes, same (scope,T) ⇒ identical SHAs (CH `e8ce4c9d…`, PG
  `74af9dcf…` over 92 rows/3 runs at a run-splitting T; onboarding×fr×T → 24); **parity AT T at SET
  level** legacy↔owned (scores 6=6/3=3 metric-equal; gating 92=92 and 62=62 with equal
  (run,case,language) sets — 62 shows per-case `scored_at` precision splitting an in-flight run
  identically on both sides). Note: as-of-T on the ONLINE store is reproducible **within the
  6-month TTL retention** by design — an instant older than retention loses its rows on both
  mediums equally (monitoring telemetry; the opposable gating porteur has no TTL). **Bake started**
  (V3): :8392 relaunched per-fact SHADOW (scores+gating) + ledger=postgres, background traffic loop
  (scoped sweeps every 60s + a real turn every ~4 min, counters checkpointed to
  `/tmp/tessera-bake.log`) — G5/H2 stay gated on the sustained window.
- **Phase H ✅ — `df1ee67`** (twice-green + pushed). **The audit/S1 ledger is promoted** (§Amendment 3).
  One journal, one chain: the S1 governance events already flow through `emit_audit`, so promoting
  `audit.log` promotes both ledgers the amendment names. (1) **`guard/ledger_store.py`**:
  `audit_ledger (seq, occurred_at, agent_id, payload jsonb, prev_hash, hash)`, append-only
  **enforced by a `BEFORE UPDATE OR DELETE` trigger that raises** (mutation impossible at the
  store), unique `hash` = idempotence key, `occurred_at`/`seq` indexed for as-of-T (TE-01).
  (2) **Verification WALKS the chain** from the genesis hash via `prev_hash`, recomputing every
  canonical payload — order-independent (a healed dual-write gap lands late without weakening the
  proof); fork / orphan / gap / edited payload all break the walk. (3) **Dual-write**:
  `_append_to_chain` enqueues each chained entry to one FIFO writer thread (file sink only; chain
  order preserved); a missed insert self-heals at the boot reconcile. (4) **Verified backfill**:
  refuses to import a file whose chain does not verify (recompute+verify on import); idempotent;
  runs at every boot best-effort. (5) **The cut**: `TESSERA_LEDGER_SOURCE=postgres` repoints the
  spine's ledger read (unreachable → `SpineUnavailableError`, honest-empty) and `audit_integrity`
  verifies over the OWNED ROWS, reporting its active `medium` — gated on `shadow_verify_ledger`
  (both mediums verify AND cover the same entries). **Live-proven on the real dev ledger**: boot
  promoted **649 verified entries** → shadow-verify OK (649=649); a real guarded turn dual-wrote →
  **652=652**, chains intact; the cut serves `chain_valid=True, length 653, medium=postgres` and
  `audit_count 649` — byte-identical to file-mode. **Debugging honesty**: the contract flake was
  NOT the store — probes dated Jan-2026 sat exactly on the 6-month TTL edge (today is 07-02!) and
  background TTL merges erased them mid-test (`written_rows=2` then gone — proven via
  `system.query_log`); probes now sit inside retention, the poll workaround was removed, and the
  suite held **10/10 consecutive green**. Gate twice-green: ruff + format + mypy strict (247) +
  **974 unit** (14 new) + 16 live contracts + tsc. Hermeticity: `TESSERA_LEDGER_DUAL_WRITE=0`
  under tests. **Remaining tail = H2** (flat-file retirement + the ~10 direct
  `verify_audit_chain`/`audit_file` readers), gated on shadow-verify holding over operating time —
  the file stays canonical-written meanwhile. Hica seal remains enrichment, never the store.
- **Phase G4 ✅ — `b9b532c`** (twice-green + pushed). **The migration executed**: backfill → shadow
  bake → per-fact flip → owned-store erasure. (1) **Backfill, idempotent**:
  `scripts/backfill_owned_scores.py` fills the owned ClickHouse table from `scores.jsonl` by
  **difference** (dedup key `(scored_at@ms, metric, conversation_id, trace_id)` — computable
  identically on both sides) and sweeps the report archive into the porteur via
  `ingest_gating_reports()`; run live: online 6→**3 inserted** (3 were live-written by G2), gating
  **211 rows / 4 real release runs** + **211 Langfuse mirror scores** materialised; second run =
  **0 + 0** (proof). The same sweep reconciles at every boot (best-effort, logged, never blocks).
  (2) **Shadow bake over real traffic**: `TESSERA_SPINE_SOURCE=shadow`, 28 scoped snapshot computes
  (org × 3 agents × 4 languages) spanning a **live `/chat` turn mid-bake** (dual-write proven:
  jsonl 9 = CH 9): `tessera_spine_shadow_divergence_total` → **scores 28/28 match, gating 28/28
  match, 0 diverge**; bundles 20 match / 8 diverge (the declared-lossy fact — stays jsonl forever).
  (3) **Per-fact flip, live**: new `TESSERA_SPINE_SOURCE_SCORES` / `_GATING` overrides +
  `FactRouter` (bundles/audit have NO override — lossy-by-design / carve-out); relaunched :8392
  flipped → **values identical** (slo byte-equal, scores 9 rows, gating 211/4, `onboarding×fr` = 24
  with honoured=['agent','language']); the per-signal **`source` badge is resolved at read time**
  from the fact's active source (`capability.fact`), so the UI shows `spine` for
  scores/slo/trend/funnel/faithfulness/gating and `jsonl` for the bundles-backed signals — a flip
  can never be silent. (4) **Erasure reaches the owned store**: `ClickHouseAdapter.
  delete_conversation` (count-then-delete, values bound server-side) behind `purge_owned_scores`
  (deferred-never-faked, folded into `ErasureFootprint`); proven live — synthetic probe row +
  `DELETE /memory/{id}` → 204, probe purged, the 9 real rows intact; the gating porteur carries no
  `conversation_id` by construction (release runs are not subject-linked). Gate twice-green: ruff +
  format + mypy strict (246) + **960 unit** (15 new) + 7 live contracts ×2 + tsc. **jsonl
  retirement stays gated by the ADR's own rule** ("all signals flipped AND baked"): the 19 direct
  `persisted_scores`/`recent_scores` call sites (routes/observability ×12, proofs ×3, compliance
  ×3, availability, reliability, improvement, agent_console) still read the file and the bake
  window is minutes old → enumerated as **G5**, never silently dropped. Flip env vars must be in
  the backend's PROCESS environment (the factory reads `os.environ`, not `.env.local`). **Next: H
  (ledger promotion) — G5 rides a longer bake.**
- **Phase G3 ✅ — `f28fd08`** (twice-green + pushed). The spine now reads the **owned stores**;
  **Langfuse ceased to be a spine source** (§Amendment 1). (1) `SpineStoresReader.scores` reads the
  owned ClickHouse table: `ClickHouseAdapter.online_scores(scope)` pushes as-of-T + agent/language/
  model **server-side as bound `param_` placeholders** (values never enter SQL text); the live
  (no-`at`) read deliberately mirrors the jsonl ring's semantics — last 200 rows org-wide, THEN
  dimension filters — because the G4 parity gate compares the two readers count-for-count; rows map
  back to the exact jsonl shape (`""`→`None`, `sampled`→bool, ISO reconstructed, ms truncated never
  padded). (2) New `adapters/postgres.py` (`PostgresGatingAdapter`): the gating porteur read —
  short-lived sync connection (the readers are sync), env-schema `search_path` (ADR 0014), bounded
  `statement_timeout` 800ms, `psycopg.Error` → `SpineUnavailableError` (honest-empty). (3) **gating
  is a first-class spine fact**: `SpineReader.gating_scores` on the protocol; `CurrentStoresReader`
  reads the env-aware report-file archive through the same pure report→rows mapping as the write
  path (mtime-keyed cache; `latest_<agent>.json` deduped against its timestamped twin by run_id);
  fake seeded; `ShadowReader` records `tessera_spine_shadow_divergence_total{fact="gating"}`;
  `SnapshotContext` memoises it (4 shared reads); a compact `gating` snapshot signal (run summaries,
  never the full socle dump) declared over the full cube in `capabilities.py` AND the frontend
  `lib/signal-registry.ts` mirror. Contract-test flake fixed honestly: probe identities are
  uuid-suffixed because ClickHouse lightweight-delete visibility is async across back-to-back runs.
  Gate twice-green: ruff + format + mypy strict (246) + **945 unit** (8 new) + **7 live contracts**
  (scoped CH read round-trip incl. as-of exclusion + language compose; PG porteur read incl.
  as-of/agent/language; 3× consecutive green) + tsc + biome + 10 registry vitest. **Live-proven on
  :8392**: `snapshot?signals=gating` → **211 rows / 4 real release runs** (latest `support-client`
  59/119 — the real 18/06 run), `agent=onboarding&language=fr` → 24 rows/1 run with
  `honoured=['agent','language']`; `SpineStoresReader` serves the 3 real ClickHouse rows (agent
  slice included) and the honestly-empty Postgres porteur (0 until the G4 backfill); **perf budgets
  met**: cold p95 5.6ms (<300), warm 3.9ms (<150), **3 upstream reads for 10 signals** (≤4). The
  owned CH table ends the phase holding exactly the 3 real judge rows (all probes purged). **Next:
  G4.**
- **Phase G2 ✅ — `f82fb33`** (twice-green + pushed). Both owned write legs are live, exactly per the
  amendments. **Online** (§Correction 2b): `emit_score` direct-inserts each verdict row into
  `tessera.eval_online_scores` (`clickhouse_scores.py`: JSONEachRow, daemon thread off the already-cold
  path, lazy ensure, unattributed dims → `""` never fabricated, rows without an instant skipped) — the
  Langfuse **online** score mirror is REMOVED (the trace in Langfuse/Phoenix + `trace_id` on the owned
  row is the drill-down; Langfuse's fragile Scores ingestion is never used). jsonl stays system of
  record until G4 parity. **Gating** (§Amendment 2): the eval runner now records every release run
  durably — `gating_rows_from_report` (pure; agent-less catalogue probes yield NO rows — no fabricated
  attribution; `run_id = run_at + agent` so archive and `latest_<agent>.json` dedup), `record_gating_rows`
  (`ON CONFLICT DO NOTHING` on the unique key → idempotent re-ingest, the G4 backfill primitive), and a
  best-effort CLI hook that never fails a run. **Mirror**: `langfuse_scores.py` rewritten around the
  official SDK ("voie 1") — **empirically settled the anchor**: anchorless scores are rejected (400,
  proven live); **session-anchored scores materialise + list via the v2 API** (proven live, probe
  deleted) → gating scores mirror session-anchored on the run id, stable UUID5 `score_id` (dedup),
  flushed at CLI exit; the hand-rolled ingestion POST is deleted. **Hermeticity**: both legs default OFF
  under tests (`TESSERA_CLICKHOUSE_SCORES=0`, `TESSERA_LANGFUSE_SCORES=0` in conftest), opt-in per-test
  over stubs; a real import cycle (scores → clickhouse_scores → spine.adapters → current → scores) was
  broken by lazy adapter imports. Gate twice-green: ruff + format + mypy strict (245) + **937 unit**
  (16 new) + 5 live contract (insert round-trip self-cleaning w/ bounded lightweight-delete poll;
  idempotent gating re-record self-cleaning) + tsc clean. **Live-proven e2e**: one real `/chat` turn on
  :8392 → 3 judge rows **byte-equal jsonl↔owned ClickHouse** (agent/language/model/sampled/ms) while
  Langfuse scores stay **0**; one real 1-case `onboarding` eval run (scratch-redirected archive) →
  Postgres row (`catalogue_version 25-92b10927`, real) + session-anchored mirror score in Langfuse v2;
  re-record → **0** inserted; probes cleaned from every store. **Next: G3.**
- **Phase G1 ✅ — `fea97e9`** (twice-green + pushed). Built the two owned stores exactly per the
  amendments. **Postgres `eval_gating_scores`** (§Amendment 2, Nature 1 — the porteur):
  `ensure_eval_gating_schema()` at API lifespan, plain indexed table (no partition machinery),
  unique `(run_id, case_id, language, metric)` re-ingest key, materialised in the active env schema
  (ADR 0014 anti-fallthrough). **Owned ClickHouse `tessera.eval_online_scores`** (§Correction 2b —
  the monitoring firehose): `ClickHouseAdapter` (urllib HTTP, header auth, unreachable →
  `SpineUnavailableError`), `ensure_schema()` creates the owned database + `MergeTree` table with
  `ORDER BY (agent_id, metric, scored_at)`, **native** `PARTITION BY toYYYYMM(scored_at)` + `TTL`
  6 months — always direct DDL, **never Langfuse's Scores ingestion**; boot-time bootstrap is
  best-effort (sampled telemetry never blocks boot; deferred + logged when the stack is down, the
  write path re-ensures lazily). Gate twice-green: ruff + ruff-format (repo baseline 30 pre-existing,
  none mine) + mypy strict (244) + 921 unit (9 new locking the DDL to the amendments) + tsc clean +
  biome baseline untouched (backend-only diff). **Live-proven**: 3 integration contract tests pass
  against the real backends; `SHOW CREATE TABLE tessera.eval_online_scores` shows
  MergeTree + `toYYYYMM(scored_at)` + `TTL … toIntervalMonth(6)`; `pg_indexes` in `tessera_local`
  (and `tessera_ci`) shows `eval_gating_uq (run_id, case_id, language, metric)`. **Next: G2.**
- **📐 AMENDMENT 3 (docs only) + REVISED IMPLEMENTATION ROADMAP — the audit/proof ledger is homed; the
  governing rule names the whole model.** (2026-07-02, docs only, no code, not pushed. See ADR §Amendment 3.)
  Governing rule across Amend.1–3: **own what gates or proves; best-effort what you sample or observe** (a
  fact you *sample* is, by construction, not load-bearing). Homes: audit/S1 ledger + gating scores → **owned
  Postgres**; online sampled scores → partitioned Postgres (columnar at scale); aggregates → Prometheus;
  traces → Langfuse/Phoenix best-effort. The ADR body's Migration §A→F is annotated superseded for
  scores+ledger; the canonical tree gains `adapters/postgres.py`.

  **A→F are ✅ done, but they built the pre-amendment shape (spine reads Langfuse for score detail; jsonl
  still system-of-record). The amendments require the following NEW `pending` phases, which SUPERSEDE the
  earlier "voie 1 = rewrite `langfuse_scores.py` as the Langfuse-native SOURCE" plan — Langfuse is now a
  best-effort MIRROR, Postgres is the source:**
  - **G1 — Stores.** Postgres via idempotent `ensure_*_schema` (not Alembic): `eval_gating_scores` (plain
    indexed — the porteur). **Owned ClickHouse table `eval_online_scores`** (direct insert; `MergeTree` +
    native `PARTITION BY toYYYYMM(scored_at)` + `TTL` — no hand-rolled retention). DDL = ADR §Amend.2 +
    **§Correction 2b**. **Never via Langfuse's Scores ingestion.**
  - **G2 — Write path.** `emit_score`: **gating** → durable Postgres insert **+ best-effort Langfuse Score
    mirror via the SDK** ("voie 1" `create_score`, drill-down UX); **online** → **direct ClickHouse insert**
    (no Langfuse Score mirror — the trace already lives in Langfuse/Phoenix via `trace_id`). Online path
    already off the hot path (`_spawn_background`). jsonl kept until parity.
  - **G3 — Spine reads owned stores.** Repoint `SpineStoresReader.scores`: **gating → `postgres.py`**,
    **online → `clickhouse.py`** (both as-of-T by `scored_at`). Langfuse ceases to be a spine source.
  - **G4 — Backfill → shadow → flip → retire jsonl.** Backfill `scores.jsonl`→Postgres (idempotent);
    `TESSERA_SPINE_SOURCE=shadow` until `tessera_spine_shadow_divergence_total{fact=scores}=match` over a
    window → flip per-signal → **retire jsonl** (Phase D's gate, finally met, from Postgres).
  - **H — Ledger promotion (§Amend.3 — SEPARATE, compliance-sensitive, run AFTER G, never mixed).** Promote
    `audit.log` + S1 journal → owned **append-only hash-chained Postgres** (`seq, occurred_at, agent_id,
    payload, prev_hash, hash`), append-only enforced, `verify_audit_chain` over rows, dual-write → backfill
    (recompute+verify chain on import) → shadow-verify (chain matches file AND table) → cut reads → retire the
    flat file. Hica seal = best-effort enrichment. **Never flip a ledger read before its chain verifies.**

  **Preconditions before launching G/H (ADR §Precondition + operator rules):** (1) **clean tree / sole-writer**
  — currently ~16 unpushed local commits + uncommitted ADR docs edits + possible codex WIP → commit the ADR
  docs (targeted, *these files only*, never `git add -A`) and confirm no parallel writer; (2) **push decision**
  — the ADR protocol pushes per phase, the operator's standing rule is **NE POUSSE PAS** → resolve (local-only
  override, or push the branch) before the run reaches a commit.

- **📐 AMENDMENT 2 (docs only) — split score detail by NATURE + VOLUME (gating socle vs online
  monitoring). Roadmap (a) becomes two tables.** (2026-07-02, docs only, no code, not pushed. See
  ADR §Amendment 2, grounded in `eval/online.py`: `online_eval_sample_rate` default **0.1**, **3
  metrics/judged turn**, catalogue **64 cases**.) §Amendment 1's single `eval_scores` table
  conflated two facts:
  - **Nature 1 — GATING socle** (offline harness, `eval/reports/*.json`, `gate_*` fields): bounded
    (cases×langs×metrics×runs, grows per *release*), the **opposable** fact → owned Postgres
    **`eval_gating_scores`** (plain indexed table, **no partition/retention machinery**). Read by
    release/opposability.
  - **Nature 2 — ONLINE monitoring** (per-turn `evaluate_turn`, today `scores.jsonl`): volume =
    **traffic × sample_rate × 3 (+ flagged)**, traffic-driven, **not the gating fact** → Postgres
    **`eval_online_scores`** **PARTITIONED monthly on `scored_at` + retention policy + index NOW**;
    **columnar (ClickHouse) at scale** (trigger: > ~hundreds of M rows/yr ≈ > ~1 M turns/day @ 0.1×3).
    `SpineStoresReader.scores` reads THIS table; Langfuse mirrors THIS nature only.
  - Prometheus aggregates (SLO/trend/quantile) = both natures, unchanged. DDL for both tables is in
    ADR §Amendment 2.

  **Roadmap delta vs the Amendment-1 entry below:** step **(a)** is now **two tables** —
  `eval_gating_scores` (Nature 1, from `eval/reports`) + `eval_online_scores` (Nature 2, partitioned,
  from `scores.jsonl`). Steps (b) spine→`eval_online_scores`; (c) outbox→Langfuse mirrors Nature 2
  (voie-1 SDK); (d) backfill jsonl→`eval_online_scores` **and** `eval/reports`→`eval_gating_scores`;
  (e)-(g) unchanged (shadow parity is now jsonl↔`eval_online_scores`). Nothing flipped;
  `TESSERA_SPINE_SOURCE` still `jsonl`.
- **📐 AMENDMENT 1 (docs only) — eval-score DETAIL home = owned Postgres table; Langfuse demoted to
  a best-effort mirror. Roadmap revised.** (2026-07-02, docs only, no code, not pushed. See ADR
  §Amendment 1.) The voie-1 proof (below) validated *delivery* (the SDK materialises a Langfuse
  score), **not the choice of durable home**. A score **gates a release**: its durability + read-path
  must not depend on a third party. So the authoritative home of score detail becomes an **owned,
  transactional Postgres table**, not Langfuse. Langfuse stays as a **best-effort mirror** (drill-down
  UX) — and the voie-1 SDK fix is **repurposed as the SYNC mechanism (outbox), not the authoritative
  write.** Prometheus aggregates / Phoenix / audit-ledger + bundles carve-outs = unchanged; jsonl's
  durable-write role is **assumed by Postgres** (not "nothing", not Langfuse-only).

  **REVISED ROADMAP (replaces the "emit to Langfuse as source → retire jsonl" plan in the voie-1
  entry below):**
  - **(a)** Postgres `eval_scores` table (cols metric/score/agent_id/language/model/scored_at/
    trace_id/judge_model; index `(agent_id, metric, scored_at, trace_id)`) + a **durable,
    transactional write adapter** (replaces the `scores.jsonl` append; the online-eval scoring path
    writes here, `eval/scores.py`).
  - **(b)** `SpineStoresReader.scores` → **reads Postgres** (as-of-T by `scored_at`), not Langfuse.
    Langfuse ceases to be a spine upstream.
  - **(c)** **Outbox sync → Langfuse via the SDK** (stable `score_id` = dedup; reconcile drops
    continuously). **← the voie-1 SDK fix serves HERE**, as best-effort mirror, non-authoritative.
  - **(d)** Backfill `persisted_scores()` (jsonl) → **Postgres** (then the mirror syncs it to Langfuse).
  - **(e)** `TESSERA_SPINE_SOURCE=shadow` until `tessera_spine_shadow_divergence_total{fact=scores,
    result=match}` holds over a window.
  - **(f)** Flip spine `scores` source → **Postgres** per-signal.
  - **(g)** Retire the `scores.jsonl` (its role now owned by Postgres). audit ledger + bundles stay
    local carve-outs.

  Note: the parity `fact=scores` is now **jsonl↔Postgres** during migration (the owned store), with
  Langfuse verified separately as a mirror. Nothing flipped; `TESSERA_SPINE_SOURCE` still `jsonl`.
- **✅ DELIVERY FIX PROVEN (voie 1) — the Langfuse SDK materialises scores; the hand-rolled POST
  does not. Ready to implement.** (2026-07-02, proof only, no code change yet, probe score deleted →
  CH clean.) The Phase-D flip was blocked because Langfuse `default.scores` = 0. **Root cause
  isolated:** the raw urllib POST in `langfuse_scores.py` to `/api/public/ingestion` returns
  **201 but never materialises** (no MinIO `events/` blob; silent drop) — while the **official
  Langfuse SDK v4.7.1** (already in `.venv`) `create_score(...)+flush()` **DID materialise**:
  ClickHouse `default.scores` 0→1, Langfuse `/api/public/scores` 0→1, and — end to end —
  `SpineStoresReader.scores(Scope(agent_id="support-client"))` → **1** and `Scope(language="fr")`
  → **1** (the score carried `metadata={agent_id,language,model}`; the Phase-C reader works
  unchanged — only the data was missing). Neither Phoenix nor Langfuse observations passively
  capture the score (`tessera.eval.*` span attr does NOT reach either trace store — online-eval
  runs off the exported span), so the emit must be *active* → the SDK is the premium, ADR-faithful
  path (Langfuse=ClickHouse detail store; Prometheus aggregates already wired: rules
  `tessera:eval_score:mean5m/mean1h` loaded but ~0 samples on low traffic; jsonl to be retired).

  **PROVEN emit (copy-paste):**
  `from langfuse import Langfuse; lf=Langfuse(host="http://localhost:3900",
  public_key="pk-lf-claude-public", secret_key="sk-lf-claude-secret");
  lf.create_score(name="faithfulness", value=0.86, trace_id=<real trace id>, data_type="NUMERIC",
  comment=<judge_model>, metadata={"agent_id":..., "language":..., "model":...}); lf.flush()`.
  Verify: `docker exec tessera-claude-clickhouse clickhouse-client --user clickhouse --password
  clickhouse --query "SELECT count() FROM default.scores"`. A real trace id:
  `GET :3900/api/public/traces?limit=1` (Basic auth pk/sk). Delete a probe score:
  `DELETE :3900/api/public/scores/<id>`.

  **NEXT — the flip roadmap (resume here after /clear):**
  1. **Emit fix (step 1, committable now):** rewrite `src/tessera/observability/langfuse_scores.py`
     to emit via the SDK (module singleton `Langfuse(...)`; `emit_langfuse_score` → `create_score`),
     KEEPING: `_enabled()` gate (`TESSERA_LANGFUSE_SCORES`), `trace_id is None` no-op, best-effort
     non-blocking (SDK batches on its own bg thread — the daemon-thread wrapper can go), offline
     no-op so `tests/unit` stay hermetic (keep a pure/mocked seam; the old `build_score_event` unit
     test needs updating). Caller is `eval/scores.py:232` (unchanged). Then live-prove: a real
     `/chat` turn on `:8392` materialises its score in CH. Gate 2× green.
  2. **Backfill:** idempotent script replaying `persisted_scores()` (jsonl rows carry
     scored_at/metric/score/language/agent_id/model/trace_id/judge_model) → Langfuse via the SDK
     with a **stable score_id** (dedup) — fills the forward-only gap, the flip's prerequisite.
  3. **Shadow bake:** `TESSERA_SPINE_SOURCE=shadow` until
     `tessera_spine_shadow_divergence_total{fact=scores,result=match}` holds over a window (needs
     time + traffic — not instant).
  4. **Flip + retire jsonl:** `=spine` per-signal, then delete the convenience jsonl (audit +
     bundles stay local by design — bundles are lossy-from-traces, audit is the ledger carve-out).

  **Stack anchors:** obs = `docker-compose.obs.claude.yml`, containers `tessera-claude-*`
  (Langfuse :3900, Phoenix :16006, Prometheus :19090, ClickHouse :18123 user/pw `clickhouse`,
  Redis pw `claude-redis`, MinIO). Backend dev :8392 (see restart cmd in CLAUDE session prompt),
  front :3097. **Push coupling:** `git push` would also push the 6 unpushed cockpit-sweep commits
  (proofs `1339157`, curation `9177182`, assistant `665ed46`, automations `2a51d1a`, + 2 docs) and
  the diagnosis doc `7791ad7` — decide branch-push vs keep-local before pushing the emit fix.
- **🔎 Parity probe for the jsonl→spine flip (Phase D gate) — flip NOT safe; scores never reach
  ClickHouse.** (2026-07-02, diagnosis only, no code change, nothing flipped.) Asked to flip to the
  spine, I measured parity with the real readers instead of flipping blind. **Authoritative
  result** (`TESSERA_ENVIRONMENT=local`): `CurrentStoresReader` vs `SpineStoresReader` —
  `scores` jsonl=3 / spine=**0** → DIVERGE; `bundles` jsonl=1 / spine=100 (lossy trace-shells,
  no grounding/lineage — lossy *by design*, never a real flip); `audit` = local carve-out (never
  flips). So the only flippable fact is `scores`, and the spine holds **zero**. Flipping
  `TESSERA_SPINE_SOURCE=spine` now would blank every score-derived signal (SLO/quality/trend/
  funnel/faithfulness) — the exact regression this gate forbids.
  **Root cause (infra, not Tessera code):** ClickHouse `default.scores` = **0** rows (traces
  173 684, observations 264 536 — the OTel path works). The Tessera mirror emits correctly: POST
  `/api/public/ingestion` `score-create` → HTTP **207 `{status:201, errors:[]}`** (accepted), and
  the jsonl scores carry a valid `trace_id`. But the score never materialises in ClickHouse: the
  public-ingestion score path produces **no MinIO `events/` blob** (all 200 252 blobs are
  `events/otel/…`), and the `ingestion-queue:failed` set holds only **old (06-09) stalled
  `trace-create` jobs** — unrelated. **Restarting `langfuse-worker` did NOT fix it** (clean reboot,
  all executors incl. `ingestion-queue` re-registered, ClickhouseWriter restarted; fresh
  `score-create` still → CH scores 0, no error logged). The eval score *values* are also not
  cleanly queryable from observations (`tessera.eval.*` not present as observation metadata keys).
  **Verdict:** the flip is blocked by Langfuse-v3 self-hosted score ingestion (a third-party infra
  issue a worker restart/config tweak does not resolve), **and even once fixed the flip still needs
  a historical backfill + a shadow-mode bake to parity** — not a one-shot. **Recommendation:** keep
  `TESSERA_SPINE_SOURCE=jsonl` (jsonl stays the system of record, per this ADR's own gate — audit +
  bundles are local by design anyway); to actually migrate scores later, either (a) fix Langfuse
  v3 public score ingestion, or (b) re-point `SpineStoresReader.scores` at a source that
  materialises (a spine-adapter code change), then run `=shadow` until
  `tessera_spine_shadow_divergence_total{fact=scores,result=match}` holds over a window, then flip
  per-signal. Nothing was flipped; `TESSERA_SPINE_SOURCE` is unchanged (default `jsonl`).
- **🎉 ADR 0015 COMPLETE — Phases A→F all done, twice-green + pushed** (`697106f` · `828016f` ·
  `f6723f5` · `dfff8d8` · `9553c1b` · `98ddf13`). The runtime telemetry spine + first-class Scope
  is in place end to end: capability-declared signal registry (the "filter shown but ignored" bug
  class is *unrepresentable*), batched cached snapshot read model (cold p95 ~4 ms, 2 upstream
  reads for 9 signals), complete dimensioning + recording rules + honest per-dimension cutoff,
  real Langfuse/Prometheus/ledger read adapters behind a shadow-run seam, GDPR erasure that
  reaches the spine + evicts the cache, the four cards resolved honestly (inbox ventilated;
  fixtures flagged; traces/release/audit verified already-honest), and the agent × time × language
  cube proven. The tamper-evident ledgers stayed local (the carve-out); jsonl stays the system of
  record until parity bakes (the ADR's own gate, not yet met). Throughout: never fabricated a
  per-agent/per-language value, never marked a fixture real, never showed a filter a signal can't
  honour. Three pre-existing integration failures (firewall auth-seed + two non-hermetic memory
  Postgres tests) were proven to fail identically on pristine HEAD and are out of scope.
- **Phase F ✅ — `98ddf13`** (twice-green + pushed). Generalised Scope to language + model and
  proved the payoff (§Migration F): adding a dimension is a field on Scope (there since Phase A) +
  a registry declaration + a reader filter — **no route sweep**. The 9 store-derived hot-path
  signals + traces now declare the full `_CUBE` {agent, time, language, model}; `current.py` /
  `fake.py` / `spine.py` filter rows by `scope.language` / `scope.model` (agent + as-of-T were
  already pushed into the store read, so one shared read still serves every language slice — the
  snapshot's upstream-read count is unchanged at 2). The registry narrows the request scope to a
  signal's declared dims before the read, so a language filter can never silently reach a signal
  that can't honour it (conformance / audit / refusal report language *ignored*). Proven three
  ways end to end: (1) **hermetic** — `test_spine_cube.py` (4 tests): fr slice ≠ de slice,
  agent×language composes, the scores report honours language, `narrow_to` drops language for a
  non-cube signal; (2) **live wire** — `GET /observability/snapshot?language=fr` echoes
  `scope.language=fr` and the scores signal reports `honoured=['language'], ignored=[]`; (3)
  **live data-level over REAL data** — the durable ci score store (42 real rows) partitions
  exactly through the reader: `language=de` → 21, `language=en` → 21, de+en == 42 (exhaustive);
  `model=llama3.2:3b` → 0 (pre-stamping rows carry `model=None` — the honest forward-only "data
  available since" contract, never a fabricated value). Per the ADR, "add language + model to the
  Scope UI" *is* the Scope field + registry entries (both done); the affordance renders from
  `signalSupports(id, 'language')`, and the cube is live + honoured on the snapshot today — a
  visible per-page selector rides that page's snapshot adoption rather than the route sweep this
  design eliminates. Gate: ruff/format/mypy strict (160) + 4 new cube tests + 919 backend passed +
  tsc/biome/vitest (10) + perf budgets met. **The autonomous A→F run is complete.**
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
