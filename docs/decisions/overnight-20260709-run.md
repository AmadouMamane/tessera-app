# Overnight run — 2026-07-09 → 2026-07-10

Operating journal for the autonomous night run. One entry per lot: scope, commits, **real**
gate output, self-review, verdict (merged / parked / skipped + reason).

Rules in force (from the mission brief):

- Twice-green per lot — `ruff check` + `ruff format --check` + `mypy` + `pytest -m "not integration"`
  and `tsc --noEmit` + `biome check` + `vitest run`, two complete passes. Red twice ⇒ the lot is
  **parked** on its branch, recorded here, and the night moves on. We never merge red and we never
  weaken a gate to make it pass.
- One lot = one branch = one merge into `main`, then `git push origin main`. Targeted staging only,
  never `git add -A`, never history rewriting.
- The single writer of `0017-execution-status.md` is the supervised Claude session. This journal
  does not write there; it only *commits* ledger entries authored elsewhere, verbatim.
- Design contradiction (the ADR says A, the code demands B): do not arbitrate — park, record, continue.
- Reference servers `:3097` / `:8099` stay untouched all night. Previews run from the agent worktree
  on a free port and are torn down. `lsof +D` before any worktree mutation.

---

## RÉSUMÉ MATIN

**Ouverture :** `origin/main` = `main` = `29fdefbc`.
**Clôture :** `origin/main` = `main` = `27f7cd3f`, 0 ahead / 0 behind. Tout est poussé.
**Serveurs de référence relancés sur le main final** : front `:3097`, back `:8099`, tous deux `ok`.
Aucun rouge n'a été mergé. Aucun gate n'a été affaibli.

### Verdicts

| Lot | Sujet | Verdict |
| --- | --- | --- |
| 0 | Pré-vol + merges feu vert | ✅ **mergé** `e4eedcde` |
| 1 | Brancher la preuve (Prometheus) | ✅ **mergé** `06bbd54a` |
| 2 | I5 — `synthetic` traverse le fil | ✅ **mergé** `10183972` |
| 3 | I6 — duplex-agent | ✅ **mergé** `84c79dfc` |
| 4 | FE snapshot client | ✅ **mergé** `48e8e435` |
| 5 | e2e smoke Playwright | ⚠️ **mergé, PARTIEL** `69860a66` |
| 6 | Reliquat headers — menu grille d'apps | 🅿️ **parké** — rien commencé |
| 7 | Craft pass P3 | 🅿️ **parké** — la punch list 18-23 n'existe nulle part |
| 8 | Stretch | ⏭️ **sauté** — conditionné à 6 et 7 |

### Les trois choses qui comptent

1. **ADR 0019 Amendment 1 est implémenté (I5 + I6).** L'audit exigé par I5 a trouvé un trou plus
   grand que l'amendement : la Console *in-process* du cockpit atteint l'agent par le **même
   `POST /chat`** qu'un client et **n'était pas estampillée du tout**. Un opérateur qui *testait* un
   agent déplaçait les mêmes compteurs métier qu'un vrai client. Corrigé, avec le discriminant qui
   évite l'erreur inverse (`dedicated-ui` = la console **métier** de recouvrement, dont les
   événements sont du vrai travail et doivent compter). Les deux mutants sont vérifiés rouges.

2. **La preuve est branchée, et elle est honnête.** Les rungs calculés reviennent de faits Prometheus
   **vivants**. Deux badges coexistent sur la flotte ce matin — c'est voulu, et c'est assertable :

   | agent | badge | calculé | déclaré | preuve |
   | --- | --- | --- | --- | --- |
   | support-client | **calculé** | L2 | L2 | `observed` |
   | onboarding | **calculé** | L2 | L2 | `observed` |
   | recouvrement | déclaré | L0 | L2 | `dormant` |
   | hello-agent | déclaré | L0 | L1 | `dormant` |
   | turn-agent | déclaré | L0 | L1 | `dormant` |
   | duplex-agent | déclaré | L0 | L1 | `dormant` |

3. **Deux défauts réels trouvés en chemin, corrigés à la racine, pas contournés.**
   - La suite unitaire héritait de ton `.env.local` (ton `CANARY_SCHEDULER_ENABLED=1` faisait tomber
     un test qui affirmait « le défaut livré est OFF »). Sept autres variables étaient héritables.
     La suite résout désormais les réglages **exactement comme la CI**, avec un cliquet.
   - `agent_console.py` a cassé le cliquet de frontière ADR 0017 §1. Réparé **par le seam registre**,
     jamais en ajoutant une exception gelée.

### Chiffres

- **Tests** : backend 1523 → **1564** (+41). vitest 103 → **126** (+23). Playwright : **7 nouveaux, 7 verts**.
- **Requêtes par page** (mesurées, navigateur authentifié, stack réelle) :
  Flotte 4→4 · fiche agent 6→6 (aucune des deux ne rafalait : rendu serveur) ·
  **Vue d'ensemble 58 req / 26 endpoints → 44 / 19**. Côté backend, 7 signaux = **2 lectures amont**
  au lieu de 7 appels de route. *(Le ×2 est du React StrictMode en dev, pas de la prod.)*
- **Critères ADR 0019 §A1.2** : (a) `computed L0 → L1` **causé par l'invocation** ✓ ·
  (b) 0 ligne / 0 série dans les métriques métier ✓ **mais** voir la nuance ci-dessous ·
  (c) `git show --stat <witness> -- webapp/frontend` → **vide** ✓ ·
  (d) `hello_agent.py` / `turn_agent.py` **sha256 inchangés** ✓

### Ce que je NE revendique pas

- **Critère (b) est vrai pour une raison plus faible qu'il n'y paraît.** `include_synthetic=True`
  renvoie **aussi** zéro : rien n'ingère les `businessEvents` qu'un agent `http` renvoie. Donc c'est
  **l'absence de chemin d'ingestion** qui protège les métriques, pas le filtre §4. Le filtre, la
  garde à l'émission et l'estampille de l'agent sont corrects et testés, mais ne font pas encore le
  travail. → *Owed follow-up* dans `0019-execution-status.md`.
