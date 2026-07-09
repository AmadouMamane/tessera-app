# 0018 — Assistant runtime: the turn contract & the typed artifact lifecycle

- Status: **accepted** (decision 2026-07-06) — retro-ratifies the shipped recouvrement
  runtime as the reference implementation; generalisation phased (see §Migration plan)
- Date: 2026-07-06
- Deciders: Tessera maintainers
- Related: 0008 (audience/surface/auth), 0010 (recouvrement operator agent; Phase C
  console), 0013 (entry routing — business vs control plane), 0016 (business events
  fan-out), 0017 (+ §Amendment 1: capabilities, `external_effect_level`, invariant),
  `src/tessera/agent/recouvrement.py` (`build_recouvrement_graph_v1`),
  `src/tessera/recouvrement/message_templates.py`,
  `webapp/frontend/components/recouvrement/recouvrement-assistant-backend.ts`,
  `docs/design/ui-contract.md`, the "ADR-002/ADR-005" vision drafts (2026-07-06,
  chat-authored, outside the numbered corpus — harvested here).

## Context

The recouvrement drawer shipped a runtime that already embodies the right principles —
without naming them as a platform contract:

- **typed artifacts** built by dedicated graph nodes (`build_contact_rule_artifact`,
  `build_schedule_proposal_artifact`, `build_reminder_draft_artifact`);
- **typed artifact actions** (`ArtifactActionDecision`, `_canonical_artifact_action`,
  the artifact-action workflow) — a button dispatches an action, not chat text;
- **deterministic policies** pre-generation (`evaluate_contact_policy`,
  `evaluate_schedule_policy`) and **post-generation**
  (`review_client_message_policy`: tone, unvalidated commitments, amount consistency);
- **intent routing** over free messages (`route_recouvrement_intent`, slot extraction);
- **template-framed drafting** with generation metadata (`generation_mode`,
  `template_id`, `template_version`);
- **structured output** projected into a typed `RecouvrementOutput` with
  `businessEvents` + `businessScores` (0016).

The field incidents that motivated this shape are real and recorded (the vision drafts
document them): buttons treated as free chat, case context displaced by the last
message, internal labels leaked into user-facing copy, per-case `message.includes()`
patches, artifacts regenerated instead of updated.

**The problem:** the contract is implicit and recouvrement-specific. The graph's
TypedDicts and the front's `RecouvrementDrawerTask` / `RecouvrementBackendIntent` /
`RecouvrementArtifactFamily` unions live in per-agent files; nothing stops agent N+1
from reinventing turn handling differently — and the vision drafts *demonstrated* the
failure mode by proposing platform-wide `AssistantIntent` / `AssistantActionType`
unions filled with recouvrement values (the O(agents) enum smell, in the very document
meant to kill it). This ADR names the platform-level contract so the next agent
inherits it instead of re-deriving it.

## Governing rule

> **The LLM produces content inside a frame. State and artifacts drive the UI. Buttons
> dispatch typed actions. Deterministic policies decide authorization.**

The LLM never pilots the interface and never decides authorization (0016/0017
restated); it is invoked only to produce content, under constraints, against a schema.

## Decision

### 1. The turn contract

One entry point per agent runtime — the I/O of its graph, not a new service layer:

```
TurnInput  = { case_context, active_task,
               user_message XOR typed_action,
               artifacts, mini_history }
TurnResult = { intent, visible_reply,
               artifact_updates[], suggested_actions[] (typed),
               checks[], business_events[] (0016 envelope) }
```

*(0019 §Amendment 1, 2026-07-09: `TurnInput` gains an optional wire field
`synthetic: boolean` — set only by the platform's declared invocation consumers; an agent
serving a synthetic turn must propagate the stamp onto everything it emits. Backward
compatible; the decision and its conformance duty live in 0019 §A1.1.)*

**The state machine IS the agent's LangGraph graph** — `build_recouvrement_graph_v1`
is the reference implementation. There is no separate `AssistantService` layer: adding
one would duplicate state the graph already owns. Runtime events ride the 0016
envelope and the 0017 grammar — never a parallel `AgentEvent` type (0017 §Amendment 1
already rejected that fork).

### 2. Typed actions vs free text — and per-agent enums

A button click dispatches a **typed action** `{type, case_id, source_artifact_id,
params}`; the button label is never sent as a chat message. Free messages go through
the **intent router**; routing must consider the whole capability set, not just the
active tab (the recorded bug: "comment peut-il régler ses échéances ?" must route to
`explain_payment_options` even while `check_contact_rule` is the active task).

**Binding rule:** intent, action and task enums are **per-agent, derived from the
AgentSpec capabilities (0017 §A1.1)** — generated (backend `Literal` types + frontend
union types), never hand-written platform unions. The per-agent-file placement the
front already uses is correct and becomes codegen output. This makes the O(agents)
enum churn unrepresentable.

### 3. Artifacts are the source of truth; chat is the steering wheel

```
If the content is actionable or must be kept   → it lives in a card (artifact).
If it is a short clarification or confirmation → it lives in the chat.
```

An edit to an artifact ("rends le message plus empathique") produces **version N+1**
of the *same artifact*, retaining prior versions; the mini-history records one line
("Version 2 — ton plus empathique"), never a piled chat transcript. The chat never
becomes the primary thread.

### 4. The canonical artifact lifecycle

Cockpit, invariant checker (0017 §A1.3) and cross-agent aggregations reason over
**canonical machine states**:

```
draft → inserted → pending_validation → validated → sent
                                      ↘ blocked (terminal alternative, any stage)
```

