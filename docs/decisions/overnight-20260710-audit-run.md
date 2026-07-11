# Run de nuit 2026-07-10 → 07-11 — remédiation d'audit

Journal d'exécution de la remédiation intégrale de l'audit
`Tessera_private/audit-code-2026-07-10.md` (main `ece4f1bf`). Un lot = une branche =
un merge. Une passe `make gate` par lot avant merge ; le CI est la deuxième passe
(asynchrone). Rouge deux fois → parké. Contradiction de design → parké, pas tranché.

---

## RÉSUMÉ MATIN (mis à jour au fil de la nuit)

**État au démarrage** : gate (workflow *CI*) **vert** sur `ece4f1bf` ; workflows
*Security* + *Supply chain* **rouges** — pré-existants, hors périmètre de correction
cette nuit (voir « État de base » ci-dessous).

> ⚠️ **CI INDISPONIBLE (découvert au lot 1.3, ~06:30) — action Amadou requise.**
> Depuis cette nuit, **tous** les runs GitHub Actions échouent en ~3 s :
> *« The job was not started because recent account payments have failed or your
> spending limit needs to be increased »* (Billing & plans). Ce n'est pas mon code —
> le commit journal (docs-only) échoue pareil, et `ece4f1bf` passait hier en 30 min.
> **Conséquence** : la « 2ᵉ passe CI » est indisponible toute la nuit ; chaque merge
> repose sur le **gate local** (identique à la commande `make gate` du CI, hermétique,
> exécuté une fois par lot). STOP-THE-LINE dégradé en *local-gate-only*, assumé.
> À faire par Amadou : régler la facturation GitHub, puis relancer `make gate` /
> le CI sur `main` pour confirmer les merges de la nuit.

| Fenêtre | Lot | Sujet | Verdict | Hash |
|---|---|---|---|---|
| — | 0 | Journal + état de base | ✅ | 5ddd5215 |
| 1 | 1.1 | Tests d'intégration (job CI + tri) | ✅ | ff→main |
| 1 | 1.2 | 49 `except … pass/continue` | ✅ | ff→main |
| 1 | 1.3 | 7 SQL f-string + coverage informatif | ✅ | ff→main |
| 1 | 1.4 | Trio recouvrement + kicker credit-aurore | ✅ | ff→main |
| 2 | 2.1 | Rate-limit `/agents/{id}/invoke` | ✅ | ff→main |
| 2 | 2.2 | Sauvegarde ledger + drill restauration | ✅ | ff→main |
| 2 | 2.3 | Inventaire config généré | ⏳ | — |
| 3 | 3.0 | Prototype codegen OpenAPI→zod (fleet) | ⏳ | — |
| 3 | 3.1 | Scission `observability.py` | ⏳ | — |
| 3 | 3.2 | Extraction tabs communs | ⏳ | — |
| 4 | 4.1 | Doc posture prod | ⏳ | — |
| 4 | 4.2 | Job CI deps/CVE informatif | ⏳ | — |
| 4 | 4.3 | Échantillon biome-ignore | ⏳ | — |
| 4 | 4.4 | Fixture-trafic → flip e2e | ⏳ | — |

**Chiffres avant → après** (remplis en fin de nuit) : except classés · SQL fermés ·
coverage % · routes supprimées · rate-limit · drill OK/KO · verdict codegen · flip e2e.

**Ce qui attend Amadou / Claude** : (rempli en fin de nuit).

---

## État de base (mesuré au démarrage, `ece4f1bf`)

### Gate = vert, mais deux workflows séparés sont rouges (pré-existants)

Le workflow **CI** (= `make gate`, hermétique, bloquant) est **vert** sur `ece4f1bf`.
Deux autres workflows sont rouges **avant** ce run, indépendamment de tout lot ci-dessous :

**`security.yml`** — 4 jobs rouges :
- `bandit` : 20 findings (14 Low, 6 Medium, 0 High ; confiance High×20) → exit 1.
  Le job échoue sur **tout** finding (pas de seuil). Le lot 1.3 (SQL f-string) en
  retirera une partie mais ne le rendra pas vert seul. **Hors périmètre nuit** (c'est
  `security.yml`, pas le gate).
- `pip-audit` : CVEs réelles — `starlette 0.52.1` (CVE-2026-48817, CVE-2026-48818,
  fix 1.1.0), `vcrpy 8.1.1` (GHSA-rpj2-4hq8-938g, fix 8.2.1). Le mandat **interdit
  toute montée de version cette nuit** → documenté (posture prod 4.1), pas corrigé.
