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
| 4 | 0017-C + A2.2 + 0018-B: Métier tab (per-capability table primary, runs drill-down), fleet north-star chip, À traiter source, Conformité projection; canonical artifact lifecycle mapping; delete the hardcoded tab | [supervised] | ⬜ pending | — | gate: recouvrement fully re-homed |
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

- 2026-07-08 — **Checkpoint 4 review: MERGE FEU VERT (conditioned on operator's
  checkpoint-3 visual sign-off).** Verified on pieces: emitter invariant pinned via a
  shared helper over ALL `action.*` events (6f31f1c2 — a new un-flagged emitter fails
  the gate); BR-01 §5 conform (URL-derived selection in `agent-metier.tsx`, mode
  indicator, as-of proven honest-empty at=2020); dissolution clean (d0699d97 — the two
  grep hits are docstrings documenting the removal). **Hygiene finding (inverts the
  executor's note): `packageManager: pnpm@9.15.0` is declared → pnpm is canonical, and
  NO lockfile is tracked at all — commit `webapp/frontend/pnpm-lock.yaml` at merge time
  (reproducible FE builds), do not delete it.** After merge: step 4 row → done; unblocks
  cockpit-header work (was gated on this merge), craft pass P3 (lot 2.5), and the
  Claude async backlog.

- 2026-07-07 — **Lot 2 code review: PASS with 1 carry-over; checkpoint-3 visual pending;
  custody transfer.** Verified on `39a1bdfb` (+ lot-1.5 finish `77ee755e`, dedup fix
  `6f6fd610`): emitter gaps fixed live (`action_governance=1.0`,
  `no_uncontrolled_external_effect=1.0` on proof runs), fleet chip + pending counter,
  À traiter dual-source with Métier deep-links, Conformité legal projection, `page:
  metier` (3 uses), and two backlog items absorbed early — **business_events default =
  spine** and **`SOURCE_LOCAL="local"` with `SOURCE_JSONL` compat alias**. Carry-over
  (binding, before merge): **pin emitter completeness with a unit test** (every `action.*`
  event carries `artifact_id` + the external-effect flag; the two scores assert 1.0) —
  live proof must become pinned proof. **Custody: codex out of credits until tomorrow →
  the claude executor continues ON `codex/step-4-metier` IN the `agents/codex` worktree**
  (sole-writer holds — codex idle). Claude takes: emitter-pinning test, lot 3
  (dissolution), BR-01 §5 conformance. Craft pass P3 + e2e: antigravity tonight or codex
  tomorrow (operator's call). Checkpoint-3 visual (Flotte / À traiter / Conformité
  captures) owed by the operator before lot 3 lands.

- 2026-07-07 — **Architecture sweep dispatched (operator decision) + BR-01 rail defined.**
  Deferred to a Claude-owned async backlog: (1) RBAC alignment of the business read
  routes on the snapshot posture (rides lot 3); (2) fold business signals into the
  batched snapshot + p95 budget/probe (rides step 6 — the fan-out must not return);
  (3) minimal AgentSpecs for support-client + onboarding (30-min slice — makes the fleet
  show the L0-L3 ladder); (5) TESS-LEDGER-001 post-mortem as a publishable artifact
  (signals 160/114). Item (4) e2e Playwright smoke on Métier + recouvrement-new stays in
  the codex stream, after the craft pass. **Temporal rail decided from the operator's
  rails registry (v1.3): `BR-01 · Business Runs Rail` — substrate S3, component C2
  (shared with ER-01/CT-01), page AGENT/Métier.** §5 conformance owed to the codex
  stream: URL-derived selection (deep-link), visible time-mode indicator, global as-of
  propagated (backend `at` already supported). Forbidden: any C4/scrubber on an AGENT
  page — business-signal time navigation belongs to SURVEILLER (SR-01).

- 2026-07-07 — **Lot 1.5 visually VALIDATED (operator + Claude review on screenshots): GO
  lot 2.** All 17 punch-list items applied — structural rework matches the wireframe
  (stacked full-width, featured north-star, master-detail drill-down, 4 equal bottom
  columns), honesty items done end-to-end (not-applicable = « — » with reason, double
  negation renamed, artifact safety flags fully visible incl. « Échéancier créé : non »).
  Carry-overs into lot 2: (1) **emitter gaps surfaced by the honest 0%** — some action
  events lack artifact linkage (`action sans artefact lié`) and some lack the
  external-effect flag (`flag effet externe absent`) → complete the emitters (preferred)
  or requalify to `not_applicable` at the scorer; (2) plural rule « 1 orpheline(s) » ;
  (3) group the repeated decision headers. Lot 2 scope unchanged: fleet north-star chip,
  À traiter source, Conformité projection, `page: metier` catalog vocabulary.

- 2026-07-07 — **TESS-LEDGER-001 CLOSED.** Remediation merged + pushed; operator sign-off
  done — the amber badge renders in-browser with the attested wording (« Intégrité contenu
  vérifiée · ordre total : 29 fourches historiques, 1 orpheline(s) (attestées) »). Open
  follow-ups tracked: Hica seal implementation (priority raised, §Corr.3c),
  business_events default flip after bake, `jsonl`→`local` rename.

- 2026-07-07 — **TESS-LEDGER-001 remediation review: APPROVED — merge + push cleared.**
  Verified on the 8 commits (`claude/incident-ledger-forks`): append-only held (zero
  DELETE/UPDATE in the diff), serialized drain under `pg_advisory_xact_lock` with in-txn
  head read, partial unique anchor, position-independent `event_id` idempotence key (finer
  than the playbook), tree-aware verifier + tri-state badge, attestation append at seq
  17136, ADR 0015 §Correction 3c landed. Investigation refined the facts (first fork =
  parent 5984; `broken_at` = walk position; **+1 orphan seq 11814 = a LOST WRITE**, same
  root-cause family, ratified by the attestation — deeper investigation logged as accepted
  optional). Operator items: push; browser render of the amber badge; Hica seal
  implementation to schedule (priority raised by §Corr.3c); codex must re-merge main into
  its branch before finishing lot 1.5 (the badge changed under it).

- 2026-07-07 — **INCIDENT TESS-LEDGER-001 opened** (dossier:
  `Tessera_private/incident-ledger-forks-2026-07-07.md`). The cockpit integrity badge +
  codex's blocking check found the active `audit_ledger` **forked**: 29 duplicated
  `prev_hash` groups over 13 374 rows (first at seq 6280 → siblings 6281/6282). Root
  cause code-confirmed: per-process `_last_hash` cache + unserialized head read (no
  advisory lock, no `UNIQUE(prev_hash)`) — the Amendment-3 promotion never specified
  write serialization (ADR gap). Impact framed honestly: per-row tamper-evidence INTACT
  (it is a fork, not tampering); total order lost at 29 points. Remediation plan in the
  dossier: evidence freeze → investigate → serialize writes + partial unique index +
  concurrency test → tree-aware verifier/badge → attestation re-anchor (never rewrite) →
  ADR correction. Codex may resume lot 1.5 EXCEPT the integrity badge/footer (owned by
  the incident workstream). **The detection chain worked: badge → halt → escalate.**

- 2026-07-07 — **Checkpoint 2 visual verdict (operator): substance validated, polish owed
  → lot 1.5 inserted before lot 2.** Scope: (a) mechanical alignment of the Métier tab on
  its sibling fiche-agent tabs — reuse the house components (KPI strip, tables, badges,
  spacings from synthese/evaluations/CatalogTabView patterns) instead of the bespoke
  410-line layout where applicable; (b) the operator's specific punch list (to be
  dictated); (c) the **unattributed-row unit test** (pulled forward from lot 2). Rationale:
  the visual bar must be internalised before building 3 more surfaces (lot 2), or the
  polish debt triples. Iteration loop: servers stay up from the codex worktree,
  edit→refresh with the operator.

