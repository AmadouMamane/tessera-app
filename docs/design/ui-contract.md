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

**Scoped to the selected agent (multi-agent Phase 0, shipped).** The AGENT
section lives under `/agents/:agentId/*`; `/agent` and `/agent/*` redirect to the
default agent (`support-client`). Links are built with `agentPath(agentId, page)`
and the active agent is read with `useAgentId()` — never a hard-coded id or a
literal `/agents/...` path. The **Inbox (`a-traiter` / `a-faire`) is GLOBAL** (a
cross-agent operator queue) and therefore lives at the **top level**, not under
`/agents/:id` — see the deviation note at the bottom.

| Route | Page | Source |
| --- | --- | --- |
| `/agent`, `/agent/*` | redirect -> `/agents/support-client/*` (compat) | redirect |
| `/agents/:agentId` | redirect -> `/agents/:agentId/synthese` | redirect |
| `/agents/:agentId/synthese` | Agent dashboard (NOT "Vue d'ensemble") | reuse assistant overview |
| `/agents/:agentId/configurations` | instance config | scaffold |
| `/agents/:agentId/connaissances` | knowledge | scaffold |
| `/agents/:agentId/garde-fous` | instance guardrails | scaffold |
| `/agents/:agentId/prompts` | prompts | scaffold |
| `/agents/:agentId/evaluations` | evaluations | scaffold |
| `/agents/:agentId/console` | debug/sandbox console (DEBUG.SANDBOX banner, env=debug, excluded from prod metrics & audit) | reuse assistant console |
| `/agents/:agentId/historique` | session history | scaffold |
| `/agents/:agentId/historique/:sessionId` | session detail (drill-down, absent from sidebar) | scaffold |
| `/a-traiter` | operator queue, **global** (red/amber badge) | reuse `InboxOverview` |
| `/a-faire` | backlog, **global** (badge) | scaffold |

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
  - **Phase 0 shipped.** Routes are `/agents/:agentId/*` (`/agent/*` redirects);
    `useAgentId()` / `agentPath()` are centralized (`lib/agent-context.ts` pure +
    `lib/use-agent-id.ts` client hook); `agent_id` is stamped on the guard audit
    chain (now bitemporal: `valid_from`/`valid_to`/`recorded_at`, v2), on the turn
    metrics (`agent_id` label), and on each transcript message; the Synthèse
    aggregations are scoped by `agent_id` at the **turn grain** (one `user` message
    = one turn). The acting agent is propagated per-turn via a `ContextVar` set at
    the chat turn boundary (single agent until the supervisor lands in Phase 2).
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

**Inbox globalised (Phase 0).** The Inbox (`a-traiter` / `a-faire`) previously
sat under the AGENT routes (`/agent/a-traiter`). Because it is a **cross-agent**
operator queue — not a per-agent surface — it moved to the **top level**
(`/a-traiter`, `/a-faire`) when the AGENT section became agent-scoped
(`/agents/:agentId/*`). It still renders inside the AGENT super-section of the
sidebar for proximity, but its links are global and it is never scoped by
`agentId`. This matches the plan's "GOUVERNER / Inbox / PLATEFORME stay global"
rule; the deep-link `/agent/a-traiter` redirects to `/a-traiter` for compat.

**Synthèse made operational (image 25, conformance pass).** The Synthèse body was
aligned to the multi-agent normative `25-agent-synthese-multi-agent-normative.png`
and made **events-only** (the AT-01 trap): the two eval blocks (`Top catégories
évaluées`, `Répartition par langue (évaluation)`) were removed — eval signals live
in the Évaluations page (ER-01), linked not duplicated — and the page no longer
loads the eval snapshot at all. Added the **right column** (`Contexte de l'agent`
from the governed registry + editable overrides · `Alertes opérationnelles` on real
S1 thresholds · `Accès rapides`), the AT-01 4-segment rail (`MODE · PÉRIODE · VOIR
À DATE · COMPARAISON` + mode banner + `État à date`, driven by the existing
component-local temporal state — no temporal→URL refactor), the 7 operational KPIs,
a `Répartition des conversations` bound to real supervisor routing events
(`tessera.agent.routing`, by motive prefix; empty when none), and a rich activity
feed merging the transcript with the S1 journal (handoff / garde-fou / outil badges).
Two KPIs have **no real source** and render an honest empty state (`—`), not a
fabricated number — logged here as the only data deviations:
- **Satisfaction (CSAT)** — no satisfaction signal is instrumented anywhere
  (delta reads `CSAT non instrumenté`). Surfacing 4,6/5 would be fabricated.
