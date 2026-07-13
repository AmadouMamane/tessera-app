# Qualité IA — refonte de l'écran (run 2026-07-13)

Worktree dédié `agents/qualite`, branche `ui/qualite-ia`, base `origin/main = 2ed0920a`.
Source de vérité : `Tessera_private/spec-qualite-ia-2026-07-12.md`, **AMENDEMENT 1 inclus** (il fait foi).
Critères d'acceptation : §6 (1-6) et §A1.9 (7-12).

Un autre agent travaille sur `compute_fleet()` (`src/tessera/observability/`) — périmètre disjoint,
rien de ce lot n'y touche.

---

## Ce que l'inventaire a trouvé (mesuré, pas supposé)

**La route.** La spec §1 dit « l'UI actuelle — `/surveiller/qualite-ia`, deux onglets ». C'est
faux, et de deux façons :

- `/surveiller/qualite-ia` rend un **`ObservabilityDashboard`** (flotte, SLO, datasets). Son
  sous-titre i18n promet pourtant « Évaluations, régressions, hallucinations… ».
- L'écran à deux onglets `detail`/`compare` que la spec décrit est `ScorecardView`, monté sur
  **`/[locale]/eval`** — une route **orpheline** : zéro entrée de menu, zéro lien entrant dans
  tout le front.

→ **Cible retenue : `ScorecardView` + `components/eval/*`.** Ce sont exactement les composants que
la spec nomme pour la migration (`results-by-category`, `run-history-panel`, `model-comparison`),
et exactement le périmètre de fichiers assigné à ce lot. `components/observability/` n'est pas
touché (blast radius du lot perf).

> **FINDING pour arbitrage d'Amadou — l'écran n'a aucune porte.** `/eval` n'est atteignable que par
> URL directe. Le correctif tient en une entrée de sidebar, mais la sidebar est du chrome partagé
> (`codex/headers-refonte` est en vol) : je ne la redessine pas de mon propre chef. **Question
> ouverte.**

**Les données.** Pire que ce que la spec annonçait — les deux chemins de lecture sont cassés,
différemment :

- `lib/eval.ts::reportsDir()` retourne `eval/reports/`, mais le runner écrit dans
  `eval/reports/<env>/` (ADR 0014). En **dev**, `loadAllRuns()` ne trouve donc **aucun** JSON à la
  racine : l'écran est **vide**.
- En **image déployée** (pas de `pyproject.toml`), il retombe sur le bundle `data/eval/latest.json`
  — qui porte un run du **20 juin** de **3 cas** (un seul cas × 3 langues) à **0 token**, et
  l'affiche **« 3/3 — 100 % »**. Un run qu'aucun modèle n'a jamais répondu, publié comme un
  sans-faute.

**Le champ `reasons` EST peuplé.** La spec §1 affirme que « quel critère a sauté » n'est pas stocké
(« `passed` est un booléen nu »). **C'est faux** : `eval/runner.py::_evaluate` retourne
`(not reasons, reasons)` et le rapport les conserve — 17/17 des cas échoués de `llama3.2:3b`
portent leur motif en clair (« response contained forbidden substring 'FR76 3000…' »,
« confidence 0.75 above max_confidence 0.5 »). Le recalcul reste nécessaire (c'est lui qui donne la
**position** de la sous-chaîne à surligner), mais il est désormais *croisable* avec le témoin du
harnais au lieu de le remplacer.

---

## Rulings

**R1 — le lot 1 embarque la carte de score.** L'interdit « aucun score brut nulle part » (critère 7)
est absolu. Dès l'instant où l'écran sait lire un run du sweep, il doit l'afficher **décomposé** :
livrer « le pont » seul obligerait à publier un `90 %` nu pendant un commit. Pont et carte de score
sont donc indissociables et arrivent ensemble.

