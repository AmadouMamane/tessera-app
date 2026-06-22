# 13. Entry routing by role — business plane and control plane

Date: 2026-06-22

## Status

Accepted, **not yet implemented**. Revises this ADR's first draft, which split
entry into "customer vs operator → cockpit" — too coarse. Defines how a person
enters Tessera, **by role**, into one of two **planes**. Builds on ADR 0008/0010
(`audience`/`surface`/`auth`) and ADR 0009 (next-auth roles), and shapes ADR 0010
Phase C (recouvrement's dedicated console).

## Context

The earlier framing routed two audiences — customer, and "operator" → the cockpit.
That conflated **two different internal people**:

- A **collections officer** who *uses* `recouvrement` to do their job (chase
  arrears). Their tool is the recouvrement console.
- A **platform operator** (AI engineer / compliance / admin) who *governs* the
  agent fleet — config, eval, audit, release. Their tool is the cockpit.

Sending the collections officer "through operator → cockpit → fleet → recouvrement"
is wrong: a business user should never traverse the platform-governance console to
reach their day-job tool. **"Operator" is not one audience.**

## Decision

### Two planes

- **Business plane** — apps that *do the work*: the customer product (`/produit`,
  external) and **internal business consoles** (recouvrement, for collections
  officers).
- **Control plane** — the **cockpit**, where platform operators *govern* every
  agent.

An agent can appear in **both planes as two different things**: in the business
plane `recouvrement` is the collections officer's **tool** (its console); in the
control plane it is a **governed object** (its evals, config, audit). Same agent,
two lenses — the project's "control plane" thesis made literal.

### Entry routes by role to a home

The locale root resolves the session server-side (next-auth) and routes by role.
A person lands **directly** in their home and never traverses another plane:

| Role | Plane | Home |
|---|---|---|
| anonymous / customer | business | `/produit` |
| **`collections`** (business) | business | recouvrement console (ADR 0010 Phase C) |
| **platform operator** (`admin` / `auditor` / `superadmin`) | control | cockpit |

A customer never sees an internal console; a collections officer never sees the
cockpit; a platform operator (higher privilege) may switch to view the
product/consoles.

### Roles

ADR 0009's next-auth roles gain a **`collections`** business role, distinct from the
platform roles. `collections` reaches the recouvrement console (business plane) and
**not** the cockpit; platform roles reach the cockpit and **govern** recouvrement
but are not collections officers. The agent manifest is unchanged — `recouvrement`
stays `audience: operator` in the broad "internal/staff, not customer" sense; the
business-vs-control split lives in **roles + which surface each role enters**.

### Demo launcher (not the front door)

The select-space page becomes a **labelled demo launcher** ("démonstration"),
structured **by plane, not as a flat list of surfaces**: **two** high-level cards.
The **business plane** card (*Produits / Espaces métier* — "do the work") reveals,
in place, its two sub-surfaces — *Espace client* (external, anonymous/customer →
`/produit`) and *Console recouvrement* (internal · `collections` → `/recouvrement`).
The **control plane** card (*Cockpit · Gouvernance* — "govern") enters the cockpit
(platform roles). This is **not** the "agent list" anti-pattern: each card is a
**plane**, and each revealed sub-surface a distinct **audience-surface**, never an
arbitrary agent (support-client and onboarding still share the single customer
sub-surface). Guarded sub-surfaces (recouvrement → `collections`; cockpit →
platform) carry a "connexion requise" note: the card **informs and links**, while
the layout RBAC remains the **authority** (routing ≠ authorization). It exists only
so a reviewer can explore every surface without juggling accounts.

### Not an agent list

Adding an agent never adds an entry. Customer agents share the product
(supervisor-routed). An internal agent earns an entry **only** when it has its own
audience *and* surface (like recouvrement's collections console) — a genuine
plane/home, never a bare link.

## Consequences

**Honest product shape.** Identity routes each role to its home; nobody traverses a
foreign plane.

**The control-plane thesis becomes visible.** recouvrement is a *tool* (business
plane) and a *governed object* (control plane) — the two planes are the pitch.

**Recouvrement is reached directly by collections staff**, never via the cockpit;
the cockpit only governs it.

**Cost.** A `collections` role in the seeded next-auth accounts, the root
role-router, the demo-launcher relabel. The recouvrement console itself is ADR 0010
Phase C — so the `collections` → console route activates **with** Phase C; the
customer and platform-operator routes (both homes already exist) can ship first.

**Honesty constraint (binding).** The demo launcher is labelled "démonstration".
Role-routing chooses the **landing**; the per-surface RBAC remains the **authority**
(routing ≠ authorization — do not weaken the gates).

**Out of scope.** The recouvrement console build (ADR 0010 Phase C); the cockpit's
in-area navigation.
