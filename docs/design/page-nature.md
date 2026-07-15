# Page-nature — le modèle de contextualisation par agent, figé (2026-07-15)

**Le principe** (la doctrine `is_org_wide` appliquée aux PAGES) : une page porte une vue
par agent **si et seulement si** sa question se décompose par agent. Une page dont le
domaine est release/preuve/sécurité mais qui montre volume/latence répond à côté — un
mensonge par omission. Trois natures :

- **`org-wide`** — la question ne se décompose pas ; AUCUNE vue par agent (en mettre une
  serait du bruit, et le cliquet en fait un rouge) ;
- **`lens:<domaine>`** — la question se décompose ; la vue par agent répond à CETTE
  question. La plupart des domaines rendent via `AgentBreakdown` avec une lentille chargée
  par `loadDeclaredLens` (le domaine vient du registre, jamais de l'appelant) ; trois
  domaines sont des rendus dédiés : `monitoring` (colonnes par défaut — légitime là où le
  monitoring EST la question de la page), `release` (cartes `ReleaseControlView`),
  `access` (`RbacAgentMatrix`) ;
- **`redirect`** — le fichier ne fait que rediriger.

**Le mécanisme.** Registre : `webapp/frontend/lib/page-nature.ts` (`PAGE_NATURE`, gelé et
épinglé littéralement). Cliquet : `webapp/frontend/lib/page-nature.test.ts` — découverte
fs des cinq répertoires de zone (peut trouver PLUS de pages, jamais moins), complétude
bilatérale registre↔disque, témoins de source par nature, exceptions gelées à **ZÉRO**
(bilatéral, ne peut que baisser). En plus du test : déclarer une page `org-wide` alors
qu'elle appelle `loadDeclaredLens` est une **erreur de compilation** (TS2345 —
`DeclaredLensRoute` n'admet que les routes déclarées lentille de breakdown), et un
nouveau domaine déclaré ne compile pas tant que `DOMAIN_SIGNALS` ne le sert pas.

**La mesure d'abord.** Chaque colonne derrière un domaine de breakdown a été mesurée
avant d'être écrite (`GET /observability/snapshot?agent=<id>&signals=…`, 2026-07-15,
6/6 agents répondant `honoured: ["agent"]`) : `slo`, `scores`, `pii_leak`, `toxicity`,
`tool_validity`, `cost`, `gating`, `anomalies`, `what_changed`, `trend`, `funnel`,
`governance`, `audit_count`, `conformance`, `business_events`, `business_capabilities`,
`recouvrement_business_scores` — plus l'objet `release` par agent du payload fleet.
NON déposables (mesuré/confirmé) : `traces` (déclaré CUBE dans capabilities.py mais
**aucune lecture enregistrée** — une capacité déclarée sans serve n'est pas un substrat),
`incidents`/`automations`/`replay_shadow`/`curation`/`evidence_export` (org-only ou
fixtures), `audit_integrity` (org-wide **par conception** : une sous-chaîne par agent
serait une garantie plus faible), l'état-à-date (le builder code en dur
`DEFAULT_AGENT_ID`).

## La matrice (page → nature)

