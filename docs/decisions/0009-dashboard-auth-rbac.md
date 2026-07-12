# 0009 — Dashboard authentication & role-based access

- Status: accepted
- Date: 2026-06-03
- Deciders: Tessera maintainers
- Related: 0006 (locale-prefixed routing), 0008 (security hardening),
  `docs/threat-model.md`

## Context

The dashboard mixes two very different surfaces:

- **Public showcase** — the chat itself and the *aggregate* non-regression
  scores (totals, pass rate, per-category bars). These sell the project and
  reveal nothing exploitable.
- **Operator surfaces** — the audit trail, the budget/cost counters, and the
  *per-case* eval detail (case status + failure reasons). The failure reasons
  are effectively a map of the live deployment's weaknesses; the audit trail
  carries operational detail and subject identifiers.

ADR 0008 closed the public audit leak with a binary proxy allowlist gated by
`TESSERA_DASHBOARD_PUBLIC`. That hides the operator surfaces from *everyone* on
the public deployment — including legitimate operators — and has no notion of
identity or role. We want to keep the showcase open, restrict the operator
surfaces to authenticated roles, and in doing so demonstrate a complete
authentication / session / RBAC capability for the platform.

## Decision

**Auth lives in the Next.js front** (the BFF that already holds the agent bearer
token). The agent keeps its service-to-service bearer; end-user identity is a
front concern. The production path — propagating identity to the agent (a
forwarded OIDC token) so the agent enforces server-side RBAC and attributes
audit entries to a real principal — is explicitly out of scope here.

- **Library**: Auth.js (`next-auth` v5), App Router. **Session strategy: JWT**
  (stateless, signed cookie) — required by the Credentials provider and avoids
  coupling the front to a database.
- **Providers**:
  - *Phase 1 (this ADR)* — **Credentials** provider with seeded demo accounts;
    passwords supplied via env / Secret Manager and compared in constant time.
  - *Phase 2 (later)* — **Google OIDC** provider (GCP-aligned), with an
    email→role mapping. Requires an OAuth client in the GCP console.
- **Roles**: `admin` (all surfaces, incl. settings), `auditor` (audit + budget +
  eval detail, not settings), and unauthenticated `visitor` (chat + aggregate
  eval only). Role is carried as a JWT claim.
- **Enforcement, defence in depth**:
  1. the server-side proxy (`app/api/[...path]`) authorises `audit` / `budget`
     by role — this **replaces `TESSERA_DASHBOARD_PUBLIC`**;
  2. server components render gated content by role (eval *detail* gated, audit
     and budget pages show a sign-in prompt otherwise). Aggregate eval scores
     stay public.
- **Middleware**: the next-intl middleware is unchanged (its matcher already
  excludes `/api`). RBAC is enforced in route handlers and server components,
  *not* in middleware, to avoid a fragile next-intl × Auth.js composition.

### Demo posture (explicit, load-bearing)

The public demo **displays the admin / auditor credentials in the UI** so any
visitor can assume a role and explore the operator surfaces. This makes the gate
**theatrical** — it *demonstrates* the access-control model rather than
*restricting* access — which is acceptable because the demo data is synthetic.
Turning it into a real restriction is a one-line change: stop displaying the
credentials (the password becomes a genuine secret) and/or move to the Phase 2
IdP with an email allow-list.

## Consequences

- **New dependency**: `next-auth@5`, justified as the standard, well-supported
  auth library for the Next App Router; isolated to the front, no agent impact.
- **New secrets**: `AUTH_SECRET` (JWT signing) and the seeded account passwords
  → Secret Manager (cloud) / `.env.local` (local). Never committed.
- `TESSERA_DASHBOARD_PUBLIC` is retired in favour of role checks.
- Adds `/[locale]/login`, `/api/auth/*`, and a `SessionProvider` in the locale
  layout; adds a demo-credentials banner and lock affordances on gated nav.

## Update — the auditor is read-only on the mutation plane (2026-07-12)

The role table above says `auditor` gets *"audit + budget + eval detail, **not settings**"*.
That sentence was never enforced anywhere an attacker could reach. It shaped **which pages the
front chose to render** — which is decoration, not access control — and the agent, once ADR 0010
Phase B gave it a verified operator identity, gated on `AuthState.OPERATOR`: **one bit**, which
says *an* operator is asking and never *which*. An auditor sets that bit. So an auditor could
call all 26 observability mutations: promote an agent to production, rewrite runtime
configuration, switch a guardrail off, mutate the governance stores.

**Decision (operator call, 2026-07-12): the mutation plane requires *write authority*, not
merely operator status.**

- `MUTATION_ROLES = {admin, superadmin}` (`src/tessera/api/operator.py`), mirrored by
  `canMutateCockpit` in `webapp/frontend/lib/auth/roles.ts`. The agent's copy is the authority;
  the front's is the friendly refusal at the edge.
- The signed assertion already carried `role` and the verifier already checked it against
  `OPERATOR_ROLES` — it was then dropped into a display label and never read again.
  `SessionContext` now carries it, which is the whole mechanism.
- **`auditor` keeps every read**, including the audit trail: least privilege is not paralysis,
  and an "enforcement" that locked the auditor out of the cockpit would have broken the role it
  claims to protect. Reads are untouched (see below).
- **`collections`** (the ADR 0010 Phase C business plane) is excluded too. The front never gave
  it cockpit access, but its assertion verifies as `OPERATOR`, so the *agent* was laxer than its
  own edge — a `dedicated-ui` assertion replayed against `/observability/agents/release` would
  have been honoured.
- **401 and 403 stay distinct.** 401 = we do not know who you are. 403 = we know exactly who you
  are and the answer is still no. Telling an authenticated auditor to log in again is a lie
  about what went wrong, and an invitation to go looking for a second account.

An audit role that can change what it audits is not an audit role.

### Not decided here: the read plane (P1, open)

The 126 observability **GET** reads stay public this cycle. They are not uniform — some are
aggregate posture, some carry operational detail — and classifying them by sensitivity is a
design slice, not a flag flip. Locking them wholesale would 404 the cockpit for the very
operators this ADR protects. Tracked as **`read-plane data-classification` (P1)** in
`docs/status/overnight-security-run.md`.

## Update — operator identity forwarding to the agent (done for the operator tier)

This ADR deferred *"propagating identity to the agent … so the agent enforces
server-side RBAC"* as out of scope. **ADR 0010 Phase B does exactly that, for the
operator tier.** The Next BFF — which already holds the agent bearer and the
verified next-auth session — mints a short-lived **signed operator assertion**
(HMAC, the same pattern as the customer-session cookie) after `auth()` confirms an
operator session, and forwards it to the agent. The agent verifies it and derives
`AuthState.OPERATOR` on the `cockpit-embedded` surface; everything else stays on
the unchanged customer path. The identity remains **demo-grade** (seeded
Credentials accounts, no production IdP), but the forwarding is architecturally
real: server-verified, unforgeable by the browser, off-repo key, fail-closed in
production. See `docs/decisions/0010-…md` (Implementation note — Phase B) and
`tessera.api.operator`.
