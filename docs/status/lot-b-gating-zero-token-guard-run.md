# Lot B — garde 0-token à l'ingestion du socle + purge des runs fantômes

Run du 2026-07-16, branche `claude/lot-b-gating-zero-token-guard` (coupée de `main` =
`036079f4`), worktree `agents/claude-lotb`, session `E6D60020-369F-4813-B41A-2E4D665EC11F`.

**Trace amont** : Insight 168 (registre canonique), `docs/status/er-01-evaluation-run-rail-run.md`
§ Questions HALT (question 2), `Tessera_private/backlog-lots-suivi-2026-07-16.md` § Lot B.

**Déclaration de précédence** : ce lot PRÉCÈDE le lot A (contribution / régressions stockées
par run), qui étendra le même enregistrement (`gating_rows_from_report` / schéma du rapport).
Le lot A doit reprendre par-dessus ce garde : tout champ ajouté au rapport entre par la même
porte, et la porte demande des tokens.

## La maladie (rappel)

Un runner dont le backend LLM est mort ne crashe pas : chaque cas se termine sur la seule
couche déterministe, et le rapport porte quand même le nom du modèle **configuré**. Ingéré
dans `eval_gating_scores`, un tel run est un faux témoin — une ligne qui dit qu'un modèle a
été noté alors que rien n'a parlé. Le témoin honnête est les tokens émis
(`eval.ratchet.model_spoke`), jamais le champ `model`. Quatre runs de cette forme sont entrés
le 2026-07-12 ; la table ne stocke pas les tokens, elle ne pouvait pas se défendre seule.

## 1. Le garde — posé AVANT la purge

`record_gating_report` (`src/tessera/observability/eval/gating_scores.py`) refuse désormais,
**fail-closed et avant toute écriture durable**, un rapport qui produirait des lignes sans
qu'un modèle ait émis un seul token : il lève `ModellessRunRefusedError`. La règle est
**réutilisée** (`eval.ratchet.model_spoke`), jamais recopiée. Autour de la porte :

- `ingest_gating_reports` (sweep de boot, G4) attrape ce refus PAR RAPPORT, le loggue avec le
  fichier porteur (`gating.modelless_run_refused`) et continue — un fantôme n'entre pas ET ne
  fait pas tomber la réconciliation du reste de l'archive.
- `eval/runner.py::_record_gating` distingue le refus de la panne : `gating REFUSED — run not
  recorded` vs `gating store unavailable`. Un refus nommé « indisponibilité » rapporterait le
  mauvais fait (ADR 0026).
- Les probes synthétiques des tests de contrat (`tests/integration/test_owned_stores_contract.py`)
  portent maintenant `cost.output_tokens` — sans quoi le garde les aurait refusées et le
  `pytest.skip("postgres not up")` aurait menti sur la raison.

## 2. Mutation-test — le cliquet vu ROUGE

Garde muté (`if False and …`), `tests/unit/test_score_write_paths.py -k ZeroTokenGuard` :

```
FAILED …::test_zero_token_run_with_model_witness_is_refused
FAILED …::test_missing_cost_block_is_absence_of_proof_not_a_pass
FAILED …::test_ingest_sweep_refuses_the_ghost_and_keeps_reconciling
3 failed, 2 passed
```