- `CodeQL (python)` : rouge (analyse) — probablement upload SARIF sur repo privé sans
  GitHub Advanced Security. Structurel.
- `trivy (container)` : `Run Trivy` + `Upload Trivy SARIF` rouges — même cause SARIF.

**`supply-chain.yml`** — `provenance / final` rouge : le générateur SLSA **halte
volontairement** sur repo privé (« Repository is private … Set 'private-repository'
to override ») + exit 127 dans le générateur. Structurel, lié au repo privé.

**Lecture** : ces rouges tiennent à des réglages de dépôt (Advanced Security, override
SLSA private-repo) et à des CVEs qu'on n'a pas le droit de patcher cette nuit — pas à
une régression de code. Ils sont **consignés pour Amadou** (posture prod, lot 4.1) et
ne déclenchent pas STOP-THE-LINE, qui lit le workflow *CI* (le gate). Dependabot est
déjà configuré (branches `dependabot/*` ouvertes pour ces CVEs).

### Mécanique de merge (worktree `agents/claude`)

`main` est checked-out dans `/tessera`, donc pas de `checkout main` ici. Chaque lot :
`git fetch origin` → `git checkout -b claude/<sujet> origin/main` → edits →
`make gate` (une passe) → commit ciblé (jamais `git add -A`) →
`git push -u origin claude/<sujet>` + `git push origin HEAD:main` (ff). Branch
protection **absente** (confirmé 403 GitHub Pro), ff-push direct autorisé.

---

## Log par lot

### Lot 0 — Journal + état de base
Ce fichier. Ouverture du run, état de base mesuré et consigné ci-dessus.

### Lot 1.1 — Tests d'intégration : workflow dédié + tri (P0.1)
Branche `claude/lot-1-1-integration`.

**Correction d'audit #1 (mesurée) : ZÉRO test mort.** La reconnaissance a ouvert les
9 fichiers `integration` et vérifié chaque symbole importé contre `src/tessera` actuel —
tous présents, signatures compatibles. Aucune suppression justifiée. Le « modèle
71b15b18 » invoqué par l'audit **n'est pas** un commit de suppression de test (c'est une
refonte front du Console) ; `git log --diff-filter=D -- 'tests/**/*.py'` est **vide** —
aucun test Python n'a jamais été supprimé dans ce repo. La consigne « supprimer avec le
commit qui a retiré la surface » n'avait donc **aucune cible** ici. Consigné, pas forcé.

