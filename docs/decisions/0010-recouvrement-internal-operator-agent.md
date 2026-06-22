# 10. Recouvrement is an internal (operator) agent

Date: 2026-06-22

## Status

Accepted, **phased** (Phase A implementable immediately; B and C are follow-ups).
This ADR revises the **interim** classification recorded in ADR 0008, where
`recouvrement` was provisionally `audience: customer` on the
`shared-customer-widget`. It is now decided to be an **internal, operator-facing**
agent. It depends on ADR 0009 (dashboard auth/RBAC) for the operator identity it
will eventually consume, and extends nothing in the canonical tree.

## Context

ADR 0008 made `audience` / `surface` / `auth` first-class and, as an explicit
*interim* placeholder, parked `recouvrement` on the customer widget behind
`customer-auth` — while flagging in writing that its true home was undecided
(debtor self-service vs. internal collections). That question is now settled.

`recouvrement` is a **back-office collections function**: owner *Équipe
Conformité*, `strict` guardrails, scope *relances / impayés / échéanciers /
escalade conseiller*. Its operator is the bank's recovery staff, not a walk-up
customer. Keeping it on the customer widget — even behind `customer-auth` — models
the wrong thing: it puts a debt-collection agent one authenticated step away from
the general public chat. The honest model is **operator-facing, reached from an
operator surface, gated by `operator-rbac`** — and it makes the fleet span two
audiences (support + onboarding = customer; recouvrement = operator) instead of
pretending all three serve the same public.

### The dependency that sets the phasing

The vocabulary is already in place (`tessera.authz`: `Audience.OPERATOR`,
`Surface.COCKPIT_EMBEDDED` / `DEDICATED_UI`, `Auth.OPERATOR_RBAC`,
`AuthState.OPERATOR`, monotone ladder anonymous < customer < operator). What is
**not** in place is the server-side production of `AuthState.OPERATOR`:

- ADR 0009 deliberately kept operator identity **in the Next.js front**
  (next-auth, seeded demo accounts) and declared *"propagating identity to the
  agent … so the agent enforces server-side RBAC … is explicitly out of scope."*
- `api/session.py` derives only `ANONYMOUS` / `CUSTOMER`; it states *"the operator
  (operator-rbac) tier is intentionally out of scope."*
- The agent chat entry defines only `_PRODUIT_SURFACE = SHARED_CUSTOMER_WIDGET`;
  there is no operator/cockpit entry surface.

Consequence: the instant `recouvrement.auth` becomes `operator-rbac`, **no
server-derived session satisfies it** — the agent never sees `AuthState.OPERATOR`.
The manifest flip therefore *parks* recouvrement (reachable by no interactive
session) until operator identity is forwarded to the agent. This is the same
"install the seam, fix the exposure, defer reachability" sequencing ADR 0008 used
for the customer tier — applied now to the operator tier.

## Decision

### Reclassify recouvrement

| Property | Was (ADR 0008 interim) | Now |
|---|---|---|
| `audience` | `customer` | **`operator`** |
| `surface` | `shared-customer-widget` | **`cockpit-embedded`** (dedicated case console = `dedicated-ui`, Phase C) |
| `auth` | `customer-auth` | **`operator-rbac`** |

Handoff edges `support-client ↔ recouvrement` are **removed** from the customer
surface: a customer support chat can no longer hand off into collections (it was
never legal once auth-scoped, and is now incoherent across audiences). Any
support→collections escalation becomes an explicit, governed, audited transition
(out of scope here), never a silent route.

### Phasing

- **Phase A — reclassify (now, 1 commit).** Flip the three manifest fields; remove
  the cross-audience handoff edges. Effect: `recouvrement` leaves
  `routable(shared-customer-widget, *)` — **customers can never reach collections**,
  by construction. It is parked behind `operator-rbac` (no interactive session
  satisfies it yet) and remains exercised **offline by the eval harness** (which
  runs the agent package directly, independent of surface/auth) and observable in
  the cockpit as a governed package. This is a real safety/correctness improvement
  shipped on its own.

- **Phase B — make it operator-reachable.** Forward the operator identity that
  ADR 0009 holds in the front through to the agent (a trusted, server-verified
  signal — not a client-asserted field), so `_derive_auth_state` can return
  `AuthState.OPERATOR`; add a cockpit/operator entry surface
  (`Surface.COCKPIT_EMBEDDED`) on the chat path. This is the operator analogue of
  the customer-session wiring and is precisely the forwarding ADR 0009 deferred.

- **Phase C — the dedicated interface.** A collections **case console**
  (`Surface.DEDICATED_UI`): case list, per-debtor échéancier, relance timeline,
  governed actions — reusing recouvrement's existing LangGraph package, guard, and
  audit verbatim (re-skin, no core fork), per the ADR 0008 dedicated-interface
  pattern.

## Consequences

**Customers are definitively walled off from collections.** Phase A alone removes
`recouvrement` from every customer-reachable pool — a correctness fix, not just a
cosmetic reclassification.

**The fleet now honestly spans two audiences.** support-client + onboarding are
customer-facing; recouvrement is operator-facing. The multi-agent story stops
pretending one surface serves everyone, and the `audience`/`surface`/`auth` seam
from ADR 0008 earns its keep.

