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
| `/agir/incidents-playbooks` | org-wide | vue générique RETIRÉE (décision 2026-07-15) — pas de substrat incidents par agent |
| `/agir/automations` | org-wide | vue générique RETIRÉE (décision 2026-07-15) — signal org-wide |
| `/agir/replay-shadow` | org-wide | vue générique RETIRÉE ; **OWED : vraie lentille replay** (`_RunDiff` interne EST par agent) |
| `/agir/curation-eval-set` | org-wide | vue générique RETIRÉE (décision 2026-07-15) — catalogue transversal cas × modèles |
| `/prouver/audit-logs` | lens:proof | **NOUVEAU** — governance, audit_count ; intégrité de chaîne = org-wide par conception |
| `/prouver/etat-a-date` | org-wide | l'écran NOMME sa portée (agent par défaut Support client + flux org-wide) ; paramètre agent = OWED |
| `/prouver/evidence-store` | org-wide | proofs sans décomposition agent |
| `/configurer/signal-catalog` | org-wide | catalogue |
| `/configurer/garde-fous` | org-wide | catalogue global CONFIRMÉ (2026-07-15) — le par-agent vit dans `agents/[id]/garde-fous` |
| `/configurer/modeles` | org-wide | idem (filtre "utilisé par" ≠ vue) |
| `/configurer/connecteurs` | org-wide | config |
| `/configurer/politiques` | org-wide | config globale CONFIRMÉ (2026-07-15) |
| `/configurer/sources-memoire` | org-wide | config globale CONFIRMÉ (2026-07-15) |
| `/configurer/parametres` | org-wide | config |
| `/configurer/integrations` | org-wide | config |
| `/admin/utilisateurs` | org-wide | annuaire |
| `/admin/roles-acces` | lens:access | RbacAgentMatrix (par agent par construction) |
| `/admin/profil-systeme` | org-wide | système |

Hors registre (documenté, pas policé par ce cliquet) : `agents/[agentId]/*` (par agent
par construction — autre chantier), `/agents` (annuaire de flotte), `/a-traiter` et
`/a-faire` (files opérateur : listes dont chaque item porte son agent, pas des vues
agrégées par agent), et les surfaces hors cockpit (login, produit, espaces, comprendre…).

## Décisions produit (Amadou, 2026-07-15 — HALT résolu, exécutées)

1. **`agir/curation-eval-set`** → **org-wide, tableau générique retiré.** Le catalogue est
   transversal (jeu de cas × modèles) ; une vue par agent y serait un mensonge de
   décomposition.
2. **`configurer/{garde-fous, politiques, sources-memoire}`** → **org-wide zone confirmé.**
   Le par-agent vit déjà dans `agents/[id]/garde-fous` ; deux vues = doublon confus.
3. **`agir/{incidents-playbooks, automations, replay-shadow}`** → **vue générique retirée,
   org-wide** (pas de vue > fausse décomposition : une carte « Vue par agent » sur ces
   pages suggère une décomposition du domaine qui n'existe pas — « monitoring explicite »
   ne suffit pas). **OWED** : la vraie lentille replay par agent (`_RunDiff` de
   `replay_shadow.py` est déjà keyé par `agent_id` — la seule des trois qui mérite une
   vraie lentille) ; le lot « attribuer les clusters d'incidents aux agents » reste OWED.
4. **`prouver/etat-a-date`** → **le défaut silencieux d'identité est tué d'abord** : le
   champ Agent dit « Support client (agent par défaut) » et la bannière énonce la portée
   réelle (package de l'agent par défaut ; flux de gouvernance org-wide). Un agent fantôme
   ne décide plus silencieusement de ce que la page de preuve opposable prouve.
   **OWED** : le paramètre agent (reconstruction par agent choisi), lot futur.

Certificat règle 1 : **verbatim confirmé** — une pièce de mesure (identifiant de cas,
chiffres), pas de la prose ; on ne traduit pas une pièce.

## OWED consignés par ce lot

- `?signals=<id non enregistré>` sur `/observability/snapshot` → **500 nu** (classe
  fleet-500, aucun contrat honest-empty). Un jour, pas maintenant.
- Lentille **replay par agent** (substrat interne `_RunDiff` déjà par agent_id).
- Lot « incidents attribués aux agents à la source » (décision du 2026-07-15, inchangée).
- `etat-a-date` : paramètre agent (preuve par agent choisie).

## Preuves du cliquet (mutations, toutes restaurées)

- page `lens:security` passée en rendu générique → **rouge** : `declared lens:security
  but does not call loadDeclaredLens("/surveiller/securite-privacy", …)` + `passes no
  lens to the view` ;
- registre basculé `org-wide` sur la même page → **rouge ×2** (cohérence + épingle) et
  **TS2345** (la page ne compile plus) ;
- page de zone ajoutée sans déclaration → **rouge** : `zone pages with NO declared
  nature: /agir/page-fantome`.
