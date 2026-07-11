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

| Fenêtre | Lot | Sujet | Verdict | Hash |
|---|---|---|---|---|
| — | 0 | Journal + état de base | ✅ | 5ddd5215 |
| 1 | 1.1 | Tests d'intégration (job CI + tri) | ✅ | ff→main |
| 1 | 1.2 | 49 `except … pass/continue` | ✅ | ff→main |
| 1 | 1.3 | 7 SQL f-string + coverage informatif | ⏳ | — |
| 1 | 1.4 | Trio recouvrement + kicker credit-aurore | ⏳ | — |
| 2 | 2.1 | Rate-limit `/agents/{id}/invoke` | ⏳ | — |
| 2 | 2.2 | Sauvegarde ledger + drill restauration | ⏳ | — |
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
