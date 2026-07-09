# 0019 — Invocation binding: the declared cockpit→agent seam

- Status: **accepted** (decision 2026-07-08) — **I1–I4 implemented** (2026-07-08: I1/I4 via the
  canary-scheduler trigger `80a83753`/`9c02e35f`; I2 console generation `4340bdad`; I3 http invoker
  + first invocable external agent + conformance `3597e124`). **Amendment 1** (2026-07-09):
  `synthetic` crosses the wire + the integration witness — accepted, implementation deferred
  (I5/I6). Progress: `docs/decisions/0019-execution-status.md`
- Date: 2026-07-08
- Deciders: Tessera maintainers
- Related: 0008 (audience/surface/auth), 0010 (operator assertion — Phase B mechanism),
  0013 (planes), 0017 (+§A1/§A2 — the observability contract, AgentSpec), 0018 (turn
  contract, per-agent generated enums), `docs/signal-catalog.yaml` id 94
  (canary-tagging), `src/tessera/observability/agent_console.py`,
  `webapp/frontend/components/agent/agent-console.tsx` (streams via the in-process
  `/chat` route), the rails registry (XT-01, BR-01).

## Context

ADR 0017 made the cockpit a generated artifact: fleet cards, tabs, signals, badges and
conformance gates all derive from the AgentSpec. One surface escaped: **the Console** —
the operator's interactive test bench. Verified in code: it streams through the same
in-process `/chat` route as the product, and its debug payload derives from in-process
sources (prompt files, guard policy, runtime settings). It is the last hand-wired,
runtime-coupled surface in the control plane.

The step-7 acceptance test made the gap concrete: `hello-agent` (out-of-process, pure
OTLP, zero platform imports) reaches a computed L1 on the fleet — and has no console.
There is nothing for the console to talk to, and no declaration through which it could
learn how.

The tension is conceptual, not incidental. The 0017 governing rule — *agents publish;
the cockpit reads the spine; nobody queries an agent* — is a rule about **observability
facts**, and it is correct. But testing an agent is not observing it: a test bench, by
nature, **talks to the agent**. Extending the observability contract to cover invocation
would corrupt its plane separation; leaving the console hardcoded condemns it to
O(agents) drift and permanent in-process coupling.

A second consumer sharpens the need: the canary quality net (signal 94) shipped in step
6b as *declared, not simulated* — the descriptor is manifest-generated, but the scheduled
synthetic execution was deferred for lack of exactly this primitive: a governed way for
the platform to send a turn to an agent.

## Governing rule

> **The observability contract stays publish-only. Exactly ONE cockpit→agent path
> exists: the declared invocation binding — used only by declared consumers, under
> operator auth, with every invocation audited.**

The binding is **data** (a declaration in the AgentSpec), never an import: the 0017
boundary ratchet (zero frozen exceptions, exact-set equality) continues to forbid the
control plane from importing the agent runtime. Invocation travels over a transport, not
a module graph.

## Decision

### 1. The AgentSpec gains an `invocation` block

```yaml
invocation:
  binding: in_process_chat | http | none
  # binding: http only —
  endpoint: https://…/turn        # the agent EXPOSES; the cockpit consumes the declaration
  timeout_ms: 15000
  auth: operator-assertion        # 0010 Phase B posture; no anonymous invocation, ever
```

- `in_process_chat` — the existing `/chat` seam, now *declared* instead of assumed. The
  three native agents adopt it verbatim (parity, no behaviour change).
- `http` — the agent exposes a turn endpoint speaking the 0018 turn contract
  (`TurnInput` → `TurnResult` serialisation); the cockpit's invoker forwards the signed
  operator assertion (constant-time-verified server-side, per 0010).
- `none` — the honest default for publish-only agents (`hello-agent` today): the Console
  renders honest-empty — *"this agent exposes no test invocation — observe it through its
  runs and evals"* — never a broken chat.

### 2. The Console becomes a generated surface

It composes from four declarations that already exist:

| Ingredient | Source | Already shipped by |
|---|---|---|
| Transport (how to send a turn) | `invocation.binding` | **this ADR** |
| Typed action affordances | capabilities → generated per-agent enums | 0017 §A1.1 + 0018-C |
| Output rendering | `TurnResult` contract (reply, artifacts, business events) | 0018 §1 |
| Inspection | XT-01 trace link + the turn's grammar events (BR-01-style timeline) | rails registry, step 4 |

No per-agent console code. An agent's console is exactly as rich as its declarations —
the same generative property as every other cockpit surface.

### 3. Declared consumers, closed list

