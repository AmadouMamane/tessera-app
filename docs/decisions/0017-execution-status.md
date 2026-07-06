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
| 3 | 0017-B + A2.1 + A2.3: AgentSpec v1 (schema, CI validation, generation of SignalSpecs + FE mirror + level badge); typed envelope `actor`; declared policy metadata; recouvrement declares the first manifest | [auto] | ⬜ pending | — | recouvrement = first L3 candidate |
| 4 | 0017-C + A2.2 + 0018-B: Métier tab (per-capability table primary, runs drill-down), fleet north-star chip, À traiter source, Conformité projection; canonical artifact lifecycle mapping; delete the hardcoded tab | [supervised] | ⬜ pending | — | gate: recouvrement fully re-homed |
| 5 | 0017-D: owned ClickHouse `business_events` table; dual-write → backfill → shadow parity → flip `BusinessEventStore`; erasure probe | [auto] | ⬜ pending | — | G4 discipline. **No dependency on step 4** (UI): an autonomous run may execute 3 → 5 and halt before 4 (supervised) and 6 (review of 3 wanted first) |
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

## Log (newest first)

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
