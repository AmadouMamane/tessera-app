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
| 7 | 0017-F: out-of-process demo agent (pure OTLP, no LangGraph) reaches L1 with a **zero-line cockpit diff**; TTO measured and recorded here | [auto] | ✅ done | Lot0 `1e71f9c6` · platform `58d8b720`→`639b6403` · hello-agent (this branch) | **ADR 0017 COMPLETE.** Branch `claude/step-7-tto` off merged main `b3273e20`. Off-chrono: Lot 0 (support-client/onboarding telemetry-only manifests → computed L2/L2) + platform completion (L1 evidence-backed via Prometheus turn-count read + collector prometheus-exporter). Chrono'd: `examples/hello-agent/` (pure OTLP, zero tessera import) → fleet card **L1 computed from real `tessera_agent_turns_total`**, span-contract testkit green, **zero AGENT-SPECIFIC cockpit diff** (webapp empty; observability generic). **TTO = 20m18s** (≪ ½-day target). ADR Status → accepted — implementation complete. **HALT: final Claude review before merge to main.** |

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

- 2026-07-14 — **`/observability/fleet` answered 500 when there was nothing to observe.** The
  component whose entire job is to observe could not observe its own absence of data — the
  project's disease, in the component that sells the cure. Landed `54756402` + `ca67f31c`
  (twice-green on one tree).

  **The cause is not the one the symptom suggests.** The handler read
  `{"available": True, **await compute_fleet(lang)}` inside a `try/except`. `compute_fleet`
  **did not raise** — so the `except` never saw it. It returned, correctly, `release=None` (no
  eval has ever run) and `level=None` (no manifest): the honest-empty its own comments insist on
  (*"None … → honest-empty, not 'L0'"*). But the `response_model` had been **generated from 31
  live samples** in which every agent happened to have both, so those fields were declared
  required and non-null. FastAPI validated the RESPONSE, matched neither arm of the union — not
  `FleetPayload` (nulls where non-null was promised), not `FleetUnavailable` (`available` is
  True) — and raised.

  > *A `try`/`except` catches an exception. A partial-but-successful return walks straight past
  > it. And a SAMPLE shows what WAS there; it can never show what is ALLOWED to be absent.*

  **The contract is true by construction now.** `compute_fleet` returns a `FleetData` TypedDict
  (and `AgentRelease.as_dict()` a `ReleaseFacts`, typed at its source), so a missing or mistyped
  field is a **mypy error at build**, not a 500 at runtime; the route CONSTRUCTS the model rather
  than splatting a dict. `**business_facts` is spread by hand for the same reason — a `**` of an
  untyped dict is a hole mypy cannot see through, and this whole bug is a shape nobody checked
  reaching the wire. The schema now says what the code always did: `| None`, and deliberately
  **without a default** — nullable is not optional, the key must still be PRESENT, because
  `available: True` guaranteeing a complete payload is the entire point of the union.

  **`available: false` here would have been a second bug.** An agent that has done nothing is a
  FACT worth rendering. Three states, three answers: data (even all-zero) → `available: true`
  COMPLETE (the operator of a fresh install still sees their fleet); the read failed →
  `available: false`, logged as a failure; the payload breaks its own contract → `available:
  false` **too**, but logged as a **CONTRACT BREAK** — a bug in us, not an absence of data, and
  it must not drown in the ordinary empty. Never a 500 either way.

  **And that log line immediately earned its keep.** With the unit ratchet green and the fix
  committed, the route was driven against a REAL virgin install (empty Postgres, empty ledger) —
  and degraded, naming `north_star.evidence.last_checked_at`: declared `str`, returned `None` by
  a producer whose own docstring says *"A metric no run ever produced yields zeros and `None` —
  the genuine zero-data case"*. **The same disease, one level deeper, and only the live render
  could find it**: my fixture's virgin agent had `north_star: None`, so the payload never
  descended into `evidence` at all. *A fixture that stops short of a branch cannot fail on it.*
  Fixed, and the fixture now carries the state the live install is actually in.

  **Verified live** on an empty database and an empty ledger: **HTTP 200, `available: true`, six
  agents served with zeroes**, no contract break. The ratchet is driven through the **real router**
  with a TestClient — never by calling `compute_fleet` directly, because the bug lives in FastAPI's
  RESPONSE validation, which a direct function call does not traverse. A unit test on the function
  was green throughout; that is exactly how this survived. Mutation-tested: restore the raw splat →
  red; restore the non-nullable schema → red; **both (the code as it shipped) → the literal 500 is
  back**.

  **The class is NOT closed, and is not claimed to be.** 64 observability handlers stamp
  `{"available": True, **compute(...)}`; only the **six** with a `response_model` can 500 this way
  (the other 58 have no contract at all — a quieter disease: they serve whatever the compute
  produced and the cockpit silently misses fields). `fleet` is fixed; the remaining **five**
  (`rbac-matrix`, `chrome`, `access`, `agent-evaluations`, `sandbox-config`) are FROZEN BY NAME
  with an asserted count that may only go DOWN, checked against the **AST** so the freeze describes
  the code rather than a memory of it.

  *The AST witness earned its own scar, twice: v1 read the source TEXT and went red on the very
  docstring that explains the bug (the prose quotes the pattern it forbids); v2 forbade the `**`
  splat and went red on the FIX, whose `model_validate({"available": True, **data})` splats too —
  but into a validator. It asks the precise question now: what does this handler RETURN? A brittle
  red is how the next person deletes the assertion instead of fixing the parser.*

- 2026-07-14 — **A branch that lied about its own name, twice — and carried nothing.**
  `claude/fix-gdpr-actor-attribution` (1 commit, `d2ffc00c`) did NOT carry the GDPR actor
  attribution: that had landed long before. It carried **the F-6 audit-sink honesty** — the sink
  that swallowed a missing Cloud Logging provider under a comment reading *"graceful degradation"*,
  and the verifier that green-lit a dead file by answering `ChainStatus(verified=True, length=0)`
  on a store that is never written post-cut. A name that lies is the quietest form of the disease
  this project hunts, so it was renamed to **`claude/audit-sink-honesty`** for what it is.

  **The rename then revealed the second lie: the branch carries nothing.** Rebased onto a fresh
  `main`, git skipped the commit as *already applied*; the branch is **0 commits ahead and
  byte-identical** to the trunk. Its substance was verified on `main` **by content, never by
  ancestry** (the doctrine that cost a live P1): `_emit_cloud_logging` propagates the ImportError,
  `tests/unit/test_audit_chain_independent_of_sink.py` is present, and `cloud_run.tf` declares
  `TESSERA_LEDGER_SOURCE` + `TESSERA_LEDGER_DUAL_WRITE`. `make landed` agrees — *"touches nothing
  origin/main does not already have."*

  There was therefore **nothing to gate and nothing to fast-forward.** A fast-forward of an empty
  branch is a ceremony, not a landing, and reporting one as a landing would have been precisely the
  false green the branch itself was written to abolish. Dead stock; original sha `d2ffc00c` should
  anyone ever want to read the patch that was written.

- 2026-07-14 — **The per-agent table answered a question nobody asked, and the one it was sitting
  under went unanswered.** `AgentBreakdown` had its columns HARDCODED — its own docstring conceded
  "this is the MONITORING facet" — so on `/surveiller/qualite-ia` the banner cried **Fidélité
  71,6 % < 95 % · 19/67 mauvais** and the table directly beneath it, the only surface with a row
  per agent, replied with **latency** and **handoffs**. Not one column could name the agent burning
  the SLO. Landed `b94965da` (the lens + the ratchet) and `04e7ae9c` (reachability + honest
  emptiness); twice-green on one tree at the tip.

  **The engine already knew the answer** — `GET /observability/snapshot` returns, per signal, a
  `report` naming the scope dimensions it HONOURED and those it IGNORED, and `SignalCapability`
  already declares which signals have no per-agent substrate at all. The report crossed the wire
  (it survives zod) and **no component had ever read it.** The columns are now a lens:
  `monitoring` (default, byte-identical everywhere it already rendered — pinned by a
  non-regression test), `alarm` (value · gap to SLO in points · contribution, **sorted by
  contribution descending**), `quality` (fidelity · hallucination · blocking regressions · gate ·
  eval freshness) and `masked`.

  **The ratchet — a number nobody can prove is a number nobody may read.** `selectHonouredSignal`
  is the only door into a lens cell: it yields a value ONLY when the signal's own report declares
  `agent` honoured, and every refusal is a distinct value the cell can name (`not-honoured`,
  `org-wide`, `unavailable`, `no-report`, `absent`, `schema-drift`). **A missing or unreadable
  report refuses too** — a witness that cannot see may never report "ok" (ADR 0026).
  Mutation-tested three ways: swap in `selectSignal` → 5 red; delete the `isOrgWide` guard → red;
  let the masked lens render a table → red.

  **The reconciliation is REUSED, never re-implemented.** `7101bb2a` already put the honest logic
  in the footer, and its comment names the trap: `shared_conversations` alone *reads 0 with
  composure*. The sum of the per-agent slices does NOT reconcile with the org total by
  construction — a handed-off journey touches two agents and counts once for the org — so a column
  where the slices add up exactly would be a **coincidence, not a proof**. The alarm lens prints
  **∑ slices beside the org total** and states the relation (equal, or a named gap in amber,
  pointing at the handoff line below it). Live, on real data, it reads *"∑ contributions par agent
  = 19 · total org = 19 — cohérents sur cette fenêtre"* — true here, and it would have SAID so had
  it not been.

  **Two holes only the live page could find.** (1) The org-wide mask was **unreachable**: the
  loader always asked about `slo`, so `masked` never occurred in production — a tested, real,
  invisible capability. Selecting a row in the signal registry now focuses it (`?signal=`) and the
  server re-plans: click *Efficacité du firewall* → the table masks and says why, and the Fiche
  signal's new **"Décomposable par agent"** row (read from the capability registry, never guessed)
  says *Non — org-wide par construction*. Both surfaces read the SAME descriptor, so they cannot
  disagree. (2) Three of the six live agents have **n = 0 turns**, and their cells rendered exactly
  like a refused read. A measured emptiness is not an unprovable slice; `no-sample` is now its own
  reason, in all three locales.

  **Perf, measured before deciding — not assumed.** Six agents = six snapshot reads: **96 ms cold
  in total, 14 ms warm for all six** (~2,4 ms each; the ADR 0015 read-through cache + single-flight
  do their job). **No batch endpoint was added**: touching the read plan is the review boundary, and
  the measurement says it is not needed.