- **Un canary `in_process_chat` ne produit aucune preuve de tour** (le compteur vit sur le chemin
  *servi* ; l'invoker appelle le graphe directement). Non corrigé : déplacer le compteur ferait
  compter les runs du harnais d'eval comme preuve — pire mensonge. **Appel de l'architecte.**
- **Le docstring de `turn_evidence.py` sous-estime la récence** : un vecteur instantané a un horizon
  de péremption Prometheus (~5 min). « Dormant » veut donc dire « pas de tour observé depuis ~5 min »,
  pas « depuis la rétention ». La garde du lot B (interdire « récent » dans le libellé) avait raison ;
  le docstring, lui, est à corriger dans le lot fraîcheur.
- **La suite e2e existante est ROUGE sur `main`** (`console.spec.ts` : 2/3), **préexistant**. Donc le
  smoke n'entre dans le gate que **fichier par fichier**, pas via `pnpm test:e2e`.

### Attend Amadou

**Validations visuelles**
- La chip « **Témoin plateforme** » sur les trois cartes témoins.
- Le badge **déclaré vs calculé** (les deux sont à l'écran : `/fr/agents`).
- Le **formulaire généré** de duplex : `/fr/agents/duplex-agent/console` — libellés, `select` pour
  l'`enum`, case à cocher pour le booléen. Aucune ligne de `webapp/frontend/` ne les nomme.
- P3 : **non fait** (voir lot 7).

**Moments opérateur**
- **Canary scheduler** : `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED=1` est actif dans ton
  `.env.local` et pilote le serveur — il ne pilote **plus** la suite de tests. Sache qu'il ne fera
  **pas** monter le niveau calculé de recouvrement (voir ci-dessus).
- **TSA rfc3161** : toujours `NoOp` par défaut, inchangé cette nuit.
- **Protection de branche GitHub** : **toujours pas confirmée**. `origin/main` accepte un push direct
  — c'est ainsi que la nuit a pu lander.
- **Pour revoir duplex en `computed`** : `uv run python examples/duplex-agent/duplex_agent.py`, puis
  invoque-le depuis sa Console. Je l'ai démonté en fin de nuit (protocole), donc sa preuve s'est périmée.

### Décisions que je n'ai PAS prises

Rien n'a été tranché à ta place. Deux contradictions potentielles ont été **résolues par la lecture
du code**, pas par arbitrage : le `label_key` du témoin réutilise une clé i18n existante (donc (c)
tient sans plier), et la codegen d'enums est câblée sur `recouvrement` seul (donc aucune sortie
frontend). Une seule vraie asymétrie de design est **remontée, non tranchée** : canary in-process vs
http face à la preuve de tour.

### État des arbres

- `main` = `origin/main` = `27f7cd3f`, propre (hors captures `docs/ui-reference/` non suivies,
  déposées par toi, laissées telles quelles).
- Worktree `agents/claude` : **propre**, sur `claude/e2e-smoke-0019` (mergée). À resynchroniser sur
  `main` avant la prochaine tranche.
- Aucun preview, aucun agent d'exemple, aucun `next dev` résiduel (`lsof` vérifié : `:3096`, `:8096`,
  `:3390`, `:8500`, `:8501`, `:9096` tous libres).
- Stack d'observabilité Docker : **debout** (collector, Prometheus `:19090`, Grafana, Phoenix…).

---

## LOT 0 — Pré-vol + merges feu vert

### (a) État d'`origin/main` au démarrage

```
$ git fetch --all --prune
$ git rev-list --left-right --count main...origin/main
0	0
$ git log --oneline -1 origin/main
29fdefbc docs(adr): 0019 Amendment 1 — synthetic crosses the wire + duplex-agent integration witness
```

`main` et `origin/main` sont identiques à `29fdefbc`. Rien à rattraper.

Pré-vol processus (avant toute mutation d'arbre) :

```
$ make dev-status
  frontend :3097  pid 24080   git 29fdefbc  ok
  backend  :8099  pid 24061   git 29fdefbc  ok
$ lsof +D agents/claude   → seulement le shell de l'agent
$ lsof +D agents/codex    → node_repl (cwd), aucun serveur
$ lsof +D agents/antigravity → rien
$ docker ps  → tessera-claude-{collector,prometheus,grafana,phoenix,clickhouse,…} Up 3 hours
```

Les serveurs de référence servent bien `main`. La stack d'observabilité dev tourne déjà : c'est
l'entrée du lot 1.

### (b) Landing pad — docs en attente

Deux fichiers modifiés non commités dans `tessera/`, aucun code :

1. `docs/decisions/0019-invocation-binding.md` — **écart consigné** : l'Amendement 1 (0019 §A1 +
   cross-ref 0018 lignes 71-74) était **déjà commité** en `29fdefbc`. Le diff restant n'est pas
   l'amendement mais un raffinement de son critère d'acceptation (c) : le renderer schema→formulaire
   est du **capital plateforme**, le critère mesure le coût **marginal** de l'arrivée du témoin. Le
   message de commit prescrit par la mission aurait dupliqué `29fdefbc` ; j'ai écrit un message qui
   décrit le diff réel.
   → `0d340fde docs(adr): 0019 Amendment 1 — criterion (c) is marginal, the renderer is platform capital`
2. `docs/decisions/0017-execution-status.md` — entrée ledger de la revue fleet-legibility. Commitée
   **verbatim**, contenu non modifié (writer unique).
   → `b769859e docs(adr): 0017 ledger — fleet-legibility + level-honesty review APPROVED (merge feu vert)`

Laissés **non suivis**, intentionnellement (staging ciblé, pas de `git add -A`) :
`docs/ui-reference/header/`, `docs/ui-reference/produit/recouvrement/*.html` + `_files/`. Ce sont des
captures de référence déposées par l'opérateur ; leur intégration relève des lots 6/7 et d'une
décision qui n'est pas la mienne cette nuit.

### (c) Feu vert — merge de `claude/fleet-agent-legibility`

Deux commits en avance sur `main` (`b3d70b36` lot A, `b7ef1003` lot B), 18 fichiers,
+784/−69. Merge `--no-ff` **sans conflit** → `4331b4f2`.

Portée actée, sans radoucissement : la preuve de tour n'étant pas branchée, les cinq agents
résolvent `unverifiable` et les cinq cartes affichent le badge atténué « L{n} déclaré · aucune
preuve ». C'est la lecture honnête voulue. Le lot 1 branche la preuve.

### (c-bis) Un rouge au gate — diagnostiqué, pas contourné

La passe 1 du gate a sorti **1 échec** :

```
FAILED tests/unit/test_canary.py::test_posture_idle_by_default - assert True is False
  posture = {'enabled': True, 'scheduled': [{'agent_id': 'recouvrement', 'cadence_s': 3600}], 'scheduling': True}
```

**Ce n'est pas une régression du merge.** Preuves recueillies avant de toucher quoi que ce soit :

1. `git diff --stat b769859e HEAD -- tests/unit/test_canary.py src/tessera/agent/canary.py src/tessera/settings.py` → **vide** : le merge ne touche aucun de ces trois fichiers.
2. Le même test, rejoué sur l'arbre pré-merge dans un worktree temporaire (`/private/tmp/.../premerge`, donc **sans** `.env.local`) : `13 passed`.
3. Cause réelle : `Settings` déclare `env_file=(".env", ".env.local")`. Le `.env.local` de l'opérateur (gitignoré, absent en CI) contient
   `TESSERA_OBSERVABILITY__CANARY_SCHEDULER_ENABLED=1` — exactement le geste *go-and-observe* pour lequel le drapeau existe. `canary_posture()` appelle `get_settings()`, donc le test qui affirme « le défaut livré est OFF » affirmait en réalité « la machine de l'opérateur est OFF ».

**Classe de défaut, pas cas isolé.** Croisement des variables de `.env.local` avec celles neutralisées
par `tests/conftest.py::_isolated_env` : `TESSERA_MEMORY__BACKEND`, `TESSERA_API__{CORS_ORIGINS,PORT,
RATE_LIMIT_CHAT,RATE_LIMIT_CHAT_GLOBAL,OPERATOR_ASSERTION_SIGNING_KEY}` et
`TESSERA_OBSERVABILITY__OTEL_ENDPOINT` étaient tous héritables eux aussi — et
`tests/unit/test_pan_input_seams.py` portait déjà un contournement écrit à la main pour l'un d'eux.
Le sens de la fuite le plus dangereux n'est pas celui qu'on a vu : un override local **périmé** peut
faire passer au vert une suite rouge.

