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

## Deviation note

This two-app `produit/` + grouped cockpit tree deviates from the single flat
`app/[locale]/<page>` tree implied by CLAUDE.md. It is intentional and recorded
here; a dedicated ADR will follow if the split hardens.
