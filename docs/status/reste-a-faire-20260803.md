# Ce qui reste, au 2026-08-03

Successeur de `reste-a-faire-20260802.md`. Écrit **après** la première tranche de remédiation de
l'audit 360° (`audit-360-20260803.md`), qui a atterri dans `main` à `e0816bc4`.

Même règle que ses prédécesseurs : **chaque ligne est adossée à une mesure, un chemin de fichier
ou une commande**, jamais à une intention.

> ⚠️ `audit-360-20260803.md` est le **constat daté** du 2026-08-03 au matin. Il décrit
> l'état d'**avant** cette remédiation, et sa section P0 est en grande partie close. C'est ce
> fichier-ci qui dit l'état courant. Lire l'audit pour le *pourquoi* et le scénario ; lire
> celui-ci pour *ce qui reste*.

---

## 0. Ce qui a été soldé — `main = e0816bc4`, 6 commits, twice-green

Deux passes vertes sur **un** arbre à 188 s d'écart, 2907 tests Python, 675 vitest, 7 nouveaux
témoins dont chacun est rouge contre le code d'avant.

| # | défaut | où |
|---|---|---|
| P0 | l'effacement RGPD effaçait sous `conversation_id` quand l'écriture écrit sous `session.subject_id` — 204, succès **scellé** dans l'append-only, 0 ligne. Le test de fermeture **gravait** le bug | `memory/governance.py`, `api/routes/memory.py` |
| P0 | `confirmed_tools` était un champ de body : carte bloquée sans qu'un humain clique, et le ledger disait le contraire | `api/session.py`, `guard/adapter.py` |
| P0 | la garde de grounding n'a **jamais** tourné en production (`/chat` est SSE, `interrupt_before=[REPORTER]`) ; sortie recouvrement sans garde | `api/routes/chat.py`, `recouvrement_assistant.py` |
| P0 | `make dev-down` tuait Docker — donc le tunnel public | `Makefile` |
| P1 | l'override de modèle gouverné n'atteignait jamais Vertex (double coût, lignée fausse) | `llm/frontier.py`, `llm/router.py` |
| P1 | `POST /chat` acceptait n'importe quel modèle payant ; le verrou vivait dans le BFF Next | `api/routes/chat.py` |
| P1 | le plancher d'auth et `max_calls_per_turn` ne couvraient que `/chat` | `guard/audit.py:turn_context` |
| P1 | `/observability/compliance` : 100 % sur n=0, sonde qui tombe = score qui **monte**, chaîne d'audit affirmée par des littéraux | `observability/compliance.py` |
| — | `import tessera.guard` levait `ImportError` en process neuf | `guard/adapter.py` |
| — | `land` fusionnait la branche courante · `gate-twice` certifiait une seule passe · `deploy-diff` appelait divergence un angle mort · `seed-fixture` tronquait un fixture tracké · 18 cibles hors `.PHONY` | `Makefile`, `scripts/` |
| — | « 40 » cas dans 5 fichiers → **63 dérivé** par un test | `CLAUDE.md`, `AGENTS.md`, `SECURITY.md`, … |

---

## 1. Deux actes opératoires — décision, pas correctif

### 1.1 `admin` / `tessera-admin` — exclu sur consigne, toujours ouvert

Inchangé depuis le 2026-08-01. Le trou mécanique est `webapp/frontend/lib/auth/accounts.ts:56` :
il vérifie qu'un mot de passe est **déclaré**, jamais qu'il **diffère du défaut publié** — et la
procédure documentée (`cp frontend.secret.env.example frontend.secret.env`) déclare précisément
ce défaut. Aggravant, mesuré : agent et front publient sur **`0.0.0.0`** (`docker-compose.yml:111`
et `:150`) alors que Postgres et Redis sont sur `127.0.0.1` ; le cliquet loopback existe mais est
scopé aux **images de datastore**.

### 1.2 `main` local est très en avance sur `origin/main`

```
origin/main = c2f297c0   ·   local = e0816bc4   ·   dernier fetch : 2026-07-28
```

Aucun de ces commits n'a vu un runner ; `eval.yml` et `integration.yml` (schedule) jugent
`origin/main`, donc un arbre périmé — ce qui explique l'Eval nocturne rouge six nuits d'affilée.
Pousser est **sortant** et consomme la facturation CI : décision opérateur.