**Reachability is deferred, and that is stated, not hidden.** Between Phase A and
Phase B, recouvrement is interactively unreachable (parked behind an operator tier
the agent cannot yet satisfy); it stays demonstrable via the eval harness. Do not
describe recouvrement as "live for operators" until Phase B lands — that would
assert a path that does not exist.

**Cost.** Phase A is a manifest change plus handoff-edge removal. Phase B reopens
the operator-identity-forwarding question ADR 0009 set aside (the larger piece).
Phase C is a new operator UI. Each ships independently; none blocks Phase A.

**Honesty constraint (binding).** As in ADR 0008: a tier is real only when the
server enforces it. `operator-rbac` on recouvrement is a *floor*, not a capability —
it grants nothing until Phase B produces a real `AuthState.OPERATOR`.

## Implementation note — Phase B (operator identity forwarding) — done

Phase B forwards the operator identity ADR 0009 holds in the Next.js front through
to the agent, so recouvrement is interactively reachable **from the operator
console** while the customer widget remains exactly as before.

**The trust mechanism is a signed operator assertion**, mirroring the customer
cookie (`tessera.api.session`):

- The **Next BFF** (`webapp/frontend/app/api/chat/route.ts`) calls `auth()`. When a
  request comes from the cockpit console (`X-Tessera-Client-Surface: console`, a
  hint set by `lib/api/sse.ts` for the agent console) **and** carries a verified
  next-auth operator session, the BFF mints
  `base64url({principal,role,surface:"cockpit-embedded",iat}).base64url(HMAC-
  SHA256(key, body))` (`lib/server/operator-assertion.ts`) and forwards it as the
  `X-Tessera-Operator-Assertion` header. Without an operator session, nothing is
  minted — the client hint alone grants nothing.
- The **agent** (`tessera.api.operator`) verifies that assertion (constant-time
  MAC, freshness, `surface == cockpit-embedded`, role ∈ {admin, auditor,
  superadmin}) and only then returns `(AuthState.OPERATOR, Surface.COCKPIT_EMBEDDED)`.
  Otherwise it falls back to the unchanged customer path (signed cookie →
  `CUSTOMER`/`ANONYMOUS` on the widget). The previously hard-coded
  `surface = _PRODUIT_SURFACE` in `chat.py` is replaced by this resolver.

**Where OPERATOR comes from:** exclusively the verified signed assertion. A browser
cannot forge it (it never holds the server-only key); a raw/unsigned header is
never honoured; a forged or wrong-surface token is rejected and falls through to
the customer path. The supervisor's fallback also learned that on a surface where
the default agent is off-surface (the cockpit), it routes to the agent the surface
*does* permit (recouvrement) rather than an off-surface default.

**Secret & fail-closed (binding, as for the customer key).** The HMAC key
(`TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY`) lives off-repo (Secret Manager) and
is shared by the BFF (minter) and the agent (verifier). Production refuses to boot
without it (`validate_operator_assertion_key` in `build_app`). There is **no
ephemeral fallback** — mint and verify run in different processes, so a per-process
key could never match; when unset in dev/CI the operator path is simply inert (no
assertion verifies), which is the safe direction.

**Still demo-grade, honestly.** The operator session is the seeded next-auth
Credentials demo (ADR 0009), and the assertion binds `principal = username`. This
is the operator analogue of the demo customer session: architecturally real
(server-verified, unforgeable, fail-closed) but seeded identities, not a production
IdP.

## Implementation note — Phase C (dedicated business console) — done

Phase C gives recouvrement its own **business-plane** surface, reached **directly**
by a **`collections`** role — never via the cockpit — and re-skins, it does not
fork.

**The agent side opens a second operator surface.** `recouvrement.surface` is now
`[cockpit-embedded, dedicated-ui]`, so `routable(dedicated-ui, OPERATOR) =
{recouvrement}`. `tessera.api.operator` accepts the `collections` role (in
`OPERATOR_ROLES`, distinct from the platform roles) and an assertion carrying
**either** operator surface; `verify_operator_assertion` returns the surface
*carried by the assertion* (no hard-coded value), never the customer widget. All
operator roles still map to `AuthState.OPERATOR`; the role string is the audit
label.

**The front is a re-skin over the real chat core.** `/recouvrement`
(`app/[locale]/recouvrement/`) is a standalone console gated to `hasCollectionsAccess`
(collections + platform supervision) that **mounts the shared premium `<ChatRoom>`**
(not the debug console) with the `recouvrement` surface hint. The BFF
(`app/api/chat/route.ts`) mints `{role, surface: dedicated-ui}` for a verified
collections/operator session; the minted surface is derived from the role's
authority, so a `collections` session can only ever reach `dedicated-ui` (it can
never obtain `cockpit-embedded`). `streamChat` stays the single chat entry — no
fork.

**Panels are real or honest-empty.** The console's side panel states plainly that
Tessera has **no collections-case backend**: it fabricates **no dossiers,
échéanciers or payment plans**. Only the real exchanges with the agent and their
timestamped audit log exist.

**Where collections access comes from:** exclusively the verified signed assertion
(constant-time MAC, freshness, operator surface, operator role). A raw/unsigned
header, a forged token, or a widget-surface claim is rejected and falls back to the
customer path. The customer widget and the cockpit console are untouched; the key
stays off-repo and fail-closed in production.

