# Conformité de présentation — toutes les pages

> **Objet** : aligner la **présentation** (architecture d'information, densité, surfaçage
> gouvernance/audit, hero) de **toutes** les pages sur leurs normatives. Le **fond** est fait
> (données réelles, modèles T0/T1/T2, multi-agent, rails) — ici on **surface**, on ne refait pas.
> **Déclencheur** : l'écart diagnostiqué sur Évaluations (hero, auditabilité, barre de contexte,
> densité) — **généralisé** en rubric.
>
> **Règle d'or, priorité absolue** : on **surface du RÉEL**, **jamais** de fabrication. Et on **ne
> casse ni ne dé-câble** les données réelles/réconciliées déjà construites (ex. la réconciliation
> Évaluations `119 = 59 + 60`, le grain cas×langue, la chaîne de dérogations).

## 0. Le rubric P1–P6 (s'applique à CHAQUE page)

- **P1 — Chrome global dense (fix UNE fois, dans le shell)** : barre de contexte = **fil d'Ariane**
  (`AGENT/GOUVERNER/PLATEFORME › section › page`) + **switcher agent** + **tenant** + **env** + **rôle**
  + **statut** ; **footer** = « **Source de vérité : YAML · Git** » + **intégrité hash-chaînée vérifiée**
  + SOC/env + dernière vérif. → bénéficie à toutes les pages d'un coup.
- **P2 — Hero qui nomme les spécifiques** : chaque page **mène** avec son état clé et **nomme les items
  concrets** dans le bandeau (pas enfouis dans une table) + **remédiation/action directe**.
  (Éval : IDs T0 en échec + → AGIR Release Control · Garde-fous : top raisons de blocage · Surveiller :
  le signal franchi · Incidents : l'incident ouvert · Prouver : l'état opposable à T.)
- **P3 — Liens croisés (« Liens utiles »)** : chaque page lie sa **définition** (→ CONFIGURER), sa
  **gouvernance** (→ AGIR), ses **données liées** (Connaissances / Garde-fous appliqués). Rend le control
  plane **navigable et opposable**.
- **P4 — Densité riche MAIS lisible** : multi-panneaux, sparklines/donuts, traces (XT-01) où pertinent.
  Vise l'information-par-écran du normatif — **sans** copier sa micro-typo illisible. **Dense ET lisible.**
- **P5 — Profondeur de gouvernance** : rôles (approbateur **HoS/DPO**, **RBAC**), **versions**,
  **intégrité / hash-chaîne visible**, modes temporels (Live/Historique/As-of). Surface ce qui rend l'état
  **opposable**.
- **P6 — Vocabulaire cohérent** : « cœur non dérogeable », « gate », « socle », « opposable », « as-of »,
  « dérogation gouvernée » — homogène entre pages.

## 1. Honnêteté (non négociable)

P1–P6 = **surfacer ce qui existe**, jamais inventer. Un hero/panneau/lien **sans source réelle** →
**omettre ou état vide + log**, jamais une valeur fabriquée pour « matcher la maquette ». Et **ne pas
casser** une donnée réconciliée déjà en place. La maquette est normative pour la **forme**, jamais pour les
**données**.

## 2. Méthode (autonome, §9, vrai côte-à-côte)

- **D'ABORD le global (P1)** : barre de contexte + footer dans le shell — **une fois**, vérifie sur 2-3 pages.
- **PUIS page par page** : capture live au viewport de la normative → **composite capture | image** →
  applique **P2–P6** en **étendant** (jamais régénérer) → **auto-revue §9** (réel/vide ; cohérence
  numérique ; chrome intact ; invariants) → **gate vert** (ruff + ruff format + mypy --strict + tsc + tests)
  → **1 commit/page** → capture après.
- **GOUVERNER / PLATEFORME** : applique **AUSSI** `docs/design/multi-agent-gouverner-plateforme.md`
  (filtre agent global ≠ switcher · totaux dédupliqués) — **présentation + multi-agent ensemble**.
- **Autonome jusqu'au bout, AUCUN stop.** Déviations consignées dans `ui-contract.md`.

## 3. Ordre (priorité portfolio)