**Fait.**
- **Workflow dédié** `.github/workflows/integration.yml` — non-gatant (workflow séparé,
  ne bloque jamais un merge), **nightly** (`cron 0 3 * * *`) + **manuel**
  (`workflow_dispatch`) + label `integration` sur PR. Services **Postgres + ClickHouse**
  (les deux stores durables *owned* ; l'adapter ClickHouse fait `CREATE DATABASE/TABLE IF
  NOT EXISTS` → aucun step d'init). Étape « Wait for ClickHouse » côté runner (curl /ping)
  car la santé de l'image CH est peu fiable ; non-fatale (les tests CH sondent et skippent
  seuls). Le job `test-integration` a été **retiré de `ci.yml`** (il tournait sur chaque
  push-main, bruyant) ; en-tête de `ci.yml` mis à jour.
- **`test_agent_e2e.py`** : docstring **mensonger corrigé** (« mocked I/O » était faux —
  seule la *retrieval* est stubbée ; le LLM on-prem est appelé pour de vrai, le conftest
  force `TESSERA_LLM_PROFILE=on_prem`). Ajout d'une **sonde Ollama** (`_require_local_llm`,
  socket sur `TESSERA_OLLAMA_HOST`/`:11434`) → **skip propre** hors machine locale, au lieu
  d'erreurs. Marqué et documenté **local-only**.
- **`tests/integration/README.md`** : grille de tri (qui tourne en CI, qui skip et
  pourquoi).

**Grille fichier → verdict** (9 fichiers, 8 REPAIR / 1 LOCAL-ONLY / 0 DELETE) :

| fichier | besoin | CI nightly |
|---|---|---|
| `test_firewall_adapter.py` | rien d'externe | ✅ |
| `test_ledger_contract.py` | Postgres | ✅ |
| `test_memory_transcript/summary/persistent.py` | Postgres (+pgvector) | ✅ |
| `test_owned_stores_contract.py` | Postgres + ClickHouse | ✅ |
| `test_owned_business_events_contract.py` | ClickHouse | ✅ |
| `test_spine_adapters_contract.py` | Prometheus + Langfuse | ⏭️ skip (obs-up local) |
| `test_agent_e2e.py` | LLM on-prem Ollama | ⏭️ skip (local-only) |

Aucun secret en CI. « Réparer vers le contrat réel » = **les faire tourner** (les contrats
étaient déjà justes, surfaces présentes) ; seul `test_agent_e2e` demandait une retouche
code (sonde de skip + docstring).

### Lot 1.2 — Les 49 except silencieux : classés, 1 avaleur réparé (P0.2)
Branche `claude/lot-1-2-excepts`. 36 fichiers, comment-only sauf 1 fix + 2 logs de visibilité.

**Correction d'audit #2 (mesurée) : le danger n'était PAS dans les pass/continue.** Scan
AST de 371 handlers. Le jeu strict silencieux (`pass`/`continue`/`break`) = **57** (49
purs `src`, +4 log+continue `src`, +4 `scripts`, 0 `eval`) — l'« 49 » de l'audit = le
sous-ensemble pur `src`. Quasi tous **LEGIT** (sauts best-effort par enregistrement sur des
lectures non-gatantes : parse JSONL, coerce datetime, lecture JSON dashboard). Le vrai
danger vit dans les **return-fallback** (217 handlers), et l'audit un-par-un y a trouvé
**un seul vrai avaleur** — pas dans les pass/continue.

**L'avaleur (réparé) — `agent_synthese.py:791`** : `except (OSError, ValueError): chain_ok
= True` = **fail-OPEN sur l'intégrité du ledger** — la page Synthèse affichait la chaîne
« vérifiée » quand la vérification avait *erré*. Un faux vert, exactement ce que le projet
interdit. Le jumeau `system_profile.py:142` faisait déjà correctement `chain_ok = False`.
**Corrigé** en fail-CLOSED.

**Les 7 UNSURE, tranchés** (lecture des sites + traçage des appelants) :
- `ledger_store.py:593` (as-of malformé → retourne tout) : **dead-defensive** — le seul
  appelant non-None est `seal.py` qui passe `datetime.isoformat()`, toujours bien formé.
  Annoté, pas de changement de comportement.
- `audit.py:368` (dispatch sink) : **déjà** loggé en stderr (pas silencieux) ; durabilité
  canonique = spool du sink `file` ; limite postgres/cloud nommée. Annoté.
- `ledger_store.py:292/424` + `audit.py:132` (sauts de ligne corrompue) : LEGIT — le
  vérificateur de chaîne ne saute PAS, une vraie casse resurgit. `:292/:424` reçoivent en
  plus un **`sys.stderr.write`** de visibilité (le « log » demandé).
- `ledger_store.py:648`, `current.py:112`, `audit.py:365` : LEGIT non-gatant, annotés.

**« Zéro pass nu restant » — prouvé** : check AST → **0** handler `pass`/`continue`/`break`
silencieux sans commentaire (au-dessus ou inline) sur `src`+`scripts`+`eval`.

**Calibrage assumé** : le « log debug » du mandat est appliqué aux sites **ledger/audit**
(où une ligne perdue compte → `sys.stderr.write`), **pas** aux ~40 boucles de lecture
dashboard/eval (un log par fichier sauté à chaque page = spam) — là le commentaire porte
l'intention. Grille des 57 verdicts : voir le message de commit du lot.

### Lot 1.3 — SQL f-string + coverage informatif (P0.3 + P0.6)
Branche `claude/lot-1-3-sql-coverage`.

**Correction d'audit #3 (mesurée) : « 7 » SQL f-string → en réalité ~57, TOUTES
non-exploitables.** Sondage : ~57 sites f-string SQL dans `src/` (37 avec `# noqa: S608`),
répartis sur `guard/`, `retrieval/`, `observability/`. **Chaque** interpolation est un
**identifiant** (table/schéma/colonne) venant d'un constant module, d'un réglage boot-time,
ou de l'allow-list `_ident()` ; **chaque valeur** est liée en `%s`/param serveur. **Zéro
site exploitable par une entrée requête.** Aucun `text(f"...")` SQLAlchemy.

Le vrai défaut n'était donc pas les instances mais **deux mensonges/latences de classe** —
« fermer la classe, pas les instances » :
1. **Commentaire bandit B608 mensonger** (`pyproject.toml`) : justifiait le skip repo-wide
   par « la seule valeur interpolée est le nom de table dans `retrieval/store.py` » — **faux
   aujourd'hui** (57 sites, 3 packages). Réécrit pour dire le vrai (identifiants only,
   valeurs liées, identifiants non-paramétrables → skip repo-wide).
