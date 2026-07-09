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

*(Kept up to date at the head of this file. Filled in as lots land — see the end-of-night entry for
the final consolidated version.)*

**État à l'ouverture du run :** `origin/main` = `main` = `29fdefbc`, 0 ahead / 0 behind.

| Lot | Sujet | Verdict |
| --- | --- | --- |
| 0 | Pré-vol + merges feu vert | ✅ **mergé** `e4eedcde` (poussé) |
| 1 | Brancher la preuve (Prometheus) | ⏳ |
| 2 | I5 — `synthetic` traverse le fil | ⏳ |
| 3 | I6 — duplex-agent | ⏳ |
| 4 | FE snapshot client | ⏳ |
| 5 | e2e smoke Playwright | ⏳ |
| 6 | Reliquat headers — menu grille d'apps | ⏳ |
| 7 | Craft pass P3 | ⏳ |
| 8 | Stretch (enums FE, colonne synthétique CH) | ⏳ |

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