1. **Chrome global (P1)** — barre de contexte + footer auditabilité.
2. **Évaluations** — la page-vitrine ; finir P2–P6 (hero IDs+remédiation, Liens utiles, rôles d'appro,
   densité, « cœur non dérogeable »).
3. **AGENT restantes** : Synthèse · Garde-fous · Console · Connaissances · Configurations · Prompts · Historique.
4. **GOUVERNER** (Surveiller · Agir/**Release Control en tête** · Prouver) **+ PLATEFORME** (Configurer · Admin) :
   multi-agent (autre doc) **+** P1–P6.

## 4. Normatives

Une par page, dans `docs/ui-reference/` : pages **AGENT** → `multiagents/` (+ `agent/` pour Historique) ;
pages **cockpit** (Surveiller/Agir/Prouver/Configurer/Admin) → les images numérotées `00`–`14` +
`qualite-ia-ui-reference/`. Mappe chaque page à sa normative avant de l'attaquer ; si plusieurs variantes,
prends la plus récente (et logge le choix).

## 5. Super-prompt (à coller — nouvelle session OK)

```
RÔLE — Session sur le dépôt Tessera (control plane multi-agent, support bancaire UE). Mission :
CONFORMITÉ DE PRÉSENTATION sur TOUTES les pages, en autonomie jusqu'au bout (je bosse ailleurs).
Le fond est fait (données réelles, T0/T1/T2, multi-agent, rails) — tu SURFACES, tu ne refais pas.

LIS D'ABORD : CLAUDE.md ; docs/design/presentation-conformance.md (ce protocole : rubric P1–P6,
ordre §3) ; docs/design/ui-contract.md ; docs/design/conformance-pages-normatives.md (méthode + §9) ;
docs/design/multi-agent-gouverner-plateforme.md (pour GOUVERNER/PLATEFORME) ;
docs/design/eval-gate-policy.md (Évaluations). Restitue rubric + ordre, puis go.

RÈGLE D'OR : surfacer du RÉEL, JAMAIS fabriquer ; ne casse pas les données réconciliées déjà en place.
Maquette = normative pour la FORME, pas pour les données. Panneau sans source réelle → vide + log.

RUBRIC (chaque page) : P1 chrome global dense (fil d'Ariane + switcher + tenant + env + rôle + statut ;
footer Source de vérité YAML·Git + intégrité hash vérifiée) — fix UNE fois dans le shell.
P2 hero qui NOMME les items en échec/clés + remédiation directe (→ AGIR). P3 « Liens utiles » croisés
(→ CONFIGURER définition, → AGIR gouvernance, → données liées). P4 densité riche MAIS lisible
(panneaux/sparklines/donuts/traces) — pas la micro-typo du mockup. P5 profondeur gouvernance
(rôles HoS/DPO, RBAC, versions, hash-chaîne visible, modes temporels). P6 vocabulaire cohérent.

ORDRE : 1) chrome global P1 ; 2) Évaluations (finir P2–P6) ; 3) AGENT restantes (Synthèse, Garde-fous,
Console, Connaissances, Configurations, Prompts, Historique) ; 4) GOUVERNER (Surveiller, Agir/Release
Control en tête, Prouver) + PLATEFORME (Configurer, Admin) avec multi-agent + P1–P6.

MÉTHODE (boucle, AUCUN stop) : par page → capture live + composite capture|image (côte-à-côte) →
applique P2–P6 en ÉTENDANT → auto-revue §9 (réel/vide, cohérence numérique, chrome intact, pour
GOUVERNER/PLATEFORME : filtre≠switcher + totaux dédup) → gate vert (ruff + ruff format + mypy --strict +
tsc + tests) → 1 commit/page (Conventional Commits) → capture après → déviations dans ui-contract.md.
Normatives dans docs/ui-reference/ (AGENT → multiagents/ ; cockpit → 00–14 + qualite-ia-ui-reference/).
NE POUSSE PAS.

À LA FIN — RAPPORT unique, par page : statut, P1–P6 appliqués, données réel/vide, invariants tenus,
e2e ou non, déviations. Évaluations + chrome global + Release Control en tête.
```
