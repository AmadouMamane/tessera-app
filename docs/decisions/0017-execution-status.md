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
| 4 | 0017-C + A2.2 + 0018-B: Métier tab (per-capability table primary, runs drill-down), fleet north-star chip, À traiter source, Conformité projection; canonical artifact lifecycle mapping; delete the hardcoded tab | [supervised] | ✅ done | ebe15a90…d0699d97 · pnpm c165be72 · merge 844fa775 | Lot 0 committed after checkpoint-1 review fixes. Lot 1 (onglet Métier) implemented and twice-green with real recouvrement data; checkpoint 2 reached with captures. Lot 1.5 completed the substance fix plus the P0-bis/P0/P1/P2 punch list on real data. Lot 2 delivered Flotte north-star/pending count, À traiter business-event source, Conformité legal projection, `page: metier`, and emitter fixes for action artifact/effect flags. **Lot 2 code-review carry-overs** landed: (1) emitter-completeness pinning tests; (2) BR-01 §5 on the Métier tab (URL-derived capability/run deep-link, temporal-mode badge Live→As-of, global as-of propagated to business reads). **Lot 3 dissolution** implemented + committed (recouvrement dashboard tab / shim / `fetchRecouvrementRuns` / `/observability/recouvrement-runs` all removed; tests migrated to the generic business-runs read). Each item twice-green + targeted commit + ledger. Checkpoint-3 captures validated by Amadou; checkpoint-4 merge feu vert given → **merged to main (`844fa775`) after full gate twice-green on the merged tree.** See the step-4 closure Log entry. |
| 5 | 0017-D: owned ClickHouse `business_events` table; dual-write → backfill → shadow parity → flip `BusinessEventStore`; erasure probe | [auto] | ✅ done | `f95b6cb` | Mirrors the §Correction 2b owned score store. Table `tessera.business_events` (§5 DDL: MergeTree + `toYYYYMM(occurred_at)` + 6-month TTL; `node_name` carried beyond the §5 columns for run-timeline read parity) via `ensure_business_events_schema`; scoped/as-of read (`ClickHouseAdapter.business_events`, rebuilt to `to_row` shape) + `delete_business_events` (count-then-DELETE, bound params). **Dual-write** = `clickhouse_business_events` (best-effort daemon-thread insert, JSONEachRow line + dedup key, gated `TESSERA_CLICKHOUSE_BUSINESS_EVENTS`) hooked into `record_business_event`. **Flip** = `business_events` is now a flippable fact (default `jsonl` — mid-migration, unlike G5's scores/gating); reads route via `_read_store()` in-process→`ClickHouseBusinessEventStore` (spine)→`_ShadowBusinessEventStore` (shadow parity: serve in-process, compare owned, log divergence); source badge resolves at read time (`fact="business_events"`). **Backfill** = `scripts/backfill_owned_business_events.py` from replay bundles + in-process seed (idempotent). **Erasure (G4)** = `purge_owned_business_events` folded into `purge_telemetry`; `ErasureFootprint` gains the business-events leg (deferred-never-faked). **Live-verified** on `tessera-claude-clickhouse:18123`: integration contract (4) + end-to-end emit→dual-write→flipped-read(full fidelity)→erasure all green. Unit suite hermetic (dual-write off in conftest). Twice-green: ruff/format/pytest 1338+4int/tsc/vitest 69. **A2.1 actor** already landed step 3. **Not done here (Phase C, step 4):** the actual prod read flip is a config action (`TESSERA_SPINE_SOURCE_BUSINESS_EVENTS=spine`) after shadow bake — the mechanism ships flipped-off. Same inherited `replay.py:92` mypy debt → **main merge still withheld**. |
| 6 | 0017-E + A2.4 + 0018-C/D: SDK extraction (instrument/graph_topology), span-contract + grammar-conformance suites, canaries + coverage per agent, enum codegen from capabilities, testkit; L-level → release-gate condition | [auto] | ✅ done | 6a `baff0231`→`9126c3de` · 6b `301eee8a`→`a6633cf4` · 6c `7f80682d`→`a3d19604` | **6a+6b+6c shipped** (step 6 closed): ratchet 5→0 (SDK), testkit 103/104, enum codegen 0018-C; A2.4 L-level release gate (prod⇒L2, external⇒L3), canaries 94 + coverage 92 from the manifest. **6c**: `require_bearer` on the 4 business read routes (snapshot posture; `/security-review` clean — strict tightening); business_capabilities folded into the batched snapshot as a p95-safe probe (one-source parity); Point 1 (coverage names its source — no FE lie, no consumer) + Point 3 (honest block label: eval-gate vs observability level, level-aware summary) — see Log. Branch off main `40dadade`; pushed to origin (backup). **Not merged to main** — merge is a separate operator-gated action (twice-green-on-merged-tree + feu vert, per step 4). gate: recouvrement passes L1–L3 |
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
- **Dev-server convention (2026-07-08, after the park-under-live-server break):** the
  reference servers (:3097/:8099) run from the **main checkout** (`tessera/`) — the
  operator's browser reflects `main`. Viewing UNMERGED work at a checkpoint = a
  **temporary server on another port** (e.g. :3098) from the agent's worktree, killed
  after validation. Corollary: **any worktree mutation (checkout/park/remove) is
  preceded by a live-process check** (`lsof +D <worktree>` — same pre-flight as the
  reorg runbook); never rotate a worktree out from under a running watcher.
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

- 2026-07-08 — **step 7 Lot 0 done (OFF-CHRONO): support-client + onboarding declare
  telemetry-only manifests.** The two Q&A agents get an AgentSpec `observability` block —
  `telemetry_capabilities: [graph_topology, tools]` (what they really emit) + a scorer-less
  conversation workflow bound to `workflow_grammar.v1`, and NO business capabilities /
  policies / business_signals (they run no scored business workflow — "sans workflow" here =
  *sans workflow scoré*, the reading that makes the instruction self-consistent since the
  resolver requires a workflow binding for L1). The level is **COMPUTED, never tuned**: both
  fall out as **L2** because they are genuinely governed (their eval-gating socles ran) —
  `resolve_observability_level` → support-client L2, onboarding L2, recouvrement L3.
  Off-chrono by design: the existing agents' specs are not part of hello-agent's onboarding
  cost (counting them would falsify the TTO). Tests: the un-manifested-level assertions
  rehomed to a synthetic `observability=None` agent (every registry agent now has a
  manifest); a new test pins the telemetry-only outcome (manifest → L1 ungoverned / L2
  governed, no business_signals). Twice-green backend (1403); **no webapp / no
  `src/tessera/observability/` change**. Branch `claude/step-7-tto` off merged main
  `b3273e20`. Next: the OFF-CHRONO platform completion (per the ruling below), then the
  chrono'd hello-agent onboarding.

- 2026-07-08 — **Step-7 design-gate ruling (pre-authorized by the review, so the run need
  not halt again).** The pivotal unknown (what cockpit-readable fact L1 reads, and whether
  an OTLP-only agent can produce it) will likely surface a REAL platform gap: the §7
  remote-profile ingestion (span-events → stores the resolver reads) was named by the ADR
  but never built by any step. Ruling: (1) **generic platform completions are ALLOWED and
  OFF-CHRONO** — they are the platform finishing its own remote profile, a one-time
  capital cost, recorded as clearly-labelled "platform completion" commits (preferred
  path: the level resolver gains a turn-evidence read through the EXISTING
  `spine/adapters/langfuse.py` seam — traces are already the canonical turn-detail home
  per 0015; metrics via collector prometheus-exporter config). (2) **What stays forbidden
  and breaks acceptance: any agent-SPECIFIC control-plane code** (no `if agent_id ==
  "hello-agent"` anywhere). (3) The acceptance criterion is refined accordingly — **zero
  AGENT-SPECIFIC cockpit diff**; the TTO chrono measures hello-agent's MARGINAL onboarding
  on the completed platform. (4) This refinement is recorded in ADR 0017 at step-7 closure
  (a §Phase-F precision), with the platform-completion commits listed — the honest
  accounting: the FIRST external agent flushes out one-time gaps; the SECOND one is the
  true zero-diff proof, noted as the standing acceptance property.

- 2026-07-08 — **Lot 6c review: APPROVED — step-6 MERGE FEU VERT.** Verified: `blocked_by`
  machine-readable driving truthful labels (+ the sibling lie found and fixed:
  Release-Control tallied level-blocked agents under "Prêts à promouvoir"),
  `require_bearer` 1→7 on the routes file (all business reads at snapshot posture,
  /security-review clean), `evidence_source="business_events"` at the descriptor.
  **Notable discovery, logged as the LAST big perf debt: the FE has NO snapshot client
  at all** — the 0015 batched endpoint is unconsumed; the backend fold makes the fan-out
  foldable, the FE client slice (collapse the historic 24-37 queries → 1) is owed as its
  own slice. Merge protocol: twice-green on merged tree, ledger union, push. Then
  **step 7** — `examples/hello-agent` (decides the open question), pure OTLP, zero
  tessera imports, AgentSpec entry + config-only wiring (counted in TTO), acceptance =
  fleet card with computed L1 + **zero-line cockpit diff** + TTO chrono vs the ≤½-day
  target, recorded here and in ADR 0017.

- 2026-07-08 — **Lot 6b review: APPROVED — GO 6c, 2 requirements ride along.** Verified:
  `resolve_observability_level` single-source (business_capabilities → lifecycle/release),
  `REQUIRED_TURN_SPAN_ATTRIBUTES` homed in semconv (control plane reuses the L1 contract
  without importing the SDK — testkit re-exports). Review answers to the 3 flagged
  points: (1) coverage-from-business-event-Scope accepted as the honest available proxy,
  **REQUIRED: the user-facing label/description must state the evidence source**
  (« couverture Scope — événements métier »), never imply span coverage; future widening
  to span stores (Phoenix/Langfuse reads) logged as optional; (2) canary
  declared-not-faked accepted — the scheduled synthetic execution is a named runtime
  piece for later; (3) **REQUIRED: the blocked-state label must not say "eval-gate" when
  an L-level condition blocks** — specialize or genericize (« Bloqué » + reason), same
  honest-label rule as everywhere. 6c = auth + snapshot fold, with a /security-review
  pass on the auth diff.

- 2026-07-08 — **Lot 6a review: APPROVED — GO 6b.** Verified on pieces:
  `_FROZEN_EXCEPTIONS = frozenset()` (ratchet 5→0, bidirectional guard intact),
  `spine/runtime.py` = pure Protocol port (zero runtime imports; agent adapter installs
  at `build_app`, honest-empty on cockpit-only deploy), SDK at `agent/sdk/` with testkit
  (span-contract 103 + grammar-conformance 104) and generate-and-diff enum codegen
  (0018-C). Decisions: **push the branch** (backup, not merge); no separate code-review
  pass for 6a (targeted review + twice-green suffice — /security-review reserved for 6c,
  which touches auth); **ADR 0017 erratum** (the §7-area claim that `instrument.py`
  imports langgraph is inaccurate — only `graph_topology` did) = one-line doc fix riding
  6b; **owed slice logged**: FE drawer-task/artifact-family enums stay hand-owned until
  the manifest declares the domain aliasing (then codegen absorbs them). Base 40dadade
  acknowledged (strict superset of ac18d8bc — the dev-tooling commits).

- 2026-07-08 — **step 6 lot 6c done → step 6 CLOSED** (`7f80682d`→`a3d19604`, 4 commits;
  ledger this commit). Discharges the two operator rulings + the RBAC/anti-fan-out alignment.
  **(A) RBAC — `require_bearer` on the business read routes** (`7f80682d`): the four business
  surfaces (`/observability/{business-events, business/capabilities, business/runs,
  quality-nets}`) gain the route-level `Depends(require_bearer)` gate the `/observability/snapshot`
  route already carries — no-op without a token (CI/dev), constant-time enforcement with one, on
  top of the global `AuthMiddleware`. **`/security-review` on the auth diff: clean** (no findings
  ≥8 confidence — a strict tightening: no new sink, the one new data-returning capability reaches
  only already-authenticated code paths). **(B) Honest block label — Point 3** (`f35560ec`): a
  "Bloqué (eval-gate)" shown when the L-level is what blocks was the soft-lie class we've been
  eradicating. Specialized: `ReleaseDecision` carries a machine-readable `blocked_by`
  (`eval_gate` | `observability_level` | None) via `_blocked_by`; the state label reads
  "Bloqué (eval-gate)" ONLY on a real gate failure, else **"Bloqué (niveau d'observabilité)"**
  (new `s_blocked_level`, fr/de/en). `release_control`'s summary KPIs now count from the
  level-aware lifecycle tone, so a level-blocked agent (eval-gate passed) is counted blocked —
  never miscounted "ready to promote"; the FE summary label **"Bloqués (eval-gate)" → "Bloqués"**
  (the count aggregates both causes). `allowed` logic unchanged; `blocked_by` is a plain zod-stripped
  extra key on the FE (no breakage). **(C) Coverage names its source — Point 1** (`54a78cb7`): the
  Scope-dim proxy is accepted as the honestly-available evidence PROVIDED it says its source —
  `coverage_descriptor` (92) now carries `evidence_source="business_events"` +
  `measures="scope_dimensions"` (both branches) + a docstring stating the proxy and the future
  span-store option; **no rendered lie existed** (quality-nets has no FE consumer — honesty is at
  the descriptor). Point 2 (canary declared-not-simulated): accepted as-is, no change. **(D) Fold —
  business_capabilities into the batched snapshot** (`a3d19604`): declared (AGENT+TIME,
  fact=`business_events`) + registered with a read calling the SAME `business_capability_aggregate`
  as its route (**never two sources** — parity test asserts snapshot == route across agents), OFF
  the default hot path (`in_snapshot=False`) as a probe (`?signals=business_capabilities`) so it
  never inflates the snapshot p95 budget; FE `signal-registry` mirrors it. **Honest scope boundary:**
  the backend fold makes the aggregate available through the one batched pass, but the Métier
  **FE** still fetches the route directly — no snapshot client exists on the FE yet (pre-existing
  gap). The fan-out is now *foldable*, not yet folded at the FE call site; building the FE snapshot
  client is a separate slice, not smuggled into 6c. **Twice-green** (identical ×2): backend
  ruff/format/mypy(274)/pytest **1402**; FE tsc/biome(changed)/vitest **78**. **Only step 7 remains**
  (out-of-process demo agent + TTO). Merge to main is a separate operator-gated action.

- 2026-07-08 — **step 6 lot 6b done** (`301eee8a`→`a6633cf4`, 2 commits): A2.4 + the
  manifest-generated quality nets. **A2.4 — the observability level is a release-gate
  condition** (not a parallel lifecycle): `agent_lifecycle.release_decision` now blocks
  (1) **production below L2** and (2) any agent declaring external effects
  (`requires_validation` / `external_action`) that is not **L3**; `required_level` is L3 if
  external else L2-in-prod else none, so non-prod ungated agents are unchanged (existing
  tests preserved). The level is resolved once by a new canonical
  `business_capabilities.resolve_observability_level` (+ `declares_external_effects`), reused
  by the gate — one source for the number; `ReleaseDecision` carries `observability_level` +
  `required_level` into the API and the S1 audit event. Verified: recouvrement → required L3,
  level L3 → releasable. **Quality nets from the manifest** (`observability/quality_nets.py`,
  registry-seam only): `coverage_descriptor` (signal 92) measures the fraction of the required
  turn-span Scope dims the agent actually stamps from its most recent business event
  (honest-empty `no_evidence` when none — never a fabricated %); `canary_descriptor` (signal
  94) gives the manifest's target workflow(s) + last-observed-turn freshness (fresh/stale/never
  from replay bundles) — scheduled synthetic execution is the runtime piece, declared not
  faked. Served at `GET /observability/quality-nets?agent=` (null for un-manifested). One-source
  move: `REQUIRED_TURN_SPAN_ATTRIBUTES` relocated into `semconv.py` so the boundary-scanned
  control plane reuses the L1 contract WITHOUT importing the agent SDK (span_contract
  re-exports). Verified: recouvrement coverage 100 %, canary fresh. **Twice-green** (backend
  delta, ×2): ruff/format/mypy(274)/pytest **1396**. **Erratum shipped with this ledger**: the
  §Context claim that `instrument.py` imports langgraph is corrected (only `graph_topology`
  named it, in a type hint; `instrument` wraps LangGraph nodes). **6c owed:** require_bearer on
  every business route + business signals folded into the batched snapshot (p95 budget + probe,
  never two sources) — `/security-review` reserved for it (auth surface). **HALT for Claude
  review before 6c.**

