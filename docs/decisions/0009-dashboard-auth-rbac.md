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
