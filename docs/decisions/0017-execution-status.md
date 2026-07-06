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
| 2 | 0017-A + 0018-A (freeze): import-linter contract (cockpit ⊄ `tessera.agent.*`/`langgraph`); generalise `/observability/business/runs?workflow_id=…` + `<WorkflowRunsPanel>`; stamp `grammar_version`; extract TurnInput/TurnResult protocol; acceptance tests over the existing runtime | [auto] | 🟡 implemented — host gate pending | — | Boundary shipped as a **stdlib AST ratchet test** (`test_observability_boundary.py`, exact-set equality, 5 frozen exceptions → Phase E), no new dependency. Generic read `_business_runs_response` + `/observability/business/runs`; `recouvrement-runs` = thin alias (same fn name/signature — existing tests untouched). `GRAMMAR_VERSION` stamped on the envelope. `turn_contract.py` + 5 acceptance tests. FE: `WorkflowRunsPanel` (copy via props), shim + `fetchBusinessRuns`, dashboard rewired, URL expectation updated. Owed debt fixed: `signal-registry.test.ts` synthetic ids realigned post-demotions. Sandbox-verified: `tsc --noEmit` green, `py_compile` green, boundary test dry-run PASS. **Sandbox cannot run ruff/mypy/pytest (py3.12 host venv) nor biome/vitest (darwin-arm64 binaries) → twice-green gate runs on the host, then targeted commit.** |
| 3 | 0017-B + A2.1 + A2.3: AgentSpec v1 (schema, CI validation, generation of SignalSpecs + FE mirror + level badge); typed envelope `actor`; declared policy metadata; recouvrement declares the first manifest | [auto] | ✅ done | `3011bac` | AgentSpec = pydantic `extra="forbid"` block in `tessera.agent.agentspec` (a manifest is an API: malformed→ValueError at load), re-exported through `tessera.agent.registry` (the boundary-allowed seam). Referential integrity + ≤1 north_star + **A2.2 outcome-undeclarable** enforced. Recouvrement's first manifest: 5 capabilities, 4 policies (metadata only — impls stay code), scorer `recouvrement.collections.v1`, 10 business_signals (north-star `contact_window_compliance`; `engagement: legal` on contact/validation compliance). A2.1 actor = closed vocab enforced at emit. Generation: `agentspec_projection` computes **level L0–L2 from facts** (None when un-manifested; L3=Phase C) + business-signal descriptors; fleet stamps `level`, card/row render honest-empty LevelBadge. FE mirror: business signal ids in `signal-registry.ts`, `FleetSchema.level`, capability/policy label_keys in fr/en/de. CI gates: `test_agentspec` (schema), `test_agentspec_conformance` (declared business_score keys ⊆ scorer-produced; manifest label_keys ∈ every locale — the i18n sweep is now a manifest-label gate), `test_business_event_actor`. Twice-green: ruff/format/pytest 1323/tsc/biome(changed)/vitest 69. **Deferred to step 4 (supervised):** north-star chip render, per-agent generated FE mirror, Métier tab (Phase C). **Inherited debt untouched:** mypy `observability/replay.py:92` (from antigravity merge `6c1a0db`; `replay.py` left alone per protocol) — blocks a clean `mypy src/tessera`, so **main merge withheld** until it is resolved by its owner. |
| 4 | 0017-C + A2.2 + 0018-B: Métier tab (per-capability table primary, runs drill-down), fleet north-star chip, À traiter source, Conformité projection; canonical artifact lifecycle mapping; delete the hardcoded tab | [supervised] | ⬜ pending | — | gate: recouvrement fully re-homed |
| 5 | 0017-D: owned ClickHouse `business_events` table; dual-write → backfill → shadow parity → flip `BusinessEventStore`; erasure probe | [auto] | ⬜ pending | — | G4 discipline |
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

## Log (newest first)

- 2026-07-07 — **step 3 done** (`3011bac`): AgentSpec v1 + A2.1 actor + A2.3 policy metadata;
  recouvrement declares the first manifest; level L0–L2 computed from facts; twice-green
  (my delta clean across ruff/format/mypy/pytest/tsc/biome/vitest). Baseline finding: the
  branch inherited a pre-existing `mypy` error at `observability/replay.py:92` from the
  antigravity merge (`6c1a0db`, commit `b2e7b53`); `replay.py` is left untouched per protocol,
  so `mypy src/tessera` is not clean and **the main merge is withheld** for the owner to fix.
  Frontend deps install via `npm ci` (package-lock.json; no pnpm-lock despite the
  `packageManager` field). Proceeding to step 5 (independent of step 4).
- 2026-07-06 — file seeded; steps 0–7 defined; branch inventory produced (4 real conflicts,
  13 duplicate-identical files, business-events stack is codex-only, i18n codex-only).