2. **Site latent `agent_scope.py::dedup_org_total(where=...)`** : le prédicat `where` était
   interpolé **brut** (seuls les identifiants passaient `_ident()`). Traçage : **un seul
   appelant** (`fleet.py:187`), **personne ne passe `where`**. → **paramètre supprimé**
   (mort + injection-prone) : la seule surface d'injection *forward* des 57 sites est close,
   structurellement (behavior-neutral, prouvé par le gate + `test_agent_scope.py` inchangé).

**Coverage (P0.6)** : ajout de `--cov=src/tessera --cov-report=term-missing
--cov-fail-under=0` au `pytest` de `gate-py` (Makefile) → le gate (et le CI, qui appelle
`make gate-py`) **affiche** la couverture, **aucun seuil bloquant** (`fail_under=0` surcharge
le 55 de `pyproject`). Testé : exit 0, table affichée, pas de heurt `filterwarnings=error`.
Le chiffre réel de la nuit est dans le log du gate du lot (à reporter au résumé matin).
Couverture mesurée : **77.8 %** (unit + non-integration).

### Lot 1.4 — Trio recouvrement dissous + kicker « Démo Tessera » retiré (P0.4 + P0.5)
Branche `claude/lot-1-4-recouvrement`. Frontend-only.

**P0.4 — le trio, et l'inversion qu'il cachait.** L'URL propre `/recouvrement` (celle que
visent TOUS les liens + le role-router `spaceRedirectForRole` + la gate `collections`)
**redirigeait vers le vieux console `-legacy`** (244 LOC), tandis que le vrai produit
(`RecouvrementProductExperience`, 2701 LOC) était bloqué sur `-new` **sans la gate**
(trou de surface). Dissolution :
- `recouvrement/page.tsx` **réécrit** : rend `RecouvrementProductExperience` (le contenu de
  `-new`), derrière sa gate `collections` (layout.tsx déjà là) → **ferme le trou non-gaté**.
- `recouvrement-new/page.tsx` et `recouvrement-legacy/{page,layout}.tsx` **supprimés**.
- Specs repointées : `recouvrement-new.spec.ts` → **renommée** `recouvrement.spec.ts`
  (`PAGE = /fr/recouvrement` + docstring) ; `business-counting.spec.ts` (`DEDICATED`).
- **Sécurité du repoint vérifiée** : les 2 specs se loggent en `admin` ; `admin` → rôle
  `admin` → `isOperator` → `hasCollectionsAccess = true` (roles.ts:53) → passe la gate. Le
  produit rendu est le MÊME composant que `-new` (déjà couvert vert). Aucun lien à changer.
- **Consigné pour suivi (pas cette nuit)** : `RecouvrementConsole` (+ son backend assistant)
  devient un **îlot mort** (son unique montage était `-legacy`). Ce n'est PAS une surface de
  navigation (rien n'y route → pas un mensonge de nav), donc pas de cascade de suppression
  risquée dans un lot à e2e ; à retirer dans un lot dédié dead-code.

**P0.5 — le kicker (et un jumeau non nommé).** `credit-aurore-mes-comptes-host.tsx` :
- `<strong className="demo-kicker">Démo Tessera</strong>` **retiré** (+ son CSS `.demo-kicker`
  mort). La démo reste divulguée par « Page client fictive, chat réel » + l'aria-label du
  strip « Statut de la démonstration ».
- **Jumeau trouvé et corrigé** : l'aria-label `« Ouvrir l'assistant Tessera »` était la MÊME
  violation lexique (Tessera côté produit, `ui-contract.md §Annexe`) → `« Ouvrir l'assistant »`.
- Test `header-components.test.ts:135` : l'assertion-pin `toContain("Démo Tessera")` (qui
  **épinglait** la violation) **remplacée** par le garde-fou `not.toContain("Tessera")` — le
  fichier n'a plus aucun « Tessera » (vérifié au gate vitest). Annexe citée au commit.

**e2e (specs de routes touchées)** : **8/8 vert**. Build de production 1.4 servi sur `:3390`
(→ backend de référence `:8099`, inchangé par ce lot frontend-only), playwright 1 worker :
`app-grid.spec.ts` 4/4 + `recouvrement.spec.ts` 4/4 — dont « the operator's day is the
landing view » (le produit rend bien sur `/fr/recouvrement`, admin passe la gate) et « the
product plane never says Tessera ». `business-counting.spec.ts` (qui **mute** le store
partagé + exige ClickHouse) **non lancé ici** — son changement est un repoint de constante
d'une ligne, couvert par la suite de fin de nuit sur main. (CI e2e billing-bloqué, cf. note.)

