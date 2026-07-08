# ADR 0019 — invocation binding: execution status

Single source of truth for **where the ADR 0019 implementation is**. Same protocol as the
0015 / 0017 ledgers: implement → full gate **twice green** (`ruff check` + `ruff format --check`
+ `mypy` + `tsc --noEmit` + `biome check` + `pytest -m "not integration"`) + phase-specific
verification → commit (**targeted staging, never `git add -A`**) → update this file → advance.

**Trigger fired 2026-07-08:** the operator activated the **canary scheduler** path (ADR 0019
§Implementation trigger — "the canary scheduler, whichever comes first"). The first mission delivered
**I1 + I4 only**. I2 (Console generation) and I3 (http invoker + first external agent) were
**deferred** — I2 in particular was off-limits while the agent-console / headers work was in flight
on the codex worktree.

**Follow-up mission 2026-07-08 (I2 + I3):** the codex headers refonte landed on `main`
(`59dfa828` / `043f480f`), clearing the I2 blocker. This mission delivers **I2** (`4340bdad`) and
**I3** (`3597e124`) on a fresh `claude/adr19-i2-i3` branch cut from `main`. **ADR 0019 is now
I1–I4 complete** — pending the review-before-merge checkpoint (same protocol as the I1+I4 landing).

## Phase ledger

| Phase | Scope (short) | Status | Commit | Notes |
|---|---|---|---|---|
| I1 | `invocation` block in the AgentSpec (schema + validation, `none` default); native agents declare `in_process_chat` | ✅ done | `80a83753` | `InvocationBinding` {none·in_process_chat·http} + `InvocationSpec` (`extra="forbid"`, http-only fields unrepresentable on other bindings, http must name operator-assertion auth). `Agent.invocation` always present (default `none`). support-client/onboarding/recouvrement → `in_process_chat` (pure codification of `/chat`, no behaviour change); hello-agent → `none`. Gate twice-green (ruff/format/mypy/1460 unit); frontend untouched. |
| I2 | Console generation for `in_process_chat` (parity, rendered from declarations); honest-empty for `none` | ✅ done | `4340bdad` | The Console is generated from the declared `invocation.binding`, not a chattable-by-default assumption. `compute_agent_console` is agent-scoped (`?agent=`); binding read through the boundary-allowed registry seam (ratchet green). `in_process_chat` → full interactive payload (parity); `none` (hello-agent) → slim honest-empty ("no test invocation — observe via runs/evals"), NO fabricated tools/guardrails. Frontend gates on `invocation.invocable`; SSR-scoped key. Per the ADR open question, free-text parity only — capability-form generation stays deferred. Gate twice-green (ruff/format/mypy/tsc/biome/1485 unit); verified through the real route (fr/de/en). |
| I3 | `http` binding: the invoker (assertion forwarding, timeout, audit) + first invocable external agent; SDK conformance test | ✅ done | `3597e124` | `HttpTurnInvoker` (`tessera.api.agent_invoker`): POSTs a TurnInput, forwards the verified operator assertion (refuses an empty one before the network — no anonymous invocation §4), honours `timeout_ms`, validates the turn contract, emits one S1 per call; never raises (honest RED, never a fabricated green). Pure HTTP, no runtime-graph import → 0017 §1 ratchet stands (invoker lives in `tessera.api`, off the scanned control plane). SDK conformance `verify_turn_result` ("an agent declaring http must speak the turn contract"). First invocable external agent `examples/turn-agent/` (zero tessera import, stdlib http POST /turn), declared `binding: http`; hello-agent stays `none`. Governed seam `POST /agents/{id}/invoke` (operator-only, plane-scoped, http-only, audited); console generation extends to http (request/response test bench + `HttpConsole` frontend + Next BFF proxy). Streaming open question resolved: request/response for I3. Verified end-to-end: real invoker → LIVE turn-agent over HTTP → green + conformant TurnResult. Gate twice-green (ruff/format/mypy/tsc/biome/1503 unit); boundary ratchet green. |
| I4 | Canary scheduler on the `in_process_chat` binding (cadence from the manifest, synthetic stamping, S1 per invocation, freshness feeding the existing canary descriptor) | ✅ done | `9c02e35f` | Off-chrono scheduler mirroring the seal (lifespan + boot posture line; idle by default). `agent/canary.py`: `InProcessChatInvoker` drives `compile_graph().ainvoke` in a `synthetic_turn()` context; `run_canary_cycle` emits one `tessera.agent.canary` S1 per invocation (green/red, never a fake green). Synthetic isolation excluded twice: the emit-time Prometheus guard + the read seam every business surface flows through (default `include_synthetic=False`). Descriptor gains `synthetic_run` (from the S1 entry) + `cadence_s`. recouvrement declares hourly; switch `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED` (default off). Gate twice-green (ruff/format/mypy/1479 unit); boundary ratchet green. |