⚠️ Corollaire à ne pas oublier : « CI is billing-blocked », écrit à quatre endroits
(`Makefile`, `CLAUDE.md`, `ci.yml`, `supply-chain.yml`), n'est **plus** le fait dominant — les
runs *schedule* s'exécutent depuis au moins le 2026-08-01. L'écart au distant l'est.

---

## 2. Le grader d'éval rend des faux négatifs — c'est lui qui bloque la release

`eval/runner.py:96-98` compare la chaîne interdite au texte brut, sans notion de polarité.
**83 paires (cas, langue, critère)** ont un `must_not_contain` littéralement présent dans le
prompt de leur propre cas ; ~18 sont légitimes (echo de PII), **~65 rendent une réfutation
correcte impossible** :

> « …**je ne peux pas confirmer** si nous avons une politique de remboursement rétroactif
> automatique sur 12 mois » → **ÉCHEC**, parce que la phrase interdite est celle que le prompt
> a posée.

Les deux régressions Rule 1 courantes sont de celles-là. Remède : un critère de **polarité**
(`must_not_assert`, échec seulement si la revendication est présente **et** non niée), jamais un
juge LLM.

Second foyer : `must_contain_any` allemand exige `"kann ich nicht"` (ordre inversé) quand le
modèle produit la V2 normale `"ich kann … nicht"`. `11_prompt_injection_base64|de` et
`53_citation_fabrication_court_case|de` échouent dans **13 rapports sur 13**, et
`08_prompt_injection_beneficiaire|de` en est **contaminé** dans la baseline de puissance.

⚠️ **La variance entre deux runs ne vient PAS d'un juge.** Le grader du catalogue est 100 %
déterministe ; l'agent est échantillonné à `temperature=0.2` **sans seed**
(`llm/local.py`, `frontier.py`). Remède : un mode `TESSERA_EVAL_DETERMINISTIC=1`.

---

## 3. Les 29 critères que le plancher d'auth tranche à la place de l'agent

Gelés dans `tests/unit/test_eval_posture_is_declared.py` (`_FROZEN_VACUOUS_TOOL_CRITERIA = 29`),
ne peuvent que **baisser**. Sous la posture `anonymous` — celle que le harnais mesure, désormais
déclarée et estampillée dans le rapport — un `must_not_invoke_tools` nommant un outil
authentifié est satisfait par le garde avant que l'agent ait son mot à dire.

Concerne notamment `29_tool_misuse_blocage_sans_auth`, `31_tool_misuse_balance_tiers`,
`54_tool_misuse_block_third_party_card`, `55_tool_misuse_destructive_no_auth` — dont c'est
exactement le sujet. Ils passent, et passeraient contre un agent qui essaierait.

Baisser le chiffre = déclarer `auth_state: customer` sur le cas, ce qui **déplace sa baseline** :
commit séparé qui re-mesure le plancher (`make eval-null-write`, `make eval-power-write`).

---

## 4. Le jeu de démonstration périme le 2026-08-24

`agent/tools/transaction_search.py:80,88` fige deux transactions au **26** et **25 mai 2026** ;
`workers/account_lookup.py:165` construit `since = date.today() - 90 jours` ; le contrat refuse
toute fenêtre plus large (minimisation, `_MAX_LOOKBACK_DAYS = 90`). Données fixes, fenêtre
glissante. Calculé :

| date | opérations visibles |
|---|---|
| 2026-08-23 | 2 / 2 |
| **2026-08-24** | **1 / 2** |
| **2026-08-25** | **0 / 2** |

Symptôme : un message bien formé et faux — « Aucune opération n'a été trouvée sur les 90 derniers
jours » (`account_lookup.py:88`, + DE/EN). Aucune erreur, aucun log, aucune sonde.

⚠️ **L'éval est protégée de ce bug par un autre bug** : `transaction_search` exige
`customer-auth`, et le harnais tourne en `anonymous` (§3). Le jour où quelqu'un corrige la
posture **après le 25 août**, ces cas s'exécuteront contre un jeu vide et échoueront pour une
raison sans rapport avec ce qu'ils mesurent.

Correctif : dates relatives (`datetime.now(UTC) - timedelta(days=3)`) + un test qui gèle la
propriété « le jeu de démo est visible quelle que soit la date ».

---

## 5. Budget — le plafond n'est pas celui qui est annoncé

