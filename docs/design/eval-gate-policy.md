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

## 7. Invariants flotte (rollup multi-agents)

Un rollup de flotte ne doit **jamais** présenter trois évaluations **indépendantes** comme un instantané unique cohérent. Chaque agent est un **package gouverné indépendamment** (ADR 0010) : son run est **décalé dans le temps**, scoré contre **sa propre version de catalogue** sur **son propre set domaine**.

- **Portée par chiffre.** Un **verdict de release** et un **taux de réussite** appartiennent à **un agent**, jamais à la flotte. Le **seul** chiffre de flotte légitime est le **rollup de verdict** : le nombre d'agents libérables (gate au vert) sur ceux ayant un run. **Aucun « % » de flotte agrégé** (un taux mélangé ne mappe à aucun agent et le « sans-blocage » sur-vend la réussite).
- **Comparabilité cross-agent = socle uniquement.** Le **socle** (mêmes cas pour chaque agent) est le **seul** comparatif inter-agents. Les **taux domaine** sont étiquetés **« contre son propre set »** — **jamais** un classement entre agents.
- **Provenance obligatoire.** Chaque chiffre porte sa **date de run** + sa **version de catalogue** (« onboarding · 17/06 · cat v25 »). Pas de « dernière éval » unique de flotte qui masque la staggération.
- **Verdict périmé.** Si un agent a été évalué contre une version de catalogue **supersédée** (`catalogue_version` du run ≠ version applicable courante, calculée depuis la **vraie** source : manifeste eval-set + catalogue de cas), marquer **« verdict périmé · re-éval requise »** — jamais un nombre inventé.
- **Source vivante.** Lanceur = cockpit = rapports : tous lisent la **même source courante** (`eval/reports/` vivant). Le **fallback bundlé** (image prod) est **régénéré depuis le dernier run au build** (`pnpm sync:eval` / `prebuild`), jamais un snapshot figé.
- **Frontière publique (ADR 0009).** Verdict + date + version + taux + socle = **public-safe**. La **catégorie d'échec** (PII, injection…) reste **operator-only** — le « pourquoi » vit dans le cockpit gardé.