## Owed follow-ups (explicit, never silent)

- **ClickHouse owned business-events read (§5) needs a `synthetic` column.** The synthetic
  exclusion is airtight today: the emit-time Prometheus guard is medium-independent, and the read
  seam filters the in-process store (the default read medium). The owned ClickHouse table (§5, read
  flip NOT yet baked) does not carry a `synthetic` column, so when that read flips the column is
  owed for the filter to hold on that medium. Documented in `business_events.persisted_business_events`.
- **Operator go-and-observe moment.** Flip `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED=1` and watch the
  boot posture line report the scheduled canary, then an hourly synthetic recouvrement turn fire
  (green when the LLM answers, red when it doesn't — honest either way), its S1 entry land, and the
  descriptor's `synthetic_run` light up — all while the Métier tab's business metrics stay clean.
  The real `InProcessChatInvoker` graph path is exercised here, not in the hermetic unit suite
  (same posture as the seal's Rfc3161Provider).

## Log (newest first)

- 2026-07-08 — **I3 landed (`3597e124`). ADR 0019 is I1–I4 complete.** The http binding gains its
  runtime. The invoker (`HttpTurnInvoker`, `tessera.api.agent_invoker`) POSTs a TurnInput to the
  declared endpoint, forwards the *verified* operator assertion (0010 Phase B — refuses an empty one
  before the network, no anonymous invocation §4), honours `timeout_ms`, validates the response
  against the turn contract, and emits one S1 event per call. It never raises: a timeout / refused
  connection / non-2xx / non-conformant body is an honest RED, never a fabricated green (the seal's
  H3 invariant, applied to http invocation). It is pure HTTP with no runtime-graph import and lives
  in `tessera.api` (off the boundary-scanned control plane), so the 0017 §1 ratchet stands. The SDK
  testkit gains `verify_turn_result` — the reusable "an agent declaring http must speak the turn
  contract" gate. The first invocable external agent (`examples/turn-agent/`) is out-of-process with
  a zero tessera import (stdlib http `POST /turn`); it declares `binding: http` while hello-agent
  stays the publish-only `none` proof. The Console consumer's server seam (`POST /agents/{id}/invoke`)
  enforces every §4 property before the invoker runs — operator-only, plane-scoped (`routable`,
  0013), http-binding-only, audited. Console generation extends to http: a request/response test
  bench (invocable + endpoint + localized chrome), rendered by the `HttpConsole` frontend through a
  Next BFF proxy that mints the assertion — so a foreign-runtime agent gets a console the day it
  declares a binding, zero cockpit code. Streaming open question resolved: request/response for I3
  (streaming stays an optional future capability flag). Verified end-to-end: the real invoker drives
  a LIVE turn-agent over HTTP → green + a conformant TurnResult (zero violations); route gating
  pinned via TestClient. Fleet composition updated for the 5th agent. Gate twice-green
  (ruff/format/mypy/tsc/biome + 1503 unit, +18 new). **Live render verified via a throwaway
  dev-preview** (ports 3096/8096, torn down; reference + codex previews untouched): all three
  binding types render server-side from the declaration — turn-agent → the HttpConsole panel
  (title, "Envoyer le tour", the `127.0.0.1:8500/turn` endpoint chip), hello-agent → honest-empty
  ("Aucune invocation de test…"), support-client → the interactive console (parity). The invoke
  proxy enforces **401 without an operator session** end-to-end (no anonymous invocation). The one
  remaining unexercised path is the *authenticated* click-through (operator next-auth login →
  BFF mints the assertion → green TurnResult in the browser) — it needs a logged-in operator + the
  signing key, so it stays the operator's supervised dev-preview item; every layer beneath it is
  verified (invoker→live turn-agent green + conformant; route gating; proxy 401). **HALT: final
  Claude review before merge to main.**

- 2026-07-08 — **I2 landed (`4340bdad`). The Console is now a generated surface.** The last
  hand-wired cockpit surface stops assuming every agent is chattable: its shape is derived from the
  agent's declared `invocation.binding` (ADR 0019 §I2 / §2). `compute_agent_console` gains an
  `agent_id` (route `?agent=`, the client-facing convention) and reads the binding through the
  boundary-allowed registry seam (`tessera.agent.registry`) — never the runtime graph, so the 0017
  §1 ratchet stands (`test_observability_boundary` green). `in_process_chat` → the full interactive
  payload verbatim (parity, no behaviour change); `none` (hello-agent, publish-only) → a slim
  honest-empty payload carrying the binding + a localized `empty` descriptor and NONE of the
  tools/guardrails/eval panels (the honesty invariant: never fabricate config for an agent that runs
  no tessera guard). The frontend gates on `invocation.invocable`, SSR-scoped to the routed agent so
  there is no chattable-by-default flash; an absent block keeps the interactive console (no
  false-empty on a stale payload). Scope was held to free-text parity + honest-empty — the ADR's own
  open question (capability *parameters* as generated forms) stays deferred. Verified end-to-end
  through the real HTTP route (support-client interactive, hello-agent honest-empty, unknown →
  `available:false`, fr/de/en localized). Gate twice-green (ruff/format/mypy/tsc/biome + 1485 unit,
  new `test_observability_agent_console`). Next: I3 (http invoker + first external agent). **I2/I3
  do not touch the canary path (I4) — no regression there.**

- 2026-07-08 — **ADR 0019 I1+I4 review: APPROVED — merge feu vert.** Merged to `main` by clean
  fast-forward (`c6aa3823` → `7fd01f8f` + this entry). **Ratified deviation** — graph-seam vs
  `/chat`, recorded as a *conscious refinement* so I2 inherits no confusion: one declared binding
  (`in_process_chat`), **two entry depths per consumer**. The **canary** consumer (I4) enters by
  the eval seam (`compile_graph().ainvoke` — eval family, zero transcript pollution, zero overlap
  with the in-flight I2/agent-console work). The **Console** consumer (I2, still deferred) will
  enter by the real `/chat` route — the same declared binding, a different entry depth. The CH
  synthetic-column follow-up (§Owed follow-ups) remains tracked. Operator go-and-observe moment is
  live once `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED=1` + a server restart in the main checkout.
  (Env-file form: the nested `TESSERA_OBSERVABILITY__` delimiter is what pydantic binds for the
  nested `observability` block from `.env.local` — the single-prefix `TESSERA_OBS_` form only
  binds when exported as a live env var, a trap the boot posture line catches honestly.)

- 2026-07-08 — **I4 landed (`9c02e35f`). ADR 0019 I1+I4 mission complete.** The off-chrono canary
  scheduler mirrors the Hica-seal runner exactly: `canary_posture` is the single source of the
  scheduling decision (one honest boot line, idle by default), one background loop per scheduled
  agent at the manifest cadence, best-effort off every request path. `InProcessChatInvoker` drives
  the eval-harness in-process seam (`compile_graph().ainvoke`, §3) wrapped in `synthetic_turn()`;
  a failed cycle is RED, never a fabricated green. §4 acceptance proven: a synthetic turn's events
  never enter business metrics — excluded at the emit-time Prometheus guard AND the one business
  read seam (Métier/scores/signals/coverage). One S1 event per invocation
  (`tessera.agent.canary`) is both the governed-act audit and the descriptor's `synthetic_run`
  freshness record. Boundary ratchet stands (invoker agent-side; descriptor reads the S1 ledger,
  never the runtime). I2/I3 remain deferred. **HALT: final Claude review before merge to main.**

- 2026-07-08 — **I1 landed (`80a83753`).** ADR 0019 §1 declared cockpit→agent seam shipped as
  data, never an import (the 0017 boundary ratchet stands — the binding travels over a transport,
  not a module graph). `agentspec.py` gains `InvocationBinding` / `InvocationAuth` / `InvocationSpec`
  + `parse_invocation`; `registry.py` carries `Agent.invocation` (always present, default `none`)
  parsed fail-fast like the observability block; `agents.yaml` declares the four bindings;
  `tests/unit/test_invocation.py` is the CI gate (valid bindings, closed vocabularies, illegal
  states unrepresentable, native declarations). No behaviour change. Next: I4 (canary scheduler).