- 2026-07-08 — **step 6 lot 6a done** (`baff0231`→`9126c3de`, 5 commits): 0017 Phase E SDK
  extraction + 0018-C/D. Branched `claude/step-6-sdk-conformance` off **main `40dadade`**
  (the run plan cited a stale `ac18d8bc` — 2 dev-tooling commits behind; `40dadade` is the
  current `main` and a strict superset). **The ratchet is the proof: `_FROZEN_EXCEPTIONS`
  5 → 0** — the control plane now imports no part of the agent runtime (ADR 0017 §1
  achieved). (1) `instrument.py` → `tessera.agent.sdk` (off the boundary-scanned tree; §7
  "two profiles, one wire"), all 7 importers repointed, the scanned `observability/__init__`
  re-export dropped. (2/3) the three route imports (reporter/router/graph) moved behind a new
  spine port `observability/spine/runtime.py` (`RuntimeProvider` Protocol + honest-empty null
  default, **no agent import in the scanned module**); the agent-side adapter
  `agent/telemetry.py` lives outside the scan and installs at `main.build_app()`;
  `graph_topology.py` → `tessera.agent.sdk`. `/observability/sandbox-config` +
  `/observability/graph-topology` now read the port — behavior preserved (verified via
  build_app: real 3477-char FR prompt / policy count 13; real fingerprint 9 nodes/17 edges;
  cockpit-only deploy serves honest-empty). **(4) Conformance testkit** (`tessera.agent.sdk.testkit`,
  §7/0018-D): `span_contract` (signal 103, L1 — full Scope dims, keys sourced from
  `stamp_turn_dimensions`) + `grammar_conformance` (signal 104, L3 — the 13-name grammar +
  strict PII-free payloads via a new public `business_events.validate_business_event` +
  `GRAMMAR_EVENT_NAMES`), each `verify_*`/`assert_*`; 13 tests incl. drift guards tying each
  contract to its authoritative source + a stray-payload-key (PII) rejection. **(5) Enum
  codegen (0018-C):** `agent/codegen.py` + `scripts/generate_agent_enums.py` generate
  recouvrement's backend `Literal` + FE union from the AgentSpec capability ids; FE
  `RecouvrementBackendIntent` now aliases the generated union (single source); a
  generate-and-diff test gates committed == regenerated == live manifest. **Twice-green**
  (delta clean, ×2): backend ruff/format/mypy(273)/pytest **1379**; FE tsc/biome(changed)/vitest
  **78**. **Scope/honesty notes:** `instrument.py` did NOT actually violate the boundary (only
  `graph_topology` did, via its `TYPE_CHECKING` `AgentState`/`langgraph` hints) — moved per §7
  grouping; ADR line 210's claim that `instrument.py` imports langgraph is inaccurate (flagged).
  The drawer-task/artifact-family FE enums stay hand-owned (domain aliasing/grouping not 1:1
  with capability ids — owed a manifest-mapping slice). Canaries (94) + coverage (92) + A2.4
  release gate are **6b**; require_bearer + snapshot fold are **6c**. **HALT for Claude review
  before 6b.**

