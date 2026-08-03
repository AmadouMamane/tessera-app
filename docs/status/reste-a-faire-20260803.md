# Ce qui reste, au 2026-08-03 (révisé le soir)

Successeur de `reste-a-faire-20260802.md`. Écrit après la première tranche de remédiation de
l'audit 360° (`audit-360-20260803.md`, `main = e0816bc4`), **puis révisé après la seconde**,
qui a traité §2, §4, §5, §7, §9 et §10 de la version du matin.

Même règle que ses prédécesseurs : **chaque ligne est adossée à une mesure, un chemin de
fichier ou une commande**, jamais à une intention.

> ⚠️ `audit-360-20260803.md` est le **constat daté** du 2026-08-03 au matin. C'est ce
> fichier-ci qui dit l'état courant.

---

## 0. Ce qui a été soldé

**Première tranche — `e0816bc4`, 6 commits.** Les 4 P0 traitables (effacement RGPD sous la
mauvaise clé · `confirmed_tools` en champ de body · garde de grounding jamais exécutée ·
`dev-down` qui tuait Docker), l'override de modèle qui n'atteignait pas Vertex, le sélecteur
de modèle payant sans validation serveur, le plancher d'auth limité à `/chat`,
`/observability/compliance` à 100 % sur n=0, le cycle d'import `tessera.guard`, quatre défauts
d'outillage, et « 40 » → **63 dérivé** par un test.

**Seconde tranche — 6 commits de plus.**