- 2026-07-07 — **Step-4 checkpoint 2 review: PASS on code, 1 carry-over, visual validation
  pending.** Verified on the diffs (ebe15a90 lot 0, 73ab8e4a lot 1): checkpoint-1 findings
  fixed (generic module pure; unknown-capability mechanism in place), ui-polish findings
  absorbed (« Planifié (interne) » + `artifactStatus.*` keys ×3 languages), L3 gating with
  honest-empty + level shown, KPI grouped by level, AT-01 respected (Synthèse untouched),
  heavy i18n (+68×3). Carry-over into lot 2 (binding): **a dedicated unit test pinning the
  unattributed row** (events with `capability_id NULL` → `UNKNOWN_CAPABILITY_ID` row) —
  the 364-line aggregation module currently has endpoint-level coverage only. Visual
  validation by the operator required before GO lot 2 (servers must run from the
  `agents/codex` worktree — the branch is unmerged).

- 2026-07-07 — **ui-polish landed as `04b249b3` directly on main** (operator-ordered commit
  by the e2e-review session; targeted gates green). Review decision: **accepted as-is** —
  rewriting shared main for procedure would cost more than the deviation; the branch
  procedure remains the rule for agents. **Its 2 findings are now BINDING lot-1 items**:
  (1) `executed` label must carry the boundary (« Planifié (interne) » or equivalent —
  0018 §4: no label claims more than the chain proves); (2) cockpit-side status labels via
  i18n keys `artifactStatus.<status>` in `messages/{fr,de,en}` (the FR map may remain a
  drawer fallback transitionally). codex/step-4-metier fast-forwarded onto it — sequence
  gate cleared. Housekeeping owed: push main; commit this ledger; `git gc` at a quiet
  moment (unreachable-objects warning).