- 2026-07-08 — **Reference-server migration after the park-under-live-server break.** The
  step-4 closure parked `agents/codex` while its dev servers (front `:3097`, back `:8099`)
  were **live** → the worktree reverted under the running Next watcher and
  `recouvrement-product-experience.tsx` lost `@/lib/recouvrement/artifact-status` (Module
  not found). Fix: restored the worktree (branch already merged — zero loss), then
  **migrated the reference servers to the `main` checkout** (`tessera/`, stale `.next`
  cleared): backend `:8099` (uvicorn, cwd `tessera/`), frontend `:3097`
  (`PORT=3097 pnpm dev`) — the operator's browser now reflects `main`. `agents/codex`
  re-parked on `codex/parking`. Convention engraved in Preconditions above (3rd of the
  "process-state vs git-state" family — sandbox `index.lock`, mv-broken `.pth`, now this):
  **every worktree mutation (checkout/park/remove) is preceded by a live-process check
  (`lsof`)**; reviewing unmerged work = a temporary server on another port from the agent's
  worktree, killed after validation.

- 2026-07-08 — **step 4 CLOSED → merged to `main` (`844fa775`), pushed to origin.**
  Executes the checkpoint-4 feu vert (next entry), on Amadou's checkpoint-3 visual
  sign-off (given). `codex/step-4-metier` merged `--no-ff`; the only conflict was this
  ledger, resolved by **union** — all 12 review-side + 9 executor-side Log entries kept,
  common tail deduplicated (verified 31 entries, 0 markers). Full gate **twice-green on
  the merged tree**, identical both runs: `ruff` / `ruff format --check` (507 files) /
  `mypy src/tessera` clean (264 files — the old `replay.py:92` debt is gone on main) /
  **pytest 1362 passed** (50 integration deselected); FE `tsc` clean / `biome` 27 warnings
  = documented baseline, no new findings / **vitest 78 passed**. **Frontend standardized
  on pnpm** (`c165be72`, rides the merge): `pnpm@9.15.0` is the declared packageManager, so
  `pnpm-lock.yaml` is committed (verified in sync via `--frozen-lockfile`) and the
  redundant `package-lock.json` removed; devcontainer `postCreate` switched `npm ci` →
  `corepack pnpm install --frozen-lockfile`. **Correction to the checkpoint-4 note:** it
  read "NO lockfile is tracked" — in fact `package-lock.json` *was* git-tracked (npm the
  de-facto installer despite the pnpm declaration); this merge removes it, ending the
  dual-lockfile split. Housekeeping: `agents/codex` worktree parked (codex resumes on a
  clean machine); the ~13 MB untracked `docs/ui-reference/…/Crédit Aurore · Mes comptes`
  saved page in the main worktree was **left untouched** (not part of step 4 — owner's
  call).

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

