# Registre des rails temporels — Tessera

> Section destinée à `docs/design/ui-contract.md` · v1.3 (2026-06-27)
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
| **TE-01** | Temporal Evidence Rail | Preuve opposable / reconstitution à T | `PROUVER / État à date` | S1 | C1 (as-of) | Normatif validé |
| **OT-01** | Object Trace Rail | Historique local d'un objet agent | Configurations, Connaissances, Garde-fous, Prompts | S1 | C1 (par-objet) | Partiel — Connaissances cadré |
| **AT-01** | Agent Activity Rail | Activité récente (feed) — *pas* les signaux | `AGENT / Synthèse` | S1 | C1 (feed) | À faire |
| **ER-01** | Evaluation Run Rail | Historique des runs d'évaluation | `AGENT / Évaluations` | S3 | C2 | À faire |
| **CT-01** | Conversation Timeline Rail | Chronologie conversationnelle | `AGENT / Historique` | S3 | C2 | À faire |
| **WF-01** | Workflow Case Rail | Cycle de traitement humain | `AGENT / À traiter`, `À faire` | S3 | C2 + état | À faire |
| **XT-01** | Execution Trace Rail | Trace technique d'une exécution | `AGENT / Console`, `AGIR / Replay` | S2 | C3 | À faire |
| **SR-01** | Signal Scrubber Rail | Surveillance continue dans le temps | `SURVEILLER` (toutes) | S4 | C4 | Implémenté |

> **SR-01 (état au 2026-06-27)** — implémenté comme `components/overview/temporal-rail.tsx`, rendu par les pages SURVEILLER (Vue d'ensemble, Qualité IA, Conformité, Sécurité & privacy). Modes **Live · Historique · Comparé (baseline) · À une date** — navigation de **signaux** uniquement (S4/C4). **Aucun replay d'exécution** : ce composant ne rejoue jamais un tour/trace (déplacement d'un curseur T sur les signaux persistés, lus as-of-T). Mode actif **toujours affiché** ; état dérivé de l'**URL** (deep-link `?asof=&win=`), pas d'un état local ; fenêtre (Période) lue depuis le **window-store partagé**, non dupliquée (§8). Le code de rail (`SR-01`) reste interne — **jamais affiché** (§ glossaire). Auparavant mal nommé « XT-01 » sur la Vue d'ensemble : corrigé.

> **XT-01 reste « À faire »** — son seul home est `AGENT / Console` et `AGIR / Replay` (trace d'exécution S2/C3, replay d'exécution). Il **n'est plus** sur la Vue d'ensemble. Le waterfall de trace de la Console (`TraceColumn`) en est l'amorce ; le rail XT-01 normatif complet (scrub de spans + replay) reste à spécifier/implémenter.

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

- `AGIR` : **As-of** (lire l'état à T, via `TE-01`) **+ Live** (agir maintenant).
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
| **Intégrité partielle** | chaîne valide **mais** sceau absent / non vérifiable | fiable en interne ; opposabilité tierce non garantie |
| **Non scellé** | échec d'intégrité (chaîne rompue) | état **non opposable** — à investiguer |
| *(transitoire)* **Vérification en cours** | `verify(chain)` non terminé | aucun statut d'opposabilité affiché tant que la vérif n'a pas abouti |

Mention obligatoire sous le badge : « *Statut attribué uniquement après vérification réussie.* »

> La numérotation `1 · 2 · 3 · A · D` n'est **pas** requise sur l'écran opérationnel (lecture en scan) ; elle est **réservée à l'export Evidence Pack** (artefact légal, lecture séquentielle type affidavit).

> **Règle de production** : ne pas régénérer une page validée pour ce genre d'évolution — encoder l'invariant ici. Une régénération risque de réintroduire des régressions (visuelles, textuelles ou de navigation).
