# 8. Agent audience and surface

Date: 2026-06-22

## Status

Accepted, **not yet implemented**. This ADR extends the agent manifest
(`src/tessera/agent/agents.yaml`) and the supervisor
(`src/tessera/agent/supervisor.py`) with three first-class agent properties —
`audience`, `surface`, `auth` — and makes turn routing and handoff **scoped by
surface and authentication state** rather than ranging over one undifferentiated
fleet. The canonical tree is otherwise unchanged.

The interim fleet classification recorded below keeps **all three agents on the
shared customer chat** (no new UI is built now); the only behavioural change is
that `recouvrement` becomes reachable **only once the session is authenticated**,
which closes a live exposure described under Context.

A note on sequencing: the three manifest fields are **inert until `route_turn`
enforces them**. Shipping the fields without the scoping would be decorative and
dishonest — the boundary does not exist until it is enforced. The two land
together or not at all.

## Context

Tessera ships three governed agents — `support-client`, `onboarding`,
`recouvrement` — behind a single customer chat surface, with a server-side
supervisor (`route_turn`) selecting the agent per turn and a governed handoff
graph allowing agents to pass control to one another. The produit reframe (the
embeddable chat widget) assumes the customer talks to *one* assistant and the
supervisor routes invisibly.

That model rests on a hidden assumption: **every agent serves the same audience
through the same surface.** It does not survive contact with the fleet.

### The assumption breaks on recouvrement

`recouvrement` is owned by **Équipe Conformité**, runs **`strict`** guardrails,
and is described as *« Relances et impayés : échéanciers, rappels, escalade
conseiller »*. Whether its interlocutor is a **debtor** (a known, authenticated
customer negotiating their own arrears) or the **bank's collections staff** (an
internal back-office tool), it is categorically not a walk-up, anonymous,
general-public conversation the way `support-client` and `onboarding` are. It is
sensitive by construction.

### What the code encodes today

1. **The manifest has no notion of audience or surface.** `agents.yaml` binds
   model, prompts, knowledge, guardrails, eval set, tools, tags, and a handoff
   graph. `tags` (`[recouvrement, impayés]`) and `owner` (`Équipe Conformité`)
   *hint* at a different nature, but nothing the system reads acts on them. All
   three agents are one flat, equally-reachable pool.

2. **The supervisor routes over the whole fleet.** `route_turn(current_agent,
   user_input)` selects an agent from intent detection (`_detect_intent`) plus
   handoff legality (`can_handoff`). The handoff graph wires
   `support-client ↔ recouvrement`. Therefore, on the anonymous customer widget,
   a visitor whose message matches recouvrement intent **can be handed into the
   debt-collection agent** — one that reaches account data (`account_balance`,
   `transaction_search`) under `strict` compliance rules.

3. **There is no surface concept on the request either.** `ChatRequest`
   (`api/routes/chat.py`, `extra="forbid"`) carries `subject_id`, language,
   history, model — no agent, and no surface or audience. The entry point cannot
   tell the supervisor "this is the anonymous public widget; route accordingly."

The consequence is a **live audience/auth leak**: the most sensitive agent in the
fleet is reachable from the least privileged surface. This is not a future risk to
design against; it is a present gap to close.

### Why decide this now

The cost asymmetry is the whole argument. Adding audience/surface to the manifest
and deriving the routable pool from it is a small, local change. Retrofitting it
after a second surface exists means untangling the supervisor, the handoff graph,
the auth model, and the produit entry **simultaneously**, under live routing. The
seam is cheap before there is anything to tear apart and expensive after.

## Decision

### Three first-class properties on every agent

Each agent in `agents.yaml` declares:

| Property | Values | Meaning |
|---|---|---|
| `audience` | `customer` \| `operator` | The primary human the agent converses with: the bank's end-customer/prospect/debtor, or bank staff. |
| `surface` | `shared-customer-widget` \| `dedicated-ui` \| `cockpit-embedded` \| `api-only` | The delivery channel the agent is exposed through. |
| `auth` | `anonymous-ok` \| `customer-auth` \| `operator-rbac` | The minimum identity/authorization the session must satisfy to reach the agent. |

These are governed bindings like the rest of the manifest — declared once, read by
`tessera.agent.registry`, stamped through to routing.

### Routing and handoff become surface-and-auth scoped

`route_turn` takes the **entry surface** and the **session auth-state**, and
considers only agents whose `surface` includes that entry and whose `auth` the
session satisfies:

```
routable(surface, auth_state) =
    { a ∈ fleet : surface ∈ a.surface  ∧  auth_state ⊇ a.auth }
```

Handoff is legal only **within the same surface** (and auth permitting). A silent
cross-surface handoff is forbidden: moving a customer from a support chat into a
collections context, or from the public widget into an operator tool, is never an
implicit route — it is, if it exists at all, an explicit, governed, audited
transition (out of scope here). `can_handoff` gains the same surface/auth guard.

The produit entry passes its surface (`shared-customer-widget`) and the session's
auth-state to the chat endpoint. `ChatRequest` gains a **server-derived**
surface/auth context — never client-asserted authority: the auth-state is computed
server-side from the session, not read from the request body (which stays
`extra="forbid"`).

### Interim fleet classification (the decision recorded today)