- 2026-07-07 — **Step-4 checkpoint 1 (lot 0) review: APPROVED on substance, 2 findings,
  sequence gate.** Right: mapping in the domain package (`recouvrement/capabilities.py`),
  stamping via `_event_common` with deterministic test proof (graph → `summarize_case`/
  `draft_reminder`; action workflow → from artifact type), aggregate columns = A1.4
  exactly (incl. `label_key` i18n + honest `insufficient_data` trend), manifest-driven
  capability enumeration. Findings: (1) **domain constant `no_schedule_created` inside the
  new generic `business_capabilities.py`** — 0016 rule; new code gets no transitional
  grace: derive "effects prevented" from grammar events/generic envelope fields, or read
  flag keys from the manifest; (2) **unattributed events must be visible** — events with
  `capability_id NULL` (history) must aggregate into an explicit "unattributed" row with a
  test, never silently dropped. Sequence gate: `codex/ui-polish-honesty` recovery was
  NEVER executed — the polish still sits uncommitted on the landing pad; recover + fix its
  2 findings + merge to main BEFORE lot 1, then codex merges main into
  `codex/step-4-metier` (lot 1 builds on the 3-state panel).

- 2026-07-07 — **Landing-pad incident #2 + recovery.** An ad-hoc codex UI-polish prompt ran
  in the main checkout, leaving 5 files modified uncommitted on `main` (nothing pushed, no
  loss). Recovery: `git switch -c codex/ui-polish-honesty` (carries the changes), targeted
  commit, landing pad restored. Review verdict: **adopt** — includes a genuine honesty bug
  fix (external-effect header badge used `.some()`: one safe flag masked a real effect
  elsewhere; now strict 3-state) — with 2 findings to fix on the branch before merge:
  (1) `executed → "Planifié"` overclaims (no real calendar event exists — 0018 §4 honesty
  rule): label must carry the boundary ("Planifié (interne)" or equivalent); (2) hardcoded
  FR labels bypass i18n on the cockpit side → `artifactStatus.<status>` keys in
  `messages/{fr,de,en}`. Merge this branch BEFORE step 4 (it touches
  `workflow-runs-panel.tsx`). **Process lesson:** every executor prompt MUST start with
  `cd …/agents/<name>` + branch creation; ad-hoc prompts route through this register.
  Note for 0018 Phase B: `artifact-status.ts` is the transitional FE label map that the
  AgentSpec label→canonical-state mapping will absorb — linked so they don't drift.

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
