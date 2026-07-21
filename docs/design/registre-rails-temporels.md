# Registre des rails temporels — Tessera

> Section destinée à `docs/design/ui-contract.md` · v1.5 (2026-07-21)
>
> v1.5 — audit complet des 8 rails contre le code (SR-01 confirmé conforme et pris comme norme
> de référence, validée produit). Le registre se trompait dans les deux sens : TE-01 passe à
> **Implémenté** (la page État à date existait au complet ; le deep-link `?asof=` et la puce de
> mode, seuls manquants, sont posés) ; AT-01 et CT-01 passent à **Partiel** (feed et timeline
> réels, branchés) ; OT-01 est requalifié (la note v1.4 « Connaissances cadré » ne décrivait pas
> la réalité). Trois mensonges d'UI purgés au passage : le mode « État à date » cosmétique de la
> Synthèse (bandeau « données reconstituées » sur des données live), les boutons as-of/comparer
> sans `onClick` des snapshots Garde-fous/Prompts, et l'historique overlay servi mais jamais
> rendu (Prompts, désormais affiché). Notes datées par rail ci-dessous ; §9 documente le 5e état
> de badge que le code expose depuis Hica.
>
> v1.4 — ER-01 passe à **Implémenté** (rail des runs d'évaluation, page AGENT / Évaluations) : `webapp/frontend/components/agent/evaluation-run-rail.tsx`, payload `src/tessera/observability/agent_evaluations.py` (`_runs_rail`).
>
> v1.3 — SR-01 passe à **Implémenté** (scrubber de signaux SURVEILLER) ; le rail de la Vue d'ensemble, jadis mal nommé « XT-01 » et porteur d'un « rejeu », est réaligné sur SR-01 (modes Live/Historique/Comparé/À une date, zéro replay d'exécution, deep-link URL). XT-01 reste « À faire » sur son home Console/AGIR.

## 1. Principe

Un **rail temporel** est un composant de navigation dans le temps, réutilisable et adressable par code (`TE-01`, …).

- **Reproductibilité** — chaque rail est une **projection déterministe** d'un substrat **append-only, horodaté, taggé `agentId`**. Même `(rail, scope, T)` ⇒ même vue, re-vérifiable.
- **Modularité** — les rails qui lisent le **même substrat** partagent le **même composant de base**. On construit **4 composants**, pas 8 rails.
- **Contexte global borné** — le sélecteur « voir à date » (instant `T` / plage) peut être propagé par l'URL et suivre l'utilisateur, **mais** chaque page doit **afficher explicitement le mode actif** : `Live`, `Historique`, `As-of` ou `Replay`. **Aucune page ne bascule implicitement en mode historique sans indicateur visible.**

Règle de placement : **config → versions · signaux → scrubber (Surveiller) · preuve → as-of (Prouver).**

## 2. Substrats

| Code | Substrat | Propriétés |
|------|----------|------------|
| **S1** | Journal config / état | bitemporal (valid/transaction), **hash-chaîné**, append-only |
| **S2** | Traces d'exécution (spans / inférence) | append-only ; capture des entrées **nécessaires au replay** : retrieval, prompt assemblé, params, tools, modèle, runtime, seed *si disponible* |
| **S3** | Journaux métier (runs, conversations, cases) | append-only, événements non réécrits |
| **S4** | Séries de signaux / métriques | time-series (rétention, agrégation, downsampling) |

## 3. Composants de base

| Code | Composant | Lit | Projections |
|------|-----------|-----|-------------|
| **C1** | Fold engine | S1 | as-of · par-objet · feed récent |
| **C2** | Timeline-over-X | S3 | liste ordonnée + filtres (WF : + machine à états) |
| **C3** | Trace viewer | S2 | arbre de spans d'une exécution |
| **C4** | Signal Scrubber | S4 | Live · Historique · **Baseline** · comparaison de périodes |

> **Replay = AGIR uniquement** (via `XT-01`). Le C4 ne rejoue pas une exécution : il navigue dans les signaux et compare des périodes.

## 4. Registre des rails

États : `Proposé` · `Cadré` (spécifié) · `Normatif validé` (design validé, impl. non confirmée) · `Implémenté` (code complet) · `À faire`.

| Code | Nom canonique | Usage | Pages | Substrat | Composant | État |
|------|---------------|-------|-------|----------|-----------|------|
| **TE-01** | Temporal Evidence Rail | Preuve opposable / reconstitution à T | `PROUVER / État à date` | S1 | C1 (as-of) | Implémenté |
| **OT-01** | Object Trace Rail | Historique local d'un objet agent | Configurations, Connaissances, Garde-fous, Prompts, Sources & mémoire | S1 | C1 (par-objet) | Partiel — amorces (note) |
| **AT-01** | Agent Activity Rail | Activité récente (feed) — *pas* les signaux | `AGENT / Synthèse` | S1 | C1 (feed) | Partiel — feed implémenté |
| **ER-01** | Evaluation Run Rail | Historique des runs d'évaluation | `AGENT / Évaluations` | S3 | C2 | Implémenté |
| **CT-01** | Conversation Timeline Rail | Chronologie conversationnelle | `AGENT / Historique` | S3 | C2 | Partiel — timeline implémentée |
| **WF-01** | Workflow Case Rail | Cycle de traitement humain | `AGENT / À traiter`, `À faire` | S3 | C2 + état | À faire — substrat manquant (note) |
| **XT-01** | Execution Trace Rail | Trace technique d'une exécution | `AGENT / Console`, `AGIR / Replay` | S2 | C3 | À faire — amorces (note) |
| **SR-01** | Signal Scrubber Rail | Surveillance continue dans le temps | `SURVEILLER` (toutes) | S4 | C4 | Implémenté |

> **SR-01 (état au 2026-06-27)** — implémenté comme `components/overview/temporal-rail.tsx`, rendu par les pages SURVEILLER (Vue d'ensemble, Qualité IA, Conformité, Sécurité & privacy). Modes **Live · Historique · Comparé (baseline) · À une date** — navigation de **signaux** uniquement (S4/C4). **Aucun replay d'exécution** : ce composant ne rejoue jamais un tour/trace (déplacement d'un curseur T sur les signaux persistés, lus as-of-T). Mode actif **toujours affiché** ; état dérivé de l'**URL** (deep-link `?asof=&period=` — le paramètre de fenêtre s'appelle `period`, corrigé v1.5, plus `at`/`to`/`compare`), pas d'un état local ; fenêtre (Période) lue depuis le **window-store partagé**, non dupliquée (§8). Le code de rail (`SR-01`) reste interne — **jamais affiché** (§ glossaire). Auparavant mal nommé « XT-01 » sur la Vue d'ensemble : corrigé.

> **XT-01 reste « À faire »** — son seul home est `AGENT / Console` et `AGIR / Replay` (trace d'exécution S2/C3, replay d'exécution). Il **n'est plus** sur la Vue d'ensemble. Le waterfall de trace de la Console (`TraceColumn`) en est l'amorce ; le rail XT-01 normatif complet (scrub de spans + replay) reste à spécifier/implémenter.

> **ER-01 (état au 2026-07-15)** — implémenté comme `webapp/frontend/components/agent/evaluation-run-rail.tsx`, rendu par `AGENT / Évaluations` ; payload `runs` de `src/tessera/observability/agent_evaluations.py` (`_runs_rail`). Il parcourt les **runs d'évaluation** de l'agent (S3/C2 — journal de runs lu depuis `eval/reports/<env>/`, convergent avec la table `eval_gating` mesurée le 2026-07-15 : 29/29 runs partagés identiques) — **pas** les signaux (domaine du SR-01, S4/C4), **aucun replay**. Chaque point = un run portant sa **provenance stockée** (date + version de catalogue + modèle, `eval-gate-policy.md` § provenance — jamais une « dernière éval » unique) et le **verdict gate enregistré au moment du run** (absent = « non enregistré », jamais recalculé contre les dérogations d'aujourd'hui). Modes **Live (dernier run) · Historique (run sélectionné)**, toujours affichés ; sélection dérivée de l'**URL** (deep-link `?run=<run_at>`), jamais d'un état local. Honest-empty : agent sans run ⇒ rail explicitement vide (« Éval non exécutée ») ; 1 run ⇒ 1 point sans tendance ; **Δ** de taux seulement entre **deux** runs de la **même** version de catalogue. Le code de rail (`ER-01`) reste interne — **jamais affiché**. Portes d'entrée : la Vue par agent (lentille qualité de `SURVEILLER / Qualité IA`) et la Flotte mènent à la page Évaluations de l'agent.

> **TE-01 (état au 2026-07-21) — Implémenté.** Page `PROUVER / État à date` complète :
> `components/proofs/etat-a-date.tsx` + `observability/etat_a_date.py` (`build_etat_a_date`,
> projection as-of réelle) ; badge d'opposabilité **calculé à l'affichage** par
> `active_ledger_opposability(at=T)`, mention obligatoire rendue, honest-empty partout, e2e
> `etat-a-date.spec.ts`. Les deux derniers écarts à la norme sont clos en v1.5 : l'instant T est
> **dérivé de l'URL** (`?asof=`, partageable, honoré aussi par le prefetch serveur) comme
> `?sources=` et `?agent=`, et le **mode est une puce toujours visible** (`meta.as_of_label`,
> Live vert / instant violet) à côté du badge.

> **AT-01 (état au 2026-07-21) — Partiel.** Le **feed C1 est implémenté et réel** :
> `agent_synthese.py` (`_scan_journal` sur le journal S1 hash-chaîné + tours du transcript,
> `_activity_rows`), rendu sur `AGENT / Synthèse` ; honest-empty ; aucun signal d'éval dans le
> feed (la règle §7 tient). En v1.5 le rail a été **réduit à ce qu'il honore** : Live + Période.
> Le segment « Voir à date » et son bandeau « données reconstituées au point sélectionné »
> mentaient — `compute_agent_synthese` n'a **aucun paramètre as-of** (fenêtre glissante finissant
> maintenant) ; le segment « Comparaison » était un texte statique. Promotion à Implémenté =
> borner `_fetch_transcript`/`_scan_journal` par `until=T`, passer T du client au backend, et
> alors seulement ré-offrir le mode.

> **CT-01 (état au 2026-07-21) — Partiel.** La **timeline tour-par-tour est implémentée et
> réelle** : `agents/[agentId]/historique/[sessionId]/page.tsx` (sélection par l'URL de route),
> payload `observability/session_detail.py` sur le transcript durable (ADR 0040), honest-empty,
> distinction denied/empty (F-4). v1.5 la **désorpheline** : chaque conversation du bloc
> « Conversations en direct » (`agent-historique.tsx`) est un lien vers sa chronologie, la plus
> récente porte « Dernière », la page détail affiche la puce de mode « Historique · conversation
> sélectionnée », et `transcript.list_conversations` **exclut enfin les tours synthétiques**
> (un essai d'opérateur ne se présente plus comme une conversation client). Promotion =
> filtres C2 sur la timeline et sortie du fixture éval qui partage l'écran.

> **OT-01 (état au 2026-07-21) — Partiel, requalifié.** La note v1.4 (« Connaissances cadré »)
> ne décrivait pas la réalité : le seul bloc **Versions** réel (runs d'ingestion + honest-empty)
> vit sur **CONFIGURER / Sources & mémoire** (`sources-overview.tsx` `VersionsBlock`,
> `sources.py` `_corpus_versions`) — home ajouté au tableau. **Garde-fous** et **Prompts**
> rendent le rail **SR-01** (signaux S4) — ce n'est pas un OT-01 ; leurs snapshots portaient des
> contrôles as-of/comparer **sans `onClick`**, retirés en v1.5 (un contrôle qui promet un as-of
> inexistant est un mensonge). **Prompts** : l'historique du cycle overlay (ADR 0037 — proposé /
> approuvé / rejeté / révoqué, chaque événement nommant son auteur) était servi par le backend et
> jamais rendu — **affiché depuis v1.5** ; c'est la première vraie trace par-objet à l'écran.
> **Configurations** : l'historique mêlait tous les agents — **filtré per-objet** (`agent_id`)
> en v1.5, les mtimes de fichiers dépôt restant comme provenance commune. Promotion = un vrai
> C1 par-objet (versions consultables à T) sur chaque home.

> **WF-01 (état au 2026-07-21) — À faire, le substrat manque.** Le magasin d'état des cas
> (`operator_items.py`, `operator_items_state.json`) est à **écrasement** : `set_item_state`
> mute l'entrée et réécrit le fichier — aucune liste de transitions horodatées, et les deux
> endpoints de transition (`mutations.py`) ne capturent **pas l'auteur** (pas de session, pas
> d'émission gouvernance — écart ADR 0024). L'onglet Historique du drawer l'avoue (« Les
> transitions de statut ne sont pas journalisées »). Un rail est une projection d'un substrat
> append-only (§1) : sans journal de transitions `{from, to, at, by}`, WF-01 ne peut pas
> exister. Déjà bons et à conserver : partition par nature (ADR 0038), horloge SLA depuis
> l'entrée en file (ADR 0039), badge d'état courant, mode Live affiché, honest-empty.

> **XT-01 (état au 2026-07-21) — À faire, amorces précisées.** `agir-rail.tsx` n'est **pas**
> XT-01 : c'est l'implémentation conforme de la **composition §6** (As-of + Live, `?asof` URL,
> mode affiché, mutations gelées à T) rendue sur curation / automations / replay-shadow. La
> Console rend un **waterfall plat** du tour live (`TraceColumn` — pas d'arbre parent/enfant
> persisté) ; les spans OTel partent vers des backends externes (pas de magasin S2 relisible par
> exécution). Le **backend replay existe** (`replay.py` : bundles append-only, `POST
> /observability/replay`, re-génère + re-juge avec `score_delta`) mais la capture S2 est
> incomplète (prompt assemblé, params, tools, seed absents du `ReplayBundle`) et la **lentille
> replay UI reste due** — la page AGIR / Replay est un dashboard analytique, aucune cassette.
> Chemin : compléter la capture S2 → lentille replay (mode « Replay » affiché, dérivé de l'URL)
> → arbre C3.

## 5. Contrat de composant (commun)

```
Rail({
  code,                                         // TE-01 … SR-01
  scope: { tenant, agentId, objectId? },
  time:  { mode, T?, range? },                  // mode = live | historique | as-of | baseline | replay
  source                                        // substrat S1…S4
})
```

Le **mode actif est toujours affiché** dans le rail, et l'état/surlignage **dérive de l'URL** (deep-link), jamais d'un état local.

## 6. Compositions autorisées

- `AGIR` : **As-of** (lire l'état à T, via `TE-01`) **+ Live** (agir maintenant) — implémentée
  par `components/agir/agir-rail.tsx` (`?asof` URL, mode affiché, mutations gelées à T ; rendu
  sur curation, automations, replay-shadow).
- `Console` : **XT-01** (trace de l'exécution de test) **+ Live**.

## 7. Garanties de reproductibilité & écarts

- **S1** — reproductible (immuable, hash-chaîné). Base de `TE-01` / `OT-01` / `AT-01`.
- **S2 / XT-01** — `XT-01` permet de **rejouer ou diagnostiquer** une exécution ; il **ne garantit pas toujours une sortie strictement identique** si le runtime modèle n'est pas déterministe (API, non-déterminisme matériel). On capture tout le nécessaire ; la repro bit-à-bit n'est pas promise.
- **S3** — reproductible **si** les événements métier sont append-only et non réécrits.
- **S4** — ne garantit la reproductibilité que **sur la période de rétention brute** ; au-delà, les vues peuvent dépendre d'**agrégats** (downsampling).
- **AT-01** — ne doit **pas** afficher de *signaux* (domaine de Surveiller) → feed d'activité uniquement + lien vers Surveiller.
- **SR-01** — ne rejoue pas une exécution. Il permet de **naviguer dans les signaux, comparer des périodes et contextualiser des anomalies**. Le replay d'exécution appartient à AGIR via `XT-01`.

## 8. Séparation des responsabilités

| Domaine | Rôle temporel |
|---------|---------------|
| **SURVEILLER** | scrubber de **signaux** (Live · Historique · Baseline) |
| **PROUVER** | **état opposable à T** (as-of) |
| **AGIR** | **replay d'exécution** |
| **AGENT** | **activité & historique opérationnel** |

## 9. Badge d'opposabilité (TE-01 / État à date)

Le badge est **dynamique** : calculé **à l'affichage** à partir du résultat de la vérification — jamais stocké, jamais cosmétique.

| Badge | Condition | Implication |
|-------|-----------|-------------|
| **Scellé · opposable** | chaîne de hash vérifiée **ET** sceau tiers (Hica) vérifié | état pleinement opposable |
| **Scellé (non qualifié)** | chaîne vérifiée **ET** sceau tiers vérifié, mais TSA **non qualifié** eIDAS | opposable techniquement ; qualification juridique du sceau non établie *(état exposé par le code depuis Hica, documenté v1.5)* |
| **Intégrité partielle** | chaîne valide **mais** sceau absent / non vérifiable | fiable en interne ; opposabilité tierce non garantie |
| **Non scellé** | échec d'intégrité (chaîne rompue) | état **non opposable** — à investiguer |
| *(transitoire)* **Vérification en cours** | `verify(chain)` non terminé | aucun statut d'opposabilité affiché tant que la vérif n'a pas abouti |

Mention obligatoire sous le badge : « *Statut attribué uniquement après vérification réussie.* »

> La numérotation `1 · 2 · 3 · A · D` n'est **pas** requise sur l'écran opérationnel (lecture en scan) ; elle est **réservée à l'export Evidence Pack** (artefact légal, lecture séquentielle type affidavit).

> **Règle de production** : ne pas régénérer une page validée pour ce genre d'évolution — encoder l'invariant ici. Une régénération risque de réintroduire des régressions (visuelles, textuelles ou de navigation).
