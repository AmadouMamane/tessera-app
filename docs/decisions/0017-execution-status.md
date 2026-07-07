# ADR 0017 + 0018 — execution status

Single source of truth for **where the 0017/0018 implementation is**. The executing session
updates this file after every step. A resuming session reads this first, then continues the
**next `pending` step** — no re-work. Same protocol as `0015-execution-status.md`:

- **Protocol**: implement → full gate **twice green** (`ruff check` + `ruff format --check` +
  `mypy` + `tsc --noEmit` + `biome check` + `pytest -m "not integration"`) + step-specific
  verification → commit + push (**targeted staging, never `git add -A`**) → update this file →
  advance.
- **Mode**: steps marked `[auto]` run autonomously without a human gate; steps marked
  `[supervised]` require the operator in the loop (visual/reconciliation judgment).
- **Stop it anytime**: create **`docs/decisions/0017-STOP`** — the run finishes its current
  safe step, records state, exits cleanly.
- **Preconditions**: clean working tree, sole writer per worktree (0015 §Precondition).

## Step ledger

| Step | Scope (short) | Mode | Status | Commit | Notes |
|---|---|---|---|---|---|
| 0 | Hygiene: commit the doc corpus (0017+A1+A2, 0018, ui-contract lexicon, this file); clean the WIP in the main dir | [supervised] | ✅ done | `4df8629` | WIP `replay.py` + `produit/page.tsx` deliberately left unstaged (pre-existing, other workstream) |
| 1 | Branch reconciliation: merge `feature/redesign` into the main-dir branch; 4 real conflicts; exit gate = twice-green + recouvrement drawer + wiring proofs + PAN gate | [supervised] | ✅ done | `f8923f8` | 3 of 4 auto-merged; the real one: redesign's "stabilize" was a from-scratch client-only drawer rewrite → **HEAD (codex, backend-wired) kept wholesale**, orphaned redesign test deleted (operator-approved). Gates twice-green (1285 pytest, wiring 137/137, PAN, tsc). Pre-existing debt found, untouched: biome 33 errors (outside ci gate), 1 vitest fail `lib/signal-registry.test.ts` (isSynthetic naming mismatch automations/replay_shadow/policies vs automation_workflow/shadow_traffic/policy_versioning) — **fix owed to step 2/3** (it is the registry the AgentSpec generation builds on) |
| 2 | 0017-A + 0018-A (freeze): import-linter contract (cockpit ⊄ `tessera.agent.*`/`langgraph`); generalise `/observability/business/runs?workflow_id=…` + `<WorkflowRunsPanel>`; stamp `grammar_version`; extract TurnInput/TurnResult protocol; acceptance tests over the existing runtime | [auto] | ✅ done | `d6f3df4` | Boundary shipped as a **stdlib AST ratchet test** (`test_observability_boundary.py`, exact-set equality, 5 frozen exceptions → Phase E), no new dependency. Generic read `_business_runs_response` + `/observability/business/runs`; `recouvrement-runs` = thin alias (same fn name/signature — existing tests untouched). `GRAMMAR_VERSION` stamped on the envelope. `turn_contract.py` + 5 acceptance tests. FE: `WorkflowRunsPanel` (copy via props), shim + `fetchBusinessRuns`, dashboard rewired, URL expectation updated. Owed debt fixed: `signal-registry.test.ts` synthetic ids realigned post-demotions. Sandbox-verified: `tsc --noEmit` green, `py_compile` green, boundary test dry-run PASS. **Sandbox cannot run ruff/mypy/pytest (py3.12 host venv) nor biome/vitest (darwin-arm64 binaries) → twice-green gate runs on the host, then targeted commit.** |
| 3 | 0017-B + A2.1 + A2.3: AgentSpec v1 (schema, CI validation, generation of SignalSpecs + FE mirror + level badge); typed envelope `actor`; declared policy metadata; recouvrement declares the first manifest | [auto] | ✅ done | `3011bac` | AgentSpec = pydantic `extra="forbid"` block in `tessera.agent.agentspec` (a manifest is an API: malformed→ValueError at load), re-exported through `tessera.agent.registry` (the boundary-allowed seam). Referential integrity + ≤1 north_star + **A2.2 outcome-undeclarable** enforced. Recouvrement's first manifest: 5 capabilities, 4 policies (metadata only — impls stay code), scorer `recouvrement.collections.v1`, 10 business_signals (north-star `contact_window_compliance`; `engagement: legal` on contact/validation compliance). A2.1 actor = closed vocab enforced at emit. Generation: `agentspec_projection` computes **level L0–L2 from facts** (None when un-manifested; L3=Phase C) + business-signal descriptors; fleet stamps `level`, card/row render honest-empty LevelBadge. FE mirror: business signal ids in `signal-registry.ts`, `FleetSchema.level`, capability/policy label_keys in fr/en/de. CI gates: `test_agentspec` (schema), `test_agentspec_conformance` (declared business_score keys ⊆ scorer-produced; manifest label_keys ∈ every locale — the i18n sweep is now a manifest-label gate), `test_business_event_actor`. Twice-green: ruff/format/pytest 1323/tsc/biome(changed)/vitest 69. **Deferred to step 4 (supervised):** north-star chip render, per-agent generated FE mirror, Métier tab (Phase C). **Inherited debt untouched:** mypy `observability/replay.py:92` (from antigravity merge `6c1a0db`; `replay.py` left alone per protocol) — blocks a clean `mypy src/tessera`, so **main merge withheld** until it is resolved by its owner. |
| 4 | 0017-C + A2.2 + 0018-B: Métier tab (per-capability table primary, runs drill-down), fleet north-star chip, À traiter source, Conformité projection; canonical artifact lifecycle mapping; delete the hardcoded tab | [supervised] | ⏸ checkpoint 3 visual validation | this commit | Lot 0 committed after checkpoint-1 review fixes. Lot 1 (onglet Métier) implemented and twice-green with real recouvrement data; checkpoint 2 reached with captures. Lot 1.5 completed the substance fix plus the P0-bis/P0/P1/P2 punch list on real data. Lot 2 delivered Flotte north-star/pending count, À traiter business-event source, Conformité legal projection, `page: metier`, and emitter fixes for action artifact/effect flags. **HALT: checkpoint 3 captures ready; Amadou visual validation required before lot 3.** |
| 5 | 0017-D: owned ClickHouse `business_events` table; dual-write → backfill → shadow parity → flip `BusinessEventStore`; erasure probe | [auto] | ✅ done | `f95b6cb` | Mirrors the §Correction 2b owned score store. Table `tessera.business_events` (§5 DDL: MergeTree + `toYYYYMM(occurred_at)` + 6-month TTL; `node_name` carried beyond the §5 columns for run-timeline read parity) via `ensure_business_events_schema`; scoped/as-of read (`ClickHouseAdapter.business_events`, rebuilt to `to_row` shape) + `delete_business_events` (count-then-DELETE, bound params). **Dual-write** = `clickhouse_business_events` (best-effort daemon-thread insert, JSONEachRow line + dedup key, gated `TESSERA_CLICKHOUSE_BUSINESS_EVENTS`) hooked into `record_business_event`. **Flip** = `business_events` is now a flippable fact (default `jsonl` — mid-migration, unlike G5's scores/gating); reads route via `_read_store()` in-process→`ClickHouseBusinessEventStore` (spine)→`_ShadowBusinessEventStore` (shadow parity: serve in-process, compare owned, log divergence); source badge resolves at read time (`fact="business_events"`). **Backfill** = `scripts/backfill_owned_business_events.py` from replay bundles + in-process seed (idempotent). **Erasure (G4)** = `purge_owned_business_events` folded into `purge_telemetry`; `ErasureFootprint` gains the business-events leg (deferred-never-faked). **Live-verified** on `tessera-claude-clickhouse:18123`: integration contract (4) + end-to-end emit→dual-write→flipped-read(full fidelity)→erasure all green. Unit suite hermetic (dual-write off in conftest). Twice-green: ruff/format/pytest 1338+4int/tsc/vitest 69. **A2.1 actor** already landed step 3. **Not done here (Phase C, step 4):** the actual prod read flip is a config action (`TESSERA_SPINE_SOURCE_BUSINESS_EVENTS=spine`) after shadow bake — the mechanism ships flipped-off. Same inherited `replay.py:92` mypy debt → **main merge still withheld**. |
| 6 | 0017-E + A2.4 + 0018-C/D: SDK extraction (instrument/graph_topology), span-contract + grammar-conformance suites, canaries + coverage per agent, enum codegen from capabilities, testkit; L-level → release-gate condition | [auto] | ⬜ pending | — | gate: recouvrement passes L1–L3 |
| 7 | 0017-F: out-of-process demo agent (pure OTLP, no LangGraph) reaches L1 with a **zero-line cockpit diff**; TTO measured and recorded here | [auto] | ⬜ pending | — | the architecture's acceptance test |

## Coordination register (parallel workstreams — sole-writer rule)

- **antigravity** works the support-client / produit chat UI on worktree
  `tessera-fix-produit`, branch `codex/fix-produit-chat-widget` (35 files vs its merge-base:
  chat components, product widget/host, session route, eval data). **Zero overlap** with the
  step-2 scope (observability routes/panel/spine/turn contract). Two watch-items for its
  landing: its merge-base (`b2e7b53`) predates the redesign merge → it will need its own small
  reconciliation; and `produit/page.tsx` is ALSO an unstaged WIP in the main dir — do not
  blend (0015 §Precondition).
- Steps 2+ in the main dir must **never stage** `replay.py` / `produit/page.tsx` WIP hunks.
- **Sandbox sessions use read-only git only** in the shared repo (`git --no-optional-locks
  status`, plumbing reads): a sandboxed `git status` refreshed the index, could not unlink
  its lock (`Operation not permitted`) and left the stale `.git/index.lock` the step-2
  executor had to clear (liveness-checked first — correct handling).
- **Post-reorg roles (2026-07-07):** the main checkout `tessera-app/tessera` is the
  **landing pad** — no agent edits it directly; all work happens in `agents/*` worktrees.
  UI produit work is reassigned **antigravity → codex** (operator call: codex is stronger
  on UI); antigravity parked pending reassignment. Incident recorded: a stale-context
  session live-edited the main checkout and **reverted committed step-2 work** in
  `signal-registry.test.ts` (uncommitted); restored to HEAD, the orphan patch (incl. a new
  `capabilityFor` describe block someone may want to reclaim) saved at
  `Tessera_private/patch-orphelin-signal-registry-test-2026-07-06.diff`.

## Log (newest first)

- 2026-07-07 — **step 4 / lot 2 code-review carry-over 1: emitter completeness pinned.**
  The lot-2 live proof (ledger runs `lot2-schedule-proof`, `lot2-reminder-proof`,
  `lot2-action-blocked-proof`) becomes regression-gated proof. Three new tests in
  `tests/unit/test_recouvrement_graph_v1.py`
  (`test_lot2_{schedule,reminder,blocked_contact}_flow_pins_action_emitter_completeness`)
  drive the real schedule and reminder flows and assert, across **every** `action.*` event of
  the flow (not a single spot-check), that it carries the `no_external_effect` flag and —
  unless it is a block — a linked `artifact_id`; and that `action_governance` = 1.0
  (`artifact_actions_traceable`) and `no_uncontrolled_external_effect` = 1.0
  (`no_external_effect_preserved`). A shared `_assert_action_emitter_completeness` helper
  encodes the invariant so a new un-flagged action emitter fails the gate instead of silently
  regressing the demo. Backend-only (tests); no src change, frontend gate unaffected.
  Twice-green: `ruff check`, `ruff format --check`, `mypy src/tessera` (264 files),
  `pytest -m "not integration"` (1362 passed, +3, 50 deselected), repeated identically green.

- 2026-07-07 — **step 4 / lot 2 completed; checkpoint 3 reached (HALT for Amadou visual validation).**
  Emitters first: Recouvrement now links generated action events to their artifact and carries
  the external-effect flag through schedule proposals, reminder drafts, validations and blocked
  actions. Real-run proof, not scorer indulgence: `lot2-schedule-proof` has
  `validation.requested(action_name=prepare_schedule_proposal, requires_validation=true,
  no_external_effect=true)` and `action.prepared(artifact_id=RC-2048-schedule-36-months-v2,
  no_external_effect=true)`, with `action_governance=1.0` and
  `no_uncontrolled_external_effect=1.0`; `lot2-reminder-proof` has
  `action.prepared(artifact_id=RC-2048-reminder-v1, no_external_effect=true)` with the same
  two scores at 1.0. A real blocked-contact run (`lot2-action-blocked-proof`) emits
  `action.blocked(action_name=prepare_outbound_call, no_external_effect=true)` and scores
  `action_blocking_correctness=1.0`, `no_uncontrolled_external_effect=1.0`.
  The business-signal aggregate now averages scored runs instead of scoring the whole spine
  bucket as one mega-run: old broken dev runs remain visible as failures, while fresh real
  runs are no longer collapsed to 0% (`action_governance=33.3%`,
  `no_uncontrolled_external_effect=38.5%`, reason `scored_runs_mean`, 132 events).
  Flotte: recouvrement card renders the manifest north-star chip
  `contact_window_compliance=100%` (`outside_contact_window_blocked`) and
  `10 métier en attente`. À traiter: `validation.requested` + `action.blocked` become
  `OperatorItems` with deep-links to `/agents/recouvrement/metier?...`; duplicate natural
  business ids are deduped before rendering (API proof: 28 ids / 28 unique, 10 business
  items). Conformité: only legal business signals are projected (`contact_window_compliance`
  100%, `validation_required_compliance` 100%, source `spine`, href Métier). Signal catalog:
  `page: metier` added to the vocabulary and candidate signals rehomed. Micro-nits absorbed:
  `business_events` default read source is `spine`; the bounded in-memory source is labelled
  `local` while `jsonl` remains an alias for compatibility. Captures:
  `/tmp/tessera-lot2-flotte.png`, `/tmp/tessera-lot2-a-traiter.png`,
  `/tmp/tessera-lot2-conformite.png`. Servers relaunched from the codex worktree
  (`:8099`, `:3097`); health and proxy `/api/healthz` both 200. Twice-green full gate after
  final code edits: `ruff format --check .`, `ruff check .`, `mypy src/tessera`,
  `pytest tests/unit/ -q` (1359 passed), `pnpm exec biome check .` (exit 0, 27 known
  warnings), `pnpm typecheck`, `pnpm test` (69 passed), repeated identically green. **HALT
  after commit: checkpoint 3 visual review required before lot 3.**

- 2026-07-07 — **step 4 / lot 1.5 completed (substance + punch list; checkpoint 2 still held).**
  Substance first, before edits: the red `action_governance=0%` and
  `no_uncontrolled_external_effect=0%` on historical recouvrement runs were not an UI-only
  artefact. The scorer was correctly returning `action_artifact_missing` and
  `action_missing_no_external_effect_flag` because `action.prepared` events carried only
  `action_name`; they lacked the linked `artifact_id` and `no_external_effect=true`. The
  `validation_required_compliance=unknown` cases were honest-empty (`no_validation_required_event`)
  on flows where no validation-required event existed. Fix: schedule proposals and reminder
  drafts now emit traceable `action.prepared` events with artifact linkage, validation intent
  and explicit no-external-effect flags; fresh real runs now score `action_governance=100%`
  and `Effets externes contrôlés=100%`.
  P0 honesty: absent/not-applicable scores render `—` with neutral reasons in the drill-down,
  the `Résumé du dossier` conformity no longer becomes `0%` from the diagnostic
  `recouvrement_trace_completeness` metric, and the `non attribué` row remains visible for
  unstamped events. P0-bis/P1/P2: the tab was restructured to the house pattern (signal
  band -> full-width capabilities table -> vertical master-detail on selection), with the
  north-star KPI promoted, secondary KPIs grouped, trend text collapsed to a discreet dash,
  short IDs + copy buttons, deduped reason chips, full-width chronology, and four equal
  bottom panels for artefacts/decisions/actions/scores with the safety flags visible.
  Visual proof on the restarted codex worktree (`:3097`, authenticated admin demo session):
  `/tmp/tessera-metier-p0-summary-dash-fixed.png`,
  `/tmp/tessera-metier-p0bis-schedule-drilldown-fixed.png`,
  `/tmp/tessera-metier-p0-four-panels-fixed.png`. DOM proof: no horizontal overflow, no
  repeated "Tendance indisponible", `Échéancier créé=non`, `Effet externe=aucun`,
  `Gouvernance des actions=100%`, `Effets externes contrôlés=100%`. Real API proof:
  `/observability/business/capabilities?agent=recouvrement` is L3 with 108 events,
  `summarize_case.conformity_pct=null`, `propose_schedule.volume=11`, and the unstamped
  row volume is 2. Audit-chain check on the real backend: `verified=true`,
  `content_integrity=true`, `linear=false`, `fork_count=29`, `orphan_count=1`,
  `attested=true`; these are historical attested forks/orphan, not a content-integrity
  incident. Twice-green full gate after the final edits: `ruff format --check .`,
  `ruff check .`, `mypy src/tessera`, `pytest tests/unit/ -q` (1353 passed),
  `pnpm typecheck`, targeted `pnpm exec biome check` on changed UI/i18n files, and
  `pnpm test` (69 passed); repeated identically green. **HALT: Amadou visual validation
  required before lot 2.**

- 2026-07-07 — **step 4 / lot 1.5a house alignment (checkpoint 2 still held).**
  Audited `agent-metier.tsx` against the shipped Cockpit/Agent patterns: the business
  signal strip now uses the shared `MetricCard` KPI atom; the capabilities panel uses
  `Card` + `Table` primitives with the same dense spacing as the catalogue/evaluations
  tables; the honest-empty state uses `EmptyState`; the visible runs vocabulary is now
  "exécutions" / "chronologie" / "tour" instead of internal "run" labels on this surface.
  The tab still reads only real `/observability/business/capabilities` data and keeps
  unstamped events visible as the `—` / `non attribué` row. Added the constraining unit
  test `test_unknown_capability_row_is_rendered_as_non_attribue` for
  `UNKNOWN_CAPABILITY_ID`; updated the generic run-panel copy test to the new label.
  Visual proof on the live local worktree (`/fr/agents/recouvrement/metier`): 10 KPI
  tiles, 6 capability rows, `non attribué` visible, no "Données métier indisponibles";
  capture `/tmp/tessera-metier-lot-1-5a-after-load.png`. Twice-green executable gate:
  `ruff format --check .`, `ruff check .`, `mypy src/tessera
  tests/unit/test_business_capabilities.py` (clean; full `uv run mypy` still hits the
  pre-existing tests-wide typing baseline), `pytest -m "not integration" -q`
  (1345 passed, 48 deselected), `biome check` on changed frontend files, `pnpm
  typecheck`, `pnpm test` (69 passed); repeated identically green. **Still halted at
  checkpoint 2 for operator visual validation before lot 2.**

- 2026-07-07 — **step 4 / lot 1 checkpoint 2 reached (onglet Métier, supervised halt).**
  Added `/agents/<agentId>/metier` between Synthèse and Évaluations, visible through the
  per-agent command bar only. The tab reads the generated manifest and renders an
  honest-empty state unless the agent reaches L3; for recouvrement, L3 now requires manifest
  + governed release facts + stamped business events. The main table is server-side
  `/observability/business/capabilities` data only: manifest capabilities by i18n label,
  volumes, conformity/validation/blocked rates, prevented external effects and honest-empty
  trends; unstamped events keep the `non attribué` row. The signal banner renders
  `business_signals` grouped by level with localized labels. Drill-down reuses
  `WorkflowRunsPanel` filtered by `capability_id`; schema fixed to accept the generic API's
  `workflow_id: null` when no workflow filter is requested. Real-data proof: a live
  recouvrement turn (`case_id=RC-2048`, `conversation_id=ckpt2-metier-live`) produced 9
  business events; `propose_schedule` shows volume 1, conformity 66.7%, validation 100%,
  blocked 0%, external_effects_prevented 2, and drill-down shows `schedule_proposal_v2`,
  `VALIDATION_REQUIRED`, `CLIENT_AGREEMENT_REQUIRED`, `SCHEDULE_NOT_CREATED`. Captures:
  `/tmp/tessera-metier-checkpoint2-capabilities.png` and
  `/tmp/tessera-metier-checkpoint2-drilldown.png`. Twice-green full gate: `ruff format
  --check .`, `ruff check .`, `mypy src/tessera`, `pytest -m "not integration" -q`
  (1344 passed, 48 deselected), `npx biome check .` (code 0; 27 warnings), `npm run
  typecheck`, `npm test` (69 passed); repeated identically green. **HALT at checkpoint 2.**

- 2026-07-07 — **step 4 / lot 0 review fixes + ui-polish absorbed; checkpoint 1 validated.**
  Review finding 1 fixed: the generic `business_capabilities` aggregate no longer knows
  recouvrement payload flags such as `no_schedule_created`; `external_effects_prevented`
  is derived from the grammar (`action.blocked`, `validation.requested`, and
  `action.prepared` for manifest capabilities with external-effect levels). Review finding
  2 fixed: unstamped historical events stay under the technical id `—` but now expose the
  human row label `non attribué`, with a regression test. Ui-polish landed from base:
  artifact status `executed` now displays `Planifié (interne)`, and the Cockpit run panel
  resolves artifact status labels via `artifactStatus.<status>` in `messages/{fr,en,de}`.
  Gate hygiene needed for the requested full Biome gate: pre-existing blocking Biome errors
  in front scripts/product helpers were fixed mechanically (warnings remain non-blocking).
  Twice-green full gate after final edits: `ruff format --check .` (504 files),
  `ruff check .`, `mypy src/tessera` (264 files), `pytest -m "not integration" -q`
  (1344 passed, 48 deselected), `npx biome check .` (code 0; 27 warnings), `npm run
  typecheck`, `npm test` (69 passed). Repeated identically green. **GO lot 1 per operator;
  halt at checkpoint 2.**

- 2026-07-07 — **step 4 / lot 0 checkpoint reached (backend prereq, supervised halt).**
  Shipped the domain-owned Recouvrement capability mapping (`summary`→`summarize_case`,
  `check_rule`→`check_contact_rule`, artifact/action mappings) in `tessera.recouvrement`;
  the graph stamps `capability_id` on emitted business events when the capability is known,
  including artifact-action workflows. Business-event reads now accept `capability_id`
  through the in-memory store, ClickHouse store, shadow store, `/observability/business-events`,
  and `/observability/business/runs`; OTel span events also carry
  `tessera.business.capability_id`. Added `/observability/business/capabilities`, a
  server-side aggregate over `fact=business_events` with manifest rows plus honest
  `—` for historical unstamped events. Live proof (real recouvrement graph run, no synthetic
  metrics): `validation.requested` row has `capability_id="propose_schedule"`; aggregate row
  schema is `capability_id,label_key,external_effect_level,volume,conformity_pct,
  validation_required_pct,blocked_pct,external_effects_prevented,trend,event_count`; live
  `propose_schedule` row: volume 1, validation_required_pct 100.0, blocked_pct 0.0,
  external_effects_prevented 2, trend honest-empty (`insufficient_data`). Twice-green after
  final edits: `ruff format --check` + `ruff check` targeted (9 files), `mypy src/tessera`
  (264 files, clean), `pytest tests/unit/test_business_event_envelope.py
  tests/unit/test_recouvrement_graph_v1.py tests/unit/test_owned_business_events.py -q`
  (52 passed), `npx biome check lib/api/client.ts lib/api/schemas.ts`, `npm run typecheck`;
  repeated identically green. **HALT here per checkpoint 1: Claude review required before lot 1.**

- 2026-07-07 — **steps 3+5 merged to `main` (`fa63bd9a`), pushed to origin.** The 3 review
  must-fixes executed in order: (1) `14bd3a4f` — replay.py orphan WIP committed as the mypy
  fix (walrus hoist), clearing the sole `mypy src/tessera` error that had withheld the merge;
  (2) `dcb0c38a` — packaging fix (`eval` added to the wheel `packages`; proven `from
  eval.sets import load_eval_set` imports with no PYTHONPATH via the install); (3) `e76215eb`
  — optional `capability_id` on the BusinessEvent envelope (A1.2) + to_row/round-trip test.
  Merge conflicts were the ledger only (step table + Log union — resolved keeping every
  entry; row 2 done from main, rows 3/5 done from the branch). **Twice-green on the merged
  tree** (a healthy venv required `rm -rf .venv && uv sync` — the reorg's stale-`.pth`
  artifact): ruff, ruff-format, `mypy` **Success (262 files, clean)**, pytest 1341 unit + 4
  business_events integration (live ClickHouse), tsc, biome (changed FE), vitest 69. Push was
  a clean fast-forward (`f008458a..fa63bd9a`). **Owed follow-ups** (from the clarification
  below): after a short bake, flip the `business_events` read default to `spine`; rename the
  switch value `jsonl` → `local`. Steps 4 (supervised) and 6 (post-review) remain.

- 2026-07-07 — clarification (operator question): the `business_events` fact's legacy leg
  labelled `jsonl` in the per-fact source switch is the **bounded in-memory projection**,
  never a file (verified; a test asserts `business_events.jsonl` does not exist — 0016
  rule). Two follow-ups owed: (a) after the must-fix merge + a short bake, **flip the
  `business_events` default to `spine`** (in-memory demotes to test-only default, 0017 §5);
  (b) vocabulary debt — rename the switch value `jsonl` → `local` once the scores
  retirement (0015 G5 bake) concludes, so the label stops lying about the medium.

- 2026-07-07 — **Architecture review of steps 3+5 (claude/step-3-agentspec): APPROVED with
  3 must-fix before merge.** Core verdict: AgentSpec v1 conforms (extra=forbid frozen,
  closed vocabularies, i18n namespace validators, referential integrity, ≤1 north-star,
  A2.2 outcome-undeclarable enforced as a model validator — illegal state unrepresentable);
  boundary ratchet intact (5 frozen exceptions); registry seam respected. Must-fix:
  (1) **replay.py orphan WIP adjudicated — it IS the mypy fix** (walrus hoist of
  `row.get("business_events")`); commit it as its own fix commit — this unblocks the
  green-merge rule; (2) **packaging debt still owed** (wheel `packages` unchanged) —
  execute the logged fix; (3) **A1.2 gap: `capability_id` exists as a CH column but NOT on
  the envelope** — add the optional field (+ to_row test); it is step 4's per-capability
  join key; emitter stamping may ride step 4. Then re-gate twice → merge to main → push
  (`-u origin`).

- 2026-07-07 — **step 5 done** (`f95b6cb`): owned ClickHouse `business_events` store — table +
  dual-write + read-flip (jsonl→spine→shadow) + backfill + G4 erasure. Live-verified against the
  running `tessera-claude-clickhouse` (:18123): the integration contract and a full
  emit→dual-write→flipped-read→erasure round-trip pass. Twice-green (delta clean). **HALT here per
  the run plan**: step 4 is `[supervised]` (Métier tab + fleet north-star chip + À traiter +
  Conformité projection — visual/reconciliation judgment) and step 6 is post-review. Ready for the
  operator to (a) resolve the inherited `replay.py:92` mypy debt and merge steps 3+5 to main once
  `mypy src/tessera` is clean, and (b) drive step 4.
- 2026-07-07 — **step 3 done** (`3011bac`): AgentSpec v1 + A2.1 actor + A2.3 policy metadata;
  recouvrement declares the first manifest; level L0–L2 computed from facts; twice-green
  (my delta clean across ruff/format/mypy/pytest/tsc/biome/vitest). Baseline finding: the
  branch inherited a pre-existing `mypy` error at `observability/replay.py:92` from the
  antigravity merge (`6c1a0db`, commit `b2e7b53`); `replay.py` is left untouched per protocol,
  so `mypy src/tessera` is not clean and **the main merge is withheld** for the owner to fix.
  Frontend deps install via `npm ci` (package-lock.json; no pnpm-lock despite the
  `packageManager` field). Proceeding to step 5 (independent of step 4).

- 2026-07-07 — dev servers relaunched from the new path, verified end-to-end (backend :8099
  healthz/readyz, front :3097 → 200, proxy /api 200; obs-core up). Three finds, two fixed
  locally: `PYTHONPATH=.` needed (see debt below), pnpm `--` forwarding quirk, and
  `webapp/frontend/.env.local` pointing at dead :8392 → :8099 (gitignored, correct home for
  the fix). **Debt owed — durable packaging fix:** the root `eval/` package is NOT in
  `[tool.hatch.build.targets.wheel] packages` → `make run` bare and the `tessera-eval`
  console script are broken on any clean sync (latent bug exposed by the reorg re-sync,
  masked before by inherited venv state). Fix: `packages = ["src/tessera", "eval"]` +
  `uv sync` + prove `from eval.sets import load_eval_set` imports WITHOUT PYTHONPATH; gate;
  commit. Small, gate-able — ride it at the START of the step-3 session or the morning
  review. (Later, separate slice: consider renaming the top-level `eval` package.)

- 2026-07-07 — **Repo reorg executed** (`Tessera_private/runbook-reorg-repo-2026-07-06.md`):
  `main` fast-forwarded to `c26cb9d` (merge-2/antigravity + step-2, both landed) and pushed to
  origin (`tessera-app.git`) for the first time; `codex/recouvrement-logic-on-drawer-5c61984`
  deleted (local only, never existed on origin). Stale worktrees cleaned: `tessera-phase2-wiring`
  (`feature/redesign`) and `tessera-fix-produit` (`codex/fix-produit-chat-widget`) removed —
  both fully merged into `main`. `tessera-observability-refinement` turned out to be a worktree
  of the **old legacy repo** (`apps/tessera`, origin `tessera.git`), not this one — its
  registration in this repo was stale/orphaned (git safely refused a plain `worktree remove`);
  cleaned only this repo's orphaned `.git/worktrees/` entry, left the directory and the legacy
  repo's own worktree untouched (out of scope for this reorg, operator call). Repo moved
  `apps/codex/tessera` → `apps/tessera-app/tessera`; `git worktree repair` + `uv sync` (editable
  install `.pth` hardcodes an absolute path, breaks on move — re-sync fixes it) + smoke test
  (`test_observability_boundary.py`) + full suite (1291 passed) all green from the new path.
  Three fresh agent worktrees cut from `main`: `agents/{claude,codex,antigravity}` on
  `{claude/step-3-agentspec, codex/parking, antigravity/parking}`. `replay.py` and the
  in-flight `signal-registry.test.ts` edit (someone else's live, mid-write session on this
  exact tree — Phase 0 caught it late) rode across every step via stash-and-pop, never staged.
  Lesson: a directory that "looks like" this repo's worktree isn't necessarily one — always
  check the worktree's own `.git` file (source of truth), not just this repo's registry, before
  removing anything.

- 2026-07-06 — antigravity finished (`aad890c`); merge-2 inventory done (3 i18n files =
  the whole conflict surface; the main-dir `produit/page.tsx` WIP is byte-identical to
  AG's commit → discard). Protocol in `Tessera_private/reconciliation-branches-2026-07-06.md`
  §Merge 2. Rule going forward: worktrees sync FROM the trunk at every slice boundary.

- 2026-07-06 — **Step 2 done** (`d6f3df4`), twice-green (ruff + mypy + 1291 pytest ×2; FE
  typecheck + 69/69 vitest). Executor corrections on review: import sort + comparison style
  in the acceptance test, and **one real assertion bug** — the expected reason string was
  `validation_requested_pending_or_declared` (the shipped constant), not the guessed
  `validation_requested_or_pending`. Lesson recorded: assertions on domain constants must be
  read from source, never inferred. Boundary ratchet live (5 frozen exceptions).

- 2026-07-06 — file seeded; steps 0–7 defined; branch inventory produced (4 real conflicts,
  13 duplicate-identical files, business-events stack is codex-only, i18n codex-only).
