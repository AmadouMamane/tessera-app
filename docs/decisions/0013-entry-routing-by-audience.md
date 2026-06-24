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

The select-space page is a **labelled demo launcher** ("démonstration") that is a
**chooser of the two planes**, not a flat surface list: **two** high-level cards.
The **business plane** card (*Produits / Espaces métier* — "do the work") links to
**`/espaces`**, a dedicated **directory of business surfaces**; the **control
plane** card (*Cockpit · Gouvernance* — "govern") enters the cockpit (platform
roles). The launcher also keeps a public-safe **signal digest** (verdict rollup —
*Contrôle actif · N/M agents libérables*) and the reconciled **per-agent footer**.

The surface list lives in `/espaces`. Its shape **echoes** the Flotte agent
directory (`/agents`) — Flotte lists governed **agents** (list → agent détail),
`/espaces` lists business **surfaces** grouped by audience (list → surface), never
a list of agents. **This symmetry is a design rationale, not a user link**: a
business page links to **nothing in the control plane**, and a control page links
to nothing in the business plane. The two planes meet **only at the launcher**. The
sole allowed cross-plane direction is the **operator→product** header toggle
(operator-only, higher privilege); business→control is **never** offered — a
`collections` user has no cockpit access, so such a link would be a dead end into
the RBAC guard. Each surface shows its audience (external/internal) and its
**access facet**: open ("Ouvrir"), or sign-in required ("Connexion requise", with
a 1-click demo login in demo mode). support-client and onboarding still
share the single *Espace client* surface; adding an agent never adds an entry.
The card **informs and links**, while the layout RBAC remains the **authority**
(routing ≠ authorization). The launcher and `/espaces` exist only so a reviewer can
explore every surface without juggling accounts; a real user is role-routed at the
locale root and never needs them.

### Not an agent list

Adding an agent never adds an entry. Customer agents share the product
(supervisor-routed). An internal agent earns an entry **only** when it has its own
audience *and* surface (like recouvrement's collections console) — a genuine
plane/home, never a bare link.

**Where the agent grid lives.** A rich agent directory — every agent, with search,
audience filters + counters, grid/list, scaling 1→100+ — is the right pattern for
the **Flotte** (`/agents`, control plane, operator-gated): listing all agents is
correct there, and a click opens the agent's **governance workspace** (synthèse /
evals / guardrails), **never a chat**. The same shape must **never** appear on the
business plane: a customer picking an agent and chatting would break the supervisor
(the server routes the agent — `ChatRequest` has no agent field, ADR 0008/0010) and
the audience boundary (a customer would see Fraude, Recouvrement, Conformité…).
So `/espaces` lists **surfaces** (Espace client = one supervisor-routed entry), the
Flotte lists **agents**, and the agent picker→chat pattern is rejected outright.

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

## Amendment — surface health is access, not the eval-gate verdict

The original text gave each `/espaces` surface a "public-safe health" equal to the
**release verdict** of its backing agent(s) (a green/blocked dot). This was wrong on
two counts: (1) the eval-gate verdict is a **control-plane** fact — its home is the
Flotte (`/agents`) governance cards and the Vue d'ensemble per-agent breakdown, not a
business door; (2) it was **misleading** — a surface can read "Bloqué" while being
perfectly **usable in the demo** (the gate blocks *production release*, not the demo
surface). Showing a control-plane verdict on a business surface is cross-plane leakage.

A business surface now advertises only its **access facet**: *open* ("Ouvrir") or
*sign-in required* ("Connexion requise", with the demo login CTA in demo mode), plus
its audience (Externe/Interne) and description. `/espaces` no longer reads the fleet
release data at all. The release verdict stays where it belongs: Flotte / Vue
d'ensemble (one verdict, control-plane only).