**R2 — aucun seuil de péremption en jours.** Le critère 11 demande qu'un run périmé soit signalé,
l'interdit demande qu'aucun seuil ne soit inventé. Les deux tiennent ensemble en définissant
« périmé » **structurellement** : un run est périmé quand **le jeu de cas a bougé sous lui**
(son `catalogue_version` n'est plus celui du catalogue courant). C'est un **fait mesuré**, pas un
nombre choisi. L'**âge** est affiché à côté, comme une **mesure** (« dernier run il y a N jours »),
jamais comme un gate.

**R3 — le bundle généré sort du formateur.** `data/eval/**` est un **artefact de données**, miroir
de ce que le harnais écrit. Le faire reformater par biome casserait ce miroir *et* posait un piège
dormant : un `pnpm build` local régénérait le bundle non formaté et faisait rougir le gate au coup
d'après. Exclu de `biome.json`.

**R4 — le plancher est LU, jamais recalculé.** Il vient de `eval/baselines/null-control.json`
(174 verdicts, 122 `true`). Une surface qui recalculerait le plancher qu'elle affiche corrigerait
sa propre copie.

---

## LOT 1 — le pont + la carte de score  ✅

**Le modèle de données est redéfini : un SWEEP = N runs sur UNE version de jeu de cas.**
« Latest » n'a plus de sens à trois modèles, et l'écran ne lit plus « un run ».

| Fichier | Rôle |
| --- | --- |
| `lib/eval-score.ts` | **module pur** — miroir TS de `eval/contribution.py` + `eval/ratchet.py` : décomposition (plancher / contribution / casses), `cellState` à 4+1 états, `zeroPowerCategories` (règle 3, dérivée), `modelSpoke` (tokens, jamais le champ `model`), fraîcheur |
| `lib/eval-score.test.ts` | épingle le module aux **vrais artefacts du dépôt** (baseline commitée + les 3 runs du sweep) et à la **constante Python** `MIN_CONTRIBUTION_UNCALIBRATED` |
| `lib/eval-sweep.ts` | **chargeur** server-only : sweep + plancher + catalogue ; hachage du catalogue **miroir du runner** ; dédup des alias ; refus du path-traversal sur `?run=` |
| `lib/eval-sweep.test.ts` | 7 fichiers → **3 runs** ; version calculée = `63-071edbdc` ; plancher lu 174/122 |
| `components/eval/score-card.tsx` | **LA** carte de score — aucune branche ne sait rendre un taux nu ; 3 honest-empties |
| `components/eval/scorecard-view.tsx` | recâblé sur le sweep ; en-tête référentiel + fraîcheur + plancher |
| `components/eval/run-picker.tsx` | sélecteur **sans aucun taux** (l'ancien affichait `· 90%`) |
| `scripts/sync-eval-bundle.mjs` | pont de build : embarque sweep + baseline + catalogue, évacue les 7 fichiers périmés |
| `lib/api/schemas.ts` | + baseline, + catalogue, + les 5 champs que **zod supprimait en silence** |

**Supprimés :** `lib/eval.ts` (le chargeur périmé) et `components/eval/best-run-highlight.tsx`
(il classait les runs par **taux absolu** — interdit par le critère 10, et le sweep prouve que ce
taux ne discrimine rien).

### Deux pièges trouvés et désamorcés

**zod supprimait la moitié de la fiche de cas.** `ScorecardResultSchema` ne déclarait ni
`duration_ms`, ni `input_tokens`, ni `output_tokens`, ni `started_at`/`ended_at`. Le JSON les
contient ; zod jette ce qu'il ne déclare pas. Le « contexte d'exécution » du §3 (bloc 4) était donc
**vidé en silence** avant d'atteindre le composant. Même classe que le `response_model` qui vidait
20 champs par agent.

**`invoked_tools` n'est PAS ce que le harnais évalue.** Le rapport stocke **tous** les appels
d'outils ; `_evaluate` n'évalue que les appels **réussis** (`if call.succeeded`). Un recalcul naïf
de `must_not_invoke_tools` depuis le rapport dirait donc « outil interdit invoqué » là où le harnais
dit *passé* (l'appel a été **refusé par le garde**). **Conséquence pour le lot 3** : seuls
`must_not_contain`, `must_contain_any`, `must_not_match` et `must_escalate` sont **fidèlement**
recalculables depuis le rapport. Les critères d'outils, `min/max_confidence` et `must_cite_source`
lisent des champs que le run **ne conserve pas** — ils seront affichés comme **rapportés par le
harnais, preuve non conservée**, jamais recalculés en douce.

### Vérification

- `lib/eval-score.test.ts` + `lib/eval-sweep.test.ts` : **31 tests**, tous verts, et ils
  **reproduisent les chiffres publiés** par `eval/reports/sweep/comparison.md` :
  `llama3.2:3b` → plancher 122, contribution **36/52**, **1 casse** (`56_policy_violation_disparage_bank|de`), **BLOQUÉ** ;
  `gemma3:27b` → **35/52**, **0 casse**, **PASSÉ** ; `llama3.3:70b` → 154/174, 4 casses candidates.
- Un test épingle **le point de tout l'écran** : *taux absolus identiques (157/174), verdicts
  opposés*. Si ce test passe un jour pour la mauvaise raison, c'est que l'écran s'est remis à
  classer sur le taux.
- Front complet : `lint` 0 erreur · `typecheck` propre · **282 tests** verts.

**Captures** : `/tmp/tessera-qualite/lot1-fr-admin.png`.
**Landé** : `origin/main = 588b094e` (gate-twice vert sur un seul arbre, vérifié par contenu).

---

## LOT 2 — l'ossature  ✅

**Deux onglets, pas trois.** Un dataset est un **artefact versionné** ; un run est un **événement**
(§P3). Ils se séparent. Le troisième onglet (`Comparaison`) arrive au **lot 4** : je refuse
d'afficher un onglet vide — une porte qui ne mène nulle part est un mensonge d'interface.

**Les onglets sont des LIENS, pas un `useState`.** Deux conséquences, toutes deux voulues : seul
l'onglet ouvert est rendu côté serveur (le catalogue fait 63 cas, un run 174 résultats — tout rendre
pour pouvoir basculer est du gâchis), et **un onglet est une URL qu'un opérateur peut envoyer**.

| Fichier | Rôle |
| --- | --- |
| `components/eval/eval-tabs.tsx` | réécrit : navigation par liens, `?tab=`, deep-linkable |
| `components/eval/catalogue-tab.tsx` | **onglet A** — les 63 cas par catégorie, dépliables, avec la fiche de définition |
| `components/eval/criterion-line.tsx` | une ligne de critère lisible, **partagée** avec la fiche d'exécution (lot 3) |
| `lib/eval-criteria.ts` + test | **module pur** — énumère les critères d'un cas et, surtout, dit lesquels sont **fidèlement recalculables** |

**La fiche de cas montre la preuve** : comportement attendu, critères en clair (« ne doit jamais
contenir : `FR76 3000…` »), **les prompts réellement envoyés dans les trois langues**, et la
**source citée avec son lien** (OWASP LLM Top 10, DORA, CNIL…). Cette évidence dormait dans
`eval/failures/*.json` et **aucune surface ne l'avait jamais montrée**.

**Supprimés :** `run-history-panel.tsx` et `scroll-link.tsx` (orphelins ; le panneau d'historique
affichait une colonne « Taux »).

**Un piège attrapé par le linter :** le namespace `eval` avait déjà une clé `catalogue` (une
**chaîne**), et j'y ajoutais un `catalogue` (un **objet**). `JSON.parse` garde le dernier —
l'une des deux aurait disparu **en silence**. Les clés mortes (`bestRun`, `catalogue`,
`catalogueCoverage`, consommées par les composants supprimés) sont retirées des trois langues.

**Captures** : `lot2-fr-jeu-de-cas.png`, `lot2-fr-fiche-cas.png`.