| Route | Nature | Substrat / justification |
|---|---|---|
| `/surveiller` | redirect | → vue-ensemble |
| `/surveiller/vue-ensemble` | lens:monitoring | le monitoring EST sa question (non-régression épinglée) |
| `/surveiller/qualite-ia` | lens:quality | dynamique alarm/quality/masked (`loadBreakdownLens`) |
| `/surveiller/securite-privacy` | lens:security | pii_leak, toxicity, tool_validity.denied |
| `/surveiller/conformite` | lens:compliance | governance, audit_count |
| `/surveiller/fiabilite-cout` | lens:reliability | tool_validity.errored, cost |
| `/surveiller/amelioration` | lens:improvement | réutilise quality (décision produit 2026-07-15) |
| `/surveiller/observabilite` | lens:observability | **NOUVEAU** — anomalies, conformance |
| `/agir/release-control` | lens:release | cartes par agent + **la raison** (floor_block, périmé, comptes) |
| `/agir/incidents-playbooks` | lens:monitoring | pas de substrat incidents par agent — OWED (décision 2026-07-15) |
| `/agir/automations` | lens:monitoring | signal org-wide — proposition en HALT |
| `/agir/replay-shadow` | lens:monitoring | org-wide (mais `_RunDiff` interne EST par agent → substrat futur) |
| `/agir/curation-eval-set` | lens:monitoring | fixture org — proposition org-wide en HALT |
| `/prouver/audit-logs` | lens:proof | **NOUVEAU** — governance, audit_count ; intégrité de chaîne = org-wide par conception |
| `/prouver/etat-a-date` | org-wide | builder mono-agent (DEFAULT_AGENT_ID) — voir HALT |
| `/prouver/evidence-store` | org-wide | proofs sans décomposition agent |
| `/configurer/signal-catalog` | org-wide | catalogue |
| `/configurer/garde-fous` | org-wide | catalogue global (filtre "utilisé par" ≠ vue) — question en HALT |
| `/configurer/modeles` | org-wide | idem |
| `/configurer/connecteurs` | org-wide | config |
| `/configurer/politiques` | org-wide | config globale — question en HALT |
| `/configurer/sources-memoire` | org-wide | config globale — question en HALT |
| `/configurer/parametres` | org-wide | config |
| `/configurer/integrations` | org-wide | config |
| `/admin/utilisateurs` | org-wide | annuaire |
| `/admin/roles-acces` | lens:access | RbacAgentMatrix (par agent par construction) |
| `/admin/profil-systeme` | org-wide | système |

Hors registre (documenté, pas policé par ce cliquet) : `agents/[agentId]/*` (par agent
par construction — autre chantier), `/agents` (annuaire de flotte), `/a-traiter` et
`/a-faire` (files opérateur : listes dont chaque item porte son agent, pas des vues
agrégées par agent), et les surfaces hors cockpit (login, produit, espaces, comprendre…).

## Décisions produit en attente (HALT)

1. **`agir/curation-eval-set`** — le catalogue est transversal (jeu de cas × modèles).
   Proposition : **org-wide** (retirer le tableau monitoring générique). À trancher.
2. **`configurer/{garde-fous, politiques, sources-memoire}`** — config globale, ou
   déclinée par agent ? Les fiches par agent existent déjà sous `agents/[id]/garde-fous`.
   Proposition : org-wide au niveau zone, le par-agent vit dans la fiche. À trancher.
3. **`agir/{incidents-playbooks, automations, replay-shadow}`** — la spine n'expose pas
   de fait par agent dans leur domaine. Proposition : **retirer la vue générique**
   (pas de vue > fausse vue) et re-déclarer org-wide — OU garder monitoring explicite en
   attendant le substrat (incidents : le lot futur « attribuer les clusters aux agents »
   est déjà OWED ; replay : `_RunDiff` interne est déjà par agent, l'exposer est un petit
   lot). À trancher page par page.
4. **`prouver/etat-a-date`** — le builder reconstruit l'état d'UN agent implicite
   (`DEFAULT_AGENT_ID`) sans le dire. Substrat partiel (audit log et transcript portent
   l'agent). Proposition : petit lot « paramètre agent » OU assumer org-wide et l'écrire
   sur la page. À trancher.

## Preuves du cliquet (mutations, toutes restaurées)

- page `lens:security` passée en rendu générique → **rouge** : `declared lens:security
  but does not call loadDeclaredLens("/surveiller/securite-privacy", …)` + `passes no
  lens to the view` ;
- registre basculé `org-wide` sur la même page → **rouge ×2** (cohérence + épingle) et
  **TS2345** (la page ne compile plus) ;
- page de zone ajoutée sans déclaration → **rouge** : `zone pages with NO declared
  nature: /agir/page-fantome`.
