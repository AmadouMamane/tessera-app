# ADR 0019 — invocation binding: execution status

Single source of truth for **where the ADR 0019 implementation is**. Same protocol as the
0015 / 0017 ledgers: implement → full gate **twice green** (`ruff check` + `ruff format --check`
+ `mypy` + `tsc --noEmit` + `biome check` + `pytest -m "not integration"`) + phase-specific
verification → commit (**targeted staging, never `git add -A`**) → update this file → advance.

**Trigger fired 2026-07-08:** the operator activated the **canary scheduler** path (ADR 0019
§Implementation trigger — "the canary scheduler, whichever comes first"). This mission delivers
**I1 + I4 only**. I2 (Console generation) and I3 (http invoker + first external agent) stay
**deferred** — I2 in particular is off-limits while the agent-console / headers work is in flight
on the codex worktree (avoid a conflict on a surface being edited live).

## Phase ledger

| Phase | Scope (short) | Status | Commit | Notes |
|---|---|---|---|---|
| I1 | `invocation` block in the AgentSpec (schema + validation, `none` default); native agents declare `in_process_chat` | ✅ done | `80a83753` | `InvocationBinding` {none·in_process_chat·http} + `InvocationSpec` (`extra="forbid"`, http-only fields unrepresentable on other bindings, http must name operator-assertion auth). `Agent.invocation` always present (default `none`). support-client/onboarding/recouvrement → `in_process_chat` (pure codification of `/chat`, no behaviour change); hello-agent → `none`. Gate twice-green (ruff/format/mypy/1460 unit); frontend untouched. |
| I2 | Console generation for `in_process_chat` (parity, rendered from declarations); honest-empty for `none` | ⛔ deferred | — | **Out of scope this mission.** Conflicts with the agent-console / headers work in flight (codex). |
| I3 | `http` binding: the invoker (assertion forwarding, timeout, audit) + first invocable external agent; SDK conformance test | ⛔ deferred | — | Out of scope this mission. The http *schema* is modelled by I1; the *invoker* is not built. |
| I4 | Canary scheduler on the `in_process_chat` binding (cadence from the manifest, synthetic stamping, S1 per invocation, freshness feeding the existing canary descriptor) | ✅ done | `9c02e35f` | Off-chrono scheduler mirroring the seal (lifespan + boot posture line; idle by default). `agent/canary.py`: `InProcessChatInvoker` drives `compile_graph().ainvoke` in a `synthetic_turn()` context; `run_canary_cycle` emits one `tessera.agent.canary` S1 per invocation (green/red, never a fake green). Synthetic isolation excluded twice: the emit-time Prometheus guard + the read seam every business surface flows through (default `include_synthetic=False`). Descriptor gains `synthetic_run` (from the S1 entry) + `cadence_s`. recouvrement declares hourly; switch `TESSERA_OBS_CANARY_SCHEDULER_ENABLED` (default off). Gate twice-green (ruff/format/mypy/1479 unit); boundary ratchet green. |

## Owed follow-ups (explicit, never silent)

- **ClickHouse owned business-events read (§5) needs a `synthetic` column.** The synthetic
  exclusion is airtight today: the emit-time Prometheus guard is medium-independent, and the read
  seam filters the in-process store (the default read medium). The owned ClickHouse table (§5, read
  flip NOT yet baked) does not carry a `synthetic` column, so when that read flips the column is
  owed for the filter to hold on that medium. Documented in `business_events.persisted_business_events`.
- **Operator go-and-observe moment.** Flip `TESSERA_OBS_CANARY_SCHEDULER_ENABLED=1` and watch the
  boot posture line report the scheduled canary, then an hourly synthetic recouvrement turn fire
  (green when the LLM answers, red when it doesn't — honest either way), its S1 entry land, and the
  descriptor's `synthetic_run` light up — all while the Métier tab's business metrics stay clean.
  The real `InProcessChatInvoker` graph path is exercised here, not in the hermetic unit suite
  (same posture as the seal's Rfc3161Provider).

## Log (newest first)

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