1. **The Console** — interactive operator testing.
2. **The canary scheduler** (signal 94's deferred runtime piece) — scheduled synthetic
   turns through the *same* binding; this ADR is the prerequisite it was waiting for.
3. **Evals stay harness-side** — already manifest-declared per capability
   (`eval_packs`, 0017 §A1.1); the harness invokes agent packages directly and is not a
   cockpit consumer.

Any other cockpit→agent call is illegal. Adding a consumer requires amending this list.

### 4. Every invocation is a governed act

- Auth: the operator assertion (0010 Phase B), role-labelled; `collections`-tier roles
  cannot invoke cockpit-tier consoles (0013 plane rules apply unchanged).
- Audit: each invocation emits an S1 event (who tested which agent, when, binding used)
  into the audit ledger — a test is an *action on a governed system*, and the ledger is
  where actions live.
- Honesty: test and canary turns are stamped synthetic (the `environment`/synthetic
  dimension, signal 94's tagging) so they can **never pollute business metrics** — the
  Métier tab and the business signals must be able to exclude them by declaration, not
  by convention.

## Consequences

**Positive.** The last hand-wired cockpit surface becomes generated; foreign-runtime
agents get a console the day they declare a binding — zero cockpit code; canaries gain
their missing primitive; the publish-only observability contract stays pure; the
cockpit→agent surface is enumerable, authenticated and audited instead of implicit.

**Negative / costs.** A second contract to version and validate; the http binding needs
a streaming story (see §Open questions); the invoker is new attack surface — mitigated
by the closed consumer list, mandatory operator assertion, and audit-on-every-call.

**Neutral.** Nothing changes for the three native agents until implementation: declaring
`in_process_chat` is a no-op codification of current behaviour.

## Alternatives considered

- **Extend the 0017 observability contract with invocation.** Rejected: conflates the
  publish-only data plane with a control action; the boundary rule would stop meaning
  anything precise.
- **Per-agent console pages.** Rejected: O(agents) — the exact drift class 0017
  §Alternatives already buried (hardcoded panels).
- **Ad-hoc cockpit→agent HTTP without declaration.** Rejected: undeclared coupling,
  un-enumerable attack surface, and nothing for conformance to check.
- **Console reads-only (drop interactive testing).** Rejected: the operator's ability to
  probe an agent before promoting it is part of the governance story (0010 §console);
  evals cover the systematic case, not the exploratory one.

## Implementation trigger & phases (deferred, pre-sequenced)

Priority rises with the first http-invocable external agent OR the canary scheduler —
whichever is wanted first.

- **I1 — ✅ done (`80a83753`).** `invocation` block in the AgentSpec (schema + validation;
  `none` default); native agents declare `in_process_chat`. No behaviour change.
- **I2 — ✅ done (`4340bdad`).** Console generation from the declared binding: `in_process_chat`
  renders today's console (parity), `none` renders honest-empty. The payload is agent-scoped and the
  binding is read via the registry seam (the 0017 §1 ratchet stands). Free-text parity only —
  capability-form generation (see Open questions) stays deferred.
- **I3 — ✅ done (`3597e124`).** `http` binding runtime: the invoker (`HttpTurnInvoker` — assertion
  forwarding, timeout, turn-contract validation, one S1 audit event per call, honest RED never a
  fabricated green; pure HTTP, no runtime-graph import, ratchet stands) + the first invocable
  external agent (`examples/turn-agent/`, zero tessera import, declared `binding: http`) + the SDK
  conformance test (`verify_turn_result`). The governed seam `POST /agents/{id}/invoke` (operator +
  plane + binding + audit) makes it reachable; console generation extends to a request/response test
  bench. Verified end-to-end against a live turn-agent.
- **I4 — ✅ done (`9c02e35f`).** Canary scheduler on the binding (cadence from the manifest via
  `invocation.canary_cadence_s`, synthetic stamping excluded from business metrics, one S1 event
  per invocation, freshness feeding the existing canary descriptor's `synthetic_run` facet).
  Off-chrono runner mirroring the Hica seal; idle until `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED`.

## Open questions

- **Streaming over the http binding**: ~~the in-process console streams SSE; does the http
  binding require streaming for parity, or is request/response acceptable for test turns?~~
  **Resolved (I3):** request/response. The http console is a request/response test bench
  (`POST /agents/{id}/invoke` → one TurnResult); streaming stays an optional future capability
  flag, not required for the test-turn use case.
- Rate limits / concurrency caps per binding (an operator hammering a production agent's
  test endpoint is a governance question, not just an infra one).
- ~~Whether the Console exposes capability *parameters* (from `input_schema`) as generated
  forms in I2 or only free-text + typed action buttons initially.~~
  **Resolved (Amendment 1):** yes, generated forms — deferred until a declaration exists to
  generate from. §A1.2(c) makes the integration witness the forcing function, with the
  acceptance criterion that settles it: zero hand-written frontend lines.

## Amendment 1 — `synthetic` crosses the wire; the integration witness (2026-07-09)

Status: **accepted** (2026-07-09) — **implementation deferred**, pre-sequenced as I5/I6.
Nothing in this amendment modifies the two existing witnesses.

### A1.1 The synthetic stamp becomes part of the turn contract

**The gap.** §4 promises that test and canary turns *never pollute business metrics*. Every
mechanism behind that promise is in-process: `synthetic_turn()` is a ContextVar, and the
emit-time Prometheus guard and the business read seam key off platform-side stamping. An
`http`-bound agent emits its own telemetry from another process — nothing carries the stamp
across the boundary. The gap is unobservable today only by luck: the sole http agent
(`turn-agent`) emits nothing, so there is nothing to mis-stamp. The first http agent that
*both* serves turns and publishes telemetry breaks §4 silently.

**Decision.**

- `TurnInput` gains **`synthetic: boolean`** (wire key `synthetic`; absent ⇒ `false`). Set
  exclusively by the platform's declared consumers (Console test turns, canary turns);
  product traffic never sets it. A 0018 wire-schema addition, backward compatible;
  0018 §1 carries a pointer here.
- **Propagation duty:** an agent serving a turn with `synthetic: true` MUST stamp the
  synthetic dimension (signal 94's existing vocabulary) on every span, metric and business
  event it emits for that turn. For `http` bindings this duty is a **conformance
  requirement checked by the SDK testkit** (the span-contract and grammar-conformance
  suites gain the case) — mandatory, not advisory, because unpropagated synthetic traffic
  inflates business metrics until caught.
- **Trust posture — belt and braces, both directions.** The platform does not *rely* on
  the agent: every synthetic invocation already leaves its own S1 record (§4), the
  in-process guard stays, and platform-side read seams keep excluding by the platform's
  own record where they can. But out-of-process emissions reach the spine bearing only
  what the agent stamped — hence the duty, and hence the testkit gate.

**Rejected.**

- *Trusting the ContextVar across processes* — impossible by construction; a ContextVar is
  process-local.
- *A parallel test-traffic event taxonomy* — 0017 §A1 already buried parallel taxonomies;
  the existing synthetic dimension is the entire vocabulary.
- *Distinguishing console-vs-canary on the wire* — the agent must not care who is testing
  it: one flag, one duty.

### A1.2 The integration witness: `examples/duplex-agent/`

**The rule that keeps `examples/` from becoming a zoo:** each example is the minimal
witness of exactly one claim. `hello-agent`: *observable without being invocable*
(0017 §F). `turn-agent`: *invocable without being observable* (§I3). Their emptiness is
the assertion — the import-absence test guards it — and they are never merged or enriched.

**The unclaimed claim: the two planes compose across a process boundary.** Three couplings
no current witness exercises: the proof loop never closes (turn-agent cannot emit
evidence; hello-agent cannot be invoked); §4 is untested across the wire (A1.1's subject);
console form generation has no declaration to generate from.

**Decision.** One new witness, `duplex-agent` — named for what it does: it speaks both
directions. It serves `POST /turn` (0018 wire contract) AND emits OTLP for the turns it
serves, honouring the A1.1 propagation duty; it declares one capability with an
`input_schema`; **zero tessera imports** (the import-absence test extends to it); its
manifest `description` follows the fleet-card register rule (business language, intent —
never implementation notes).

**Acceptance** — each criterion closes a hole no current witness covers:

- **(a) The proof loop closes.** Invoking it (Console or canary) produces turn evidence
  through the existing OTLP-metrics pipeline; the level resolver reads it; the computed
  level rises *because of the invocation*. Any platform gap found on the way is a capital
  cost — labelled, fixed off-clock, the same accounting rule as the TTO run.
- **(b) §4 holds across the wire.** A synthetic turn against it appears **nowhere** in
  business metrics — the end-to-end proof of A1.1.
- **(c) Generated forms get their forcing function.** Its `input_schema` renders as a
  generated console form with **zero lines touched in `webapp/frontend/`**. The criterion
  is the usual one: if a single hand-written frontend line is needed, the generative
  thesis is refuted, not bent.
- **(d) The existing witnesses stay minimal.** `hello_agent.py` and `turn_agent.py` are
  unchanged (their minimality is part of the platform's test surface);
  `examples/README.md` gains one table row.

### Sequencing

- **I5 — A1.1** (contract field + invoker sets the flag + testkit case). Lands first:
  small, and every future http agent needs it.
- **I6 — A1.2** (`duplex-agent` + acceptance a–d). Depends on I5.

Both deferred pending an explicit go — this amendment records the decision, not the
schedule.
