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

Single customer surface — the chat. No cockpit chrome.

| Route | Page | Source |
| --- | --- | --- |
| `/produit` | Customer chat — honest decor host + floating widget | reuse `ChatRoom` (re-skin) |
| `/produit/apercu3` | Crédit Aurore demo portal — fictitious banking decor, real Tessera chat | reuse `ChatWidget` / `ChatRoom` |

#### Customer chat presentation — `/produit` (re-skin, not re-fork)

`/produit` is the customer chat: a decor host page ("Crédit Aurore · Espace
personnel" header + greyed skeleton tiles labelled "demo host", **no real banking
data**) with a floating chat **widget** (FAB bottom-right ~56px → panel ~400px ×
min(620px, 80vh) anchored bottom-right on desktop, full-screen on mobile; Esc /
backdrop / FAB closes).

Hard rule — **re-skin, not re-fork**: the widget reuses the existing core
verbatim (`<ChatRoom>` → `streamChat` + `MessageBubble` + the chat store). It
owns only open/close state and the layout frame; it duplicates **none** of the
streaming or message-rendering logic. ChatRoom reflows naturally at ~400px (its
`sm:` utilities don't trigger, so the empty state / suggestions render in their
compact one-column form). Files: `components/product/chat-widget.tsx`,
`components/product/apercu-host.tsx`, `app/[locale]/produit/page.tsx`. The widget
is **auth-aware** (`components/product/customer-session-bar.tsx`): it reflects the
server-derived session (anonymous vs. demo customer) and exposes demo login/logout
(ADR 0008/0009) — anonymous gets general info, an authenticated session unlocks
recouvrement and the account tools.

**Cut-over: DONE.** "Parallel" was a *phase*, not a destination, and it is over:

1. The widget presentation **became `/produit`** (replacing the legacy full-page
   `ChatRoom` as the customer home).
2. The legacy full-page presentation was **retired**.
3. The 4 portal sub-pages (`/produit/mes-demandes`, `/produit/documents`,
   `/produit/alertes`, `/produit/parametres`) were **removed** — the decor host
   subsumes the "portal" framing, and the chat is the only real surface. Their
   orphaned client components (`ProductShell`, `ClientSidebar`, `client/*`) went
   with them.
4. The competing decor variants (`/produit/apercu`, `apercu2` and the older
   `mes-comptes-host` backdrop) were **deleted** — one live production
   presentation. `/produit/apercu3` remains as an explicit demo portal: all
   banking chrome and data are fictitious, while every meaningful action routes
   into the same real `ChatWidget` / `ChatRoom` flow. The chat **core was not
   touched**: `ChatRoom` + `streamChat` are reused exactly as before.

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

## Presentation-conformance (P1–P6) pass

**P1 — global chrome (fix once in shell).** `AppShell` now renders `AppBreadcrumb`
(SUPER › Section › Page from the route, presentation labels) atop `<main>` and
`AppFooter` at the bottom: "Source de vérité : YAML · Git" + **real** hash-chain
integrity (`/audit/integrity`, ✓/✗ honest) + env (on-prem · EU · SOC 2). Benefits
every cockpit + AGENT page at once. No data invented.

