# UI contract — navigation (source of truth)

Tessera ships **two distinct apps behind a first-level toggle PRODUIT <-> COCKPIT**,
with two separate shells and two auth contexts. The end customer never sees the
Cockpit.

Transverse principles (non-negotiable):

- All navigation is URL-driven. No tab/sub-nav local state. The active item is
  derived from the current route.
- One view = one URL. Every leaf is deep-linkable: a refresh (F5) or a shared
  direct link lands exactly on the page, never on a default. Back/forward navigate
  between pages.
- One route = one lazy-loaded module (Next App Router code-splits per segment),
  with its own data-fetch and loading / empty / error states.
- Stack: Next.js App Router, locale-prefixed (`/[locale]/...`, ADR 0006). The route
  slugs below are written without the locale prefix.

No URL contains `cockpit`, `gouverner`, `plateforme`, or `/agent/assistant`. The
super-headers AGENT / GOUVERNER / PLATEFORME are typographic only.

## App 1 — PRODUIT (end customer)

Client shell (`ProductShell`): client auth, simple nav, no cockpit chrome. Pages
are all siblings; the chat is the home, never a parent.

| Route | Page | Source |
| --- | --- | --- |
| `/produit` | Chat (home) | reuse `ChatRoom` |
| `/produit/mes-demandes` | Request tracking | scaffold |
| `/produit/documents` | Statements, contracts, PDFs | scaffold |
| `/produit/alertes` | Notifications | scaffold |
| `/produit/parametres` | Profile, language, privacy & consents | scaffold |

## App 2 — COCKPIT (operator / ML eng / compliance)

Cockpit shell (`AppShell` + rewritten `Sidebar`): 6 groups under 3 typographic
super-headers.

### AGENT (primary, flat group — pages are direct children, no `assistant` wrapper)

| Route | Page | Source |
| --- | --- | --- |
| `/agent` | redirect -> `/agent/synthese` | redirect |
| `/agent/synthese` | Agent dashboard (NOT "Vue d'ensemble") | reuse assistant overview |
| `/agent/configurations` | instance config | scaffold |
| `/agent/connaissances` | knowledge | scaffold |
| `/agent/garde-fous` | instance guardrails | scaffold |
| `/agent/prompts` | prompts | scaffold |
| `/agent/evaluations` | evaluations | scaffold |
| `/agent/console` | debug/sandbox console (DEBUG.SANDBOX banner, env=debug, excluded from prod metrics & audit) | reuse assistant console |
| `/agent/historique` | session history | scaffold |
| `/agent/historique/:sessionId` | session detail (drill-down, absent from sidebar) | scaffold |
| `/agent/a-traiter` | operator queue (red/amber badge) | reuse `InboxOverview` |
| `/agent/a-faire` | backlog (badge) | scaffold |

### GOUVERNER

Group **Surveiller**:

| Route | Page | Source |
| --- | --- | --- |
| `/surveiller` | redirect -> `/surveiller/vue-ensemble` | redirect |
| `/surveiller/vue-ensemble` | overview cockpit | move from `/` |
| `/surveiller/qualite-ia` | AI quality | move from `/observability` |
| `/surveiller/securite-privacy` | security & privacy | move from `/security` |
| `/surveiller/conformite` | compliance | move from `/compliance` |
| `/surveiller/fiabilite-cout` | reliability & cost | move from `/reliability` |
| `/surveiller/observabilite` | service health | move from `/health` |
| `/surveiller/amelioration` | improvement | move from `/improvement` |

Group **Agir**:

| Route | Page | Source |
| --- | --- | --- |
| `/agir/incidents-playbooks` | incidents (red badge) | move from `/incidents` |
| `/agir/replay-shadow` | replay & shadow | move from `/replay` |
| `/agir/curation-eval-set` | curation (amber badge) | move from `/curation` |
| `/agir/release-control` | release control | scaffold |
| `/agir/automations` | automations | move from `/automations` |

Group **Prouver**:

| Route | Page | Source |
| --- | --- | --- |
| `/prouver/audit-logs` | audit log | move from `/audit` |
| `/prouver/evidence-store` | evidence store | move from `/proofs` |

### PLATEFORME

Group **Configurer** (reusable, cross-agent platform catalogue):

| Route | Page | Source |
| --- | --- | --- |
| `/configurer/signal-catalog` | signal catalog | move from `/signals` |
| `/configurer/garde-fous` | platform guardrails | scaffold |
| `/configurer/modeles` | models | scaffold |
| `/configurer/connecteurs` | connectors | scaffold |
| `/configurer/politiques` | policies | move from `/policies` |
| `/configurer/sources-memoire` | sources & memory | move from `/sources` |
| `/configurer/parametres` | platform settings | move from `/parametres` |
| `/configurer/integrations` | integrations | move from `/integrations` |

Group **Admin**:

| Route | Page | Source |
| --- | --- | --- |
| `/admin/utilisateurs` | users | scaffold |
| `/admin/roles-acces` | roles & access | move from `/access` |
| `/admin/profil-systeme` | system profile | move from `/system` |

### Root