- 2026-07-07 — **step 4 / lot 3 dissolution implemented (HALT before main merge).**
  The transitional recouvrement-runs aliases are gone, generalised to the ADR 0017 business-runs
  read. **Removed:** the hardcoded `recouvrement` tab of the Qualité IA dashboard (`TAB_DEFS` +
  `recouvrementRuns` query + render branch + `TAB_META` icon + the now-unused `WorkflowRunsPanel`
  / `fetchBusinessRuns` imports + `quality.tabs.recouvrement` in fr/en/de), the
  `recouvrement-runs-panel.tsx` shim, the `fetchRecouvrementRuns` client alias, and the backend
  `/observability/recouvrement-runs` route + `observability_recouvrement_runs` handler.
  **Migrated:** the backend test now drives `observability_business_runs(agent="recouvrement",
  workflow_id="recouvrement_collections_v1", …)` (renamed `test_observability_business_runs_…`);
  the frontend `fetchRecouvrementRuns` client test → `fetchBusinessRuns({agent, workflowId, limit})`
  (same `/observability/business/runs?…` URL asserted); `recouvrement-runs-panel.test.ts` rehomed to
  `workflow-runs-panel.test.ts` (generic-panel assertions). Grep for `recouvrement-runs` /
  `fetchRecouvrementRuns` / `RecouvrementRunsPanel` / `observability_recouvrement_runs` → **0 code
  hits** (only a doc comment). **Dissolution proof:** Qualité IA tab strip is now 6 tabs, no
  Recouvrement — `/tmp/tessera-ck3-qualite-dissolution.png`. Twice-green: backend
  ruff/format/`mypy src/tessera`/`pytest -m "not integration"` (1362); frontend `tsc` / `vitest`
  (78, panel test rehomed) / `biome check .` (27 warnings, 0 new); repeated identically green.
  **Checkpoint-3 captures re-produced from this worktree** (`:3097`/`:8099`) for Amadou:
  `/tmp/tessera-ck3-flotte.png` (recouvrement card north-star chip `Respect des fenêtres de contact
  100%` + `10 métier en attente`), `/tmp/tessera-ck3-a-traiter.png` (Métier-sourced OperatorItems —
  `Action bloquée · RC-2048`, Approbations 9/32 %, "Métier a signalé RC-2048"),
  `/tmp/tessera-ck3-conformite.png` (posture réglementaire surface). **HALT before any merge to
  main** — checkpoint-4 merge feu vert is Claude's, after Amadou's checkpoint-3 visual validation.

