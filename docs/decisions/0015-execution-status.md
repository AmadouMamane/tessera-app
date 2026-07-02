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

Status legend: ⬜ pending · 🟡 in progress · ✅ done (twice-green + pushed) · ⛔ blocked (see notes).

## Log (newest first)

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
  - **G1 — Postgres score tables.** `ensure_eval_scores_schema()` at lifespan (Tessera builds schema via
    idempotent `ensure_*_schema`, not Alembic): `eval_gating_scores` (plain indexed) + `eval_online_scores`
    (monthly `PARTITION BY RANGE(scored_at)` + retention DROP). DDL = ADR §Amend.2.
  - **G2 — Write path (outbox).** `emit_score` writes **durably to Postgres** (the truth), then **mirrors to
    Langfuse via the SDK** (the "voie 1" `create_score`, repurposed as best-effort sync; stable `score_id`
    dedup). Online path already off the hot path (`_spawn_background`). jsonl kept until parity.
  - **G3 — Spine reads Postgres.** Repoint `SpineStoresReader.scores` from Langfuse → the new `postgres.py`
    adapter (as-of-T by `scored_at`). Langfuse ceases to be a spine source.
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