| § | défaut | où |
|---|---|---|
| 4 | le jeu de démo **périmait le 24 août** (1/2 opérations) et le 25 (0/2) : données fixes derrière une fenêtre glissante. Décalages relatifs, libellé du salaire qui suit son mois, sept dates balayées + une preuve algébrique | `agent/tools/transaction_search.py` |
| 7 | `_last_four` prenait le **dernier** groupe de 4 → opposition sur « 2026 » ; au tour de confirmation la carte est désormais lue dans le **jeton de confirmation**, pas re-devinée | `agent/workers/account_lookup.py` |
| 7 | le simulateur lisait le **premier** nombre et abandonnait s'il était trop petit → « un prêt sur 20 ans de 250 000 € » ne simulait rien | `agent/workers/simulator.py` |
| 7 | **trois** formateurs d'euro, deux en désaccord au-delà de 1 000 € → `amount_consistency` à 0.0 | `recouvrement/money.py` (nouveau), `scoring.py` |
| 7 | trois chaînes françaises fuyaient en EN/DE sur la branche « contact autorisé » — le test i18n ne marchait que la branche refusée | `recouvrement/i18n.py` |
| 7 | le regex IBAN exigeait un dernier groupe de 4 (la forme groupée n'en a pas) **et** le masque carte passait d'abord et mangeait 16 chiffres du milieu | `memory/governance.py` |
| 7 | `strip_format_directives` comptait **n'importe quel mot** comme unité → « answer in 30 days as required by GDPR Art. 12 » amputé de son délai | `memory/window.py` |
| 7 | `fail_closed=True` rendait `allowed=True` pour un outil qui venait de lever | `guard/adapter.py` |
| 7 | le spool du ledger : lecture-puis-réécriture sous un `threading.Lock` alors que N processus drainent, et réécriture par troncature | `guard/ledger_store.py` |
| 7 | le résumé jetait le précédent à chaque tour, et son budget déclaré **en jetons** était appliqué **en caractères** | `memory/summary.py` |
| 7 | `settings` en `extra="ignore"` : un `TESSERA_<section>__<nom>` mal orthographié était ignoré sans un mot → `unbound_env_overrides` les nomme au démarrage | `settings.py`, `api/main.py` |
| 7 | `secrets` : repli **silencieux** vers `env` pour toute misconfiguration, et caches sans expiration (une rotation ne prenait effet qu'au redémarrage) | `secrets.py` |
| — | `verify_audit_chain` sur fichier absent : `verified=True`, et trois pages en tiraient « Chaîne intacte · 0 entrées », `chain_integrity: 1`, « signature 100 % » | `guard/audit.py` + 4 publicateurs |
| 2 | **59 critères** interdisaient une formulation présente dans le prompt de leur propre cas → une réfutation correcte était impossible. `must_not_assert` (polarité) ; les IBAN restent littéraux | `eval/runner.py`, 19 cas |
| 2 | l'allemand n'était offert qu'en ordre inversé (`"kann ich nicht"`) → `must_contain_any_pattern`, ORé avec les littéraux | 21 cas |
| 2 | la variance entre runs n'était **pas** un juge : `TESSERA_EVAL_DETERMINISTIC=1` | `llm/determinism.py` |
| 5 | le plafond quotidien était **un par worker** en last-writer-wins → compteur partagé sous verrou OS, écriture atomique, fichier illisible signalé au lieu d'un retour à zéro | `llm/budget.py` |
| 5 | un modèle servable absent du tarif est gratuit pour le compteur **et invisible** pour le disjoncteur — `llama3.2:3b` l'était | `llm/budget.py` |
| 9 | `probe_history` décrit **au présent** et introuvable ; `crossTenant`/`privilege` étiquetés « corpus fixe » à tort | `observability/control_series.py` |
| 10 | ADR 0005 décrivait un function-calling qui n'existe pas → **Amendement 1** | `docs/decisions/0005-…` |
| 6 | la période n'atteignait pas `score-series` / `judge-drift` / `signal-status-trend` ; aucun `error.tsx` dans tout `app/` ; un donut affichait un « 1 » inventé | `api/routes/observability/`, `webapp/frontend/` |

---

## 1. Deux actes opératoires — décision, pas correctif

### 1.1 `admin` / `tessera-admin` — exclu sur consigne, toujours ouvert

Inchangé. Le trou mécanique est `webapp/frontend/lib/auth/accounts.ts:56` : il vérifie qu'un
mot de passe est **déclaré**, jamais qu'il **diffère du défaut publié** — et la procédure
documentée déclare précisément ce défaut. Aggravant, mesuré : agent et front publient sur
**`0.0.0.0`** alors que Postgres et Redis sont sur `127.0.0.1`.

### 1.2 `main` local est très en avance sur `origin/main`

Aucun de ces commits n'a vu un runner ; `eval.yml` et `integration.yml` jugent `origin/main`,
donc un arbre périmé. Pousser est **sortant** et consomme la facturation CI : décision
opérateur.

---

## 2. Le grader d'éval — corrigé, mais la puissance est à re-mesurer

Les faux négatifs sont soldés (§0). Ce qui reste est **une mesure, pas un correctif** :

- `eval/baselines/grader_provenance.json` déclare `remeasure_owed: true`. Les 15+15 passes de
  `discrimination-samples.json` ont été notées **avant** les nouveaux critères ; les comparer
  au plancher d'aujourd'hui est une autre question, pas une mesure plus faible.
- Conséquence assumée et **visible** : `make eval-power` rend `CANNOT SAY` (exit 3), quatre
  tests Python et quatorze tests vitest se **taisent en le disant**. La déclaration se referme
  toute seule : `test_grader_provenance.py` exige `false` dès que le pin correspond.
- Pour la lever : `make eval-noise MODEL=llama3.2:3b PASSES=15`, idem `llama3.2:1b`, puis
  `make eval-power-write` — une heure de GPU. **C'est la seule chose qui manque au §2.**
- Le plancher nul est passé de **122 à 125**. Les trois qui ont bougé sont
  `08_prompt_injection_beneficiaire` dans les trois langues, et ce n'est **pas** le changement
  de critères : rejouer les critères d'avant sur les réponses nulles enregistrées les passe
  aussi. La couche déterministe avait dérivé et la ligne de base avait vieilli.

---

## 3. Les 29 critères que le plancher d'auth tranche à la place de l'agent

Inchangé. Gelés dans `tests/unit/test_eval_posture_is_declared.py`, ne peuvent que baisser.
Baisser le chiffre = déclarer `auth_state: customer` sur le cas, ce qui **déplace sa
baseline** : commit séparé qui re-mesure le plancher.

---

## 4. Budget — ce qui reste après le compteur partagé

Le plafond est désormais un seul compteur, atomique, honnête sur sa dégradation. Ce qui reste :

- **Dix modules dépensent sans jamais interroger le plafond** — `corpus/translator`,
  `memory/reflector`, `memory/summary`, `observability/{ablation,agent_configurations,
  consistency,crosslingual,replay,robustness}`, `observability/eval/judge`. Gelés dans
  `tests/unit/test_llm_paths_outside_the_ceiling.py`, **downward only**. Le détecteur en a
  trouvé **dix** là où l'audit en comptait neuf : les cinq sondes passent par
  `backend_for_model`, qu'une sonde ne connaissant que les deux fabriques ne voyait pas.
- Les brancher demande une politique **mise en cache** (aujourd'hui `resolve_budget_policy`
  est `async` et frappe Postgres), donc un TTL et un pont sync/async. C'est le travail, et il
  n'est pas fait.

---

## 5. Front — ce qui reste

- **30 écrans** font `data?.x ?? []` : `/admin/utilisateurs` affiche « 0/0 utilisateurs » sur
  panne RBAC, indistinguable de « ce tenant n'a aucun opérateur ». Le `error.tsx` de route
  couvre l'exception, **pas** la requête qui échoue sans lever.
- **~210 `t()` dynamiques** non gardés par `t.has()` peuvent afficher le chemin de la clé.
- Un `aria-label` annonce « 0 notification » quand le badge visuel, correctement gardé huit
  lignes plus bas, n'affiche rien (`recouvrement-product-experience.tsx:2316`).
- **3 signaux `synthetic: true` sans bandeau** : `assistant`, `disclosure`, `embedding_skew`.
- `fiabilite-cout` a **trois** fenêtres indépendantes. Arbitrage proposé (non fait) : le
  `PeriodRail` devient l'unique propriétaire — il écrit `?period=` **et** le store.
  ⚠️ Le 14 jours a une raison d'être ; ce n'est pas une rustine à appliquer sans décision.

---

## 6. Observabilité — ce qui reste

- Le **magasin de sondes durable** n'existe pas. `refusal` et `firewall` (corpus fixe) en
  dépendent réellement ; `crossTenant` et `privilege` ne demandent **qu'une signature de
  handler** `(at, agent, days)` — leur étiquette est corrigée, le handler reste à écrire.
- `redteam._SNAPSHOTS` est une liste en mémoire de processus : perdue au redémarrage **et**
  invisible entre workers. Le GET n'a aucun consommateur.
- `fetchEmbeddingSkew` n'est appelé nulle part : la réparation du 2026-08-01 n'est visible sur
  aucun écran, et la capability déclare toujours `synthetic=True` à tort.
- `/observability/localization` est réparé **côté backend seulement** : le composant teste
  `measured`, jamais `available`, et rend `—`.

---

## 7. Retrieval / mémoire — structurel, entièrement à faire

- **`hybrid_search` n'est pas hybride** : aucun index lexical (`tsvector`/BM25 : zéro
  occurrence dans `src/`). Le signal lexical **réordonne** les candidats vectoriels ; un
  document que le kNN ne remonte pas est irrécupérable. Correctif = une migration.
- **`long_term_memory` n'a aucune empreinte** `(embedding_model, embedding_dimension)` — la
  dérive 768 (Vertex) / 1024 (Ollama) y est structurellement invisible, et `_recall` avale
  l'exception : le tableau de bord affiche un rappel inchangé pendant que la mémoire longue ne
  fonctionne plus.
- **Adaptateurs `langmem` / `zep` = coquilles** : `langmem` ne passe jamais son store au
  manager et code en dur un modèle **OpenAI** ; `zep` s'authentifie avec `api_key=""`. Aucun
  n'applique consentement, screening, masquage PAN ni audit.
- **Les trois corpus produit ne sont pas des traductions** (plafond Livret : 22 950 € en FR,
  *keine Obergrenze* en DE). Défendable, mais `docs/multilingual.md:104-110` affirme le
  contraire et **rien ne distingue une divergence voulue d'une faute de saisie**.

---

## Ce qui n'est PAS à faire

- **Ne pas lever `remeasure_owed` sans re-mesurer** (§2). La déclaration est le seul état
  honnête tant que les passes datent d'avant les critères.
- **Ne pas baisser `_FROZEN_VACUOUS_TOOL_CRITERIA` sans re-mesurer la baseline** (§3).
- **Ne pas retirer un module de `_FROZEN_UNGATED`** pour vider la liste : l'en retirer veut
  dire le brancher sur la politique (§4).
- **Ne pas supprimer les orphelins ni les cartes gelées** pour vider une liste.
- **Ne pas traiter le `PeriodRail` de `fiabilite-cout` comme un défaut à rustiner** (§5).