| Agent | `audience` | `surface` | `auth` |
|---|---|---|---|
| `support-client` | `customer` | `shared-customer-widget` | `anonymous-ok` (account tools already gate to `customer-auth`) |
| `onboarding` | `customer` | `shared-customer-widget` | `anonymous-ok` |
| `recouvrement` | `customer` | `shared-customer-widget` *(interim)* | **`customer-auth`** |

`recouvrement` **keeps using the current product chat for now** — no new interface
is built. The single behavioural change is its `customer-auth` gate: an anonymous
walk-up can no longer be routed or handed into it, which closes the leak while
reusing the existing surface. This is the pragmatic, day-twenty-respecting choice:
install the seam, fix the exposure, defer the UI.

### The "dedicated interface" pattern (planned, not built)

When an agent outgrows the shared widget — the likely path for `recouvrement`
becoming an internal collections tool — it moves to `surface: dedicated-ui`,
`audience: operator`, `auth: operator-rbac`. That move is a **new presentation over
the unchanged core**: a scoped entry (its own route/page), scoped auth (operator
RBAC, never anonymous), and a purpose-built shell — for collections, a **case
console** (dossiers, échéanciers, relance timelines), not a chat bubble — that
**reuses the agent's existing LangGraph package, guard, and audit trail verbatim**,
and may reuse `ChatRoom` as one panel among others. No fork of the agent core,
exactly as the widget migration re-skins rather than re-implements the chat. The
manifest flip plus a new presentation is the entire change; the graph, tools,
guardrails, eval set, and audit are untouched.

## Consequences

**Closes a real exposure now.** The most sensitive agent stops being reachable
from the least privileged surface the moment the scoping lands.

**Makes the produit/cockpit split explicit and enforceable.** "The customer sees
one assistant; the operator sees the fleet" stops being a convention and becomes a
property the routing reads.

**Gives every agent a zero-rework growth path to its own interface.**
Audience/surface/auth is the seam that lets a dedicated UI be added later as a
presentation, not a re-architecture.

**Costs.** Three manifest fields; a signature change to `route_turn` and
`can_handoff` (now surface/auth-aware); a server-derived surface/auth context on
the chat entry; tests asserting (a) the anonymous widget pool excludes
`recouvrement`, (b) no cross-surface handoff, (c) the authenticated pool includes
it.

**Out of scope.** Building any dedicated UI; the operator/internal collections
console; cross-surface escalation flows; client-selectable or client-pinned agents
(`ChatRequest` stays `extra="forbid"`; surface/auth are server-derived).

**Honesty constraint (binding).** The manifest fields are inert until `route_turn`
enforces them. Do not ship `audience/surface/auth` as documentation of a boundary
the router does not yet apply — that would assert a control that does not exist.
The fields and the scoped routing land in the same change, or neither does.

## Implementation note — customer-auth session (the `_derive_auth_state` source)

The scoping above is only as honest as the `auth_state` feeding it. This note
records how that value is produced. (Recorded here rather than as a new ADR
because 0009 is already taken; the mechanism is a direct consequence of this ADR.)

**The single source of truth** is `tessera.api.session`. `_stream_turn` no longer
defaults `auth_state` to `ANONYMOUS`; it reads `resolve_session(request)`, which
verifies a **signed session cookie** and returns `CUSTOMER` when a valid session
is present, `ANONYMOUS` otherwise. `auth_state` is therefore derived server-side
from a verified artifact and **never** from `ChatRequest` (still `extra="forbid"`).

**What is real (architecturally):**

- **Signed cookie.** `tessera_session = base64url(payload) "." base64url(HMAC-
  SHA256(key, payload))`, carrying `{sub, auth, iat}`. A forged or edited cookie
  fails the constant-time MAC check and is ignored (treated as anonymous).
- **Key off-repo.** The HMAC key is `TESSERA_API_SESSION_SIGNING_KEY` (settings →
  GCP Secret Manager in prod). It is never committed; unset locally, the layer
  falls back to a process-ephemeral key with a warning.
- **Cookie hardening.** `httpOnly`, `SameSite=Lax`, `Secure` under TLS, with an
  issued-at stamp and an 8h expiry.
- **Tool gating on the same `auth_state`.** Account/PII tools (`account_balance`,
  `card_block`, `transaction_search`) declare `require_auth: customer-auth` in
  `guard/policy.yaml`. The guard adapter reads the server-derived `auth_state`
  (a contextvar set at the turn boundary) and **denies** them to an anonymous
  session — the gate is in the guard chokepoint, not cosmetic. Memory and the
  account identity bind to the session's `sub` when authenticated.

**What is demo-assumed (banque fictive, day-twenty):** "logging in" via
`POST /session/login` establishes a session for **one seeded customer identity**
(`demo-customer-001`, matching the account-tools demo dataset), labelled a demo
session. There is no password, no KYC, no production IdP, and no signup.
`POST /session/logout` clears the cookie (→ anonymous). The `operator-rbac` tier
is intentionally not built here.

**Net behavioural change:** recouvrement and the account tools, previously
unreachable from the anonymous widget, become reachable **once a session is
established** — closing the ADR's interim "gated until real auth exists" gap with a
real (if demo-fidelity) auth mechanism, without re-opening the anonymous leak.