`/` redirects to `/agent/synthese` (cockpit primary). Auth-based root routing
(client -> `/produit`, operator -> cockpit) is a follow-up once role separation
ships.

## Boundaries

- `AGENT/*` = **instance** config (tune this agent). `CONFIGURER/*` = reusable
  **platform** catalogue (cross-agent). Duplicate labels (garde-fous, parametres)
  are intentional: a distinct route prefix means a distinct scope.
- Four conversation surfaces, no duplication: client Chat (`/produit`), debug
  Console (`/agent/console`), Session detail (read an existing convo), Replay &
  shadow (`/agir/replay-shadow`).
- Staff access to a client conversation = **audited impersonation** (DORA/CNIL).

## Temporal rails & modes

Time is a global, URL-carried context, not a page. Each page renders one of the
temporal **rails** defined in `registre-rails-temporels.md` (S1–S4 substrates,
C1–C4 components, 8 named rails TE-01…SR-01). Rule of thumb: **config -> versions,
signals -> scrubber (Surveiller), proof -> as-of (Prouver)**.

- The active mode is always shown explicitly (Live / Historique / As-of). No page
  silently switches to a historical view: "Voir à date" flips the indicator and shows
  an "état au [T]" banner.
- **"Voir à date" (as-of read) is NOT "Replay".** Replay (re-execution) belongs to
  AGIR (`/agir/replay-shadow`); the cockpit-wide as-of read never re-runs the model.
- Synthèse carries `Live · Période · Voir à date · Comparaison`; its AT-01 activity
  feed shows events only — continuous signals live in SURVEILLER (link, don't duplicate).

## Opposability badge (Prouver / État à date)

The État-à-date seal badge is **dynamic**, computed at render from the integrity
check — never stored, never cosmetic (full spec in `registre-rails-temporels.md` §9):

- **Scellé / opposable** — hash chain verified AND third-party seal (Hica) verified.
- **Intégrité partielle** — chain valid but seal absent / unverifiable.
- **Non scellé** — integrity failure.
- (transient) **Vérification en cours** — no opposability status until `verify()` completes.

Caption under the badge: "Statut attribué uniquement après vérification réussie."
The `1·2·3·A·D` numbered reading order is reserved for the Evidence Pack export, not
the operational screen.

## Multi-agent model

The cockpit supervises **multiple agents**; the customer sees **one** assistant.

- **The AGENT section is scoped to a selected agent.** Routes become
  `/agents/:agentId/*` (e.g. `/agents/support-client/synthese`); `/agent/*` redirects
  to the default agent. An agent **switcher** sets the scope; a fleet page `/agents`
  lists/compares/creates agents ("+ Nouvel agent", RBAC-gated, audited).
- **Foundation now, machinery later.** Adopt the scoped routes + a centralized
  `useAgentId()` hook + `agentPath()` helper, and stamp `agent_id` on every event,
  metric and **message** (per-turn) immediately. Defer the switcher / fleet / handoff
  UI / cross-agent rollups until agent #2 is real.
- **Per-turn attribution.** Routing is a supervisor that re-evaluates each turn
  (context + intent + active policies), with agent->agent **handoff** (distinct from human
  escalation). `agent_id` is recorded **per message**, so one conversation can span
  agents; État à date / Session detail show which agent answered which turn.
- **Page scope.** AGENT (and its rails) = per-agent. GOUVERNER (Surveiller/Agir/Prouver)
  and PLATEFORME stay **global, filterable by agent**; org/cross-agent totals (deduped)
  live in the fleet `/agents` and SURVEILLER, never on a single agent's page.
- **Client side unchanged.** One unified chat; a new agent is wired via server-side
  orchestration/routing, invisible to the customer (no "products" menu).
- **An agent is a governed *package*, not just an id.** Conceptually onboarding is
  "a new `agentId`"; operationally it bundles model, prompts, knowledge, tools,
  guardrails, evaluations, permissions and a **handoff contract** (which agents it may
  hand to / receive from). The package is **versioned and approved as a unit** (release
  + eval-gate + rollback); the handoff contract defines the governed agent graph,
  checked at runtime and reconstructable in État à date.
- **Routing is auditable.** Each routing decision and handoff is a versioned, audited
  event — you can prove *why* a turn went to a given agent (active policy, at T), not
  just *that* it did.

## Editability (define / choose / govern)

For any config surface (model, prompts, guardrails, knowledge):

- **Define** a reusable building block -> `CONFIGURER/*` (read-only here).
- **Choose / tune** it for this agent -> `AGENT/*`, via a **bounded picker** (never free-text).
- **Mutate in production** -> a **governed** action: RBAC + a versioned event + audit
  (ideally propose -> review/dual-control -> deploy via Release Control), not a silent
  inline save. Direct edit allowed only in staging.
- A chosen object's metadata (provider, snapshots, cost) is read-only, inherited from
  the catalogue.

## Deviation note

This two-app `produit/` + grouped cockpit tree deviates from the single flat
`app/[locale]/<page>` tree implied by CLAUDE.md. It is intentional and recorded
here; a dedicated ADR will follow if the split hardens.