- 2026-07-13 — **ADR 0026: a witness interrogates the thing, never its neighbourhood. `make
  dev-status` was asking git about a DIRECTORY and printing the answer as if it were about the
  PROCESS.** Landed `ce61a01a` (twice-green, on an **isolated** worktree at the exact commit — see
  the incident below). The operator found it, and he was right that it matters more than the perf:
  it is a hole in the witness this project has depended on all week. `dev-status` ran `lsof` → the
  process's **cwd** → `git -C "$cwd" rev-parse HEAD`, and printed it under a column named `git`.
  Move the checkout under a live server and the witness reports the new sha with total composure —
  which is exactly what it did on 2026-07-13, while the operator's browser paid **1 087 ms** for a
  badge that costs 20 ms and every witness on the machine said all was well. **The fix, and its one
  load-bearing line:** the process hashes the `.py` files **the interpreter actually loaded it
  from** (`Path(__file__).parent` — a checkout, a site-packages install, a container image alike;
  **no git required**), captures it **at import**, and **freezes** it. A value recomputed per
  request would describe the *disk*, and the disk is not the process — that is the original bug,
  re-armed. `/healthz` publishes `code_digest` / `code_sha` / `code_sha_source` / `code_dirty`
  (`version` was the *package* version — frozen for months, and the only thing the endpoint ever
  said about its own code). `dev-status` asks the server, re-hashes the checkout **with the same
  function**, and prints **STALE · RESTART** on divergence. **Verified live**: the server
  recognises itself; slip a file under it → STALE; remove it → green. The OLD `dev-status` printed
  the same reassuring sha in all three cases. **Honest unknowns throughout**: `code_sha = None`
  (never `""`, never a placeholder) when the process cannot know; `code_dirty = None` — never a
  comfortable `false` — when `git status` did not answer; and a server publishing no digest is
  **CANNOT SAY · RESTART**, never `ok`. *A witness that cannot see must report a blind spot.*
  **Ratchet, mutation-tested three ways**: make `identity()` recompute ("it's cheap") → 2 red; put
  `git rev-parse` back in the Makefile recipe → red; declare a silent server healthy → red.
  **The doctrine (ADR 0026, the methodological twin of 0024)** — three guard-rails have now
  reported success over a hole because each asked an ADJACENT question: the gate read a pipeline's
  last line instead of its exit code (`$PIPESTATUS[0]` is empty in zsh); a guard checked a **name
  in a list** instead of calling it with a stranger's request (`require_bearer` in
  `KNOWN_AUTH_GUARDS` → anonymous `DELETE /memory/{id}` got **204**); `dev-status` asked a
  **directory** instead of the server. *A gate reports its own exit code; a guard is what refuses a
  stranger; a server states which code it loaded; a contract is what it honours.*
  **⚠️ INCIDENT, third occurrence, and the ownership marker did NOT stop it:** a second agent wrote
  **11 files** into `agents/claude` while this lot's gate was running — the gate correctly went
  **VOID** (the tree moved underneath it), which is the 2026-07-12 fix working. But `make claim`
  records the agent's **name**, and both writers are called `claude`: **two Claude sessions in one
  worktree recognise each other as legitimate.** The marker identifies a *role*, not a *session*.
  Nothing was destroyed (no stash, no checkout — the 07-12 mistake was not repeated); the verdict
  was taken in a **throwaway isolated worktree at the exact commit**, which is the only honest way
  to judge a tree somebody else is writing to. **Owed: the claim marker must carry a session id.**
  Also owed (pre-existing, found by the isolated run): `gate-py` runs a **Python** test that shells
  out to **biome**, a node tool only `gate-web` installs — so the gate cannot pass in a fresh
  worktree without a manual `pnpm install` first.

- 2026-07-13 — **FIXED, and the trace proves it: `/observability/fleet` 3 938 → 430 ms; the
  event loop is no longer frozen; the cockpit can now explain its own latency.** Branch
  `claude/fleet-perf-spans` (twice-green on the committed tree, `787acbe99e80`). Full write-up
  with every number: **`docs/status/perf-fleet-run.md`**. Headline: fleet **3 938 → 430 ms**
  (×9.2) · chrome, the header of all 32 pages, **3 725 → 714 ms** · **`/healthz` while one fleet
  request is in flight: 3 639 → 5 ms** (×728) · ledger rows materialised per fleet request
  **~206 000 → 3**. The trace cascade went from **1 span, 0 children, nothing attributed** to 32
  named children carrying their row counts. **The third number was never diagnosed and is the
  most important: the reads were synchronous inside an async route, so ONE fleet request froze
  the WHOLE server** — which is also why the operator's `/audit/integrity` read 1 169–7 270 ms
  while the endpoint itself already cost 20 ms: it was queued behind the browser's own polling.
  Cost and event-loop blocking are two different bugs, and making the reads cheap fixes only the
  first. **Order of work, and it mattered: instrument, THEN correct.** Every control-plane store
  read now emits a span with store · operation · duration · **rows materialised**
  (`observability/store_spans.py`). It is that row count — not the duration — that makes an
  O(ledger) read legible, and it found three things nobody had asked for: (1) **chrome was 3 725
  ms** and was not in the diagnosis; (2) **a full 25 716-row read still survives on the chrome
  path** (`incidents.open_incidents()`, 361 ms) — without the cascade I would have shipped chrome
  believing it clean; (3) **the same class, a third time, outside the ledger**:
  `load_eval_snapshot(agent_id)` **parses every eval report and filters by agent in Python**, once
  per agent — six agents, six full parses, and it is now the fleet's dominant remaining cost.
  **The STRONG verifiers were deliberately left alone**: `verify_active_ledger` and État à date
  still re-walk and re-hash all 25 716 rows every time. Six existing tests went red when a first
  draft routed them through the checkpoint, and **they were right**: `ChainStatus` carries no
  provenance, so backing it with a cached proof is "a checkpoint trusted in silence" — the thing
  the checkpoint module's own docstring forbids. The bug was never those functions; it was **the
  health dot and the header bell calling them to extract one boolean**. A health dot asks a weaker
  question ("is there a PROVEN break?") and may pay a weaker price — provided it says so, which
  `active_ledger_verdict` does (it hands back the age of the last full walk, unasked).
  **THE RATCHET (the deliverable), mutation-tested on both levels:** a **row budget** over the
  fixed paths, counted through the instrumentation itself (re-introduce the old scan → red on the
  fleet AND the header bell), and an **AST freeze** on the modules that can materialise the chain
  (a seventh reader → refused by name). **What is NOT claimed:
  `load_ledger_payloads_of_type` is NOT a bounded reader** — it is bounded only when the type is
  RARE, and `tessera.guard.audit` is **24 250 of 25 716 rows = 94 %** of the chain. Pushing that
  filter into SQL *reads* like a fix in the diff and saves ~6 %. **A ratchet keyed on the function
  NAME would have certified a full scan; this one counts rows.** **The class is not closed
  everywhere and the doc says so: 17 request paths still read the whole ledger** — named,
  counted, frozen, and asserted in CI so the debt is a figure that must go down. **⚠️ For the
  operator: the reference backend (:8099) is running code from BEFORE the integrity fix landed**
  (process started 12/07 23:56, fix landed 13/07 08:32) — `make dev-status` reports the git head
  of the *checkout*, not the code the *process* loaded. A restart activates 1 087 ms → 20 ms.

- 2026-07-13 — **PERF: the cockpit's main page reads the ENTIRE audit ledger SIX TIMES per
  request — and the parked P1 became the product's principal cost.** Measured, after two
  wrong Claude hypotheses (see below): `/healthz` 12 ms · `/observability/snapshot` 53 ms ·
  `/audit/integrity` **1 114 ms** · `/observability/fleet` **4 011 ms** · the Prometheus
  turn-evidence query **13 ms** (exonerated). Postgres has sent **413 GB**. **Root cause:**
  `compute_fleet()` calls `_canary_red(aid)` **per agent** → `latest_canary_verdict` →
  `_latest_canary_run` → **`load_ledger_payloads_sync()` which loads all ~29 600 ledger
  entries into memory**, to answer *"what was this agent's last canary verdict?"* — a
  question one indexed `WHERE type=… AND agent_id=… ORDER BY seq DESC LIMIT 1` answers in
  ~1 ms. Plus `_integrity_broken()`, a full chain walk. Six full ledger reads per request,
  **synchronously inside an async route** (it blocks the event loop too — the same class as
  the recouvrement graph bug). The arithmetic closes exactly: 1 full read = 1.1 s, and
  1 + 5 ≈ 4 s. **This IS the `dos-memory` P1 from the 2026-07-10 audit — parked THREE times
  as "not blocking".** It is now the principal cost of the product's main page. **Doctrine:
  a debt deferred as "not blocking" is only not-blocking until the data grows; an
  append-only store guarantees it will.** **Second finding, arguably bigger: the
  observability platform cannot explain its own slowest endpoint.** The Phoenix trace for
  the 3.9 s `fleet` request is **ONE span with ZERO children** — the HTTP layer is
  auto-instrumented, but the control plane's own store reads (Postgres, ClickHouse, ledger)
  emit nothing. The agent runtime is beautifully instrumented; **the cockpit is a black box
  to itself.** A governance tool that does not observe itself applies to others a rule it
  exempts itself from. **CLAUDE'S OWN FAILURES THIS MORNING, recorded:** (1) I diagnosed
  "the machine is swapping" from container names and a 70B model — `/healthz` at 12 ms
  refuted it; (2) I told the operator to `docker stop` the `observability-refinement`
  stack, having inferred "ghost stack from an archived branch" from its NAME — **it is the
  PRODUCTION stack serving his portfolio. He caught it before running it.** I issued a
  destructive command about a system whose purpose I never asked. That is the eighth
  inference-instead-of-measurement of this campaign and the first that would have caused
  real damage. **Rule for myself, engraved: never issue a destructive command about a
  component whose purpose you have not been told.**

- 2026-07-12 — **F-6 finalised (`claude/f6-sink-honesty`, twice-green, merge GO). But the
  finding that matters is a P0 on the PROCESS: a gate result that does not identify the
  tree it ran on is unfalsifiable.** Another agent stashed the executor's uncommitted work
  and switched the shared worktree to its own branch mid-run. Consequence, entirely
  silent: **two `make gate` returned exit 0 on TWO DIFFERENT TREES** (1862 then 1858
  tests). **The "twice" of twice-green assumes ONE tree** — without that guarantee it is
  theatre, and since CI went billing-blocked the local gate has been our ONLY witness. We
  have merged all week on a witness that does not say what it witnessed. **ORDERED,
  IMMEDIATE:** (1) `make gate` prints and records a TREE FINGERPRINT next to its exit code
  — branch, HEAD sha, dirty flag, worktree path; (2) a twice-green is only valid if BOTH
  passes carry the SAME fingerprint — assert it mechanically, do not trust the operator's
  memory; (3) worktree OWNERSHIP is declared (a lockfile or `.owner` marker) and an agent
  refuses to mutate a worktree it does not own — `dev-status` says which checkout a server
  serves, nothing says which agent owns a tree. **This retroactively weakens every
  twice-green claimed since the CI went down** — not a reason to re-run them all, but a
  reason to close the hole before the next merge. **Lot content ratified:** the silent
  `# graceful degradation` fallback in `_emit_cloud_logging` is dead (an operator following
  the runbook got audit entries in a container's stdout and every dashboard on it read zero,
  with no signal); the docs/runbook/Terraform lies are fixed (`cloud_run.tf` now declares
  LEDGER_SOURCE/DUAL_WRITE — what makes production opposable was readable nowhere in the
  infrastructure). **And the symmetric hole nobody had seen — THE VERIFIER:**
  `verify_audit_chain()` on an ABSENT file returns `verified=True, length=0`. After the
  sink cut that file is never written. So verifying `guard.audit_file` certifies **a
  perfect, empty, nonexistent chain** while 25 000 opposable lines are never read. **This
  is the purest vacuous green in the whole corpus: a verifier that verifies nothing and
  says "verified".** The trap was not armed (all surfaces go through
  `verify_active_ledger` — the executor alarmed himself, VERIFIED BEFORE REPORTING, and
  said "I was wrong"), but nothing forbade it and the primitive carries the obvious name.
  Now forbidden by ratchet. Proofs against the real store: 4 sinks → chained (seq
  29622-29625, prev_hash resolving), `verify_active_ledger()` → 25 509 lines verified,
  append-only intact. Chance did better than staging: `cloud_logging` failed honestly on
  its own (no ADC creds) **and the entry was chained anyway** — both rules proven at once.

