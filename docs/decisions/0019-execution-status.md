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
| I4 | Canary scheduler on the `in_process_chat` binding (cadence from the manifest, synthetic stamping, S1 per invocation, freshness feeding the existing canary descriptor) | 🔨 in progress | — | Runner pattern = the just-landed seal off-chrono scheduler (lifespan + boot posture line; idle by default). |

## Log (newest first)

- 2026-07-08 — **I1 landed (`80a83753`).** ADR 0019 §1 declared cockpit→agent seam shipped as
  data, never an import (the 0017 boundary ratchet stands — the binding travels over a transport,
  not a module graph). `agentspec.py` gains `InvocationBinding` / `InvocationAuth` / `InvocationSpec`
  + `parse_invocation`; `registry.py` carries `Agent.invocation` (always present, default `none`)
  parsed fail-fast like the observability block; `agents.yaml` declares the four bindings;
  `tests/unit/test_invocation.py` is the CI gate (valid bindings, closed vocabularies, illegal
  states unrepresentable, native declarations). No behaviour change. Next: I4 (canary scheduler).
