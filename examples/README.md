# `examples/` — the platform witnesses

These are **not** banking agents. Tessera's three banking agents (`support-client`,
`onboarding`, `recouvrement`) live in `src/tessera/agent/`. The agents here exist to
*prove a property of the platform*, and each one is the **minimal witness of exactly one
claim** — that is the rule this directory is held to. An example that proves two things at
once proves neither cleanly; when one fails, you no longer know which contract broke.

Every witness shares one property, and it is the point: **zero tessera import**. None of them
depends on a single line of this codebase.

The intent is not a purity contest. A real agent fleet is heterogeneous — other teams, other
vendors, other stacks, agents inherited through acquisitions. A platform that can only govern
the agents it built governs nothing, because the claim is circular. These agents are
deliberately foreign, and the cockpit observes them, tests them, and reads their declarations
anyway. That is the whole demonstration: **uniform governance over a fleet you did not
entirely build.**

| Example | Claim it witnesses | Direction | ADR |
|---|---|---|---|
| [`hello-agent/`](hello-agent/) | The cockpit can **observe** a foreign-runtime agent: it reaches a computed observability level from telemetry alone. | agent → cockpit | 0017 §F |
| [`turn-agent/`](turn-agent/) | An operator can **test** a foreign-runtime agent: it exposes an HTTP turn endpoint the cockpit invokes under the declared binding. | cockpit → agent | 0019 §I3 |
| [`duplex-agent/`](duplex-agent/) | The two planes **compose** across a process boundary: it serves turns *and* publishes telemetry, so invoking it produces the evidence that raises its own computed level — and the `synthetic` stamp survives the crossing. | both | 0019 §A1.2 |

The two directions are the two planes, and ADR 0019 keeps them apart on purpose: the
observability contract stays publish-only, and invocation travels the single declared,
authenticated, audited path. Hence the deliberate asymmetry — `hello_agent.py` imports
`opentelemetry` and opens no socket; `turn_agent.py` opens a socket and imports no
`opentelemetry`. **The absence is the assertion.** Adding the missing import to either file
would silently destroy the proof it exists to make, so `tests/unit/test_example_agents.py`
checks the negative space.

`duplex-agent` does both, and that is *its* single claim: not "an agent that can do more", but
**the composition itself**, which neither of the others can witness alone. Keeping the first two
minimal is what lets the third mean something — so the same test asserts they stay that way.

## Running them

```bash
# hello-agent — needs the observability stack (collector on :4418)
uv run python examples/hello-agent/hello_agent.py

# turn-agent — serves POST /turn on :8500; the cockpit's console invokes it
uv run python examples/turn-agent/turn_agent.py

# duplex-agent — serves POST /turn on :8501 AND emits to the collector; invoke it from the
# cockpit's console and watch its computed level rise off its own telemetry
uv run python examples/duplex-agent/duplex_agent.py
```

All three appear in the cockpit's fleet, tagged `demo`. That is intentional: hiding them would
make the fleet lie about what the spine governs, and `hello-agent`'s presence on the fleet
*is* the acceptance test of ADR 0017 §F. Their manifest entries live in
`src/tessera/agent/agents.yaml`.

## The gap `duplex-agent` closed (2026-07-09)

Until it existed, `turn-agent` emitted no telemetry and `hello-agent` accepted no turns, so **no
example closed the loop** — invoke an agent, watch it emit, see the cockpit's evidence rise — and
the `synthetic` stamp that keeps test turns out of business metrics (ADR 0019 §4) was an in-process
`ContextVar` that cannot cross a process boundary.

Both are now witnessed. `synthetic` travels on the wire as part of the turn contract (§A1.1), and
`duplex-agent` propagates it onto every span, metric and business event it emits — a duty the SDK
testkit *checks*, so it cannot quietly lapse. `duplex-agent` also declares the first `input_schema`
anywhere, and the Console renders it as a generated form: it gained a typed test bench without a
single hand-written line in `webapp/frontend/`.