Les 3 tests qui policent le refus tombent ; les 2 tests de préservation (un run parlant entre,
une probe sans agent n'atteint jamais la porte) restent verts — la signature attendue. Garde
restauré : 24/24 verts sur le fichier. Un cliquet jamais vu rouge n'est pas un cliquet.

## 3. La purge — par interrogation, jamais par id codé en dur

Outil : `scripts/purge_modelless_gating_runs.py --date 2026-07-12 [--apply]` (dry-run par
défaut). L'interrogation, faute de tokens en table : **l'archive est le seul endroit où les
tokens vivent** — un run publié est jugé par `model_spoke` sur son propre report ; un run que
l'archive ne publie nulle part est *table-only*, sans aucun témoin qu'un modèle ait parlé, et
ses propres lignes (sweep complet étalé sur 1,6–3,7 s) disent que rien n'a pu parler. Témoin
discriminant vérifié : les **29 autres runs de la table sont tous publiés par l'archive, tous
avec tokens > 0** ; les 4 seuls runs non publiés sont exactement les 4 du 12/07. Le script
importe `ModellessRunRefusedError` : il ne peut pas tourner dans un arbre où l'entrée est encore
ouverte.

```
BEFORE  schema=tessera_local rows=2822 runs=33
ghosts: 4 run(s), 387 row(s) to purge
  20260712T125537Z_support-client  (119 lignes, 3.7s)   — table-only
  20260712T125540Z_recouvrement    (80 lignes, 1.6s)    — table-only
  20260712T125543Z_onboarding      (69 lignes, 2.0s)    — table-only
  20260712T125613Z_support-client  (119 lignes, 2.8s)   — table-only
deleted 387 row(s) across 4 run(s)
AFTER   rows=2435 runs=29 (expected rows=2435, runs=29)
```

Trouvés = 4 = le chiffre attendu — pas de HALT sur le compte. Aucun fichier fantôme n'existe
dans les archives (`eval/reports/local/` des deux checkouts, vérifié) ni dans l'historique git
des `latest_<agent>.json` : le sweep de boot ne peut rien réinjecter.

## 4. Contamination du gate de release / POWER_FLOOR — MESURÉE

Hypothèse d'Amadou : `discrimination.json` vient de `.eval-noise/`, pas de cette table.
**Confirmée, par le code ET par la mesure.**

- **Code** : `scripts/check_discrimination.py` (mode check) lit exclusivement
  `eval/baselines/{null-control,discrimination-samples,discrimination}.json` + les cas sur
  disque ; en mode `--write` il lit les passes brutes de `.eval-noise/`. Le gate de release
  (`grade_against_own_floor`, tuile ET bouton) lit l'`EvalSnapshot` (fichiers de l'archive via
  `iter_report_files`) + `null-control.json` + `discrimination.json`. Les seuls consommateurs
  de `eval_gating_scores` sont : le runner (écriture), le sweep de boot (écriture), le
  backfill (écriture), le miroir Langfuse et les adapters du spine (lecture — rail ER-01 /
  page Évaluations / fait « gating »). Aucun maillon de la chaîne du plancher ne touche la table.
- **Mesure** : `make eval-power` (verdict + exit 0, plancher 3 cases / 4 runs) et le verdict
  release des trois agents touchés (`support-client` Ok, `recouvrement` NotOk — inversion
  certifiée `56_policy_violation_disparage_bank|de`, indépendante des fantômes —
  `onboarding` Ok) sont **byte-identiques avant et après purge**. Déplacement : **0**.

Verdict : les 4 fantômes étaient **isolés** du gate de release et de la classification figée.
Ce qu'ils contaminaient réellement : le journal S3 que sert le spine — le rail ER-01 et la
page Évaluations listaient 4 runs « llama3.2:3b » où aucun modèle n'a parlé
(support-client 13→11 runs, recouvrement 10→9, onboarding 10→9). C'est l'effet voulu de la
purge, pas une contamination du plancher.

## Fenêtre résiduelle (à dire au FF)

Tant que cette branche n'est pas sur `main`, la porte du checkout main reste ouverte : une
**nouvelle** probe nulle par-agent lancée depuis main entrerait encore dans la table (aucune
réinjection possible des 4 purgés — leurs fichiers n'existent pas ; seul un nouveau run
pourrait créer un nouveau fantôme). Après FF, elle est refusée à la porte.

## Verdicts

- Tests unitaires du fichier touché : 24/24 verts ; mutation rouge démontrée puis restaurée.
- Contrats d'intégration Postgres du porteur : 4/4 verts en live (5 skips ClickHouse
  préexistants, honnêtement nommés).
- `mypy --strict` : propre (313 fichiers).
- `make gate-twice` : voir le commit — lancé sur l'arbre committé.
