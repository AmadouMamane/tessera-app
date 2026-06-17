# Kickoff — Chantier multi-agent Tessera

## 0. État réel du code (constaté 17/06/2026) — à lire AVANT les phases

Stack : **Next.js app router**, routes locale-préfixées `webapp/frontend/app/[locale]/…` (front) ; **Python / LangGraph** `src/tessera/` (back).

**Déjà en place — ÉTENDRE, ne pas reconstruire :**
- **Chaîne de hash tamper-evident** : `src/tessera/guard/audit.py` (`emit_audit`, `verify_audit_chain`, hash précédent + SHA-256 ; ADR 0010 #3) → **socle d'opposabilité** ; le « journal S1 » = *étendre ceci* (ajouter `agent_id` + bitemporal valid/transaction).
- **Graphe agent (LangGraph)** : `src/tessera/agent/graph.py` + `router.py` → planner → workers → reviewer → reporter + grounding. ⚠ routage **intra-agent** (vers workers), pas inter-agents.
- **Handoff humain** : `agent/tools/ticket_escalate.py` — distinct du handoff agent↔agent.
- **Contexte temporel** : `webapp/frontend/lib/temporal-context.ts` (ADR 0011) + `components/overview/temporal-rail.tsx` + `components/observability/period-rail.tsx` → **patron à mirrorer pour `agentId`**.
- **Trace par tour** : `observability/trace_snapshot.py` (= XT-01). **Métriques** : `observability/metrics.py`.
- **Nav settled déjà construite** (`app/[locale]/{agent,surveiller,agir,prouver,configurer,admin,produit}` + `select-space`) + **réfs UI normatives** `docs/ui-reference/`.

**Le vrai gap multi-agent :**
1. `agent_id` n'est **pas** pervasif (seul `observability/agent_configurations.py`) → le tagger : audit, métriques, trace, **messages**.
2. `app/[locale]/agent/*` (mono) → `app/[locale]/agents/[agentId]/*` + `agent-context.ts` (mirror `temporal-context.ts`) + redirect + liens.
3. Étendre `guard/audit.py` : **bitemporal + agent_id**.
4. **Supervisor inter-agents** = couche **au-dessus** du graphe (réutiliser `agent/router.py`) ; handoff agent↔agent + `agent_id` par message ≠ router intra-agent ≠ escalade humaine.
5. Seed : 1 agent aujourd'hui → support-client / onboarding / recouvrement.

**Recadrage des phases** : Phase 0 = (front) route `agent→agents/[agentId]` + `agent-context` ; (back) `agent_id` partout + group-by au grain tour + bitemporal sur l'audit chain. Phase 2 = supervisor **au-dessus** du graphe existant. **On étend l'existant (hash-chain, router, rails), on ne le refait pas.**

---

## 1. Documents à fournir à Claude Code (context pack)

**A. Contrat & specs (copiés dans le repo — `docs/design/`)**
- `docs/design/plan-build-multi-agent.md` — **le plan, lecture n°1** : 4 phases + acceptance.
- `docs/design/registre-rails-temporels.md` — rails temporels (S1–S4 / C1–C4 / 8 rails) + **§9 badge** (v1.2).
- `docs/design/s1-journal-evenements.svg` — schéma du **substrat S1** (append-only, bitemporal, hash-chaîné, as-of).

**B. Contrat repo (confirmer qu'ils sont présents)**
- `CLAUDE.md` — spec contraignante du repo.
- `docs/design/ui-contract.md` — **structure nav canonique + registre d'écarts** (doit refléter : sidebar settled, règle de portée, rails §9, règle d'éditabilité, modèle multi-agent, routing/attribution). Si incomplet → le plan + le registre font foi.
- `docs/decisions/` — ADRs (modèle temporel Live/Historique/As-of ; ADR mémoire pgvector).
- `docs/signal-catalog.yaml` — **source de vérité** des signaux.
- **Réfs UI normatives** : `docs/ui-reference/` (écrans validés + sous-dossiers `agent/`, `prouver/`, `produit/`…).
- **Back à étendre (pas reconstruire)** : `src/tessera/guard/audit.py` (hash-chain), `src/tessera/agent/{graph,router}.py`, `src/tessera/observability/{metrics,trace_snapshot,agent_configurations}.py`.
- **Front, patrons** : `webapp/frontend/lib/temporal-context.ts`, `components/overview/temporal-rail.tsx`.

**C. Références UI validées (normatives — captures ou HTML)**
- Sidebar **settled** : `AGENT / GOUVERNER{Surveiller·Agir·Prouver} / PLATEFORME{Configurer·Admin}`.
- Écrans validés : **Synthèse**, **Connaissances**, **État à date** (version finale).

---

## 2. Super-prompt (à coller)

```
RÔLE — Tu es l'ingénieur qui implémente le chantier MULTI-AGENT de Tessera (AI Control Plane).

AVANT TOUTE LIGNE DE CODE :
1. Lis, dans l'ordre : docs/design/plan-build-multi-agent.md (le plan),
   docs/design/registre-rails-temporels.md, docs/design/s1-journal-evenements.svg,
   puis CLAUDE.md, docs/design/ui-contract.md, docs/decisions/ (ADRs),
   docs/signal-catalog.yaml. Ces documents sont CONTRAIGNANTS.
2. Restitue ta compréhension : un résumé du plan + ta to-do de la PHASE 0 uniquement,
   et la liste des fichiers que tu vas toucher. ATTENDS ma validation avant de coder.

INVARIANTS NON NÉGOCIABLES (à chaque phase) :
- Sidebar settled : AGENT / GOUVERNER{Surveiller·Agir·Prouver} / PLATEFORME{Configurer·Admin}.
  Super-en-têtes non-cliquables. NE PAS régénérer une page validée — encoder les invariants.
- Portée : configure par agent (AGENT) · surveille/prouve global filtrable (GOUVERNER) ·
  définir = CONFIGURER (on bind, on ne redéfinit pas).
- agent_id PAR MESSAGE (attribution per-turn), jamais par conversation.
- Rails = projections d'UN journal append-only hash-chaîné (cf. registre + S1).
  Modes temporels explicites (Live/Historique/As-of). « Voir à date » ≠ « Replay » (Replay = AGIR).
- Badge d'opposabilité dynamique (Scellé / Intégrité partielle / Non scellé), calculé après
  vérification — jamais cosmétique.

MÉTHODE (boucle, obligatoire) :
  Pour chaque phase du plan (0 → 1 → 2 → 3) :
    a. annonce le périmètre + les fichiers ;
    b. implémente UNIQUEMENT cette phase ;
    c. exécute toi-même les critères d'ACCEPTANCE de la phase (montre la preuve : tests,
       routes, diffs, captures) ;
    d. STOP — montre un récap + le diff, attends ma validation AVANT la phase suivante.
  Ne jamais enchaîner plusieurs phases sans validation. La Phase 0 est BLOQUANTE.

DÉMARRAGE :
  Commence par la PHASE 0 (Fondation) du plan :
   - routes /agents/:agentId/* + redirect /agent/* → /agents/support-client/* ;
   - hook useAgentId() + helper agentPath() centralisés (zéro agent en dur, zéro URL littérale) ;
   - agent_id sur chaque événement S1, chaque métrique et chaque MESSAGE ;
   - agrégations Synthèse groupées par agent_id au grain TOUR ;
   - GOUVERNER / Inbox / PLATEFORME restent GLOBAUX (hors /agents/:id).
  Puis applique la boucle ci-dessus. Ne touche pas au contenu des pages validées :
  elles reçoivent agentId via le hook.

CONTRAINTES TECHNIQUES :
  - Pages deep-linkables ; surlignage actif dérivé de l'URL ; code-splitting par route.
  - Adapte slugs/routeur à la stack existante (ne réinvente pas l'archi en place).
  - Tout écart vs les références validées → le consigner dans docs/design/ui-contract.md, pas l'appliquer en silence.

LIVRABLE PHASE 0 : le diff + la preuve d'acceptance, puis STOP pour revue.
```

---

## 3. Rappel de cadrage

- **Ordre strict** : Phase 0 (bloquante) → 1 → 2 → 3, une validation entre chaque.
- **Le joyau** = Phase 2 (routeur/superviseur + handoff + attribution per-turn). C'est ce qui se voit dans un portfolio.
- **La vraie barre** (au-delà de l'archi) = la rigueur empirique : évals, itération sur les échecs réels. À garder en ligne de mire pour la suite.