- `get_budget_tracker()` est `@lru_cache(maxsize=1)` **par process** et `_persist()` réécrit tout
  le fichier depuis la mémoire, sans relecture ni verrou ⇒ avec `api.workers = N` le plafond réel
  est **`N × daily_eur`**, en last-writer-wins. ADR 0034 dit « one org-wide daily breaker ».
- Écriture non atomique (`write_text`, `budget.py:186-203`) ; `_load()` avale un JSON tronqué et
  **repart de zéro** — fail-open silencieux sur un disjoncteur de coût. `fsutil.atomic_write_text`
  existe et n'est pas utilisé.
- Un modèle servable absent de `_PRICES` est **gratuit pour le compteur et invisible pour le
  disjoncteur** (`model_is_paid` → `False`). Témoin manquant : « tout modèle servable est tarifé ».
- Neuf autres chemins LLM (`ablation`, `consistency`, `crosslingual`, `robustness`, `replay`,
  `judge`, `reflector`, `summary`, `translator`) consomment le compteur sans jamais être gatés.

---

## 6. Front — la période, et les faux zéros

- **La période n'atteint pas** `score-series`, `judge-drift`, `signal-status-trend` :
  `lib/api/client.ts` ne construit **jamais** de paramètre `days` pour ces trois-là, et les sept
  `queryKey` concernées n'incluent pas `period`. L'opérateur choisit « 30 jours », les vignettes
  mesurent 7. (Le bug « 8 tranches » est résolu pour `control-series`, pas pour ceux-ci.)
- **`fiabilite-cout` a trois fenêtres indépendantes**, pas deux : le ruban SLO lit le store
  Zustand (d7, non contrôlable ici), la table par agent lit `?period=` (d7), le corps un
  `useState` local piloté par `PeriodRail` (**14 j**). Arbitrage proposé : faire du `PeriodRail`
  l'unique propriétaire (il écrit `?period=` **et** le store), ce qui préserve l'ancrage.
- **13 écrans** destructurent `useQuery` sans `isError` puis rendent `…` : sur panne backend
  l'opérateur voit une ellipse muette. **Aucun `error.tsx` dans tout `app/`.**
- **30 écrans** font `data?.x ?? []` : `/admin/utilisateurs` affiche « 0/0 utilisateurs » sur
  panne RBAC, indistinguable de « ce tenant n'a aucun opérateur ».
- Un `aria-label` annonce « 0 notification » quand le badge visuel, correctement gardé 8 lignes
  plus bas, n'affiche rien · un donut affiche un **« 1 » inventé** (`|| 1` rendu au centre) ·
  ~210 `t()` dynamiques non gardés par `t.has()` peuvent afficher le chemin de la clé i18n.
- **3 signaux déclarés `synthetic: true` n'ont aucun bandeau** : `assistant`, `disclosure`,
  `embedding_skew`.

---

## 7. Bugs métier isolés

| fichier | effet |
|---|---|
| `agent/recouvrement.py:297` vs `recouvrement/scoring.py:87` | deux formateurs d'euro (`'1 260,50 €'` ≠ `'1260,50 €'`) ⇒ le KPI `amount_consistency` tombe à **0.0** dès qu'un dossier dépasse 1 000 € |
| `agent/recouvrement.py:1466-1476` | trois chaînes françaises fuitent en **EN et DE** sur la branche « contact autorisé » ; le test i18n n'exerce que la branche bloquée |
| `agent/workers/simulator.py:29-32` | « un prêt **sur 20 ans** de 250 000 € » ⇒ montant non parsé, aucune mensualité, aucune escalade |
| `agent/workers/account_lookup.py:111` | `_last_four = matches[-1]` : « carte finissant par 1234 volée le 12 juillet **2026** » ⇒ opposition sur « 2026 » ; au tour de confirmation, repli sur `"4242"` |
| `memory/governance.py:97` | le regex IBAN exige un dernier groupe de 4 ⇒ ne matche **jamais** la forme groupée, et `_CARD_RE` passe avant et mange le milieu |
| `memory/window.py:36-56` | `strip_format_directives` mutile « répondre **in 30 days** as required by GDPR Art. 12 » |
| `memory/summary.py:222-239` | le résumé n'est jamais replié (pas d'incrémental) et `token_budget=2000` est appliqué **en caractères** |
| `guard/ledger_store.py:383-402` | le spool est réécrit sans fsync et sous un `threading.Lock` **sans protection inter-process**, alors que chaque worker draine |
| `guard/adapter.py:576` | **`fail_closed=True` avale** l'exception ; `False` la propage. Le nom dit l'inverse de l'effet |
| `guard/audit.py:1189` | `verify_audit_chain` sur fichier absent renvoie `verified=True` — un `Ok` sans preuve là où la réponse est `CannotSay` |
| `settings.py` (9 blocs) | `extra="ignore"` partout, y compris racine — ADR 0024 §rule 2 cite nommément ce cas |
| `secrets.py:142-163` | repli **silencieux** vers `env` pour toute misconfiguration ; caches sans TTL ⇒ un secret roté n'est jamais relu |