**Correction (branche `claude/canary-test-hermeticity`, pas dans le landing pad).** `_isolated_env`
coupe `env_file` pour la durée de la suite : en local, les réglages se résolvent **exactement** comme
en CI, et tout non-défaut dont la suite dépend est épinglé dans la fixture, à découvert. Les vraies
variables d'environnement continuent de gagner (c'est ainsi que la fixture et les déploiements
configurent Tessera). `tests/unit/test_settings_hermeticity.py` est le cliquet (3 tests : le fichier
reste coupé ; le défaut livré survit à l'override opérateur ; l'env override toujours).

C'est un **renforcement** du gate, jamais un affaiblissement : l'assertion « le défaut est OFF » est
intacte, elle porte désormais sur ce qu'elle prétendait porter. → `b472d6b8`, mergé en `e4eedcde`.

### Gates — sortie réelle sur l'arbre fusionné (`e4eedcde`), deux passes

```
═══════════ BACKEND PASS 1 ═══════════        ═══════════ BACKEND PASS 2 ═══════════
All checks passed!                            All checks passed!
542 files already formatted                   542 files already formatted
Success: no issues found in 280 source files  Success: no issues found in 280 source files
1523 passed, 50 deselected in 10.93s          1523 passed, 50 deselected in 10.71s

═══════════ FRONTEND PASS 1 ═══════════       ═══════════ FRONTEND PASS 2 ═══════════
tsc --noEmit  → ok                            tsc --noEmit  → ok
biome check   → 329 files, 27 warnings,       biome check   → 329 files, 27 warnings,
                exit 0                                        exit 0
vitest run    → 12 files, 103 tests passed    vitest run    → 12 files, 103 tests passed
```

Les 27 avertissements Biome préexistent et ne bloquent pas (`exit 0`) ; aucun n'est introduit par
les deux merges.

### Auto-revue

- Le merge feu vert est passé **tel quel**, aucune ligne de son code retouchée.
- Le seul rouge rencontré a été instruit avant d'être corrigé : j'ai d'abord **prouvé** qu'il
  préexistait (worktree pré-merge propre), au lieu de supposer.
- **Erreur commise et corrigée** : le premier `Edit` de `conftest.py` a atterri dans le checkout
  principal (landing pad = zéro code). Restauré par `git checkout --` avant tout commit ; la
  correction a été refaite dans le worktree agent, sur sa propre branche. Aucun code n'a été commité
  depuis `tessera/`.