## Fenêtre 2 — sécurité et survie

### Lot 2.1 — Rate-limit + concurrence sur `/agents/{id}/invoke` (P1.1)
Branche `claude/lot-2-1-invoke-ratelimit`.

**Réutiliser, pas réinventer.** Une infra de rate-limit existait déjà (`api/ratelimit.py`,
lib `limits`, `RateLimitMiddleware` : `/chat` strict + global, read générique). L'invoke ne
recevait que le **read générique** (120/min) — pas de limite dédiée ni de plafond de
concurrence (le trou P1.1 / question ouverte 0019). J'ai **étendu** l'existant, pas construit
un limiteur parallèle :
- `InvokeLimiter` (`api/ratelimit.py`) : fenêtre glissante par **(agent, rôle=surface,
  subject)** via le moteur `limits` (donc un `rate_limit_storage_uri` Redis le rend
  cross-instance) + **plafond de concurrence** in-process par (agent, rôle). 429 honnête +
  `Retry-After`, jamais un drop silencieux.
- Câblé dans `invoke_agent` après les gates auth/plane/binding, avant l'invoke.
- Réglages : `rate_limit_invoke = "12/minute"`, `invoke_max_concurrent = 4` (APISettings).
- Tests : 4 (route 429 bout-en-bout avec Retry-After ; unit débit-par-subject ; unit plafond
  de concurrence ; unit désactivé=no-op) + fixture de reset du singleton. **9 passed** au total.
- **Question ouverte 0019 résolue** (rature + note, style des précédentes) : `docs/decisions/
  0019-invocation-binding.md §Open questions`.

Note : « par rôle » = la **surface operator** (`cockpit-embedded` / `dedicated-ui`), la
granularité de palier de rôle que le handler a sous la main (le rôle exact vit dans
l'assertion). In-process par défaut (le compteur de concurrence n'est pas partagé cross-
instance — un limiteur distribué exigerait Redis, hors périmètre, documenté à la source).

### Lot 2.2 — Sauvegarde du ledger + drill de restauration (P1.2)
Branche `claude/lot-2-2-ledger-backup`. **L'item le plus embarrassant de l'audit** : le
registre opposable n'avait AUCUNE sauvegarde planifiée (seul le gel d'incident existait).

**Fait — et prouvé sur les vraies données (23 122 lignes)** :
- `make ledger-backup` : `pg_dump` **data-only** horodaté + **SHA-256 loggé** (sidecar
  `.sha256`) de `<schema>.audit_ledger` → `backups/ledger/` (gitignoré). Data-only assumé :
  la table + le trigger append-only + le fork guard sont du **code** (recréés par
  `ensure_audit_ledger_schema`) ; la DATA de la chaîne est l'irremplaçable.
- `make ledger-restore-drill` (`scripts/ledger_restore_drill.py`) : restaure le dernier
  backup dans une base **JETABLE**, recrée **la seule table** (pas le fork guard — voir
  ci-dessous), rejoue le dump, vérifie **tree-aware** (`verify_ledger_tree`), puis DROP la
  jetable (`WITH (FORCE)`, même en échec). Le drill **PROUVE que la sauvegarde sert** —
  résultat mesuré : `restored 23122 rows · content_integrity=True · forks=29 · orphans=1 ·
  length=23122 → ✓ DRILL PASSED`. Sonde SHA-256 at-rest OK.
- Doc rétention + planification (cron/launchd = geste opérateur) : `docs/runbook.md §Audit
  log`. Rien ne touche le ledger vivant (backup = lecture ; drill = base jetable).

**Deux pièges résolus (consignés pour la mémoire)** :
1. **Import circulaire** guard↔agent quand `ledger_store` est le premier import tessera d'un
   script standalone → pré-chargement `import tessera.agent.state` (comme le conftest).
2. **Le fork guard rejetait la restauration** : `ensure_audit_ledger_schema` installe un
   `UNIQUE(prev_hash)` ancré à 0 sur la table vide, qui **rejette les 29 forks historiques**
   grandfathered (le store les tolère car ancrés sous le high-water mark). Le drill recrée
   donc **seulement la table** — `verify_ledger_tree` *rapporte* les forks sans les interdire,
   ce qui est le contrat correct de vérification.