Domain **status labels** stay expressive and agent-owned — today's code uses
`indicatif`, `prepared`, `reminder_prepared`, `insertion_prepared`, `approved`,
`local_clipboard_only` — but each artifact type **declares its label → canonical-state
mapping** in the AgentSpec (e.g. `indicatif → draft`, `approved → validated`).
Honesty constraint (binding): **no label may map to `validated` without a validating
event in the chain, and none may map to `sent` without a real external channel** —
recouvrement today tops out at `insertion_prepared` (there is no case backend, 0010),
and its mapping must say so rather than cosplay a send.

### 5. Deterministic policy stages

Two named stages, both emitting grammar events (`policy.decision_made`,
`action.blocked`) with reason codes:

- **pre-generation** — authorization and routing decisions (contact window, schedule
  validation requirement, surface authorization);
- **post-generation** — review of LLM output before it reaches the UI (pressure/tone,
  unvalidated financial commitments, amount consistency);
  `review_client_message_policy` is the reference.

Policies remain **code in the domain package** with **declared metadata** (0017 §A1.1,
§Amendment 2); the vision drafts' YAML policy *engine* stays rejected.

### 6. Structured LLM calls

The LLM is called only when content must be produced (summary, draft, reformulation,
explanation), with a **structured task**: `{task, case_context, constraints[],
output_schema}` — never a vague prompt. Output is schema-validated (Pydantic; a Zod
mirror where the front parses it). Invalid output → **`error_recoverable`**: keep the
previous state, offer regeneration, never render unvalidated content. Template-framed
generation keeps its metadata (`generation_mode`, `template_id`, `template_version`) so
provenance renders in the cockpit (message provenance already ships this).

### 7. Context discipline

The stable case context anchors every turn; the last user message never displaces it.
The collaborator operating the assistant is **never the customer** (their questions are
internal instructions; the customer never speaks to the drawer). Internal identifiers
(intent ids, task keys, capability ids) never render as user-facing copy — labels come
from i18n keys, sweep-gated (0017 §3).

## Acceptance criteria (platform-level; seeded into each agent's eval pack)

1. A button click after a schedule proposal reuses the existing artifact — no
   regeneration, no LLM call for pure UI actions (insert/copy).
2. "Puis-je l'appeler à 22 h ?" answers a deterministic no when the window is 8h–20h —
   from the policy, not the model.
3. An off-task free message routes to the right capability (the
   `explain_payment_options` case).
4. Internal labels never appear as user-visible copy.
5. No `message.includes()`-style dispatch anywhere in a runtime path.
6. An artifact edit produces a new version of the same artifact, prior version kept.
7. External effects require validation (0017 §A1.3 invariant — verified over events).
8. Invalid LLM output never renders; the previous state survives.

## Migration plan

- **A — Name the contract in code (no behaviour change).** Extract the
  `TurnInput`/`TurnResult` protocol from the recouvrement TypedDicts; document
  graph-as-state-machine; wire the acceptance criteria as tests over the existing
  runtime.
- **B — Canonical lifecycle.** Add the label→state mapping per artifact type to the
  AgentSpec; align cockpit badge rendering and the A1.3 invariant checker to canonical
  states; audit today's labels against the honesty constraint.
- **C — Enum codegen.** Generate backend `Literal`s and frontend unions from the
  AgentSpec capabilities; the recouvrement per-agent types become generated files.
- **D — Testkit.** Move the acceptance suite into the SDK testkit (0017 §7) so every
  new agent runs it in CI; seed eval-pack templates from it.

## Consequences

**Positive.** Agent N+1 inherits a proven runtime shape instead of re-deriving it; the
UI is predictable (cards, versions, typed actions); auditability falls out naturally
(typed everything → grammar events); the platform-union enum smell is unrepresentable;
the honesty constraints (no fake `sent`, no unvalidated `validated`) are structural.

**Negative / costs.** Codegen and schema discipline are new machinery; migrating
recouvrement's hand-written types to generated ones is real work; the canonical-state
mapping demands per-artifact-type care; conversational scenario tests must be
maintained.

**Neutral.** No behaviour change for the shipped recouvrement drawer in Phase A — this
ADR names what it does; later phases refactor its *types*, not its UX.

## Alternatives considered

- **Platform-wide intent/action unions** (the vision drafts' own shape) — rejected:
  O(agents) type churn and cross-agent coupling; the manifest generates per-agent
  enums instead.
- **A separate `AssistantService` layer above the graph** — rejected: the graph is the
  state machine; a second layer duplicates state and invites drift.
- **Chat-first UX with artifacts as attachments** — rejected for regulated surfaces:
  the artifact is the unit of work, validation and audit; a chat pile is none of those.
- **A parallel runtime event type (`AgentEvent`)** — rejected (0017 §Amendment 1): the
  0016 envelope + grammar is the only event model.
- **A YAML policy engine** — rejected again (0017 §Amendment 1 / §Amendment 2):
  policies are deterministic domain code with declared metadata.

## Open questions

- Are `inserted` and `sent` both needed when the SI has no real write path? Today
  insertion is `insertion_prepared` / `local_clipboard_only` (honest: no case backend,
  0010). The canonical states exist in the vocabulary now; agents map into the prefix
  they can honestly reach.
- Artifact version retention: keep all versions per case, or last N with the audit
  trail carrying the rest? (Ties to the replay bundle size budget.)
- Whether `TurnInput.typed_action` and the artifact-action workflow merge into one
  dispatcher or stay two entry paths (today: two, converging in the graph).
