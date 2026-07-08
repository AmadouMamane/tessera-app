# 0019 — Invocation binding: the declared cockpit→agent seam

- Status: **accepted** (decision 2026-07-08) — **implementation deferred**; the priority
  trigger is the first http-invocable external agent OR the canary scheduler, whichever
  comes first (see §Implementation trigger)
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

- **I1** — `invocation` block in the AgentSpec (schema + validation; `none` default);
  native agents declare `in_process_chat`. No behaviour change.
- **I2** — Console generation for `in_process_chat` (parity with today's console,
  rendered from declarations); honest-empty for `none`.
- **I3** — `http` binding: the invoker (assertion forwarding, timeout, audit event) +
  the first invocable external agent; conformance test in the SDK testkit (an agent
  declaring `http` must speak the turn contract).
- **I4** — Canary scheduler on the binding (cadence from the manifest, synthetic
  stamping, freshness feeding the existing canary descriptor).

## Open questions

- **Streaming over the http binding**: the in-process console streams SSE; does the http
  binding require streaming for parity, or is request/response acceptable for test
  turns? (Leaning: request/response for I3; streaming as an optional capability flag.)
- Rate limits / concurrency caps per binding (an operator hammering a production agent's
  test endpoint is a governance question, not just an infra one).
- Whether the Console exposes capability *parameters* (from `input_schema`) as generated
  forms in I2 or only free-text + typed action buttons initially.
