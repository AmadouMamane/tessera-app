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
| 0 | Pré-vol + merges feu vert | 🔄 en cours |
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

*(en cours — sortie des gates ci-dessous)*