- 2026-07-12 — **THE NULL CONTROL: the eval gate has never gated anything.** Lot-0 eval
  (points 1/3/4 done, gate green, `eval/lot0-harness-truth`) produced the most important
  finding of the project. With **every LLM backend unplugged**, the catalogue passes
  **122/174 (70%) in 5 seconds with 0 tokens generated** — the deterministic layers
  (router short-circuits, guard refusals, planner escalations) do the work. So llama3.2's
  "90%" is a **70-point floor + 20 points of model**, and it reads as a model score.
  Worse: a dead backend does not crash the runner — every case completes, the report
  still writes `"model": "llama3.2:3b"` (the CONFIGURED model, never proof of a call),
  and the scorecard shows a pristine 70%. Nothing distinguished *the model is good* from
  *the model is absent*. Measured consequences: **4 of 6 `critical` cases pass with no
  model**; `policy_violation` (15/15) and `escalation_failure` (6/6) pass 100% modelless —
  **zero discriminating power**; and the three domain bars (55/65/55%) are ALL BELOW the
  70% null floor — **no bar can reject anything the guard already passes. The gate is
  vacuous, at the scale of the entire quality claim.** **CLAUDE RULING — the gate scores
  the MODEL'S CONTRIBUTION, never the absolute pass rate** (an absolute rate conflates
  guard + model): (1) **non-regression on the floor** — the model must break ZERO cases
  the null run passes (llama3.2:3b currently breaks 3 → RED today); (2) **positive
  contribution** — the model must pass ≥X of the 52 cases the null run FAILS; (3)
  categories where the null run passes 100% leave the MODEL gate entirely (they are the
  guard's test suite, not the model's) or gain cases the guard cannot handle. The bars
  become a function of the measured floor, never an absolute number. **Doctrine engraved:
  every eval needs a NULL CONTROL. A score without a floor is not a score — it is the
  sum of everything that was already true.** Ratchet shipped (`eval/ratchet.py`): the
  witness that a model spoke is **tokens**, never the `model` field; the null run is a
  committed 174-verdict baseline pinned by exact equality (an improvement fails too — a
  refresh is deliberate and its diff is the proof); half the tests are mutation tests,
  verified. Workflow split: the null control is HERMETIC (no model, no Postgres, no
  secret) → runs on every push, locks 70% of the catalogue for free; the model half moves
  to `workflow_dispatch` on a runner that actually has a model — because `ubuntu-latest`
  has neither Ollama nor Vertex creds, so the nightly replay would have produced not a
  weak verdict but a **false** one. Two self-retracted conclusions, both honest and both
  instructive. **SYSTEMIC CLASS NAMED — silent degradation on malformed declaration.**
  Three instances now, all the same shape: (a) `extra="ignore"` swallowed the wrong Ollama
  field name (`host` vs `base_url`) → the config silently did nothing and 12 649 phantom
  tokens appeared; (b) a mismatched `response_model` **silently erases** the field
  (typing pilot); (c) `audit_sink=stdout` **silently disables** the ledger chain (F-6).
  **In this codebase, a declaration error produces silent degradation, not a loud
  failure.** That is the systemic vulnerability class — it deserves its own sweep
  (`extra="forbid"` on settings; fail-loud on unknown keys) and it is the thread that
  connects F-6, the typing pilot, and this finding.

- 2026-07-12 — **P0 STILL OPEN — third audit (Fable) is RIGHT, and it is worse than
  reported. CONFIRMED by Claude line-by-line.** `POST /recouvrement-assistant/{message,
  action}`: the backend router is mounted BARE (`APIRouter(tags=[...])`, zero
  dependencies, `main.py:351`) and `requested_by: str = Field(default="Julie Dubois")`
  takes the ACTOR from the request body. The laundering path is NOT the `[...path]` BFF
  (that 404s this head) — it is a **dedicated Next handler**
  (`app/api/recouvrement-assistant/message/route.ts`) that performs **no session check at
  all**, takes the raw body, and forwards it to the backend **with the service bearer
  attached** (`backendHeaders`). So an anonymous visitor, from a browser, on the front's
  public origin, executes a governed workflow — and the opposable ledger records whatever
  actor the caller typed. **This is not merely an auth hole: it is a LEDGER INTEGRITY
  hole.** The hash chain, anti-fork index and RFC-3161 seal make the record tamper-evident
  AFTER the write; a caller-declared actor produces an entry that is perfectly chained,
  perfectly sealed, and LYING ABOUT WHO ACTED. A lie written through the front door is
  worse than tampering — tampering is detectable. **Claude owns the miss:** I hardened the
  CONTROL plane (the 26 observability mutations) and left the BUSINESS plane wide open —
  the same `provenance ≠ identity` class I had just engraved. We fixed 26 routes and never
  fixed the PATTERN that let a 27th exist unguarded. **The fix must be plane-correct, not
  the obvious one:** `require_operator` would be WRONG here (control-plane gate; would
  conflate the planes ADR 0013 separates). recouvrement's console is the BUSINESS plane
  (`dedicated-ui`, `collections` tier, ADR 0010 Phase C) — and `operator.py:163` already
  knows that surface. Fix = (1) backend router behind a business-plane dependency
  resolving a verified `collections` identity from the signed assertion; (2) **delete
  `requested_by` from the request model entirely** — a field naming the actor must NEVER
  be caller-supplied, it is derived server-side from the verified session; (3) the Next
  handler verifies the session + role BEFORE proxying, and forwards the assertion — it must
  never launder an anonymous call with the service bearer. **(4) CLOSE THE CLASS, not the
  instance: a ratchet that enumerates every mounted router and FAILS if any lacks a
  plane-appropriate guard.** That ratchet is the real deliverable — without it there will
  be a 28th. Two independent audits (opus, Fable) also converge on the unmet CLAUDE.md
  non-negotiable (an upstream `mcp-firewall` PR, no trace) and on the visibility thesis
  (close the P0 → go public → the CI/branch-protection/0010 tripwires all resolve at once).