---

## 8. Retrieval / mémoire — structurel

- **`hybrid_search` n'est pas hybride** : aucun index lexical (`tsvector`/BM25 : zéro occurrence
  dans `src/`). Le signal lexical **réordonne** les candidats vectoriels ; un document que le kNN
  ne remonte pas est irrécupérable.
- **`long_term_memory` n'a aucune empreinte** `(embedding_model, embedding_dimension)` — la
  dérive 768 (Vertex) / 1024 (Ollama) y est structurellement invisible, et `_recall` avale
  l'exception : le tableau de bord affiche un taux de rappel inchangé pendant que la mémoire
  longue ne fonctionne plus.
- **Adaptateurs `langmem` / `zep` = coquilles** : `langmem` ne passe jamais son store au manager
  (écriture et lecture visent deux stores différents) et code en dur un modèle **OpenAI** ; `zep`
  s'authentifie avec `api_key=""`. Aucun des trois n'applique consentement, screening, masquage
  PAN ni audit.
- **Les trois corpus produit ne sont pas des traductions** (plafond Livret : **22 950 €** en FR,
  **keine Obergrenze** en DE). Défendable, mais `docs/multilingual.md:104-110` affirme le
  contraire et **rien ne distingue une divergence voulue d'une faute de saisie**.

---

## 9. Observabilité — le magasin de sondes, et deux motifs faux

- `control_series.py:255-260` décrit **au présent** un `probe_history` qui n'existe nulle part
  (`grep` ne renvoie que ce commentaire).
- Sur les 5 courbes absentes, **2 seulement** demandent un magasin durable (`refusal`,
  `firewall`, à corpus fixe). `crossTenant` et `privilege` ne demandent **qu'une signature de
  handler** (`at`, `agent`, `days`) : leurs échantillons sont horodatés, leur motif « corpus
  fixe » est **faux**. `inversion` est une fixture, pas un corpus fixe.
- `redteam._SNAPSHOTS` est une liste en mémoire de processus : perdue au redémarrage **et**
  invisible entre workers. Le GET n'a de toute façon aucun consommateur, et le panneau
  « Red team » du cockpit affiche en réalité de l'efficacité pare-feu.
- `fetchEmbeddingSkew` n'est appelé nulle part : la réparation du 2026-08-01 n'est visible sur
  aucun écran, et la capability déclare toujours `synthetic=True` à tort.
- `/observability/localization` est réparé **côté backend seulement** : le composant teste
  `measured`, jamais `available`, et rend `—`.

---

## 10. ADR 0005 — trancher

Aucun `bind_tools`, `tool_choice`, `ToolNode` ni `tools=` dans tout `src/`. La séparation
physique outils/workers tient ; sa **justification** est fictive, et elle est répétée dans
l'ADR, dans trois docstrings et dans `CLAUDE.md`. Deux issues honnêtes : brancher le
function-calling (les 5 schémas Pydantic sont déjà des contrats stables, `guarded_invoke`
s'applique tel quel), ou amender l'ADR pour dire que les outils sont des *cibles d'action
typées* invoquées par les workers.

---

## Ce qui n'est PAS à faire

- **Ne pas « réparer » le gate d'éval pour reverdir la release** — les régressions sont des faux
  négatifs du grader (§2) ; le correctif est dans les critères.
- **Ne pas baisser `_FROZEN_VACUOUS_TOOL_CRITERIA` sans re-mesurer la baseline** (§3).
- **Ne pas supprimer les orphelins ni les cartes gelées** pour vider une liste.
- **Ne pas traiter le `PeriodRail` de `fiabilite-cout` comme un défaut à rustiner** : c'est une
  décision de design, et le 14 jours a une raison d'être.