- Tentation écartée : épingler la seule variable canary (2 lignes, dans l'idiome existant) aurait
  laissé les sept autres fuites en place. La correction de fond a été retenue **parce qu'elle était
  mesurable sur-le-champ** — suite complète verte, 1520 → 1523 tests, zéro dégât collatéral.
- Non fait, volontairement : les fichiers non suivis `docs/ui-reference/header/` et
  `docs/ui-reference/produit/recouvrement/*.html` restent non suivis (staging ciblé).

### Verdict

**MERGÉ et poussé.** `29fdefbc..e4eedcde` → `origin/main`. `main` ≡ `origin/main` (0/0).

| Commit | Objet |
| --- | --- |
| `0d340fde` | docs — 0019 Amendment 1, critère (c) marginal |
| `b769859e` | docs — entrée ledger 0017 (verbatim) |
| `d913e9a7` | docs — ouverture de ce journal |
| `4331b4f2` | **merge** `claude/fleet-agent-legibility` |
| `b472d6b8` | test — hermétisation de la suite vis-à-vis de `.env.local` |
| `e4eedcde` | **merge** `claude/canary-test-hermeticity` |

**Pour Amadou (validation visuelle demain) :** la chip « Témoin plateforme » sur les cartes de flotte,
et le badge atténué « L{n} déclaré · aucune preuve » — qui doit basculer en badge *calculé* sur
support-client / onboarding une fois le lot 1 en place.

**Conséquence opérateur immédiate :** ton `.env.local` garde `CANARY_SCHEDULER_ENABLED=1` ; il pilote
toujours le serveur, il ne pilote plus la suite de tests.


---

## LOT 1 — Brancher la preuve (platform-completion/config)

Branche `claude/evidence-path-config`, coupée de `origin/main` (`50a8504c`).

### Ce que le code dit vraiment (lu, pas déduit d'un nom)

- `observability/turn_evidence.py` lit `TESSERA_LEVEL_TURN_EVIDENCE` via **`os.environ` direct**,
  pas via `Settings` pydantic. Le drapeau n'a donc **aucun** préfixe `TESSERA_<section>__`. Déduire
  le mécanisme du nom aurait été faux : ce qui l'amène au processus, c'est
  `scripts/run_local.py::_load_process_env`, qui exporte `.env.local` dans `os.environ`
  (`setdefault` — une vraie variable d'env gagne).
- La requête est `sum by (agent_id) (tessera_agent_turns_total)`, **vecteur instantané**, via
  `PrometheusAdapter` → `TESSERA_PROMETHEUS_URL`, défaut `http://localhost:19090`.
- Ni l'un ni l'autre n'était documenté nulle part (`grep` sur tout le dépôt : uniquement le défaut
  en dur dans le code et une mention dans un test). → les deux sont désormais dans `.env.example`.

### Pourquoi la preuve était vide alors que la métrique existait

`tessera_agent_turns_total` **existait** dans Prometheus (série
`{agent_id="support-client", job="tessera-agent"}`), mais la requête instantanée renvoyait `[]`.
Cause réelle, vérifiée : un compteur Prometheus **étiqueté** n'existe qu'une fois incrémenté. Le
backend avait redémarré à 21:04 ; le dernier échantillon datait de 20:17. Cible de scrape saine
(`up{job="tessera-agent"} = 1`), exporteur bien à l'écoute sur `:9090` — simplement, **aucun tour
n'avait été servi depuis le redémarrage**. Brancher la preuve n'est donc pas « lever un drapeau » :
il faut de vrais tours.

### Action de configuration (machine, pas dépôt)

`TESSERA_LEVEL_TURN_EVIDENCE=1` ajouté au `.env.local` (gitignoré, jamais commité, secrets jamais
lus ni affichés), puis `make dev-down && make dev-up` **depuis le checkout principal** — les serveurs
de référence continuent de servir `main`, jamais un worktree d'agent. Lecture de la consigne :
« référence intouchée » = jamais servie depuis un worktree d'agent ; le lot 1 prescrit explicitement
`make dev-up`, et la FIN DE NUIT le refait. Santé revérifiée après relance.

### Mesure — les trois états, tous constatés sur l'API vivante `GET /observability/fleet`

```
(1) drapeau ÉTEINT, code d'avant le merge        (2) drapeau ALLUMÉ, zéro tour servi
    level=L2 …  (aucun champ de preuve)              agent           level  declared  evidence
                                                     support-client  L0     L2        dormant
                                                     onboarding      L0     L2        dormant
                                                     recouvrement    L0     L2        dormant
                                                     hello-agent     L0     L1        dormant
                                                     turn-agent      L0     L1        dormant
```

`dormant` (et non `unverifiable`) est déjà la preuve que la lecture **a lieu** : Prometheus a été
joint et a répondu l'ensemble vide.

Deux vrais tours pilotés contre la stack vivante (`POST :8099/chat`, graphe réel + Ollama
`llama3.2:3b`) : un message neutre → `support-client` (5,5 s, 68 jetons) ; « ouvrir un nouveau
compte … pièces justificatives » → handoff `onboarding` (2,8 s, 52 jetons). Exporteur `:9090` :

```
tessera_agent_turns_total{agent_id="support-client",language="fr",outcome="complete"} 1.0
tessera_agent_turns_total{agent_id="onboarding",language="fr",outcome="complete"} 1.0
```

Après un scrape (15 s), la requête **exacte** du cockpit renvoie `support-client=1`, `onboarding=1`.

```
(3) APRÈS — GET /observability/fleet
    agent           AVANT (calc/preuve)   APRÈS (calc/preuve)   déclaré
    support-client  L0 / dormant       →  L2 / observed         L2   ⬆
    onboarding      L0 / dormant       →  L2 / observed         L2   ⬆
    recouvrement    L0 / dormant          L0 / dormant          L2
    hello-agent     L0 / dormant          L0 / dormant          L1
    turn-agent      L0 / dormant          L0 / dormant          L1
```

**Critère de sortie atteint** : les rungs calculés reviennent de faits Prometheus **vivants**, et
`turn-agent` reste honnêtement « L1 déclaré · aucune preuve » — c'est I6 qui refermera la boucle.
Effet de bord utile pour le lot 5 : les **deux** variantes de badge (`computed` et `declared`) sont
maintenant simultanément visibles dans le cockpit, donc assertables par le smoke.

### Constat n°1 — un canary activé ne produit AUCUNE preuve de tour

`canary_posture` au boot : `{"enabled": true, "scheduled": [{"agent_id": "recouvrement",
"cadence_s": 3600}], "scheduling": true}`. Pourtant `recouvrement` reste `dormant`, et le restera.

Raison, lue dans le code : `AGENT_TURNS_TOTAL.labels(...).inc()` n'existe **que** dans
`api/routes/chat.py` (chemin **servi**). `InProcessChatInvoker.invoke()` appelle
`compile_graph().ainvoke(initial)` **directement** et court-circuite la route. Un tour de canary
n'incrémente donc jamais le compteur.

**Je ne tranche pas.** Déplacer le compteur dans le graphe ferait compter les exécutions du **harnais
d'eval** (qui invoque `compile_graph()` par le même seam) comme preuve de tour : ce serait un
mensonge pire que le trou. Il y a là une asymétrie réelle entre bindings — un canary `http`
produira de la preuve (l'agent externe émet son propre compteur, cf. I6 critère (a)), un canary
`in_process_chat` n'en produira jamais. Cela touche la sémantique du §4 et le seam du harnais
d'eval. **Consigné, non corrigé, remonté à l'architecte.**

### Constat n°2 — l'ADR 0017 promettait encore `trusted-true`

`0017-agent-observability-contract.md` §Phase-F disait encore « evidence-*unknown* is trusted, never
treated as absence » — exactement le comportement que le lot B a supprimé et que la revue a ratifié
comme sur-affirmation. Ce n'est pas un arbitrage : la décision est déjà prise au ledger. La phrase
reçoit une **correction datée** au lieu de décrire un comportement que le code refuse délibérément.

### Sémantique de fraîcheur — hors périmètre, mais un fait à verser au dossier

Le lot ne touche pas à la fraîcheur (garde du lot B en place : cliquet sur les *range selectors*
PromQL, `recent|récent|kürzlich` interdits dans les chaînes de niveau). Une observation quand même,
pour le lot dédié : le docstring de `turn_evidence.py` affirme qu'il n'y a « deliberately **no
rolling window** », donc que `dormant` = « aucun tour sur la rétention du store ». C'est **inexact**
en pratique : un vecteur instantané a un horizon de péremption Prometheus (~5 min). Un agent qui a
servi des tours puis dont l'exporteur s'arrête retombe en `dormant` après ~5 min — il *existe* une
fenêtre de récence, imposée par la péremption, pas par la requête. C'est précisément ce qu'on a
observé au départ (dernier échantillon 20:17, backend relancé 21:04, requête vide). **La garde du
lot B a donc eu raison sur le fond** — le libellé ne doit pas promettre de récence — mais le
docstring, lui, sous-estime la récence qui existe déjà. À traiter dans le lot fraîcheur, pas ici.

### Gates — sortie réelle

```
BACKEND (branche, ×2)          : ruff ok · format 542 ok · mypy 280 files ok · 1523 passed
BACKEND (arbre fusionné, ×2)   : ruff ok · format 542 ok · mypy 280 files ok · 1523 passed
FRONTEND (arbre fusionné, ×2)  : tsc ok · biome exit 0 · vitest 12 files / 103 tests passed
```

### Verdict

**MERGÉ et poussé.** `5a93f232` (config + correction ADR) → merge `06bbd54a`. `main ≡ origin/main`.

Aucun code applicatif touché : le lot est bien `config` + docs, comme prescrit. La bascule vit dans
`.env.local` (machine), la **documentation** de la bascule vit dans le dépôt.

---

## LOT 2 — I5 : `synthetic` traverse le fil (ADR 0019 §A1.1)

Branche `claude/adr19-i5-synthetic-wire`, coupée d'`origin/main`. Commit `01c6bfe1`, merge `10183972`.

### L'audit demandé a trouvé un trou plus grand que l'amendement

L'ADR §A1.1 nomme **un** trou : un ContextVar ne franchit pas une frontière de processus, donc un
agent `http` qui émet sa propre télémétrie casse §4 en silence. La consigne ajoutait : « audite le
chemin console in_process ». Résultat de l'audit, vérifié dans le code, pas supposé :

> `grep -rn "synthetic_turn\b" src/` → **3 sites réels, tous dans `agent/canary.py`**.
> `src/tessera/api/routes/chat.py` → **zéro** occurrence de `synthetic`.

La Console du cockpit, pour un agent `in_process_chat`, atteint l'agent par le **même
`POST /chat`** qu'un client. Un opérateur qui **teste** un agent déplaçait donc exactement les mêmes
compteurs métier qu'un vrai client. §4 était violé **des deux côtés du fil**, pas seulement au-delà.

### Le piège qu'il ne fallait pas tomber dedans

Le discriminant naïf — « toute session opérateur est un test » — aurait été catastrophique.
`resolve_request_context` rend `(OPERATOR, <surface portée par l'assertion>)`, et il y a **deux**
surfaces opérateur :

| Surface | Qui | Ses événements métier |
| --- | --- | --- |
| `cockpit-embedded` | la Console du cockpit — **banc de test** | ne doivent **jamais** compter |
| `dedicated-ui` | la console **métier** de recouvrement | sont du **vrai travail**, ils comptent |

Estampiller toute surface opérateur aurait **effacé silencieusement l'intégralité du dossier métier
de recouvrement**. C'est l'erreur inverse, et la pire. Le discriminant retenu est donc
`surface is Surface.COCKPIT_EMBEDDED`, dérivé côté serveur de l'assertion **signée** (jamais affirmé
par le client — `operatorSurfaceForHint` réserve `cockpit-embedded` aux rôles plateforme, et le rôle
`collections` n'obtient que `dedicated-ui` même s'il forge le *hint* « console »).

### Ce qui a été livré

- **Contrat** : `TurnInput.synthetic` (clé wire `synthetic`, **absent ⇒ false** — un agent antérieur
  au champ reste conforme).
- **Fil** : `HttpTurnInvoker.invoke()` prend `synthetic` en **kwarg obligatoire** et l'écrit sur le
  corps, au seul endroit où la plateforme parle à un agent hors-processus. La posture de l'appelant
  **écrase** ce que portait le `TurnInput` : l'autorité est la plateforme, pas son entrée.
- **Consommateurs déclarés** : `POST /agents/{id}/invoke` déclare `synthetic=True` (c'est *le* banc
  de test : opérateur seul, toute session produit refusée en amont). Le scheduler canary ne peut
  structurellement pas piloter `http` (`scheduled_canaries()` ne sélectionne que `in_process_chat`,
  contrainte aussi au niveau du manifeste) ; il estampille déjà en ContextVar. Le trafic produit ne
  pose jamais le drapeau.
- **Span** : `semconv.TESSERA_SYNTHETIC`, estampillé **seulement** si synthétique — même règle
  « absent ⇒ false » que le fil, une seule règle pour les deux. `stamp_turn_dimensions` prend
  `synthetic` en kwarg obligatoire (leçon du lot B : *un défaut est l'endroit où se cache une
  hypothèse*). Il n'entre **pas** dans `REQUIRED_TURN_SPAN_ATTRIBUTES` : cela aurait cassé la
  conformité de `hello-agent`.
- **Devoir de propagation, gaté et non consultatif** : `verify_turn_span` et
  `verify_business_event` / `verify_event_stream` prennent la posture déclarée du tour et signalent
  **les deux sens** — un tour synthétique non estampillé (trafic de test qui gonfle les métriques
  métier) **et** un tour produit estampillé (faits réels silencieusement supprimés).

### Preuve que les tests ont des dents — mutation testing

`tests/unit/test_synthetic_propagation.py` pilote la **vraie route ASGI** (`build_app()`, assertion
opérateur réelle, dérivation de surface réelle) avec un graphe-sonde qui lit la marque **là où le
graphe la lirait**. Deux mutants introduits exprès :

```
── mutant 1: is_test_turn() → False (le comportement pré-I5) ──
FAILED test_cockpit_console_test_turn_is_synthetic
FAILED test_only_the_cockpit_surface_is_a_test_bench
2 failed, 7 passed

── mutant 2: toute surface opérateur estampillée (le sens DANGEREUX) ──
FAILED test_recouvrement_business_console_turn_is_not_synthetic
FAILED test_only_the_cockpit_surface_is_a_test_bench
2 failed, 7 passed
```

Les deux sens sont attrapés. Fichier restauré après chaque mutant (`chat.py` inchangé au byte).

### Une erreur commise, et ce qu'elle a appris

Mon propre test a d'abord **empoisonné la session** : `mark_synthetic_turn()` n'a **aucune portée à
quitter** — sa portée *est* le contexte. Appelé dans un test (contexte partagé), le drapeau ne
redescend jamais, et trois tests de `test_turn_contract_acceptance.py` sont tombés parce que leurs
événements métier étaient devenus synthétiques.

Ce n'est pas un défaut du code de production : chaque requête ASGI tourne dans son **propre contexte
copié** (c'est déjà l'hypothèse de `current_model.set`, `current_agent_id.set`, `guard_disabled.set`
dans le même fichier). Mais c'est un piège pour le prochain appelant. Le test **prouve désormais la
garantie** (`copy_context().run(...)` puis vérifie que la marque est retombée) et l'avertissement est
dans la docstring de la fonction.

### Constat remonté, non tranché

**Un canary `in_process_chat` ne produit aucune preuve de tour.** `AGENT_TURNS_TOTAL` n'est
incrémenté que dans `chat.py` (chemin **servi**) ; `InProcessChatInvoker` appelle
`compile_graph().ainvoke()` directement. Donc un canary activé ne peut jamais faire monter le niveau
**calculé** de son agent. Non corrigé à vue : déplacer le compteur dans le graphe ferait compter les
runs du **harnais d'eval** (même seam) comme preuve — sur-affirmation pire que le trou. Asymétrie
réelle entre bindings (un canary `http` **produira** de la preuve : c'est le critère (a) de I6).
Consigné dans « Owed follow-ups » de `0019-execution-status.md`. **Appel de l'architecte.**

### Gates — sortie réelle

```
BACKEND (branche, ×2)        : ruff ok · format 543 ok · mypy 280 ok · 1540 passed
BACKEND (fusionné, ×2)       : ruff ok · format 543 ok · mypy 280 ok · 1540 passed
FRONTEND (fusionné, ×2)      : tsc ok · biome exit 0 · vitest 12 files / 103 tests
```

(1523 → 1540 tests : +17, dont 9 d'acceptation I5 et 8 de conformité testkit.)

### Verdict

**MERGÉ et poussé.** `01c6bfe1` → merge `10183972`. I5 coché au §Sequencing de l'ADR 0019 ; ligne
ajoutée au ledger `0019-execution-status.md`.

---

## LOT 3 — I6 : duplex-agent (ADR 0019 §A1.2, les 4 critères font foi)

Branche `claude/adr19-i6-duplex`. Deux commits, **volontairement séparés pour que le critère (c)
soit mesurable et non affirmé** : `84eaff43` (capital plateforme) puis `eadf5f8f` (le témoin).
Merge `84c79dfc`.

### Un blocage potentiel, levé par la lecture du code et non par un arbitrage

Avant d'écrire une ligne : `Capability.label_key` doit exister dans
`webapp/frontend/messages/{fr,de,en}.json` (gate `test_manifest_label_keys_exist_in_every_locale`).
Or le critère (c) exige **zéro ligne** de `webapp/frontend/` à l'arrivée du témoin. Contradiction
apparente — j'étais prêt à parker.

Vérification : les catalogues portent **déjà** cinq clés `capability.*` dans les trois langues, et
`recouvrement` déclare déjà des capacités. Le témoin peut donc déclarer
`label_key: capability.propose_schedule` — **aucune clé nouvelle**. Vérification n°2 : la codegen
d'enums (`scripts/generate_agent_enums.py`) est câblée sur `_AGENTS = ("recouvrement",)`, donc
ajouter une capacité à duplex n'émet aucun enum frontend. Le critère est atteignable **sans plier
quoi que ce soit**. Pas de park.

### Un trou plateforme, corrigé en capital, jamais simulé

`agent_console.py` importait `tessera.agent.capability_schema` → **le cliquet de frontière de
l'ADR 0017 §1 est tombé** (`test_control_plane_never_imports_the_agent_runtime`). Le chemin facile
était `_FROZEN_EXCEPTIONS`. Il est explicitement interdit (« ratchet in both directions », liste
gelée vide). Le schéma d'une capacité **fait partie de ce que le manifeste déclare** : le chargeur
est donc ré-exporté par `tessera.agent.registry`, le seul seam que le cliquet autorise — exactement
comme `InvocationBinding` l'est déjà. Cliquet vert, sans exception.

### Les quatre critères

**(a) La boucle de preuve se referme.** Mesuré sur la stack vivante, pas déduit.

```
AVANT   duplex-agent  computed=L0  declared=L1  evidence=dormant
        prometheus observed set: ['onboarding', 'support-client']
        tessera_agent_turns_total{agent_id="duplex-agent"} → 0 série

INVOCATION — vrai HttpTurnInvoker, vrai HTTP, assertion opérateur SIGNÉE et vérifiée par l'agent
  turn 1 (formulaire de capacité) : verdict=green status=200  45ms conformance=[]
  turn 2 (message libre)          : verdict=green status=200  15ms conformance=[]
  event.synthetic=True  ← le devoir de propagation, revenu à travers le fil

APRÈS   tessera_agent_turns_total{agent_id="duplex-agent", job="remote-agent-metrics",
                                   synthetic="true", outcome="answered"} = 2
        prometheus observed set: ['duplex-agent', 'onboarding', 'support-client']
        duplex-agent  computed=L1  declared=L1  evidence=observed        ⬆
```

Le rung **monte parce que l'invocation a produit la preuve**. C'est la boucle qu'aucun exemple ne
fermait.

**(b) Le tour synthétique n'apparaît nulle part dans les métriques métier — et voici ce que ce
chiffre ne prouve PAS.**

```
business_event_rows(agent_id='duplex-agent')            → 0 rows
business_event_rows() ∩ duplex-agent                    → 0 rows
business_event_rows(..., include_synthetic=True)        → 0 rows   ← la ligne qui compte
tessera_business_events_total{agent_id="duplex-agent"}  → 0 série
```

La troisième ligne est l'aveu. Avec `include_synthetic=True` le seam renvoie **aussi** zéro : les
événements métier que duplex renvoie dans son `TurnResult` **ne sont ingérés nulle part**.
`HttpTurnInvoker._interpret` valide le contrat et rend le résultat ; personne n'écrit ses
`businessEvents` dans le store. Donc (b) est vrai — mais il est vrai **parce qu'aucun chemin
d'ingestion n'existe**, pas parce que le filtre §4 a exclu quoi que ce soit.

Le filtre, la garde à l'émission et l'estampille de l'agent sont tous correctement **pré-positionnés**
et testés (l'événement rendu par duplex porte bien `synthetic: true`, vérifié par le testkit), mais
ils ne font pas encore le travail pour un agent hors-processus. **Consigné en « Owed follow-ups » de
`0019-execution-status.md`, jamais revendiqué comme prouvé.**

**(c) Coût marginal — mesuré sur le diff du commit du témoin.**

```
$ git show --stat eadf5f8f -- webapp/frontend
(vide)
```

Zéro ligne. Le renderer générique (`lib/schema-form.ts`, `components/agent/schema-form.tsx`,
16 tests vitest) est du **capital plateforme** livré dans `84eaff43`, agnostique de l'agent : aucune
occurrence de `duplex`, aucun `agentId === …`. Le libellé de la capacité voyage en **clé**
(`label_key`), résolue côté frontend contre le catalogue existant — c'est précisément ce qui rend (c)
atteignable.

**(d) Les témoins existants restent minimaux.**

```
b033bf712e9271a73ad52088c9fa3a944f8992806768423ce7081d08e642184b  hello_agent.py   (inchangé)
0476172f4247f306cc77c656654b005d14393e3af6fd8a587d5173328f32544e  turn_agent.py    (inchangé)
$ git status --porcelain examples/hello-agent examples/turn-agent   → vide
```

`examples/README.md` gagne sa ligne, et la section « Known gap » — qui décrivait précisément le trou
que duplex referme — est réécrite plutôt que laissée mentir. Un test neuf
(`test_the_existing_witnesses_stay_minimal`) **assure** leur minimalité au lieu de lui faire confiance.

### Le témoin

`examples/duplex-agent/duplex_agent.py` : sert `POST /turn` (contrat 0018) **et** émet OTLP (span L1
+ compteur de tours). Déclare **une** capacité avec `input_schema` — la première du dépôt. **Zéro
import tessera** : clés du fil, attributs de span, dimension `synthetic`, enveloppe d'événement,
format de l'assertion opérateur — tout est **redéclaré à la main**, comme le ferait un agent écrit
dans un autre langage. *La duplication est la preuve.* Description au registre métier (le test
anti-jargon, qui bannit `runtime`/`binding`/`endpoint`/`code`/`import`/`OTLP`, passe dessus).

### Gates — sortie réelle

```
BACKEND (branche, ×2)   : ruff ok · format 546 ok · mypy 281 ok · 1564 passed
BACKEND (fusionné, ×2)  : ruff ok · format 546 ok · mypy 281 ok · 1564 passed
FRONTEND (fusionné, ×2) : tsc ok · biome exit 0 · vitest 13 files / 119 tests
```

(1540 → 1564 unitaires : +24. 103 → 119 vitest : +16.)

### Auto-revue

- Le renderer frontend a été construit en parallèle par un sous-agent, sur un périmètre disjoint,
  avec la contrainte « une ligne spécifique-agent = échec ». Il a rendu le gate vert et confirmé zéro
  ligne agent-spécifique, zéro clé i18n nouvelle.
- `duplex-agent` a été **démonté** en fin de lot (`:8501` libre, aucun processus résiduel).
  Conséquence honnête : sans lui, sa preuve de tour se périme (~5 min d'horizon de péremption
  Prometheus) et sa carte retombe sur « L1 déclaré · aucune preuve ». C'est la lecture correcte d'un
  agent qui n'émet plus. Pour le revoir calculé :
  `uv run python examples/duplex-agent/duplex_agent.py`.
- Non fait : la vérification **visuelle** du formulaire généré dans la Console. Elle est du ressort
  du lot 5 (Playwright) et de la validation d'Amadou. Le payload est testé côté backend, la
  projection côté vitest ; le rendu de bout en bout ne l'est pas encore.

### Verdict

**MERGÉ et poussé.** `84eaff43` + `eadf5f8f` + docs → merge `84c79dfc`.
**ADR 0019 Amendment 1 est implémenté (I5 + I6).**

---

## LOT 4 — FE snapshot client

Branche `claude/fe-snapshot-client`, commit `c8ef9b31`, merge `48e8e435`.

### La prémisse était fausse, et c'est la mesure qui l'a dit

La consigne parlait des « 24-37 requêtes en rafale **des pages** ». Mesure réelle, navigateur
headless authentifié contre la stack de référence, **avant** toute modification :

| Page | requêtes `/api/*` | endpoints distincts |
| --- | --- | --- |
| Flotte (`/fr/agents`) | 4 | 2 |
| Fiche agent (`/fr/agents/support-client/synthese`) | 6 | 3 |
| **Vue d'ensemble** (`/fr/surveiller/vue-ensemble`) | **58** | **26** |

Flotte et la fiche agent **ne rafalent pas** : elles sont rendues côté serveur. La rafale est
entièrement sur Vue d'ensemble. J'ai mesuré avant de coder, et c'est ce qui a évité de « corriger »
deux pages qui n'avaient rien.

### Le backend l'avait déjà construit ; personne ne l'appelait

`GET /observability/snapshot` existe depuis la migration spine (ADR 0015 §Performance). Son
docstring dit mot pour mot : *« collapsing 24-37 per-page requests into one round-trip »*. Il est
batché, mis en cache (TTL = cadence de poll), avec *single-flight*. Et
`tests/unit/test_spine_signals_parity.py` **épingle déjà** chaque tranche comme *byte-identical* à
la route individuelle qu'elle remplace.

Vérifié en direct avant de m'appuyer dessus — 9 signaux, 9 routes :

```
signal        data == payload de la route ?
  slo         ✓ identical      cost         ✓ identical
  trend       ✓ identical      anomalies    ✓ identical
  funnel      ✓ identical      what_changed ✓ identical
  toxicity    ✓ identical      scores       ✓ identical
  pii_leak    ✓ identical
meta: {"upstream_reads": 3, "n_signals": 10}
```

Le lot n'était donc pas « construire un snapshot » : c'était **adopter celui qui existe**.

### Deux requêtes, pas une — et c'est délibéré

`anomalies` et `what_changed` rafraîchissent toutes les **20 s** ; les sept autres toutes les 15 s
(`POLL_MS`). Les plier dans une seule clé de requête aurait **silencieusement re-cadencé** deux
cartes. Invisible à l'écran, et exactement le genre de « aucun changement de comportement » qui n'en
est pas un. Donc : `?signals=` en deux sous-ensembles, un par cadence.

### Aucune vérité nouvelle

Chaque carte `select` sa tranche et la **valide avec le schéma zod de sa propre route**. Honest-empty
préservé champ par champ : un signal que le backend n'a pas su calculer reste `undefined` — jamais
`{}`, jamais un zéro fabriqué. Une seule source indisponible dégrade **une** carte, comme
aujourd'hui, et ne vide jamais la page. Les routes par signal sont **conservées** (d'autres pages les
appellent, et elles restent le contrat contre lequel le snapshot est vérifié). Sept tests vitest
neufs, dont « une charge qui a dérivé du contrat retombe en honest-empty » et « le jeu de signaux du
backend est épinglé ».

### Mesure APRÈS (preview depuis le worktree, `:3096`/`:8096`, jamais les ports de référence)

| Page | avant | après |
| --- | --- | --- |
| Flotte | 4 req / 2 endpoints | 4 / 2 (inchangé) |
| Fiche agent | 6 / 3 | 6 / 3 (inchangé) |
| **Vue d'ensemble** | **58 / 26** | **44 / 19** |

Et côté backend : les 7 signaux « rapides » coûtent **2 lectures amont** au lieu de 7 appels de route
(`upstream_reads: 2`), les 2 « lents » en coûtent 1. La page a été assertée non-vide (son contenu
réel s'affiche), pas seulement « 200 OK ».

### Trois choses que ces chiffres ne prouvent PAS — dites plutôt que tues

1. **Le ×2 est du React StrictMode** en dev (double invocation des effets), pas un comportement de
   production. 58 → 44 en dev correspond à ~29 → ~22 en prod.
2. **`/observability/slo` survit dans la liste après** : une autre composante (le *breach hero*) le
   fetch pour son compte. Le replier est sa propre tranche, pas celle-ci.
3. Les endpoints hors du jeu snapshot (`conformance`, `tool-validity`, `firewall-efficacy`,
   `refusal`, `playbooks`, `roadmap`, `ai-act`, `timeline`, `control-signals`, `governance`,
   `inbox`, `traces-obs`, `data-range`) **restent un appel chacun**. Le jeu de signaux du backend en
   contient 10 ; les élargir est une décision plateforme, pas un recâblage client.

### Gates — sortie réelle

```
BACKEND (fusionné, ×2)  : ruff ok · format 546 ok · mypy 281 ok · 1564 passed
FRONTEND (fusionné, ×2) : tsc ok · biome exit 0 · vitest 14 files / 126 tests
```

(119 → 126 vitest : +7.)

### Auto-revue

- Le preview a été monté depuis le **worktree** (`:3096`/`:8096`, port métriques `9096` pour ne pas
  disputer `:9090` au backend de référence), puis **démonté**. Les serveurs de référence
  (`:3097`/`:8099`) n'ont pas bougé de la nuit hors du redémarrage sanctionné du lot 1.
- Un `webapp/frontend/.env.local` a dû être copié dans le worktree pour que NextAuth signe la session
  du navigateur de mesure (sans lui : 0 requête, la page ne montait pas). Il est **gitignoré** et a
  été **supprimé** après la mesure. Aucun secret n'a été affiché ni commité.

### Verdict

**MERGÉ et poussé.** `c8ef9b31` → merge `48e8e435`.

---

## LOT 5 — e2e smoke Playwright  (⚠️ MERGÉ, mais PARTIEL — périmètre réduit assumé)

Branche `claude/e2e-smoke-0019`, merge `69860a66`. Fichier neuf :
`webapp/frontend/e2e/smoke-0019.spec.ts`, **7 tests, 7 verts** contre la stack de référence réelle.

### Ce qui est couvert

**Badges de niveau (variante déclaré vs calculé).** La stack du lot 1 rend les deux visibles
simultanément — c'est ce que le smoke exige :

```
support-client  badge=computed  computed=L2  declared=L2  evidence=observed
onboarding      badge=computed  computed=L2  declared=L2  evidence=observed
recouvrement    badge=declared  computed=L0  declared=L2  evidence=dormant
hello-agent     badge=declared  computed=L0  declared=L1  evidence=dormant
turn-agent      badge=declared  computed=L0  declared=L1  evidence=dormant
duplex-agent    badge=declared  computed=L0  declared=L1  evidence=dormant
```

**Consoles 0019.** `none` (hello-agent) → honest-empty **et** absence prouvée du banc de test ;
`http` (turn-agent) → banc requête/réponse avec l'endpoint déclaré affiché ; `http` + `input_schema`
(duplex-agent) → **formulaire généré**, dont les libellés sont les `title` du schéma, l'`enum` est
devenu un `select` et le booléen une case à cocher. **Le critère (c) de l'ADR 0019 §A1.2 est ainsi
vérifié dans un navigateur**, plus seulement argumenté.

Sélecteurs par **rôle, label et texte visible**, jamais par classe CSS : les passes de craft
retouchent les classes, et un smoke qui casse sur un changement de couleur ne protège rien.

### Une précondition rendue explicite plutôt que cachée

Le badge *calculé* n'existe que si un agent a **réellement servi un tour** sur cette stack
(`TESSERA_LEVEL_TURN_EVIDENCE=1` + Prometheus + au moins un `POST /chat`). Zéro fixture fabriquée,
donc l'assertion porte un message : un zéro ici est **un constat sur le chemin de preuve**, jamais
une raison de stubber une donnée.

### Ce qui n'est PAS couvert (dit, pas sous-entendu)

Le lot demandait cinq familles de specs. J'en ai livré deux (badges, consoles). **Non écrits** :
onglet **Métier** (table par capacité, drill-down runs), **recouvrement-new**, **headers**
(pill posture + popover, ⌘K, identité). Raison : budget de nuit ; j'ai priorisé les surfaces que
les merges de cette nuit ont *changées*, donc celles qui pouvaient régresser sans que rien ne le voie.

### Constat annexe — la suite e2e existante est ROUGE sur `main`

`e2e/console.spec.ts` : **2 échecs sur 3** contre `main` (le sélecteur `Fenetre temporelle` et le
lien `Timeline incidents` ne résolvent plus). **Préexistant**, sans rapport avec les merges de la
nuit. Je ne l'ai pas corrigé : ces pages relèvent d'une validation visuelle. **Conséquence pratique :
le smoke ne peut entrer dans le gate que *fichier par fichier* (`playwright test e2e/smoke-0019.spec.ts`),
pas via `pnpm test:e2e` qui reste rouge.** À trancher par Amadou.

### Gates

```
FRONTEND (fusionné, ×2) : tsc ok · biome exit 0 · vitest 14 files / 126 tests
BACKEND  (fusionné, ×2) : ruff ok · mypy 281 ok · 1564 passed
SMOKE                   : 7 passed (20,7 s) — rejoué vert après merge
```

---

## LOT 6 — Reliquat headers : menu grille d'apps  🅿️ **PARKÉ**

**Constat (fait, pas supposé)** : le menu **n'existe pas** sur `main` (grep sur
`app-grid|AppGrid|apps-menu|AppsMenu` dans `components/`, `app/`, `lib/` : aucune occurrence de
composant). Et il **est bien spécifié**, dans `Tessera_private/spec-headers-premium-2026-07-07.md`,
§Addendum, emprunt (b) :

> « **menu grille d'apps Espaces métier / Espace client** = le toggle operator→product que 0013
> autorise explicitement — à ajouter, gaté rôle opérateur »

**Pourquoi parké** : ce n'est ni une contradiction ni un rouge — c'est du **budget de nuit**. Il
reste à faire : composant + popover, gate rôle opérateur (0013, seule direction cross-plane
autorisée), invisibilité pour un rôle produit, i18n ×3, lexique (jamais « Tessera » côté produit),
tests. Le finir à la hâte au moment où il faut aussi refermer la nuit proprement (suite complète,
relance des serveurs, démontage vérifié) aurait produit une fonctionnalité non mergeable. **Une
tranche non finie vaut moins qu'un park propre.**

**Rien n'a été commencé** : aucune branche, aucun fichier touché. Point de départ pour la reprise :
`webapp/frontend/components/layout/` (le header cockpit) et `lib/auth/roles.ts`
(`hasCockpitAccess`, `spaceRedirectForRole`), plus `codex/headers-refonte` déjà ancêtre de `main`.

---

## LOT 7 — Craft pass P3 (punch list items 18-23)  🅿️ **PARKÉ — source introuvable**

La consigne vise « **punch list items 18-23, lot 2.5** ». Recherche exhaustive :

- dépôt : `grep -rl "punch" docs/` → uniquement `docs/decisions/0017-execution-status.md` (mentions,
  pas de liste) ;
- docs de pilotage : `ls Tessera_private/ | grep -i punch` → **un seul fichier**,
  `punchlist-metier-lot1.5-2026-07-07.md`, dont la numérotation commence à 1 et ne va pas jusqu'à 18.

**Il n'existe aucune punch list « lot 2.5 » ni aucun item 18-23 accessible.** Exécuter « des
retouches ciblées » sans la liste des retouches reviendrait à **inventer le périmètre** sur des pages
validées — exactement ce que la règle du registre des rails interdit (« jamais de régénération d'une
page validée »). **Parké, consigné, non deviné.** Amadou : fournir le fichier, ou pointer les items.

---

## LOT 8 — Stretch  ⏭️ **SAUTÉ**

Conditionné à « seulement si tout le reste est fini » — 6 et 7 ne le sont pas.

Néanmoins, la vérification demandée a été faite, et son résultat est utile :

**Colonne synthétique ClickHouse.** La consigne dit : « vérifie d'abord si le bake business-events
est terminé ; sinon consigne l'état et n'y touche pas. » ClickHouse est **joignable** (`:18123`,
conteneur `tessera-claude-clickhouse` healthy) mais **refuse l'authentification par défaut**
(`Code: 516 … AUTHENTICATION_FAILED`). L'état du bake **n'a donc pas pu être établi**, et je n'y ai
**pas touché**. La dette elle-même reste correctement documentée dans
`business_events.persisted_business_events` et dans « Owed follow-ups » de
`0019-execution-status.md`.

**Aliasing des enums FE** (drawer-task / artifact-family via manifeste) : non commencé.

---
---

# Day run 2026-07-10

Same protocol as the night: one lot = one branch = one merge; twice-green per lot; red twice ⇒
parked, recorded, move on. `0017-execution-status.md` is never written here.

## RÉSUMÉ (tenu à jour en tête de section)

**Ouverture :** `main` = `origin/main` = `e1a73c5c`. Serveurs de référence `:3097`/`:8099` dessus,
Amadou regarde dessus aujourd'hui → **previews depuis le worktree uniquement**.

| Lot | Sujet | Verdict |
| --- | --- | --- |
| 0 | Mirroir des 2 décisions dans le ledger 0019 | 🔄 |
| 1 | Réparer le rouge e2e préexistant | ⏳ |
| 2 | Compléter le smoke e2e + verrou §4 | ⏳ |
| 3 | Menu grille d'apps | ⏳ |
| 4 | Craft pass P3 (items 18-23) | ⏳ |
| 5 | Colonne synthétique ClickHouse | ⏳ |
| 6 | Aliasing enums FE | ⏳ |

---

## LOT 0 — Mirroir des décisions Claude

Deux décisions d'architecte reçues ce matin, écrites dans `docs/decisions/0019-execution-status.md`
(§Owed follow-ups). Elles **ferment** les deux dettes que j'avais remontées cette nuit sans les
trancher.

1. **Preuve de tour du canary.** Verbatim reçu et consigné tel quel : le compteur **reste** sur le
   chemin servi ; `tessera_agent_turns_total` signifie « tours servis à de vrais consommateurs par le
   seam déclaré » ; la vivacité canary a **déjà son fait propre** (facette S1 `synthetic_run`). Les
   combiner en un badge « dormant mais réactif » est une **tranche fraîcheur au backlog** — *jamais
   fusionner les sources.* Donc : ce n'est pas un défaut, c'est une séparation voulue. Rien à coder.

2. **Critère (b) owed.** Le seam d'ingestion des `businessEvents` d'un agent `http` est une
   **décision de DESIGN**, prise avant tout code. **Ne rien implémenter dessus.**

   **Note de transmission, dite plutôt que masquée :** la ligne est arrivée **tronquée** (« le seams
   d'agents http est une décision de DESIGN (Claude tranche avant tout code). N'implémente rien
   dessus. »). J'ai consigné sa **substance non ambiguë** — l'interdiction d'implémenter, et la
   nature « design » de la décision — plutôt que de reconstruire un « verbatim » que je n'ai pas reçu.
   Si le libellé exact importe, il est à re-fournir ; l'effet opérationnel, lui, est sans ambiguïté et
   respecté : **aucun code sur ce seam aujourd'hui.**
