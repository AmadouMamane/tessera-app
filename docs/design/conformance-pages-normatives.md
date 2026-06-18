# Conformité UI — pages AGENT vs images normatives

> **Objet** : aligner l'implémentation des pages **AGENT** sur les **images normatives multi-agent
> du 17/06/2026** (`docs/ui-reference/multiagents/`), **une page à la fois**, en méthode **côte à côte**.
> **Périmètre** : **Vague 1** = 6 pages ; **Vague 2** (à enchaîner après validation des 6) = Évaluations + Historique.
> **Discipline** : on n'invente pas, on **aligne** ; on **étend**, on ne régénère pas ; l'image est normative
> pour la **structure / IA / libellés / états**, **jamais** pour les **données**.

## 0. État réel constaté (17/06)

Le **shell deux couches est déjà en place** (décision Option 1) :

- `app/[locale]/agents/layout.tsx` monte **`AppShell` une seule fois** (sidebar settled + topbar global + switcher d'agent + « Voir la flotte »).
- `app/[locale]/agents/[agentId]/layout.tsx` porte **`AgentTabs`** (command-bar) + titre/sous-titre + corps.
- Les `page.tsx` AGENT **ne montent plus `AppShell`**.

**Conséquence** : la conformité se joue au **niveau du corps** de chaque page, **pas du chrome**.
Ne touche pas au sidebar / topbar / command-bar — sauf si une image révèle un écart de chrome explicite ;
dans ce cas, corrige **dans le layout**, jamais page par page.

## 1. Périmètre & mapping (source de vérité = l'image)

### Vague 1 — les 6 pages

| # | Page AGENT | Route (fichier) | Image normative (17/06) |
|---|------------|-----------------|--------------------------|
| 1 | Synthèse | `agents/[agentId]/synthese/page.tsx` | `multiagents/25-agent-synthese-multi-agent-normative.png` |
| 2 | Configurations | `agents/[agentId]/configurations/page.tsx` | `multiagents/04-multi-agent-configuration-normative.png` |
| 3 | Connaissances | `agents/[agentId]/connaissances/page.tsx` | `multiagents/03-agent-connaissance-multi-agent-normative.png` (+ `03-b-…` = 2ᵉ vue) |
| 4 | Garde-fous | `agents/[agentId]/garde-fous/page.tsx` | `multiagents/06-multi-agent-garde-fous-normative.png` |
| 5 | Prompts | `agents/[agentId]/prompts/page.tsx` | `multiagents/07-multi-agent-prompt-normative.png` |
| 6 | Console | `agents/[agentId]/console/page.tsx` | `multiagents/05-multi-agent-console-normative.png` |

### Vague 2 — à enchaîner après les 6 (sur ma validation)

| # | Page AGENT | Route (fichier) | Image normative | Note |
|---|------------|-----------------|------------------|------|
| 7 | Évaluations | `agents/[agentId]/evaluations/page.tsx` | `multiagents/09-multi-agent-evaluations-normative-fina.png` | **Sémantique liée à `docs/design/eval-gate-policy.md` (contraignant)** : l'image fixe le **layout**, la **politique de gate** fixe le **verdict et les nombres**. En cas de conflit, **la politique gagne** → logger l'écart. |
| 8 | Historique | `agents/[agentId]/historique/page.tsx` (+ `[sessionId]`) | liste : `agent/30-assistant-historique-sessions-normative-new.png` · détail : `qualite-ia-ui-reference/301assistant-historique-sessions-details-normative-new.png` | **Images mono-agent** (pas de version multi-agent) → applique l'invariant multi-agent : **le détail de session montre quel agent a répondu à quel tour** (`agent_id` par message). Si une image multi-agent plus récente est déposée, elle prime. |

## 2. Sources contraignantes (ordre de lecture)

1. L'**image normative** de la page (table §1) — **source de vérité** visuelle et structurelle.
2. `docs/design/ui-contract.md` — IA, portée, rails, modèle multi-agent, éditabilité.
3. `docs/design/registre-rails-temporels.md` — le **rail temporel** que la page doit rendre.
4. `docs/design/eval-gate-policy.md` — **(Évaluations uniquement)** contrat de gate : verdict, tiers, dérogation, grain.
5. `CLAUDE.md` — disciplines repo (🟢 avant tool call, Conventional Commits, ne pas régénérer une page validée).

## 3. Invariants non négociables (ne jamais casser en alignant)

- **Chrome** : sidebar settled `AGENT / GOUVERNER / PLATEFORME` (super-en-têtes non cliquables) ; switcher d'agent + « Voir la flotte des agents » ; topbar global. Ça vit dans les **layouts**, pas dans les pages.
- **Nav URL-driven** : surlignage actif **dérivé de l'URL** ; pages deep-linkables ; aucun `cockpit/gouverner/plateforme` dans l'URL.
- **Rails temporels** : chaque page rend **son** rail — Synthèse → `AT-01` ; Configurations / Connaissances / Garde-fous / Prompts → `OT-01` ; Console → `XT-01` ; Évaluations → `ER-01` ; Historique → `CT-01`. Modes explicites (Live / Historique / As-of). **« Voir à date » ≠ « Replay »** (Replay = AGIR).
- **Portée define / choose / govern** : AGENT = instance (picker **borné**, jamais free-text) · CONFIGURER = catalogue (lecture seule ici) · muter en prod = **action gouvernée** (RBAC + événement versionné + audit).
- **Multi-agent** : `agentId` via `useAgentId()` / `agentPath()` ; attribution **`agent_id` par message** (per-turn).

## 4. Règle données vs image (LA règle à ne pas rater)

L'image normative fixe : **IA, structure, disposition des blocs, libellés / microcopy, états (vide / chargement / erreur), composants, densité**.
Elle ne fixe **PAS** les données.

- Les **chiffres et exemples de l'image sont illustratifs** → **interdiction de les coder en dur**. Chaque valeur affichée se **lie au backend réel** (mêmes sources que les pages déjà câblées).
- À la livraison, **distinguer explicitement** : « *valeurs affichées = réelles* » vs « *interactions = câblées* », et dire **lequel tient** (cf. `docs/functional-page-playbook.md`). **Jamais** une fixture déterministe qualifiée de « réelle ».
- Si l'image montre un état riche mais que la donnée réelle est vide → rendre l'**état vide réel**, pas une maquette de données.

## 5. Méthode — boucle de conformité, UNE page à la fois

Pour chaque page (ordre §7) :

a. **Rends la page live** (dev server, `webapp/frontend`) au **viewport de l'image** (largeur native de la PNG, ≈ 1536 px), avec un **agent seedé** pour ne pas tomber sur du vide ; **capture**.
b. Ouvre l'**image normative** et place **capture + image côte à côte**.
c. Produis l'**inventaire d'écarts** (§6) — **AVANT toute ligne de code**. **STOP**, attends validation.
d. **Implémente** les corrections : *aligner* en **étendant** les composants existants ; encoder les invariants ; **ne pas régénérer** la page de zéro.
e. **Re-capture** et replace **côte à côte (avant → après → normative)** ; prouve la conformité ; **logue tout écart intentionnel** (et son pourquoi) dans `ui-contract.md`.
f. **STOP** — récap + diff ; **1 commit / page** (Conventional Commits) ; attends validation avant la page suivante.

## 6. Inventaire d'écarts (gabarit, par page)

| Zone | Image normative | Implémentation actuelle | Type | Action |
|------|------------------|--------------------------|------|--------|
| en-tête & titre | … | … | STRUCTURE/IA · COPY · ÉTAT · DONNÉES · VISUEL | aligner · lier au backend · garder + justifier |
| rail temporel | | | | |
| KPIs | | | | |
| tableau(x) | | | | |
| panneaux latéraux | | | | |
| états (vide / chargement / erreur) | | | | |
| libellés / microcopy | | | | |
| actions / boutons | | | | |
| espacement / couleur / densité | | | | |

- **Type** ∈ {STRUCTURE/IA, COPY, ÉTAT, DONNÉES, VISUEL}.
- **Action** ∈ {aligner sur l'image · lier au backend (données) · garder + justifier → déviation loggée dans `ui-contract.md`}.

## 7. Ordre & livrable

**Ordre Vague 1** (du plus structurant au plus simple) : **Synthèse → Configurations → Connaissances → Garde-fous → Prompts → Console**.
**Ordre Vague 2** (après validation des 6) : **Évaluations → Historique**.

**Livrable par page** : (1) inventaire d'écarts validé ; (2) captures avant / après + image normative ; (3) diff de code ; (4) écarts intentionnels loggés dans `ui-contract.md` ; (5) 1 commit.

## 8. Super-prompt à coller

```
RÔLE — Tu alignes l'implémentation des pages AGENT de Tessera sur leurs IMAGES NORMATIVES
multi-agent (docs/ui-reference/multiagents/, datées 17/06), en méthode CÔTE À CÔTE.

LIS D'ABORD (contraignant) : docs/design/conformance-pages-normatives.md (le protocole),
docs/design/ui-contract.md, docs/design/registre-rails-temporels.md, CLAUDE.md.
Pour Évaluations uniquement : docs/design/eval-gate-policy.md.
Restitue ta compréhension + la liste des pages et leur image, puis ATTENDS ma validation.

PÉRIMÈTRE :
  VAGUE 1 (les 6) : Synthèse, Configurations, Connaissances, Garde-fous, Prompts, Console.
  VAGUE 2 (à enchaîner APRÈS validation des 6) : Évaluations, puis Historique.

MAPPING IMAGE -> PAGE (docs/ui-reference/) :
  Synthèse        multiagents/25-agent-synthese-multi-agent-normative.png
  Configurations  multiagents/04-multi-agent-configuration-normative.png
  Connaissances   multiagents/03-agent-connaissance-multi-agent-normative.png (+ 03-b-... = 2e vue)
  Garde-fous      multiagents/06-multi-agent-garde-fous-normative.png
  Prompts         multiagents/07-multi-agent-prompt-normative.png
  Console         multiagents/05-multi-agent-console-normative.png
  Évaluations     multiagents/09-multi-agent-evaluations-normative-fina.png
                  + SÉMANTIQUE contraignante = docs/design/eval-gate-policy.md (en cas de conflit, la policy gagne)
  Historique      agent/30-assistant-historique-sessions-normative-new.png (liste, MONO-AGENT)
                  qualite-ia-ui-reference/301assistant-historique-sessions-details-normative-new.png (détail)
                  -> applique l'invariant multi-agent : le détail montre quel agent a répondu à quel tour.

INVARIANTS (ne jamais casser) : shell deux couches déjà en place (AppShell dans agents/layout,
AgentTabs dans agents/[agentId]/layout) -> tu travailles le CORPS des pages, pas le chrome ;
sidebar settled ; nav URL-driven + surlignage dérivé de l'URL ; rails temporels (modes explicites,
« Voir à date » != Replay) ; portée define/choose/govern ; agent_id par message.

REGLE DONNEES : l'image est normative pour IA/structure/libellés/états — JAMAIS pour les données.
Aucune valeur codée en dur : tout se lie au backend réel. A la livraison, distingue « valeurs réelles »
de « interactions câblées » et dis lequel tient. Jamais une fixture qualifiée de « réelle ».

METHODE (boucle, UNE page à la fois) :
  a. rends la page live (webapp/frontend) au viewport de l'image (~1536px), agent seedé ; capture.
  b. place capture + image normative côte à côte.
  c. produis l'INVENTAIRE D'ECARTS (Zone | Image | Impl | Type{STRUCTURE,COPY,ETAT,DONNEES,VISUEL} | Action).
     STOP — attends ma validation AVANT de coder.
  d. corrige en ETENDANT (pas de régénération from scratch) ; encode les invariants.
  e. re-capture ; côte à côte avant->après->normative ; prouve la conformité ; logue tout écart
     intentionnel dans ui-contract.md.
  f. STOP — récap + diff ; 1 commit (Conventional Commits) ; attends validation avant la page suivante.

DEMARRAGE : commence par SYNTHESE. Produis l'inventaire d'écarts, puis STOP.
Quand les 6 sont validées, enchaîne VAGUE 2 (Évaluations puis Historique), même boucle.
```

## 9. Mode autonome — auto-revue par page (remplace le STOP humain)

Quand le run est **autonome** (sans validation humaine entre pages), le STOP est remplacé par : (a) cette auto-revue, passée **avant chaque commit** ; (b) un artefact de revue par page ; (c) un rapport final unique. Ne jamais committer une page qui échoue un point ci-dessous — la laisser honnêtement incomplète et le consigner.

Par page, vérifier et consigner :

- **Données** : chaque valeur est **réelle** (source citée) **ou vide réel loggé**. Règle : *source réelle → bind/dérive (nommée honnêtement)* · *manquante mais real-able → vide + seed en follow-up* · *ni source ni proxy → vide + log*. **Zéro hardcode.** Beaucoup de lignes DONNÉES = signal d'alerte → consigner, ne pas fabriquer.
- **Rail** : la page rend SON rail (Config/Connaissances/Garde-fous/Prompts → `OT-01` ; Console → `XT-01` ; Évaluations → `ER-01` ; Historique → `CT-01`) ; mode temporel explicite ; « Voir à date » ≠ Replay. **Pas de refactor temporel→URL.**
- **Portée** (Config/Garde-fous/Prompts/Connaissances) : double bloc *Définition (catalogue, lecture seule)* + *Configuration pour cet agent (éditable)* ; **picker borné jamais free-text** ; bandeau de gouvernance + événement `OT-01` (diff + raison + approbateur) sur mutation ; lien « Voir la définition dans CONFIGURER ».
- **Chrome** : intact (shell deux couches), non touché.
- **Cohérence numérique** : tous les compteurs d'une page **somment et se réconcilient entre tableaux** (leçon Évaluations) ; aucune identité « tidy » non vérifiée.
- **Évaluations (V2)** : `eval-gate-policy.md` **prime sur l'image** (verdict/nombres). Vérifs : `T0 ∩ dérogations = ∅` ; une dérogation n'est **effective qu'HORS socle** (jamais de badge « Dérogé actif » sur un cas socle) ; Venn = **appartenance structurelle** (somme aux totaux), distincte du **compte de non-concluants** ; grain **cas × langue** ; tiers cohérents ; cross-référence Statut-gate ↔ dérogations ↔ split.
- **Qualité** : `ruff` + `mypy --strict` + `tsc` + tests **verts** avant commit. Jamais committer rouge ; jamais de fake-green.
- **Décisions de jugement** : prendre le **défaut principié** (ci-dessus) et le **logger « à confirmer »** plutôt que de s'arrêter.

**Artefact par page** : inventaire d'écarts + captures **avant → après → normative** + déviations dans `ui-contract.md` + décisions données (réel/vide/dérivé) + risques auto-signalés.

**Rapport final unique** (pour la revue du matin), par page : *statut · décisions données · déviations · vérifié e2e ou non · risques auto-signalés*. Mettre **Évaluations en tête** (page la plus complexe et la plus critique).