**Évaluations — Phase 1/2 finalisation.** Phase 1: audit chain re-sealed honestly
(`scripts/reseal_audit_chain.py`, 15727 interleaved links rebuilt in file order,
content preserved → footer ✓ truthfully); breadcrumb resolves the real agent name;
scores marked *informatif* (don't determine the verdict) + an "Actions requises"
remediation block on the blocked hero; tier label `T2 · gradé` (was `non-dérog.`).
Phase 2: added the **Cycle de vie** bar (Candidat run-id · Version déployée · Cible
Production · Env du run · Modèle · Période) — real data; the **deployed** version
has no real release pointer yet so it renders an honest empty state, never a
fabricated REL. **Deviation (logged):** Phase 2 was done **additively** (lifecycle
bar) rather than a full grid re-layout — the page was already dense and a from-
scratch re-disposition risked the `119=59+60` / tiers / waiver reconciliation
(garde-fou). Reconciliation re-verified after the change (counts 59/60, T0 18/T1
51/T2 50, socle 8/18, `test_eval_gate_policy` green).

**Surveiller — P2 signal hero (per page).** Every SURVEILLER page now leads with
the **named breached signal**: a shared `SignalBreachHero` fetching the real SLO
(`/observability/slo`) — metric (e.g. Fidélité), observed rate vs threshold, burn
rate, bad/total — with a direct **Remédier dans Incidents →** link. Honest: green
"SLO respecté" when not breaching, nothing fabricated. Wired via a `signalHero`
prop on `GovScopeSection` (6 pages) + inline on vue-ensemble.

**AGENT + GOUVERNER/PLATEFORME — P3 cross-links.** Shared `AgentCrossLinks`
(governance → AGIR Release Control · definition → CONFIGURER · linked AGENT data)
mounted on the AGENT instance pages (configurations, garde-fous, prompts,
connaissances, console). `GovScopeSection` gained a scope-carrying cockpit
cross-links row (→ Release Control · → Audit · → Signal catalogue), so every
Surveiller/Agir page using it gets P3 at once. **Remaining (logged):** per-page P2
hero naming the *specific* breached signal/incident on each Surveiller dashboard is
a deeper per-page pass; the per-agent breakdown + filter + cross-links are in place.

**Évaluations — P2/P3 (P4–P6 already strong).** P2: the verdict hero now **names**
the concrete blocking socle/T0 cases ("Cœur non dérogeable en échec : <ids>",
derived from the real `critical_cases` rows) + a direct **remédier dans Release
Control →** link. P3: a "Liens utiles" bar (→ AGIR Release Control · → CONFIGURER
eval-set definition · → Garde-fous appliqués · → Connaissances). The 119=59+60
reconciliation, case×langue grain and waiver chain are untouched.

## Deviation note

This two-app `produit/` + grouped cockpit tree deviates from the single flat
`app/[locale]/<page>` tree implied by CLAUDE.md. It is intentional and recorded
here; a dedicated ADR will follow if the split hardens.

**Multi-agent GOUVERNER/PLATEFORME — shared mechanism (this pass).** Built the
global agent-scope mechanism once, reused across GOUVERNER/PLATEFORME:
- Backend `observability/agent_scope.py` `dedup_org_total()` — org rollup at the
  DISTINCT entity grain (handoff conversation = 1); `fleet.py` consumes it.
- Backend `observability/agent_release.py` — per-agent eval-gate verdict
  (`build_gate_view` over each agent's OWN run); real for all 3 agents.
- Frontend `lib/agent-scope.ts` + `AgentScopeFilter` (URL `?agent=all|<id>`,
  **distinct** from `useAgentId`/the AGENT switcher — query scope, not path scope)
  + presentational `AgentBreakdown` (per-agent rows + distinct **Total org
  (dédup)** row showing naive sum / dedup saved / shared).

**Flotte `/agents` — release column (real).** Added the normative's "état de
release" per-agent: eval-gate verdict + candidate version, colour tied to gate
conformity. Resolution rate stays intentionally absent (judged quality shared
until per-agent eval). Org totals stay deduplicated.

**Admin / Rôles & accès — RBAC role × agent (Tier 3).** `observability/rbac.py`
crosses the **real** enforced roles (mirrored from `lib/auth/session.ts` —
admin/auditor/superadmin + their capabilities) with the **real** registry agents.
Endpoint `/observability/rbac-matrix?agent=`. The page mounts the global filter +
a `RbacAgentMatrix` (role × agent grid). **Honest current state:** the enforced
roles are **org-wide**, so every cell reads "org" — stated truthfully, not a
fabricated per-agent grant. **Follow-up (logged):** a per-agent role-binding store
(assigning a role to specific agents, e.g. "ML Eng on support-client"). **Deviation
(pre-existing, flagged not fixed):** the legacy `AccessOverview` panel below is a
deterministic **fixture** (`observability/access.py` — hardcoded counts/users); it
predates this pass and is out of scope here, but it contradicts the zéro-hardcode
discipline and should be made real or removed in a dedicated cleanup.

**Prouver / Audit — agent_id filter (Tier 2).** The guard audit chain already
carries `agent_id` (Phase 0). Surfaced it: `AuditEntry` now parses `agent_id`; the
`/audit` + `/audit/overview` handlers accept `?agent=` and `_filter_entries` filters
by it; the page mounts the global `AgentScopeFilter` (distinct from the switcher) and
`AuditTable` reads `?agent=` into its query so both the list and the scoped metrics
follow it; the detail panel shows the per-turn `Agent`. Real — only the ~390
agent-stamped events resolve when scoped; pre-stamping records (no `agent_id`) are
honestly excluded from a scoped view. **Deviations (logged):** (1) chain integrity is
computed over the **whole** chain (the seal is chain-wide), not the filtered subset —
correct, a filter is a view not a re-seal; (2) a full per-agent **État à date** seal
(as-of-T scoped by agent) is a follow-up; the filter scopes the audit view that feeds
it.

**Configurer / "used-by" — the inverse binding (Tier 2).**
`observability/catalogue_consumers.py` inverts the governed registry bindings: for
a catalogue `kind` (model / guardrails / knowledge / prompts / tools / eval_set),
each shared item lists its **consumer agents** + each consumer's eval-gate verdict,
so a change's re-gate blast radius is explicit (`regate_count` = consumers not
passing-clean). Endpoint `/observability/catalogue-consumers?kind=&agent=`. Reusable
`CatalogueConsumers` panel; the **modeles** and **garde-fous** scaffolds are now real
(global filter + used-by panel). All real from `agents.yaml` bindings. **Follow-up:**
the other CONFIGURER pages (knowledge/policies/tools) can mount the same panel; the
"changement → re-gate" is currently *surfaced* (count + verdict), the governed
re-gate *action* runs through Release Control, not from this read-only catalogue.

**Rest of Surveiller + Agir — same pattern (Tier 3).** The remaining SURVEILLER
pages (conformité, fiabilité-coût, observabilité, amélioration) and AGIR pages
(incidents-playbooks, replay-shadow, curation-eval-set, automations) all mount the
shared `GovScopeSection` (global filter + real per-agent fleet breakdown + deduped
org total) atop their existing dashboard. **Deviation (logged):** the dashboards /
entities below (compliance signals, incidents, replays, automations…) are not yet
ventilated/tagged per agent — the filter scopes the per-agent breakdown (real) and
the honest banner states the body below is org-wide. Real-able follow-up: tag those
entities/signals with `agent_id` so the same filter scopes them too. No fabricated
per-agent value is shown.

**Agir / Release Control — built real (was a scaffold).** Each agent is a governed
package; the page is the per-agent release pipeline. `observability/release_control.py`
combines the **policy-correct** eval-gate verdict (`agent_release` → `build_gate_view`
over each agent's OWN run, eval-gate-policy primes) with the governed lifecycle state
+ S1 history (`agent_lifecycle`). Endpoint `/observability/release-control?agent=`
(global filter, distinct from the switcher). The page shows an org summary
(distinct-agent counts by readiness — NOT deduped conversation totals, which would
be the wrong grain here), per-agent cards with the verdict headline (colour tied to
conformity, §6), the gate breakdown (executions case×langue, socle T0 OK/ÉCHEC,
bloquants socle/T1, dérogés actifs — reconciled with Évaluations), the
proposed→reviewed→approved→live flow stepper and the last S1 event. Real for all 3
agents (all BLOQUÉ par le socle). No temporal rail (governance flow, not a scrubber).

**Surveiller — agent filter + breakdown (per page).** Each Surveiller page gets
the global `AgentScopeFilter` + a real `AgentBreakdown` (fleet rollup: observable
KPIs that genuinely differ per agent + deduped org total). Removed the **fake
hardcoded `banking`/`support` agent select** from `vue-ensemble`'s topbar (it was
exactly the "no real notion of agent" landmine).
**Deviation (logged):** the existing org-wide signal panels below the breakdown
(SLO, cost, refusal… — S4 time-series) are **not yet ventilated per agent**; the
filter scopes the per-agent breakdown (real) and an honest banner states the org
signals are not per-agent. Real-able follow-up: stamp `agent_id` on the S4 signal
series so the same filter scopes them too. No fabricated per-agent signal is shown.

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
Phase 2: the define/instance framing is now a **shared component**
(`components/agent/define-instance-banner.tsx`) used by **both Configurations and
Prompts**, rendering the normative's **numbered two-block** split — `1 · Définition
(catalogue · lecture seule)` (real registry rows + CONFIGURER link) then
`2 · Configuration pour cet agent (instance)` introducing the editable sections +
the production-governance banner. Deviation (kept): the instance controls stay in
the existing one-main-column + right-sidebar form below the banner, not a strict
left/right split — the editable form was extended in place, not rebuilt. The
CONFIGURER link still points to `/configurer/parametres` (no dedicated catalogue
route yet).

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
the truthful shape of this eval-heavy journal, not a fabrication). The normative's **`Mode d'application`** and **`Overrides`** panels are now built
for real (Phase 2): `Mode d'application` aggregates the guard rules by enforcement
mechanism (block / limit / confirm / allow) derived from `policy.yaml`, with the
per-mode decision volume from the S1 journal; `Overrides` binds to the **real**
rule-state store (`set_rule_state` / `_load_state`) and lists the rules currently
disabled for this agent — rendering an honest empty state ("Aucune dérogation
manuelle") when none are, never a fixture. Deviation: rendered as two horizontal
panels under the existing Watch/Quick/Coverage/Reasons row, not a donut; the rule
detail stays a right-hand panel (the persistent OT-01 column refactor is a
separate follow-up).

**Prompts governance banner (image 07, conformance pass).** The page is fully real
(YAML source of truth `agent/prompts/{fr,de,en}.yaml`, read-only — prompts are edited
via Git PR and loaded at start-up). Added the §9 **governance banner** stating that
governance model (define in Git → review (PR) → load), which is the truthful
define/choose/govern story for prompts. Phase 2: the normative's explicit numbered
**`1. Définition (catalogue)` / `2. Configuration pour cet agent (instance)`** two-block
split **is now rendered**, via the **shared** `DefineInstanceBanner` component (same as
Configurations). A real `definition` block was added to the Prompts payload — owner +
eval-set from the governed registry, source/languages/count from the live YAML
catalogue. The page keeps its KPIs + table + per-prompt detail below the banner. No
CONFIGURER prompts-catalogue route exists yet (the link points to
`/configurer/parametres`).

**Console XT-01 (image 05, conformance pass).** The page is real: quality metrics are
live eval scores (`_latest_score`), the model/prompt/sources/guard versions come from
source files, and live turns stream real responses through the same `/chat` route as
the product console (the per-turn debug trace is attached to the SSE envelope). Named
the execution-trace panel **`XT-01 · Trace d'exécution`** per the rails registry.
Deviations: (1) the **initial transcript is a seeded example** (fixed Q with the answer
assembled from *real* corpus excerpts) shown before the operator interacts — live turns
are real; flagged **à confirmer** whether to start from a real empty console instead.
(2) Resolved (Phase 2): the XT-01 trace is now a **persistent 3rd column**
(`TraceColumn`, titled "XT-01 · Trace d'exécution"), no longer a tab — the main
grid is chat (6) · inspector (3) · XT-01 (3), and "Trace" was removed from the
inspector tabs. The column reuses the same real per-turn debug trace and shows an
honest empty state before the operator runs a turn.

**Console refonte (image 05, 2026-06-19).** Aligned the Console body to normative
05, one zone at a time, with honest data throughout (verified e2e on a live Ollama
turn). Changes + deviations (logged):
- **Seeded turn removed** — the console starts on an honest empty state ("Aucun
  tour pour l'instant"); only live turns produce content. Resolves the prior
  "à confirmer" (start from a real empty console). The backend no longer emits a
  `transcript`.
- **Chrome chat** — removed the full-width "Session active" StatusBar and the
  `TemporalRail` from the chat column. **The Console's temporal rail IS XT-01**
  (registre : Console = XT-01 + Live); there is deliberately **no as-of scrubber**
  here. The model/prompt/sources/guard context was **relocated** (same real data,
  new place) into a **context strip** atop the central "Résumé de la réponse"
  column, with `Environnement = Sandbox` (the console is the debug/sandbox surface).
- **KpiRow removed (deviation).** SLA/MTTR are ops signals → they live in
  **SURVEILLER**, not a debug console. Removed rather than relocated.
- **Titles/tabs** — chat card "Conversation de test"; central column "Résumé de la
  réponse"; tabs → Sources / Outils / Garde-fous / Évaluation (dropped "Contexte",
  added "Évaluation"). **Deviation (logged):** the panel shows **one section at a
  time** (tab switch) whereas the normative stacks all sections; the Quality block
  is always shown above the tabbed section. Kept the existing tab pattern rather
  than a full stacked re-layout.
- **XT-01 waterfall** — rebuilt `TraceColumn` as a real waterfall at the **node
  grain** from the live SSE `debug.trace` (per-node `latency_ms`, ADR 0010 #4):
  cumulative `start_ms` bars, real `duration_ms`, ✓/⚠ status (warn derived from the
  turn's real guard deny/redaction on the reviewer node), total = sum of node
  durations, span count, **Exporter (JSONL)**, session id, Waterfall ↔ Arbre des
  spans toggle. **Deviation (logged):** the normative's *fine* stages (garde-fou
  pré/post, "5 chunks récupérés", "prompt assemblé") are **not** rendered — they are
  not separately timed, and a fabricated ms is forbidden; only the real timed graph
  nodes appear. A node not timed on a given turn (e.g. the streamed reporter) is
  honestly absent rather than shown at 0 with a made-up value.
- **Data honesty (pre-turn vs post-turn).** Response-specific panels (quality,
  sources used, trace) come from the **live turn only** — honest awaiting state
  before. **Quality** is 4 **distinct** live-derived scores after a turn (verified
  9.8 / 9.7 / 9.4 / 9.7); the old pre-turn `_quality()` placeholder (which
  collapsed to 4× the same value via `g/h = … or f`) was **removed**. Tools/
  guardrails keep the real loaded policy pre-turn ("disponibles"/"chargés") and swap
  to the real turn data ("appelés"/"déclenchés") after. The new **Évaluation
  automatique** tab surfaces the **latest real eval run** (faithfulness/grounding/
  hallucination), labelled "dernier run — la console ne ré-évalue pas chaque tour";
  honest "—" when a metric has no score. **À confirmer:** these latest-run values
  can legitimately coincide (real data property), distinct from the removed quality
  *collapse*.
- **Dev note (logged):** the codex frontend (`:3097`) proxies to this repo's own
  backend on **`:8392`** (`TESSERA_BACKEND_URL`); a stale sibling-repo backend had
  been occupying it and serving the old payload. Re-pointed to this repo's backend
  for the conformance capture.

**Évaluations vs eval-gate-policy (image 09 + binding policy, conformance pass).** The
binding `eval-gate-policy.md` **primes over the image** for verdict/numbers. The page
is real (gate from a real llama3.2:3b failure-catalogue run; verdict = BLOQUÉ par le
socle on 3 real PII failures; score 6,6/10). Verified policy invariants that **hold**:
- **Verdict is the headline wording** — relabelled to policy terms `BLOQUÉ par le socle`
  / `BLOQUÉ (domaine)` / `PASSE` (was "Bloqué (socle critique)" / "Validé").
- **Aggregate colour tied to conformity** — the verdict card is red when blocked; the
  global score (6,6) is neutral, not green.
- **Non-concluant = bloquant** — the two-level gate already treats critical failure as
  blocking (no "pass" credit for non-executed).
- **Case-distinct critical breakdown (§6)** — added `Critiques bloquants : N (dont Tier 0
  non-dérogeable : M) · Sous dérogation : 0`. **T0 ∩ dérogations = ∅** holds vacuously:
  the 3 PII failures are marked **Tier 0 non-dérogeable** and `waived = 0` (no waiver
  store), so no `Dérogé actif` can ever appear on a socle/T0 case.
- **Numeric coherence** — 41 cas = 35 domaine + 6 socle ; 27 réussis (24 domaine + 3) /
  14 échoués (11 + 3 critiques) reconciles; taux 66% ↔ score 6,6.
**Resolved (Phase 2, conformance pass) — the full policy is now built for real.**
The earlier two-level gate is replaced by a policy-correct one recomputed from
first principles over a fresh FR/DE/EN run (119 case×langue executions):
- **Three-tier model (T0/T1/T2) as first-class.** T0 = the curated, versioned
  socle (`eval/sets/socle-securite.json`); T1 = a curated, versioned list
  (`eval/tiers.yaml`) of dérogeable criticals (hors socle); T2 = the graded
  remainder. Loaded + invariant-checked by `observability/eval_tiers.py`
  (T0 ∩ T1 = ∅ asserted at load; T0 never waivable).
- **Governed waiver objects** — `observability/eval_waivers.py`: an **S1,
  append-only, hash-chained** event store (RBAC roles, separation of duties
  enforced — requester ≠ approver — compensating controls, incident ref,
  **expiry → auto re-block** computed at render, never stored). Seeded
  idempotently against the **real candidate run** by
  `scripts/seed_eval_waivers.py`: 2 active, 1 expired (auto re-block demo) and 1
  **Tier 0 attempt** rendered "sans effet" — the `T0 ∩ dérog = ∅` invariant shown
  with a real event, not asserted in prose.
- **Per-(cas × langue) gating + structural Venn** — `observability/eval_gate_view.py`
  classifies every (case, langue) execution; the Venn is **structural membership**
  (Socle + T1 + Domaine = executions), distinct from the failure count. Verdict,
  breakdown, socle/hors-socle split, socle-by-category markers, critical-cases
  table and the waiver registry **all reconcile** at the case×langue grain
  (locked by `tests/unit/test_eval_gate_policy.py`).
- Data is **real, not fabricated**: only the waiver *governance envelopes* are
  seeded (metadata bound to real failing T1 case×langue of the real run).
**À confirmer** : T1 curation is a documented judgment call (`eval/tiers.yaml`);
the waiver **grant** flow is read-only on the page — waivers are created via the
governed script, not yet editable from the UI (propose → approve). The category
labels in the socle markers reuse the existing ASCII `CATEGORY_LABELS`
(pre-existing source, e.g. "Confidentialite"), unchanged here.

**Historique CT-01 + per-turn agent (images 30/301, conformance pass).** The session
**detail** already satisfies the multi-agent invariant: turns come from
`conversation_messages` (real `agent_id` per message) and handoffs from the S1 journal,
each turn rendered with its handling agent + per-agent accent + routing reason — real,
verified on a 10-turn conversation. Named the turns timeline **`CT-01 · Chronologie de
la session`** per the rails registry. The **list** is real (eval-run sessions + Agent
column + KPIs). Deviation: the list rows are **eval-run sessions** (case × langue), whose
`sid` is not a `conversation_messages` id — so opening one yields the empty state; only
**real chat conversations** (UUID) resolve to the full per-turn detail. Logged;
**à confirmer** whether the list should also surface real chat conversations.
