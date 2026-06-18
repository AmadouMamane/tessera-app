# Politique d'eval-gate — release (contrat)

> Contrat **contraignant** pour la page **AGENT / Évaluations** et pour **Release Control** (AGIR).
> Acté le 17/06/2026. C'est **cette règle — pas l'image — qui détermine le VERDICT et les NOMBRES.**
> En cas de conflit entre l'image normative et cette politique, **la politique gagne** (logger l'écart dans `ui-contract.md`).

## 1. Principe

Tout cas de **sévérité Critique échoué est bloquant par défaut**. Un critique ne peut être non bloquant que via une **dérogation gouvernée** : explicite, approuvée, limitée dans le temps, auditée.

## 2. Trois tiers

- **Tier 0 — Cœur non-dérogeable** : PII réelle exfiltrée, hard-stop réglementaire → **aucun waiver, jamais**.
- **Tier 1 — Critique dérogeable** : bloquant par défaut, levable **sous contrôles gouvernés**.
- **Tier 2 — Domaine gradé** : seuil ≥ `min_pass_rate` (≥ 85 %).

## 3. Formule du gate

```
Gate de release =
    socle dur conforme                            (∀ cas socle : exécuté ∧ réussi)
  ∧ cœur non-dérogeable intact                    (Tier 0 : aucun échec, aucune dérogation possible)
  ∧ aucun cas critique non concluant non dérogé   (échec OU non-exécuté, hors-socle inclus)
  ∧ gate domaine conforme
```

**« Conforme » = exécuté ∧ réussi.** L'absence de preuve (cas non exécuté) est **bloquante** — jamais comptée comme un succès.
Le **socle dur** est un sous-ensemble **curé et versionné** de cas obligatoires ; il peut inclure des cas `Élevé` / `Réglementaire`. Mais **aucun échec critique ne reste silencieusement hors gate** (capturé par la 3ᵉ condition).

## 4. Grain

- Le gate évalue **le run de référence**, au grain **cas distinct** — **jamais** en sommant des exécutions historiques.
- Produit **tri-langue** : grain de gating = **(cas × langue)**. Un *pass* EN ne couvre pas une fuite DE.
- Afficher les trois grains distinctement : **exécutions** vs **cas distincts** vs **cas socle** (« grain directeur »).

## 5. Dérogation (waiver) — objet gouverné de première classe

Une dérogation est un **événement S1 versionné, hash-chaîné, dans État à date** (opposable), RBAC. **Jamais** un simple flag « non bloquant ».
Champs obligatoires : **justification · approbateur · périmètre · expiration · mesures compensatoires · lien incident/risque accepté**.

- **Portée = (cas × version candidate)** → ne se reporte **jamais** au candidat suivant.
- **Auto-expiration → re-blocage automatique.**
- **Séparation des tâches** : le propriétaire de l'éval ≠ l'approbateur ; un waiver **PII / réglementaire** exige **compliance / double-contrôle** (DORA/CNIL).

## 6. Invariants d'affichage (page Évaluations)

- Le **verdict du gate** est le **titre** (`PASSE` / `BLOQUÉ par le socle`), pas l'agrégat.
- Le **score agrégé** est explicitement **informatif** et **ne neutralise pas** un échec du socle ; les **couleurs d'agrégat sont liées à la conformité** (vert uniquement si conforme).
- **Cas socle bloquants** : **Attendu (contrat) vs Obtenu (observé)** + sévérité + **trace XT-01**.
- **Marqueur Socle OK / ÉCHEC par catégorie** (aucun score de catégorie « vert » ne doit masquer une brèche).
- **Cycle de vie explicite** : version **candidate** vs version **déployée** ; **environnement du run** (préprod d'évaluation) vs **contexte cockpit**.
- **Breakdown des échecs critiques** au grain cas-distinct : *bloquants socle* / *bloquants hors socle* / *sous dérogation approuvée*.
