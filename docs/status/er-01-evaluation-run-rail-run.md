# ER-01 — Evaluation Run Rail (run 2026-07-15)

Worktree dédié `agents/claude-er01`, branche `claude/er-01-evaluation-run-rail`, base
`origin/main = eb9259b8`. Source de vérité : `docs/design/registre-rails-temporels.md`
(ER-01 · S3 · C2 · page AGENT / Évaluations · « À faire ») et `docs/design/eval-gate-policy.md`
§ provenance (chaque run porte sa date + sa version de catalogue).

Deux autres agents en vol (floors, lentilles-par-domaine) + phase 2 (`guard/adapter.py`) —
périmètre disjoint ; `scripts/check_discrimination.py`, `lib/agent-lens.ts` et
`gov-scope-section.tsx` **non touchés**.

---

## Ce que la mesure a trouvé (mesuré, pas supposé)

**Le substrat.** Deux sources co-existent pour « les runs d'éval d'un agent » :

- **L'archive de rapports** (`eval/reports/local/`, 86 fichiers committés) — 3 agents avec runs :
  `support-client` (10), `recouvrement` (10), `onboarding` (9). **Chaque run distinct porte les
  faits suivants, tous stockés** : `run_at`, `model`, `catalogue_version` (non-nulle sur 100 % des
  runs mesurés), `eval_set`, `summary.passed/total`, `gate.passed` (verdict enregistré au moment
  du run).
- **La table Postgres `eval_gating_scores`** (porteur ADR 0015, index `(agent_id, scored_at)`) —
  33 runs. Sur les **29 runs partagés**, les deux sources sont **identiques** (passed/total,
  catalogue). La table ne porte **pas** le verdict gate (pas de colonne), ni `eval_set`, ni les
  tokens.

**⚠️ Découverte : 4 runs du 2026-07-12 n'existent QUE dans la table** (`20260712T125537Z`/
`125613Z_support-client`, `125540Z_recouvrement`, `125543Z_onboarding`) — aucun fichier de
rapport, ni committé ni sur le disque des deux checkouts. Leur timing est dégénéré : 69–119 cas
en < 4 s ⇒ **aucun modèle n'a parlé** (doctrine du plancher nul : le témoin est le temps/les
tokens, jamais le champ `model` — qui affirme pourtant `llama3.2:3b`). Ce sont très
probablement des probes null-control ingérées dans le porteur. → question HALT ci-dessous.

**Décision de lecture.** Le rail lit le journal de runs par **l'archive de rapports** (la même
« source vivante » que tout l'écran Évaluations, policy §« Source vivante ») : c'est la seule
source qui porte le **verdict gate enregistré au run** et elle est convergente avec la table sur
tout run publié. Les 4 lignes dégénérées de la table n'y apparaissent pas — c'est un effet
correct, pas une perte.

## Le jeu de colonnes (fondé sur le stocké, rien d'inventé)

- **Stocké par run → affiché** : date (`run_at`) · version de catalogue · modèle · exécutions
  (`total`) · réussis (`passed`) → taux · **verdict gate enregistré au run** (`null` = « non
  enregistré », affiché tel quel, jamais recalculé contre les dérogations d'aujourd'hui).
- **Dérivé à l'affichage** : Δ de taux vs run précédent — seulement si un run précédent existe
  **et** porte la **même** version de catalogue (deux catalogues = deux examens différents).
- **Pas stocké par run → PAS de colonne** : contribution au-dessus du plancher, régressions
  bloquantes candidates. Elles ne sont calculables que pour le run courant contre la baseline
  null-control **courante** (`grade_against_own_floor`) ; les produire pour un run historique
  serait une invention. → question HALT ci-dessous.

## Ce qui a été construit

- **Backend** — `RunHistoryEntry` porte `catalogue_version` + `model` (`eval_data.py`) ;
  `_runs_rail` (`agent_evaluations.py`) émet la provenance par run + `delta_pass_rate` gardé +
  `empty_label` honnête ; pydantic (`schemas_fleet.py`) : `gate_passed: bool | None` (l'ancien
  `bool` strict aurait 500 sur un run sans bloc gate) ; zod (`schemas.ts`) + schémas générés
  (`scripts/generate_zod.py --domain fleet`) alignés ; fixture `fleet_real_responses.json`
  recapturée par la vraie route (12 entrées, sections sœurs vérifiées inchangées).
- **Frontend** — `components/agent/evaluation-run-rail.tsx` (NOUVEAU, S3/C2 — distinct du
  `temporal-rail.tsx` SR-01 S4/C4, non réutilisé et non modifié) : un point par run (barre =
  taux, couleur = verdict enregistré), sélection **dérivée de l'URL** (`?run=<run_at>`,
  deep-link, les params du SR-01 préservés), mode **Live · dernier run / Historique · run du…**
  toujours affiché, bandeau de faits du run sélectionné (provenance « set · date · cat … » +
  modèle + taux + verdict + Δ), honest-empty (« Éval non exécutée »), 1 run = 1 point (« un
  point n'est pas une tendance »), `?run=` inconnu dit « Run demandé introuvable ». Le code
  ER-01 n'apparaît jamais à l'écran. Monté sur AGENT / Évaluations à la place de l'ancien nuage
  de chips ; les métriques jugées deviennent un panneau dédié (`JudgeMetrics`).
- **Les portes** — la Vue par agent (lentille **qualité** de SURVEILLER / Qualité IA) : le nom
  de l'agent → sa page Évaluations (`agent-breakdown.tsx`, QualityTable uniquement) ; la Flotte
  (`fleet-explorer.tsx`) : lien « Évaluations » sur la carte ET la ligne, à côté de
  « Gouverner ». Clés i18n ajoutées aux trois locales.
- **Registre** — ER-01 → **Implémenté** (v1.4, note d'état au 2026-07-15 avec fichiers).

## Preuves

- Tests : `test_agent_evaluations.py` 9/9 (provenance, Δ gardé par catalogue, verdict non
  inventé, honest-empty) ; contrat byte-identique `test_fleet_response_models.py` re-vert sur la
  fixture recapturée ; vitest 399/399 dont `evaluation-run-rail.test.tsx` 7/7 (URL = sélection,
  mode visible, honest-empty, Δ non comparable) et la porte QualityTable assertée par href.
- `make gate-twice`, rendu réel (`dev-preview`) : voir le rapport HALT de fin de lot.

## Questions HALT (avant merge)

1. **Colonnes non stockées** : contribution / régressions bloquantes par run historique — faut-il
   les **stocker par run** au moment du run (extension du rapport), ou rester à l'affichage des
   seuls faits stockés ? (Le rail actuel n'affiche que le stocké.)
2. **Les 4 runs fantômes de la table `eval_gating_scores`** (2026-07-12, < 4 s, table-only) : le
   porteur a accepté des lignes que l'archive n'a jamais publiées, et la table ne stocke pas les
   tokens — elle ne peut pas se défendre seule contre une probe null. Purge ? Garde à
   l'ingestion (`record_gating_report` refusant un run à 0 token) ? Hors périmètre ER-01, mais
   mesuré ici.