- **Utilisateurs servis** — there is no per-client identity on a transcript turn
  (no `user_id` column); seeding distinct client ids is a cheap **follow-up**. The
  count is left empty rather than relabelling `conversations` as `utilisateurs`.

**Configurations define/instance (image 04, conformance pass).** Added the
define/choose/govern framing the normative shows: a read-only **`Définition
(catalogue)`** block sourced from the governed registry package (`agents.yaml` —
name/owner/model/langue/garde-fous/jeu d'éval, never free-text) + a production
**governance banner** + a `Voir la définition dans CONFIGURER` link. The editable
sections below are the **instance** overrides (already real + durably saved).
Deviation: rendered as *Définition on top + Instance below* (one main column + right
sidebar), not the normative's strict two-column *Définition left / Instance right* —
the existing editable form was extended in place, not rebuilt. The CONFIGURER link
points to `/configurer/parametres` (there is no dedicated `/configurer/configurations`
catalogue page yet). **À confirmer** demain : faut-il la vraie disposition 2 colonnes.

**Connaissances OT-01 (image 03, conformance pass).** The page is real (live pgvector
`knowledge.py`) and functional (attach/detach/activate, durable). Added the normative's
**`État du rattachement`** block to the source detail, sourced from real data
(attach/active store + pgvector ingestion date + traffic last-use). Also **deleted a
dead deterministic fixture** module (`observability/agent_connaissances.py`) that was
unreferenced — a hardcode landmine that contradicted the zéro-hardcode discipline.
Deviations: (1) the source detail is a **drawer** opened on row-click, not the
normative's **persistent right OT-01 column** (extended the existing drawer in place
rather than rebuilding the layout); (2) the **OT-01 versioned event history** is not
built — attach/detach mutations are durable but **not yet S1-audited**, so there is no
real lifecycle-event source; only current state + ingestion date are shown (honest).
**Follow-up à confirmer** : auditer attach/detach en S1 + passer le détail en colonne OT-01 persistante.

**Garde-fous bottom charts (image 06, conformance pass).** The page is real (rules
from `policy.yaml`, firing stats from the live guard S1 journal — KPIs match the
journal: 15 338 denials / 15 702 decisions) with the `Couverture par catégorie` chart,
CONFIGURER links and a define/instance rule detail. Added the normative's **`Top
raisons de blocage`** chart, sourced from the real per-rule denial counts in the
journal (currently a single dominant reason — *Injection de prompt, 15 338* — which is
the truthful shape of this eval-heavy journal, not a fabrication). Deviations: the
normative's **`Mode d'application`** donut and **`Overrides`** panel are not built —
mode is derivable from the policy but low-value here, and there is **no real source for
manual overrides** (would be a fixture). Left out per zéro-hardcode. **À confirmer**.

**Prompts governance banner (image 07, conformance pass).** The page is fully real
(YAML source of truth `agent/prompts/{fr,de,en}.yaml`, read-only — prompts are edited
via Git PR and loaded at start-up). Added the §9 **governance banner** stating that
governance model (define in Git → review (PR) → load), which is the truthful
define/choose/govern story for prompts. Deviation: the normative's explicit numbered
**`1. Définition (catalogue)` / `2. Configuration pour cet agent (instance)`** two-block
split is **not** rendered as two side-by-side panels — the page keeps its KPIs + table +
per-prompt detail (Résumé/Contenu/Configuration). No CONFIGURER prompts-catalogue route
exists yet. **À confirmer** demain : faut-il les 2 blocs numérotés.