- 2026-07-11 — **Backend-typing PILOT (fleet, `dc820593`) RATIFIED — pattern approved,
  scale-up gated on three rulings below. THE FINDING THAT JUSTIFIES PILOTING: a wrong
  `response_model` does not fail — it SILENTLY REMOVES the field.** FastAPI filters the
  response through the model: the executor's first pass modelled `available` as a union
  everywhere (the obvious reading of the name) and FastAPI silently erased **20 fields per
  agent on the flagship route** — no exception, no log. Root cause: `available: false`
  carries TWO meanings under one key — degradation (honest-empty, 1 key ⇒ discriminated
  union) on 16 routes, and "eval not run" (a plain boolean, 20 keys either way) on
  `agents[].release`. **Doctrine: typing a backend is a DATA-LOSS risk surface, not a
  validation one. Never type a route without the byte-identity round-trip ratchet — it is
  the only thing that catches the silent erase, and it is why models must be derived from
  observed live responses (123 sampled), never from a plausible reading of the code.**
  **CLAUDE CORRECTION #4 (owned):** my brief asserted the front does `as` casts on raw
  JSON (from the audit's `validation-gap`). FALSE — zero casts; the front already
  validates with hand-written zod and `request()` throws on divergence. The real gap runs
  in BOTH directions: 13 of 14 schemas model an all-optional union (they would accept a
  backend that lost `agents` entirely — validation in name only), and ONE errs the other
  way. Fourth time this campaign I asserted from inference where the executor measured.
  **LIVE BUG, own lot, fix now:** `AccessOverviewSchema` REQUIRES every field, so the
  degraded `{available:false}` response makes zod throw and the page break — it breaks
  exactly when the store is down, i.e. when the honest-empty response exists precisely to
  keep it standing. The pilot found it; un-wiring the generated module left it live on
  main. **RULING Q1 — front and back migrate TOGETHER, one domain per lot.** A generated
  schema nothing consumes is dead weight that drifts. The "9 files must handle
  `available:false` explicitly" is not a cost, it is THE POINT: those files currently
  pretend degradation cannot happen. Honest-empty enforced by the type system is this
  project's own thesis applied to the type layer. **RULING Q2 — closedness is decided by
  the PRODUCER, never by the observed sample.** Three categories, evidence per field:
  (a) closed by code construction (backend Enum/Literal/exhaustive branch) ⇒ declare
  `Literal[...]`; mypy then guards any new branch. (b) closed by manifest declaration
  (capabilities, signal catalog) ⇒ GENERATE the enum from the manifest (0018-C precedent;
  never hand-written). (c) open (data, config, store, LLM output) ⇒ stays `str`. Key
  consequence: where the hand zod's 97 enums cover an OPEN domain they are the *same bug
  class as AccessOverviewSchema one level up* — a validator that rejects reality. So the
  apparent "precision regression" is sometimes the removal of a FALSE CLAIM. Never infer
  closedness from the 123-response sample: **observation gives a lower bound on the value
  set** — the third instance of that doctrine (grep counts, linter blind spots, now enum
  domains). **NEW SCALE-UP CONDITION (Claude):** 161 distinct shapes over 18 routes ⇒
  ~1 900 models at 164 routes. Generated is fine for maintenance but it lands in the
  FRONTEND BUNDLE: measure the generated-zod bundle delta on fleet and extrapolate BEFORE
  scaling; if it trends to megabytes, shape dedup (shared sub-models) is decided now, not
  after 164 routes of it exist.

- 2026-07-11 — **ADR renumbering (reduced scope) ACCEPTED and CLOSED (`ba62652d`).**
  Verified: collisions down to `{0010}` alone; the false citation fixed in an isolated
  commit (`11f4d3d8`) — the executor sharpened the adjudication into its best form: *the
  docstring cited the only ADR that forbids its own behaviour*. `0015→0022` free (0 bare
  refs, 6 links); `0008→0020` by **proof, not heuristic** — creation dates 2026-05-31 vs
  2026-06-22, so any reference predating June 22 can only mean the elder (23 of 25 fall
  that way). `_FROZEN_COLLISIONS = {"0010"}`, documented in three places as the first live
  tripwire of the CI banner. **Two doctrines engraved, both generalising beyond ADRs:**
  (1) **A fourth grep-invisible reference form exists** — ADR headers cite by bare number
  WITH a gloss (`0008 (security hardening)`), self-disambiguating but only if you look for
  the form; with line-broken references that makes two forms no grep sees, so **every
  count in this repo is a lower bound, mine included**. (2) **Verification must be
  bidirectional**: "zero old number left on the moved sense" says nothing about FALSE
  MOVES (a reference that should have stayed and got re-pointed) — that was precisely the
  first attempt's flaw, and it is the same shape as the boundary ratchet's exact-set
  equality and the vacuous-green lesson: **a one-directional check proves one error class
  absent while being blind to its mirror.** The ratchet is now mutated in both directions
  (new collision → red; stale frozen entry → red). Operator housekeeping: `stash@{0}`
  (the known-wrong first attempt) is droppable.

- 2026-07-11 — **Day-cleanup review. Lot 1 (SQL identifier class, `772be359`) ACCEPTED.
  Lot 2 (ADR renumbering) HALT RATIFIED — the executor refused to make the registry lie,
  applying our own rule against our own brief. Third Claude design correction accepted.**
  **Lot 1.** `safe_identifier` (fullmatch, bounded at 63 = Postgres NAMEDATALEN−1 — a name
  Postgres would silently truncate is refused, because a silently-different table is worse
  than a hard failure) routed at BOTH ends: ingestion validators and every interpolation
  site. Three findings the audit and the brief both missed — **and one of them corrects
  MY audit's own number**: `retrieval/store.py` carried NO `noqa` because ruff never
  flagged it (S608 misses indented multiline f-strings), and it is the main consumer of
  `vector_table`, the one identifier a deployment can set from the environment. My audit
  counted "7 f-string SQL sites" by grepping `execute(f"` — the same blind spot, so the
  real count was higher. **Doctrine: counting a linter's suppressions inherits the
  linter's blind spots — and so does counting with a grep shaped like the linter.** Also
  found: two pre-existing private validators, both `re.match` (accepts a trailing `\n`);
  `psycopg.sql.Identifier` already the superior idiom in `memory/`. Brief corrected on
  evidence: `noqa: S608` CANNOT be removed (S608 is syntactic — verified, not assumed).
  And the executor caught his own vacuous ratchet: v1 had the very bug it policed (a
  module-level escape hatch whitelisted `store.py`; mutation-test green) → rewritten on
  the AST, re-mutated → red. **Lot 2 — HALTED, nothing renumbered, stashed.** The
  automated pass rewrote `## 4. The audit ledger (ADR 0015)` → `(ADR 0022)`: wrong — the
  audit ledger is the SPINE's subject; the seal was DECIDED in 0015 §Corr.3c and only
  DESIGNED in the annex, so "ADR 0015" near the word *seal* means the spine. The
  expensive work is kept: `docs/status/adr-renumber-evidence.md` (structural
  discriminants — frontier numbers Phase 1–6, recouvrement letters Phase A/B/C, disjoint
  by construction; historical — neither collision existed before 2026-06-22) plus a trap
  that **invalidates every grep-based count in this campaign, mine included: references
  break across line ends** ("ADR" / "0010 Phase C"), so all counts (my "138") are
  UNDERcounts. **CLAUDE MAPPING CORRECTED (3rd correction accepted):** my brief kept
  recouvrement (52 refs) at 0010 and moved frontier (183) — backwards. I inferred
  centrality from my recent context instead of counting. The SMALL sense moves: **frontier
  KEEPS 0010; recouvrement → 0021.** Fewer rewrites = fewer chances to make the record
  lie. **CLAUDE ADJUDICATION — the unreadable reference (`spine/runtime.py:27`,
  "Console sandbox playground (ADR 0010 Phase C)"):** it points to NEITHER. Phase C exists
  only in recouvrement, where it is the *dedicated business console* (`dedicated-ui`) —
  and `SandboxDefaults` carries `system_prompt` + `policy_rule_count`, which ADR 0013
  FORBIDS on any business surface. A business console cannot hold these. It is a
  **mis-citation, already lying before anyone tried to renumber it**: do not renumber it —
  FIX it to cite what actually governs the cockpit Console sandbox (ADR 0019 §I2 + the
  security seam's rule: overrides honored only for COCKPIT_EMBEDDED + OPERATOR), and drop
  the phantom "Phase C". **Go-forward:** 0015→0022 (free — filename refs only) and
  0008→0020 (mechanical) proceed now; **0010→0021 WAITS FOR CI** — a semantic rewrite of
  the project's memory with no independent witness is exactly what the bounded acceptance
  is meant to gate. This is the campaign's first live tripwire.

- 2026-07-11 — **Security run review: Lane A ACCEPTED (`60ec9d99 → d964ad31`, 9 lots);
  Lane B (`claude/security-seam @ e4286be6`) SUBSTANCE APPROVED, merge gated on operator
  decisions + rebase. Two of CLAUDE's own security design rulings were WRONG and the
  executor caught both with evidence — recorded so the corpus owns it.** (1) B2 as I
  ruled it (mount mutations behind `require_bearer`) could NEVER have closed the anon-
  mutation P0: the BFF attaches a **service-to-service** bearer on the caller's behalf
  (route.ts:3-4), so an anonymous visitor's mutation arrives perfectly bearer-
  authenticated. The bearer answers *"did this come from our frontend?"*, never *"who is
  asking?"* — a fix behind it looks right and changes nothing. Correct fix, verified on
  the branch: the mutations router requires a verified **operator assertion**
  (`APIRouter(dependencies=[Depends(require_operator)])`, identity not provenance).
  **Doctrine engraved: provenance ≠ identity — an auth check must name WHO, not WHERE
  FROM.** (2) B1 as I ruled it gated the state's `guard_overrides` but I missed a
  SECOND read site — chat.py:857 read `request.guard_overrides` straight from the raw
  body, below the gate, controlling the streaming PII redactor: an anonymous caller
  could still get an unredacted PAN on the wire. Branch fix reads the gated value at
  both sites. **Doctrine: a body-sourced privileged field must be gated at EVERY read,
  not just the first — grep the field, don't trust the entry point.** Lane A's first
  act ratified as exemplary: main was gate-RED at open (a lint that landed during the
  billing-blocked night with no CI witness); opus fixed it FIRST (`a56bb287`) so no
  later green claim rested on a red base — honesty holding unsupervised. Live exposure
  confirmed still open on main (anon `POST /observability/agents/release` → 200) until
  B merges — so B's review is closing an OPEN hole, not cleanup. Branch was cut atop the
  A7 god-router split (mutations live in the split `observability/mutations.py`); it must
  be **rebased on `d964ad31` and re-verified before merge** (main moved 9 lots under it).
  Four decisions are the operator's (read-plane locking, staging bearer, auditor mutate,
  terraform text-ratchet-not-proof); Claude's recommendations relayed. ADR renumbering
  PARKED with the right reason (138 refs to "ADR 0010" spanning two ADRs — a record that
  lies is worse than a duplicate number; do it deliberately, not at 3am).
  **— MERGE GO (2026-07-11).** Branch `8a269a97` rebased clean on `d964ad31` (2 commits),
  three operator rulings applied and proven: `MUTATION_ROLES = {admin, superadmin}` (auditor
  AND collections excluded — auditor 403 on mutation / 200 on read), staging in
  `_BEARER_REQUIRED_ENVIRONMENTS` with a ratchet on any new Environment. Executor caught his
  OWN vacuous-green — B1/B3 closure tests failed only at ImportError (proves the guard is new,
  not that the hole existed), so he re-exercised the pre-fix code behaviorally: anon `/chat`
  with `guard_overrides=["pii"]` did disable the streaming redactor; prod without bearer did
  admit the request. The doctrine held on its author's own tests. Auditor fix exceeded brief
  in the right direction: rbac.py/access.py already CLAIMED auditor is read-only (true on
  screen, false on the wire) — a ratchet now binds the displayed matrix to the real guard,
  both ways. **Post-merge obligations (NOT merge blockers — merge changes nothing in GCP):**
  (1) Terraform manages only 4 secrets; it lacks the session key, operator-assertion key and
  AUTH_SECRET — B2 makes the front mint the assertion, so after any deploy the 26 mutation
  buttons fail-closed (401/503) until the front has them: fix the secret provisioning BEFORE
  the next `terraform apply`, never discover it in prod. (2) `is_locked=true` on the audit
  bucket is config that only bites at `apply` (irreversible) — operator's call, not the
  merge's. Both written up in the security run journal.
  **— MERGED + LIVE-VERIFIED (2026-07-11, `origin/main = 8a269a97`, FF).** All six audit
  P0s now closed on main. Attack replayed against the restarted reference: anon
  `POST /observability/agents/release` went **422 → 401** (the 422 was the proof it had
  been reaching body validation — one valid `agent_id` from promoting an agent in prod);
  public `GET /observability/access` stays 200 (cockpit intact). Third consecutive night
  with CI billing-blocked — the merge's only witness was two local gate passes. This is
  now a standing risk, not an incident: recommend restoring an independent witness by
  stripping CI to the hermetic gate only (minutes-cheap, drops the expensive e2e prod
  build that was never gating), OR going public — now UNBLOCKED by this very merge (you
  don't publish a repo with a live anon-mutation hole), which buys free Actions + free
  branch protection at once.
  **— Operator decision (2026-07-11): ACCEPT the gap for now, no structural change.**
  Legitimate for a solo, careful operator; recorded, not glossed. Honest state stands:
  `main` is neither branch-protected nor CI-verified; the only gate is one local pass per
  lot; nobody writes that `main` is protected or that twice-green is structural. This is a
  BOUNDED acceptance — it flips to «restore the witness» (strip CI to the hermetic gate, or
  go public) at the first of: a second contributor touches `main`, a real deployment, going
  public, or the first time discipline visibly slips (a red merged, a broken `main`). Until
  one fires, the residual risk is accepted deliberately.
- 2026-07-13 — **PARKED, not fixed: Langfuse trace retention (~505k traces).** A second
  front, deliberately left alone by the ledger-integrity lot. It is a *retention /
  tail-sampling* problem (how much telemetry we keep and for how long), not a *verification*
  problem (how much of the audit chain we re-walk per request), and conflating them would
  hide one behind the other. Owner: unassigned. Whoever takes it: decide the retention
  window and the sampling rule FIRST, then measure — the ledger lot's lesson is that a
  threshold set before both populations are measured is a guess wearing a number.

- 2026-07-11 — **Audit-remediation overnight run review: ACCEPTED (`ece4f1bf →
  d194c0b4`, origin; 65 files, +1682/−177).** Verified on pieces: recouvrement trio
  collapsed to one canonical route (the un-gated surface closed), invoke rate-limit +
  429, **ledger backup WITH a passing restore drill (23122 rows)** — the P1.2 gap
  closed the right way (a backup proven by restoration, not declared), config inventory
  generated, prod-posture doc, weekly deps job. **Codegen REJECT ratified** (executor
  exceeded «prototype+park» but landed right): only **10 `response_model` across 174
  routes** — OpenAPI→zod would generate `unknown` for the untyped 96% and regress the
  hand-maintained schemas.ts. His sequencing is sharper than my prompt: type the
  backend first (Pydantic response_models), then codegen becomes free — and that typing
  IS part of the security seam (B2/B3 need typed mutation responses). Window-3 splits
  parked with concrete plans (observability.py → package; tabs extraction byte-identical)
  — endorsed, they run after the security seam. **#1 MORNING ISSUE — CI is billing-
  blocked, nothing ran in Actions all night.** This VOIDS the «CI is the second pass»
  compensation of fast-iteration mode: the entire night rests on a single local gate
  pass, no independent verification. Combined with absent branch protection, main is
  currently BOTH unprotected AND unverified — the fast-iteration safety model is not
  actually in force until billing is restored. Ratchet must not relax further until it
  is. **Coordination slip owned (mine):** I appended ledger entries to 0017 on the
  reference checkout (uncommitted) while opus merged via worktree — a divergence I
  created; it happens not to conflict (opus touched neither 0017 nor 0008 this run), but
  the reference checkout now carries my uncommitted 0008 amendment + 0017 entries and
  sits behind origin. Reconcile before restart (steps handed to operator). Executor
  hygiene: a too-broad `pkill -f run_local.py` killed the reference backend (restored) —
  lesson recorded: target by port. **The security two-track prompt (opus audit) is
  unaffected by this run and still stands as issued.**

- 2026-07-11 — **SECOND AUDIT (opus, 7 parallel reading agents, artifact
  `Tessera_private/artifacts/tessera-audit-2026-07-10.html`) SUPERSEDES the structural
  audit on security — and Claude's audit is corrected in the record.** Claude's audit
  measured structure/debt and named ledger-backup the worst gap; that was wrong. The
  worst gaps are HTTP-authorization holes, and Claude missed them by auditing
  architecture without reading the HTTP seam line by line. Two most-severe P0s
  re-verified by Claude directly against `ece4f1bf`: (1) `guard_overrides` /
  `system_prompt_override` flow from the `/chat` body into state and the guard layer at
  chat.py:725-726/735 with **no gate on surface or auth_state** — an anonymous caller
  disables PII redaction / tool DENY / grounding, or swaps the system prompt; (2)
  `ALWAYS_PUBLIC` in the BFF literally contains `"observability"` (route.ts:25) → 26
  operator mutation endpoints reachable anonymously. Six P0 total (add: Cloud Run
  `allUsers` default, auth bearer fail-open at boot, fabricated payment-promise date in
  3 approved recouvrement templates, compliance dashboard rendering fixtures as real
  with no SyntheticNotice). Calibration (opus, endorsed): blast radius is bounded TODAY
  only because Crédit Aurore data is fictional and nothing is publicly deployed — the
  posture is open, so this gates any public exposure, not tonight's safety. **Night plan
  REVISED to two tracks** (below): safe/verified fixes merge autonomously; the security
  seam is designed now + implemented on a branch but HELD for Claude review + operator
  go — merging an unreviewed auth boundary is the one place the overnight-to-main model
  must not reach (green tests don't prove a boundary closed — the vacuous-green lesson,
  now load-bearing on security). Also real from the audit: reliability KPI overstates
  error ~3× (wrong formula, shown number), sync recouvrement graph blocks the event
  loop, GDPR purge never scheduled, ADR-number collisions (two each of 0008/0010/0017/
  0019), branch protection still absent (now a SECURITY finding, not just hygiene).

- 2026-07-10 — **Five-lot window review: ACCEPTED (`7d341f41 → ece4f1bf`, 8 merges —
  fixture seed, orphans, durable-store inventory, honest chrome, Comprendre page).**
  Executor rulings ratified: turn-agent `workflows` emptied (a grammar for spans never
  emitted is the same lie one level down); the second e2e-flip refusal (7 remaining
  reds are traffic-dependent — a corpus fixture cannot carry them; traffic fixture =
  its own slice); **`publicAccess` for `/comprendre` RATIFIED** — an auth-boundary call
  that is normally Claude's to make: correct on the merits (a page explaining the
  product to a signed-out visitor cannot live behind the cockpit guard), guarded
  against sprawl; a one-line 0008 amendment is owed to record it. **Kicker ruling:**
  the «Démo Tessera» kicker on credit-aurore violates the binding lexicon annex and
  predates it — remove kicker AND the deliberate test pinning it (audit P0.5).
  Hygiene: executor sessions keep leaving shells running (4 this time) — close
  non-reference processes at every window end. **Full-code audit produced on operator
  request:** `Tessera_private/audit-code-2026-07-10.md` — measured state (71k py /
  31k tests / 90k ts); P0: 9 integration-test files executed NOWHERE (gate and CI both
  `-m "not integration"`), 49 silent excepts, 7 f-string SQL, recouvrement route trio,
  coverage configured but never run; P1: no ledger backup (the most embarrassing gap
  vs the product's own discourse), no rate-limit on the invoke seam, 51-var config
  sprawl, schemas.ts 5748-line monolith (OpenAPI→zod codegen study); plan = four
  sequenced windows, refactors behaviour-preserving, windows 1-2 before any new
  feature.

- 2026-07-10 — **e2e seed fixture landed; the flip did NOT happen, and here is exactly why
  (factual record, per lot A's own instruction).** The exit criterion was "green on a runner
  twice in a row, then flip"; it was not met, so the job stays a witness (`continue-on-error`
  untouched). Measured on CI run 29101763945 (`376b8ef5`), and 29101666745 (`94b1c1e4`) agrees.
  - **What the fixture fixed:** the seed step restored **241 corpus rows** into the runner's
    Postgres (`select count(*) from tessera_local.documents → 241`, `-gt 200` guard passed). The
    Playwright tally moved from the bare-runner **160 / 19 / 2** to **172 passed / 7 failed / 1
    flaky / 2 did-not-run**. The corpus-category failures the empty database caused — the ones the
    whole fixture was built to remove — are **gone** (`sources.spec.ts` finds its 17 catalogue rows;
    the 15 corpus categories are present).
  - **What still fails, and its single shared cause — it is not corpus.** The 7 reds assert on
    seeded **traffic**, which the corpus fixture deliberately does not carry: a transcript
    (`conversation_messages`), business events, citations, and timeline events. `synthese.spec.ts:46`
    ("recent conversations come from the transcript"), `metier.spec.ts:36` ("a real event count"),
    `sources.spec.ts:169` ("the citation panel"), `incidents.spec.ts:26` ("deny clusters"),
    `business-counting.spec.ts:81` (§4 — needs a business-number baseline to prove it did NOT move),
    and `surveiller-temporal.spec.ts:213/377` all need traffic, not documents. The two temporal specs
    are additionally **date-relative and non-hermetic by their own authors' note** (they assert on
    events at instants relative to *today*), so a frozen fixture cannot make them green as "now"
    moves. `configurations.spec.ts:153` (the `/readyz` probe) is the one that is not obviously
    traffic-shaped; not yet diagnosed, flagged rather than assumed.
  - **The next slice, named not buried:** extend `make seed-fixture` to a **traffic** fixture
    (transcript + business events + citations, generated by `scripts/generate_traffic.py` /
    `ingest_transcript_traffic.py`, dumped alongside the corpus). It carries a determinism cost the
    corpus fixture did not — relative dates — which is its own design question and why it is a
    separate slice. Until it lands and the job is green ×2, the flip stays owed. Nothing here
    pretends the corpus seed alone earned it.
  - **Adjacent CI fix, same window (`376b8ef5`):** `cancel-in-progress` no longer applies to `main`.
    It was cancelling every run but the last on a burst of merges, so the seed's own proving run
    (`db4893f8`, 29101191063) never executed — the second pass existed on paper and had run zero
    times. Branch pushes still cancel; `main` never does.

- 2026-07-10 — **Durable-store inventory (ruling: "the store belongs to the operator — hand him the
  list, decide nothing"). NOTHING WAS WRITTEN, NOTHING WAS DELETED.** Read-only, `SELECT` only.

  The durable store is `app_settings` (`src/tessera/api/settings_store.py`): `key text PRIMARY KEY,
  value boolean NOT NULL, updated_at timestamptz DEFAULT now()`. The code knows **exactly one key** —
  `_SYNTHESIS_ADMIN_KEY = "synthesis_visible_to_admin"` — written only through the `POST` in
  `api/routes/settings.py`. There is no second key, so the entire store is one row wide.

  | schema | key | value | updated_at | age |
  |---|---|---|---|---|
  | `public` | `synthesis_visible_to_admin` | `false` | 2026-06-05 10:46:12 UTC | 35 days |
  | `tessera_local` | — | — | — | *(table exists, zero rows)* |

  **Three facts decide what this row is, and they point the same way.** (1) `public` is the
  **production** schema; every non-production process reads `tessera_<env>` (ADR 0014, accepted
  **2026-06-26**). The row predates environment isolation by three weeks — before it, everything
  wrote to `public`. (2) The dev and e2e processes therefore read `tessera_local.app_settings`, which
  is **empty**: this row cannot be residue from the recent e2e windows. (3) `_get_flag` defaults to
  `False`, so the stored value is **identical to the default** — keeping it and deleting it are
  observationally indistinguishable today, and diverge only if a future default flips.

  **Idempotence, checked rather than restated:** no spec under `webapp/frontend/e2e/` references the
  synthesis flag or the settings route, so nothing in the suite writes this store. The recurrence the
  ruling guarded against has no path.

  **Operator's call, not the executor's:** is that 2026-06-05 `false` a *preference you set* (an
  admin who must not see the failure synthesis) or a *residue* of a test click from before schema
  isolation? Either way it is inert today. I did not guess, and I did not rewind.

- 2026-07-10 — **Lot C — contract chips on the fleet cards (branch `claude/fleet-contract-chips`,
  `1b8a5241` + `68e391f2`). Gate green in ONE pass** (new protocol, 2026-07-10: twice-green local
  suspended, CI replays `make gate` asynchronously as the second pass; no local e2e outside the
  named windows — this lot touches neither auth, routing/planes, the §4 seam, ledger integrity nor
  the shared headers). Continues lot A/B below.
  - **Manifest fix first (`1b8a5241`).** `turn-agent` declared `telemetry_capabilities: [turns]`
    while `test_turn_agent_emits_no_telemetry` already forbade its source a telemetry import — a
    promise no line of code could keep. The fleet therefore read an *observable contract* off the
    manifest alone, and the only thing between that and an observable-looking agent was the absence
    of turn evidence: **a fact about the metrics store, not about the agent.** Set to `[]`; the
    AgentSpec accepts it (`telemetry_capabilities` defaults to `()`), so **no schema bug**. New
    guard `test_manifest_declares_only_the_telemetry_the_source_emits` pins the invariant in **both**
    directions and was mutation-verified (restoring `[turns]` fails exactly the turn-agent case).
    **Deliberate consequence:** `observability_level` returns L0 as soon as `workflows` *or*
    `telemetry_capabilities` is empty, so turn-agent's declared rung drops L1 → **L0** and its
    coverage now lists `observable_contract` as missing. That is the honest reading of an agent
    that publishes nothing.
  - **The chips (`68e391f2`).** « Observable » ← `telemetry_capabilities` non-empty (§3);
    « Testable » ← `invocation.binding` ≠ `none` (0019 §1). Derived server-side in the manifest
    projection (`declares_telemetry` / `is_invocable`), read through the registry seam the §1
    ratchet allows — **never keyed on an agent id**, so a foreign agent arrives with its chips.
    Absent when not declared (honest-empty, not a greyed chip). Grid + list, i18n ×3, WitnessChip's
    visual family via a now-shared class. **Measured on the live `compute_fleet` payload, not
    asserted:** hello `[Observable]`, turn `[Testable]`, duplex `[Observable · Testable]`, the three
    business agents both. Cross-check test: the chip and the Console must agree about invocability,
    else a card advertises a test bench that will not open.
  - **The second declaration, surfaced then paid (`fc620878`).** `turn-agent` also declared
    `workflows: [{turn_v1, workflow_grammar.v1}]` — a grammar binding for spans it never emits, the
    **same over-claim one rung down**, and **invisible in the badge** (the level formula already
    reads L0 from either field being empty), which is precisely why it needed a test and not an eye.
    Ruled by Amadou: empty it in this lot. `workflows: []`; the manifest/source guard now checks
    **both** declarations, and **each leg was mutation-verified independently** — restoring either
    field fails exactly the turn-agent case. Honesty with zero visible delta is still honesty.
- 2026-07-10 — **PROTOCOL CHANGE (operator decision): fast-iteration mode.** Local
  twice-green is suspended → **one** full `make gate` pass per lot before merge (never
  zero). Local e2e is skipped during feature windows; Playwright runs (a) at the
  «feature batch delivered» milestone, (b) when indispensable = any change touching
  auth/login, routing/planes, the §4 seam, ledger/integrity surfaces, or shared
  headers — and (c) obviously in lots whose subject IS e2e (CI seeding/flip).
  Compensation making this safe: **CI is now the second pass** — it re-runs the same
  `make gate` on every push, asynchronously, nobody waits for it; stop-the-line
  unchanged (red CI on main ⇒ fix-forward before any new lot). Everything else stands
  (targeted staging, one lot = one branch = one merge, honest-empty, no history
  rewrite).

- 2026-07-10 — **CI + e2e-debt window review: ACCEPTED (`d8e4fd4f → b197c483`, gate CI
  green on main, run 29088115658).** `make gate` is now the single definition of green
  (CI calls the same targets — no second list to drift); pnpm-pin subtlety caught
  (corepack reads `packageManager` upward from cwd; setup-node probed from root and
  pulled a Node-22-requiring pnpm — fell on the branch, not main). e2e suite 34/142/9 →
  **182/0/0 ×2 locally**; the true baseline was 170 red without AUTH_SECRET (NextAuth
  fails soft: authenticated pages 200 with a logged-out shell — why agent worktrees
  never saw the real number). Two REAL product bugs found behind specs and fixed at the
  component: the inbox-overview React Query cache written under a key the reader never
  reads (`["inbox-overview"]` vs `["inbox-overview", locale]`), and the app-header
  border violating its own surviving comment since `2735f9ad`. **The e2e flip did NOT
  happen and the refusal is ratified as exemplary:** PR #5 was opened precisely to run
  the job on a runner before making it blocking — 160/19/2, the 19 = an EMPTY database
  (fresh CI Postgres never received the pgvector corpus), not spec debt. Declining to
  gate a data-independent subset under the gate's name («a weaker gate wearing the
  gate's name») is the honesty rule applied to CI itself. **RULING (the named piece):
  seed by committed fixture, not by model.** The premise «seeding needs embeddings ⇒ a
  model ⇒ a secret» has a third path: compute embeddings ONCE locally (the stack is
  on-prem anyway), commit the seed as a versioned fixture (SQL/dump incl. vectors; LFS
  if heavy), CI seeds Postgres from it — deterministic, hermetic, zero secret. Add a
  staleness guard (fixture ↔ corpus-source hash) + `make seed-fixture` to regenerate.
  Flip e2e to gating once runner-green ×2. **RULING (4 remaining console-payload
  orphans):** the distinction raised is right — «never read» ≠ «reader removed» — but
  the console payload is an internal cockpit surface, not a public contract: a field no
  consumer ever read is speculative surface. Remove them UNLESS a field is mandated by
  a declared contract shape (0018/0019) — contract-mandated ≠ orphan; verify consumers
  by structure repo-wide first, list the inventory in the commit message. **Durable
  store residue:** operator's call — the store belongs to Amadou; hand him the list of
  current keys/values to eyeball (test-vs-preference is a human judgment; specs are now
  idempotent so it cannot recur). Branch protection: still the operator's $0 banner.
  Visual checkpoint for Amadou: `/fr/surveiller/vue-ensemble?expanded=1` (header rule
  above «Exporter rapport» — the window's only visual change).

- 2026-07-10 — **Day-run close review: ACCEPTED (9 merges `e94aad5a … d8e4fd4f`, zero red
  merged, no lot parked; craft P3 6/6 awaiting Amadou's visual validation).** Playwright
  on main: 185 / 145 green / 31 pre-existing dead contracts / 9 not executed — none of
  the 26 new specs red. Three debts confirmed for the e2e-debt slice: en-bloc gating;
  §4 negative half (vacuous until the ingestion seam — design still owed by Claude);
  smoke-0019 traffic dependence (non-hermetic: red-by-construction on a fresh stack —
  a spec must inject the traffic it asserts). **Two executor blunders, self-caught and
  honestly reported — both engraved as rules:** (a) an ad-hoc probe wrote 2 fabricated
  business events into the LIVE dev ClickHouse (removed via the governed primitive; 321
  rows re-verified, all `synthetic=0`) — rule: **ad-hoc probes never write to live
  stores; proofs use throwaway databases only** (the lot-5 proof was itself the model);
  (b) `pnpm build` run in a checkout a dev server was serving corrupted `.next`,
  disguising an outage as a red suite for three runs — rule: **never build in a checkout
  currently serving** (extends the lsof pre-flight). **Gap flagged: the mid-course
  fix-pack is NOT in this run** — no CI workflow exists yet, and the orphan
  `actions.timeline_incidents` payload field still ships. With the operator's
  $0/no-protection decision, CI is the only independent verification available: it is
  the FIRST lot of the next window (with the orphan removal), then the e2e-debt slice
  (the three debts + zero skipped tolerated at close).

- 2026-07-10 — **Branch-protection decision (operator): staying on GitHub Free for now —
  no structural enforcement on the private repo.** Recorded verbatim, per the honesty
  rule: *Branch protection unavailable on current GitHub plan. CI checks are operational
  but not structurally enforced before merge. Residual risk accepted temporarily.* Nobody
  writes that `main` is protected or that twice-green is structural while this banner
  stands. **Compensating protocol (in force now):** (a) the CI workflow is the
  independent re-execution of the gate — every push to `main` must be followed by
  checking its run went green; (b) **stop-the-line:** a red CI on `main` freezes all
  lots — the only permitted work is the fix-forward, nothing merges over a red main;
  (c) force-push and history rewrite remain absolutely forbidden (unenforced, therefore
  restated). **Revisit triggers:** the repo going public (protection becomes free on
  Free), a first external contributor, or a paid-plan decision — whichever comes first.
  The org creation (`tessera-ai`) is deferred until one of those days: at $0 it buys a
  URL, not enforcement.

- 2026-07-10 — **Day-run mid-course review (lots 1/5/2/3 merged: `e94aad5a`, `2eaee2a0`,
  `a350c073`, `996e9666`) — all four RATIFIED; three rulings.**
  **(1) The ClickHouse §4 hole — the day's real event.** The corpus premise ("business-
  events bake pending, synthetic column owed later") was inverted by evidence:
  `_FACT_DEFAULTS["business_events"] = "spine"` — ClickHouse was already the default read
  medium, and the synthetic mark was dropped at write, never rebuilt at read. A canary
  turn's events would have round-tripped the owned table as genuine business facts. Fix
  ratified in full (both legs + idempotent ALTER + four tests each failing when its own
  leg reverts; proven on live CH in throwaway databases; correctly resequenced BEFORE the
  §4 e2e lock so the lock would not pass for the wrong reason). **Reviewer's own
  correction:** the I4 review entry accepted "§4 proven at the emit-time guard AND the one
  business read seam" — the read-seam half was VACUOUSLY green (no synthetic business
  event existed to exercise it; in-process canaries emit none). Doctrine engraved: **an
  honesty lock's acceptance must inject traffic that exercises the leg it claims — a
  vacuous green proves nothing.** Same doctrine tags the §4 e2e negative half (flagged
  vacuous by its own author, header says so): both legs get real traffic the day the
  http-agent businessEvents ingestion seam lands (design ruling still owed by Claude).
  **(2) Playwright en-bloc criterion: deferral ACCEPTED.** 127 pass / 31 fail, the 31 =
  pre-existing dead contracts across 11 files (pre-multi-agent routes, pagination
  assumptions). Repairing them faithfully = its own slice («e2e debt repair»), scoped
  next window; meanwhile the gate = green subset en bloc + zero new red.
  **(3) Grep-by-string is now a three-time offender.** The night parked the apps-grid
  menu as absent; it exists (`OperatorProductMenu`, app-header.tsx:292) — built by codex
  in the headers merge. The night's grep AND the reviewer's own closure grep both
  searched display strings, which live in i18n catalogs, not in components. Rule:
  **verify presence by structure (component/route/symbol), never by rendered strings.**
  Also ratified: the prebuild-hook guard (pnpm build was silently deleting 7 tracked
  `data/eval/*.json` files — build hooks must never mutate tracked files). Lot 4 (craft
  P3) proceeding: retouch-only on validated pages, screenshots per item, sparkline stays
  unwired (no fabricated history), hero card uses only accumulated real facts.
  **(4) Fix-pack ordered (post-lot-4, from the flagged-not-buried list):** (a) remove the
  orphan `actions.timeline_incidents` console-payload field (dead since `71b15b18`);
  (b) **CI is absent entirely** — no workflow runs Playwright, vitest or biome; ordered: a
  gating workflow for the hermetic gate (ruff/format/mypy/pytest + tsc/biome/vitest) on
  PR + push, and an e2e job against a PRODUCTION build (the contention finding: `next
  dev` + 10-conn pool starves at 4 workers) — e2e job non-gating until (c) lands, then
  flipped; (c) e2e debt slice AUTHORIZED: repair the ~31 dead contracts across 11 files
  toward the real product (pagination-aware, multi-agent routes), diagnose the two
  unexplained a-faire failures, document the supported worker count. CI enforcement is
  the structural half of the protection main still lacks; branch protection (operator,
  GitHub settings) remains the other half — reminded again.

- 2026-07-10 — **Overnight-run review: ACCEPTED (7 merges, `29fdefbc → e1a73c5c`, zero red
  merged; journal `overnight-20260709-run.md`).** Spot-checked the riskiest change: the §4
  Console fix's discriminant is `is_test_turn(surface)` with `surface` derived
  **server-side from the signed operator assertion** — `console` stamps synthetic,
  `dedicated-ui` deliberately does NOT (an operator doing real recouvrement work must
  count; stamping every operator turn would erase that agent's business record — the
  asymmetric, worse error). Sound; mutation-tested per the journal. Also verified honest:
  env-leaking unit tests (suite read `.env.local`; red proven pre-existing before any fix)
  and the 0017 §1 ratchet repair via the registry seam, never a frozen exception.
  **RULING (canary turn-evidence — the executor's open question):** the turn counter
  STAYS on the served path. `tessera_agent_turns_total` means "turns served to real
  consumers through the declared seam" — that is the fact 'observable in operation' rests
  on. Canary liveness already has its own fact (the S1 `synthetic_run` freshness facet).
  Relocating the counter to the graph seam would count eval-harness runs as production
  evidence — fabrication by architecture. A future "dormant but responsive" badge may
  COMBINE the two facts (freshness backlog slice); it must never merge their sources.
  **Lot-7 park corrected:** the scope exists — `Tessera_private/punchlist-metier-
  lot1.5-2026-07-07.md`, §"P3 — craft pass", items 18–23 — inside the very file the park
  note cited. The park was procedurally right (never invent scope on validated pages) and
  factually wrong (absence declared without reading the named file through). Both sides
  own a piece: the brief said "lot 2.5" (a label that exists nowhere), the executor
  searched for the label instead of the content. **Owed follow-up confirmed as DESIGN
  first:** criterion (b) holds today only because no ingestion path exists for http-agent
  `businessEvents` — the ingestion seam is a Claude ruling before any code. Day mission
  issued: e2e red repair → e2e completion (incl. an end-to-end §4 spec) → apps-grid menu
  → P3 real scope → ClickHouse bake (auth read from compose, never inferred).

- 2026-07-09 — **Fleet-legibility + level-honesty review (lot A `b3d70b36`, lot B `b7ef1003`,
  branch `claude/fleet-agent-legibility`): APPROVED — MERGE FEU VERT.** Lot A ratified incl.
  the tooltip head-noun fix («Agent témoin de la plateforme…» — keeping «démonstration»
  would have recreated the rule-5 collision one level down). Lot B ratified: trusted-true
  killed at the parameter-default level (`has_turn_evidence` becomes a REQUIRED kwarg — a
  default is where an assumption hides); `resolve_level_state()` carries computed + declared
  + evidence, `resolve_observability_level()` returns computed only and that is what the
  release gate reads (driven end-to-end through `release_decision`, unstubbed); badge
  decision extracted to a pure module, zero agent-specific conditions, guarded by test.
  **Architect error owned:** the review prompt asserted a freshness window "already used by
  turn evidence" — none exists (`sum by (agent_id)(tessera_agent_turns_total)`, instant
  vector). The executor rightly refused «aucune preuve récente» as an over-claim IN THE
  LABEL and shipped «L{n} déclaré · aucune preuve» + two guards (PromQL range-selector
  ratchet; `recent|récent|kürzlich` forbidden in level strings). Second instance of the
  step-2 lesson (assertion-string guess): domain facts are read from source, never
  inferred — and the rule binds the reviewer first. **Scope ruling (the fleet goes muted):**
  with the turn-evidence read unwired locally (`TESSERA_LEVEL_TURN_EVIDENCE` set nowhere in
  the repo), all five agents resolve `unverifiable` → every card shows the muted declared
  badge and the release gate blocks below proven evidence. Ruled: this is the DESIRED
  honest reading of a cockpit whose evidence path is not connected — merge as-is, no
  softening (softening `unverifiable` into a normal badge would resurrect trusted-true in
  the UI). Ordered complement, overnight lot 1.5 BEFORE I6(a): wire the existing step-7
  evidence read in the dev stack (collector + Prometheus up via `make dev-up`, evidence
  flag set from its real configuration read in code — not inferred from its name); exit
  criterion = computed rungs return from live Prometheus facts, turn-agent honestly stays
  «L1 déclaré · aucune preuve» until duplex (I6) closes the loop. Freshness semantics
  (what "recent" means, `increase[24h]`) = its own backlog slice, not tonight.

- 2026-07-08 — **ADR 0019 I1+I4 review: APPROVED — MERGE FEU VERT.** Verified:
  `synthetic_turn()` ContextVar entered around `graph.ainvoke` (structural,
  medium-independent stamping); `canary_cadence_s ⇒ in_process_chat` enforced at
  manifest load; boundary ratchet still `frozenset()` (the invoker is agent-side — the
  runtime executing its own turn — never a control-plane import). **Ratified
  consumer-depth refinement, recorded so I2 inherits no confusion: the CANARY consumer
  drives the graph seam (`compile_graph().ainvoke`, the eval-harness entry — canaries
  are eval-family; avoids transcript pollution and any I2 overlap), while the CONSOLE
  consumer (I2, still deferred) will use the real `/chat` seam for interactive parity —
  one declared binding, two entry depths per consumer.** Owed follow-up tracked (opus's
  own flag): a synthetic column on the CH business-events read when its bake completes.
  Post-merge operator moment: flip `TESSERA_OBS_CANARY_SCHEDULER_ENABLED`, watch the
  hourly synthetic recouvrement turn fire, its S1 land, and the Métier tab stay clean.
  Hica closed same day (main c6aa3823, boot posture confirmed live by the operator).

- 2026-07-08 — **Hica seal final review: APPROVED — ruling (b): wire the minimal
  off-chrono scheduler, THEN merge.** Verified on pieces: `NoOpProvider` structurally
  cannot mint (honesty invariant in the type, not a convention); the etat_a_date
  hardcoded `verified=True` is gone (badge derives from seal_state + qualification);
  the seal is an appended `tessera.ledger.seal` entry **through the serialized writer**
  (inherits the advisory lock + partial unique index — the seal cannot fork the chain
  it attests); 31-test matrix incl. live degradation on the real forked table.
  Rationale for (b): a deferred scheduler creates a latent trap — a provisioned TSA
  with nothing firing is config that looks live but isn't (the quiet-dishonesty class);
  the thin runner idles under `none` and makes TSA provisioning flip-and-go. Plus a
  boot log line stating the seal posture. **Post-merge operator moment: provision
  FreeTSA and watch « Scellé (non qualifié) » light up for real — on a chain that
  carries an attested fork, which is exactly what makes it credible.**

- 2026-07-08 — **Headers H1 review: APPROVED — GO H2.** Verified on the staged diff:
  SystemStatusPill reads the SAME `LedgerIntegrityText` seam as the footer (single
  source — Hica's seal facet will land once, for both); UserMenu = display-only role
  prop + next-auth signOut + locale/theme (no client-side role toggle); DemoBadge on
  i18n key, fr value « Démonstration » (lexicon-clean); CommandSearch ⌘K wired
  (metaKey/ctrlKey + per-plan aria scope); honest-empty vocabulary in the popover
  (« Non disponible »). Minor note (non-blocking): `residenceValue` is a hardcoded
  message constant — acceptable now, config-driven when multi-deployment becomes real.
  Codex: commit H1 (targeted), then H2 (cockpit 3-zones + the anonymous→/login identity
  fix); checkpoint H2 = before/after captures for the operator.

- 2026-07-08 — **Hica seal design review: APPROVED — GO Lot 2, all questions ruled.**
  RFC 3161 TSA behind a `SealProvider` protocol ratified (attests without storing;
  offline-verifiable outside Tessera; eIDAS = the EU opposability instrument). S3
  Object-Lock rejected (a store, not an assertion) and self-signing forbidden (the
  fake-seal trap) — both correctly. Rulings: **Q1** `seal_provider="none"` default;
  FreeTSA for the first cut (real third-party tokens prove the mechanism); eIDAS-
  qualified TSA = the named production path. Qualification nuance added to §9: « Scellé
  · opposable » is RESERVED for qualified TSAs; non-qualified renders « Scellé (non
  qualifié) » — provider identity + qualification always visible in the popover.
  **Q2** appended `tessera.ledger.seal` chain entry (one journal, Corr.3b families
  pattern; each seal transitively covers prior seals; append-only trigger + advisory
  lock protect it for free). **Q3** yes — a fresh unattested fork downgrades even with
  a valid seal (defense-in-depth display; the partial unique index makes it near-
  impossible anyway). **Q4** τ=1h / staleness 2τ as CONFIG defaults; stale → « Intégrité
  partielle (sceau périmé) ». **Q5** full seal facet on TE-01/Prouver (where legal
  reconstruction lives); the footer gains only a compact « · scellé <t> » suffix when a
  valid seal exists — nothing added when none configured. **Q6 — YES: fix the
  etat-a-date over-claim; the green→amber downgrade is a CORRECTION, not a regression**
  (the incident-badge precedent: the amber that tells the truth beats the green that
  lies; the upgrade path when a TSA lands is the better demo). **Q7** keep the companion
  design note + add a decision-only §Correction 3d to ADR 0015 pointing at it. Commit
  the note now (targeted staging), then Lot 2.

- 2026-07-08 — **ADR 0019 written** (`0019-invocation-binding.md`): the declared
  cockpit→agent seam — `invocation: in_process_chat | http | none` in the AgentSpec,
  console generated from binding + capabilities + TurnResult + XT-01, closed consumer
  list (console, canary scheduler; evals stay harness-side), operator assertion + S1
  audit on every invocation, synthetic stamping so test turns never pollute business
  metrics. Status accepted, **implementation deferred** with pre-sequenced phases I1-I4;
  trigger = first http-invocable agent or the canary scheduler. Uncommitted — rides the
  next docs commit. Parallel dispatch: codex on headers (H1-H4), opus proposed on the
  Hica seal (zero overlap).

- 2026-07-08 — **Post-0017 architecture item identified (operator question): the Console
  is the last non-generated, runtime-coupled cockpit surface** — it streams through the
  in-process `/chat` seam and cannot test a foreign-runtime agent. Decision needed (ADR
  0019 candidate: "Invocation binding — the declared cockpit→agent seam"): the
  observability contract stays publish-only; testing is a CONTROL action requiring a
  second, declared contract — an `invocation:` block in the AgentSpec (`in_process_chat |
  http | none`), from which the console GENERATES (binding + capabilities' typed actions
  + TurnResult rendering + XT-01 trace link; `none` → honest-empty). Convergence: the
  same binding is the missing runtime primitive for canary scheduled execution (signal
  94's deferred piece) — one declaration, three consumers (console, canaries, evals
  already manifest-declared). Priority: rises with the first http-invocable external
  agent or the canary scheduler, whichever comes first.
- 2026-07-08 — **Headers H4 revision after Amadou feedback ready for visual validation**
  on `codex/headers-refonte` — this supersedes the previous H4 checkpoint note below where
  the Crédit Aurore stacked bars were removed and `⌘K` was added to the collections search.
  Latest operator direction applied: Crédit Aurore keeps the demo strip + utility bar, while
  the shared floating launcher now reads `Poursuivre la démonstration · explorer les espaces`;
  `recouvrement-new` uses the same long floating launcher, its dossier/client search is
  read-only and no longer advertises or handles `⌘K`; the cockpit header keeps the page
  subtitle in the 56px header, exposes `Rechercher / Commandes ⌘K`, gives the
  `Opérationnel` popover an explicit chevron/cursor affordance, adds the operator product
  grid menu (`Espaces métier` / `Espace client`), and the sidebar identity block shows
  `Session active <t>`. Visual proof on :3098:
  `/tmp/tessera-revision-produit.png`, `/tmp/tessera-revision-recouvrement.png`,
  `/tmp/tessera-revision-cockpit.png`, `/tmp/tessera-revision-cockpit-menu.png`; interaction
  proof: typing into the recouvrement search leaves the value empty (`readOnly`). **Twice-green
  on revised H4:** backend `ruff` / `ruff format --check` / `mypy src/tessera` /
  `pytest -q -m "not integration"` (`1410 passed, 50 deselected`) ×2; frontend
  `tsc --noEmit` / `biome check .` (27-warning existing baseline, no new findings) /
  `vitest run` (`93 passed`) ×2. **HALT:** revised H4 waits for Amadou visual validation
  before final commit/push/Claude merge gate.

- 2026-07-08 — **Headers H4 product surfaces checkpoint ready for Amadou visual validation**
  on `codex/headers-refonte`. Pre-flight: antigravity product branch is parked/absorbed
  (`codex/fix-produit-chat-widget` diff vs `main` empty), and the H4 header strips were still
  present, so this work was not covered elsewhere. Scope shell/header only: Crédit Aurore
  customer space no longer renders the stacked demo strip + utility bar above the bank header;
  the floating shared demo pill carries demo context. The collections console header now shows
  the dossier/client search with `⌘K`, focuses that search on `Ctrl/Cmd+K`, adds icon-button
  aria/focus treatment, aligns to the 69px Crédit Aurore header rhythm, and uses the shared
  floating `DemoBadge`. Visual proof on :3098:
  before `/tmp/tessera-h4-before-produit.png`, `/tmp/tessera-h4-before-recouvrement.png`; after
  `/tmp/tessera-h4-after-produit.png`, `/tmp/tessera-h4-after-recouvrement.png`. Shortcut proof:
  `Ctrl+K` → `Rechercher un dossier ou un client`. **Twice-green on H4:** backend `ruff` /
  `ruff format --check` / `mypy src/tessera` / `pytest -q -m "not integration"` (`1410 passed,
  50 deselected`) ×2; frontend `tsc --noEmit` / `biome check .` (27-warning existing baseline,
  no new findings) / `vitest run` (`92 passed`) ×2. **HALT:** H4 waits for Amadou visual
  validation before final commit/push/Claude merge gate.

- 2026-07-08 — **Headers H3 visual validation: APPROUVÉ — GO H4.** Amadou donne le
  feu vert après quick look launcher + `/espaces` (:3098). Next: commit H3, then H4 product
  surfaces (client space + collections console) if not already covered by antigravity.

- 2026-07-08 — **Headers H3 launcher + `/espaces` checkpoint ready for Amadou quick look**
  on `codex/headers-refonte`. Scope shell/header only: launcher and `/espaces` inherit the
  shared `UserMenu` path (language + theme inside the avatar menu; no loose language/theme
  header icons) and the shared `DemoBadge` component (no local demo-pill markup; anonymous
  launcher verified with exactly one "Démonstration" badge). Visual proof on the :3098 worktree
  preview: `/tmp/tessera-h3-launcher.png`, `/tmp/tessera-h3-espaces.png`,
  `/tmp/tessera-h3-launcher-anonymous.png`, `/tmp/tessera-h3-launcher-menu.png`.
  **Twice-green on H3:** backend `ruff` / `ruff format --check` / `mypy src/tessera` /
  `pytest -q -m "not integration"` (`1410 passed, 50 deselected`) ×2; frontend
  `tsc --noEmit` / `biome check .` (27-warning existing baseline, no new findings) /
  `vitest run` (`90 passed`) ×2. **HALT:** H3 waits for Amadou quick visual validation
  before H4.

- 2026-07-08 — **Headers H2 visual validation: APPROUVÉ — GO H3.** Amadou donne le
  feu vert après checkpoint visuel cockpit (:3098). Next: commit H2, then H3 launcher +
  `/espaces` inheritance check (UserMenu, DemoBadge, zero specific chrome).

- 2026-07-08 — **Headers H2 cockpit checkpoint ready for Amadou visual validation** on
  `codex/headers-refonte`. Scope shell/header only: cockpit header normalized to three zones
  (logo/context title · `CommandSearch` · `SystemStatusPill` + notifications + help), legacy
  posture chips collapsed into the shared status pill, page descriptions moved into the page
  subtitle, sidebar identity kept as the single `UserMenu` anchor (no header avatar), sidebar
  brand/header rhythm aligned to 56px, and anonymous cockpit sessions redirected to `/login`
  before rendering the shell. Visual proof refreshed on the :3098 worktree preview:
  before `/tmp/tessera-h2-before-metier.png`,
  `/tmp/tessera-h2-before-flotte.png`, `/tmp/tessera-h2-before-surveiller.png`; after
  `/tmp/tessera-h2-after-metier.png`, `/tmp/tessera-h2-after-flotte.png`,
  `/tmp/tessera-h2-after-surveiller.png`; mobile sanity
  `/tmp/tessera-h2-after-flotte-mobile.png` (document width 390px). Anonymous redirect proof:
  `/fr/agents` → `/fr/login`. **Twice-green on H2:** backend `ruff` /
  `ruff format --check` / `mypy src/tessera` / `pytest -q -m "not integration"` (`1410 passed,
  50 deselected`) ×2; frontend `tsc --noEmit` / `biome check .` (27-warning existing baseline,
  no new findings) / `vitest run` (`88 passed`) ×2. **HALT:** H2 waits for Amadou visual
  validation before H3.

- 2026-07-08 — **Headers H1 review: APPROUVÉ — GO H2.** Claude review accepts the H1
  foundation diff: shared `SystemStatusPill`, `CommandSearch`, `UserMenu`, `DemoBadge`,
  tree-aware ledger wording shared with the footer, fr/en/de labels and contract tests.
  Non-blocking note recorded: `residenceValue` remains message-backed for now; it becomes
  config-driven when multi-deployment is real. Next: commit H1, then H2 cockpit refonte with
  visual checkpoint before continuing.

- 2026-07-08 — **Header premium H1 checkpoint ready for Claude review** on
  `codex/headers-refonte` (base `main` = `5ece2ae0`). Scope deliberately limited to shared
  shell/header foundations, no business logic/store/API route: `SystemStatusPill`
  (health + model + residence + ledger popover), `CommandSearch` (plan-scoped button-input +
  shortcut seam), `UserMenu` (avatar/role + account switch via `/login`, sign-out, language,
  theme; no client-side role toggle), `DemoBadge` (single floating demo pattern), plus fr/en/de
  i18n and component contract tests. The footer keeps the incident-era static posture and now
  shares the same tree-aware ledger wording helper as the status popover. **Twice-green on H1:**
  backend `ruff` / `ruff format --check` / `mypy src/tessera` / `pytest -m "not integration"`
  (`1410 passed, 50 deselected`) ×2; frontend `tsc --noEmit` / `biome check .` (27-warning
  existing baseline, no new findings) / `vitest run` (`86 passed`) ×2. **HALT:** H1 diff awaits
  Claude review before any H2 visual cockpit work.
- 2026-07-08 — **step 7 CLOSED → merged to `main` (`88b00fb9`), pushed. ADR 0017 COMPLETE.**
  `claude/step-7-tto` merged `--no-ff` on the operator's final feu vert; the only conflict was
  this ledger, resolved by **union** (final-review approval + all executor step-7 entries kept).
  **Twice-green on the merged tree**, identical both runs: `ruff` / `ruff format` (498 files) /
  `mypy src/tessera` (275) / **pytest 1410** (50 integration deselected); FE `tsc` clean / `biome`
  27-warning baseline / **vitest 78**. Push clean fast-forward (`b3273e20..88b00fb9`). **All seven
  0017 steps are landed on `main`; the ADR Status reads accepted — implementation complete, TTO
  L1 = 20m18s (~12× under the ≤½-day target).** The demo agent's OTLP profile is proven end to
  end. **One open follow-up (non-blocking, display-honesty):** the evidence-strict level shows L0
  for a *dormant-but-conformant* agent — the fleet badge should distinguish « aucune preuve
  récente » from « non conforme » (e.g. « L1 déclaré · aucune preuve récente »), same family as
  the tree-aware audit-integrity badge; owed to a UI slice. **Process note (3rd occurrence):** the
  worktree-slip pattern recurred twice this session (step-7 work started in the main checkout,
  recovered by patch-move each time) — the register/landing-pad rule holds; every executor prompt
  now starts by confirming its `cwd`.

- 2026-07-08 — **Step-7 final review: APPROVED — MERGE FEU VERT. ADR 0017 reaches
  implementation-complete with TTO = 20m18s (~12× under the ≤½-day target).** All four
  acceptance criteria verified (computed L1 from a live Prometheus fact; testkit + drift
  guard; zero agent-specific cockpit diff; chrono honest — platform completion off-clock
  and labelled). Convergence note: the executor independently built the Prometheus
  evidence path before the corrected ruling arrived — two roads, same 0015 logic.
  Caveat responses: (1) computation-level proof of acceptance (a) accepted — the fleet
  payload IS the fact and the UI renders declarations generically (proven all of step 4);
  the fleet screenshot happens post-merge on the reference servers as the operator's
  final look, not a merge gate. (2) The two worktree slips (recovered cleanly) are noted
  — third occurrence of the pattern; the register rule stands, executors must start every
  phase by confirming cwd. **Refinement logged (post-merge, non-blocking): the
  evidence-strict level can read L0 for a dormant-but-conformant agent — the badge should
  distinguish "no recent evidence" from "not conformant"** (e.g. « L1 déclaré · aucune
  preuve récente ») — a display-honesty nuance in the same family as the tree-aware
  integrity badge.

- 2026-07-08 — **step 7 DONE → ADR 0017 COMPLETE (TTO measured).** The architecture's
  acceptance test passed. **hello-agent** (`examples/hello-agent/`) is an out-of-process,
  **zero-`tessera`-import** agent: pure OTLP turn spans (the full L1 Scope-dim contract) + a
  turn counter, to the collector. Onboarding it (on the completed platform) = a manifest entry
  in `agents.yaml` + the process + the test-list update — nothing in `observability/` or
  `webapp/`. **End-to-end verified LIVE:** hello-agent → collector (new metrics pipeline) →
  Prometheus (`sum by (agent_id)(tessera_agent_turns_total)` = hello-agent:15) → the cockpit
  resolver (flag on) reads that real fact → **fleet card L1** (`compute_fleet` → hello-agent
  `level=L1`; the other agents honestly L0 — evidence-strict, they haven't emitted through this
  Prometheus). **Acceptance (a) fleet L1 from real facts ✓ (b) span-contract testkit green
  (`test_hello_agent.py`, +drift guard) ✓ (c) zero AGENT-SPECIFIC diff — `webapp/` ZERO,
  `observability/` generic, 0 hardcoded `hello-agent` ✓ (d) TTO chrono.** ⏱ **TTO = 20m18s**
  (start 08:38:12Z scaffold → stop 08:58:30Z L1 green) vs the §Governing-rule target **L1 ≤ ½
  day** — **~12× under**. Onboarding friction that (honestly) counted toward the TTO: a 4th agent
  tripped 4 existing L2-era assumptions (guardrails catalogue count; every-agent-binds-an-eval-set
  ×2; the dedicated-ui routable pool) — fixed truthfully (eval-less L1 agents exempted; hello-agent
  moved off dedicated-ui to cockpit-embedded so it is not a routable chat core; catalogue count
  updated). **Twice-green backend (1410)** + FE tsc clean (no webapp delta). ADR 0017 §Phase-F
  precision + Status → **accepted — implementation complete (TTO 20m18s)**. **HALT: final Claude
  review before merge to main** (per operator instruction).

- 2026-07-08 — **Step-7 evidence-path ruling CORRECTED: Prometheus turn-count read
  (option 2), superseding the review's earlier Langfuse preference.** Reason: since A2.4
  the L level is a **release-gating input**, and the governing rule (0015 Amendment 1)
  forbids gating facts from reading best-effort third-party stores — a Langfuse-backed
  level would recreate the exact coupling the score demotion eradicated. Prometheus is
  the canonical home for counts, the `spine/adapters/prometheus.py` seam exists,
  `AGENT_TURNS_TOTAL{agent_id,…}` already flows for in-process agents → **the same read
  makes EVERY agent's L1 evidence-backed uniformly** (incl. this morning's minimal
  specs), honest-empty when Prometheus is unreachable. Platform completion = resolver
  reads turn evidence via the Prometheus adapter + collector prometheus-exporter config
  for OTLP metrics (off-chrono, labelled commits). Option 3 rejected: a manifest-only L1
  badge is asserted, not computed (§4 violation). Credit: the executor's fork-surfacing
  caught the reviewer's inconsistency — the design gate worked in both directions.

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