- 2026-07-07 — **step 4 / lot 2 code-review carry-over 2: BR-01 §5 wired on the Métier tab.**
  Conformité to the rails registry v1.3 (`Tessera_private/registre-rails-temporels.md` §5): the
  Métier surface is now a §5-compliant consumer of the global temporal state, **not** a signal
  scrubber (SR-01 keeps signal-time). (a) **Deep-link** — capability + drilled-down run selection
  derive from the URL (`?capability_id=…&turn_id=…`), never local state: `agent-metier.tsx` drops
  the `selectedCapabilityId` `useState`, reads both params from `useSearchParams`, and writes them
  via `router.replace({pathname, query}, {scroll:false})` (i18n navigation); `WorkflowRunsPanel`
  gains optional controlled props (`selectedTurnId`/`onSelectTurn`) so the run is URL-derived while
  the quality dashboard keeps its uncontrolled selection. (b) **Mode indicator** — a `TemporalMode`
  badge shows `Live` by default and `À une date · <instant>` when a global T is posed (new
  `agentMetier.temporal.{live,asOf}` in fr/en/de). (c) **As-of propagation** — the global instant
  (URL is source of truth via new pure `lib/metier-temporal.ts`; the cockpit temporal-context
  singleton follows the user) is forwarded as `at` to both `/observability/business/capabilities`
  and `/observability/business/runs`, is part of each query key, and freezes the 5 s polling when
  set; `metier/page.tsx` SSR-prefetches under the as-of-aware key. **Live API proof** (codex
  backend `:8099`): `…/business/capabilities?agent=recouvrement` → L3, 132 events, `as_of=null`;
  `…&at=2027-01-01…` → L3, 132 events (echoed `as_of`); `…&at=2020-01-01…` → L2, **0 events**
  (honest-empty at T); runs `…&at=2020-01-01…` → 0 runs — the as-of read is real, not cosmetic.
  New tests: `lib/metier-temporal.test.ts` (5, pure resolver) + `components/agent/agent-metier.test.ts`
  (4, §5 wiring guard). Frontend-only; Python gate unaffected (1362). Twice-green: `tsc` clean,
  `vitest` 78 passed (+9), `biome check .` 27 warnings (0 new), repeated identically green; Python
  `pytest -m "not integration"` 1362 confirmed green. **Visual proof** (codex worktree `:3097`,
  authenticated admin): `/tmp/tessera-ck3-metier.png` (badge `• Live`, first capability),
  `/tmp/tessera-ck3-metier-deeplink.png` (`?capability_id=propose_schedule` selects the capability
  and drills into its 12 runs), `/tmp/tessera-ck3-metier-asof.png` (`?asof=2027-01-01…` flips the
  badge to `À une date · 01/01/2027 01:00`, reads still honor the instant).

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
