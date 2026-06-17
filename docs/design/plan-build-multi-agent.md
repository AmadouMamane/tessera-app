# Plan de build multi-agent — Tessera

> Décision : **tout maintenant** (projet showcase). Ordre **imposé** : fondation → seed → handoff → machinerie.
> Build **incrémental** : on **valide chaque phase** avant la suivante. Tout se construit **contre le contrat**, jamais en régénérant une page validée.

## Garde-fous transverses (à respecter à chaque phase)

- **Sidebar settled** : `AGENT / GOUVERNER{Surveiller·Agir·Prouver} / PLATEFORME{Configurer·Admin}`. Super-en-têtes non-cliquables.
- **Scope** : *configure par agent* (AGENT) · *surveille/prouve global, filtrable* (GOUVERNER) · *définir = CONFIGURER* (catalogue). On bind, on ne redéfinit pas.
- **Attribution `agent_id` par message** (per-turn), jamais par conversation.
- **Rails temporels** = projections d'un journal append-only hash-chaîné (cf. `registre-rails-temporels.md`). Modes explicites (Live / Historique / As-of). **« Voir à date » ≠ « Replay »** (Replay = AGIR).
- Ne pas régénérer une page validée : encoder les invariants dans le contrat.

---

## Phase 0 — Fondation (avant toute UI multi-agent)

**Objectif** : rendre l'app multi-agent-ready sans encore afficher de multi-agent.

**À construire** : routage scopé, propagation centralisée de l'agent, `agent_id` partout dans les données.

```
CONTEXTE — Tessera, cockpit interne. On rend l'app multi-agent-READY (sans UI multi-agent encore).

À FAIRE :
1. ROUTES : passer la section AGENT de /agent/* à /agents/:agentId/*
   (synthese, configurations, connaissances, garde-fous, prompts, evaluations,
   console, historique). Redirect /agent/* → /agents/support-client/* (compat).
   GOUVERNER (/surveiller,/agir,/prouver), Inbox (/a-traiter,/a-faire),
   PLATEFORME (/configurer,/admin) restent GLOBAUX (pas sous /agents/:id).
2. PROPAGATION : un hook useAgentId() qui lit :agentId (aujourd'hui une seule
   valeur "support-client"), et un helper agentPath(agentId, page) pour TOUS les
   liens internes de la section AGENT. Aucun agent en dur, aucune URL littérale.
3. DONNÉES : agent_id sur chaque événement du journal (S1), chaque ligne de
   métrique, et chaque MESSAGE de conversation (attribution per-turn).
4. MÉTRIQUES : toutes les agrégations de la Synthèse se calculent GROUPÉES par
   agent_id, au GRAIN TOUR (pas par conversation).

CONTRAINTES : routeur centralisé ; surlignage actif dérivé de l'URL ;
pages deep-linkables ; ne pas toucher au contenu des pages (elles reçoivent agentId via le hook).

ACCEPTANCE : (1) chaque page AGENT lit agentId depuis la route ; (2) aucun agent
hardcodé ni lien littéral ; (3) /agent/* redirige ; (4) les métriques sont
requêtables par agent_id au grain tour ; (5) GOUVERNER/Inbox/PLATEFORME restent globaux.
```

---

## Phase 1 — Seed de 3 agents réalistes

**Objectif** : éviter les vues creuses ; permettre de tester flotte, handoff, dédup.

```
CONTEXTE — fondation Phase 0 en place.

À FAIRE : créer 3 agents avec config + données plausibles :
- support-client   (SAV)
- onboarding       (ouverture de compte)
- recouvrement     (relances/impayés)
Chacun : modèle + prompts + sources + garde-fous BINDÉS depuis le catalogue
CONFIGURER (on choisit, on ne redéfinit pas). Historique réaliste :
conversations, événements (journal S1), métriques sur ~30 jours.
IMPORTANT : inclure quelques conversations PARTAGÉES (un agent passe la main à un
autre) pour tester l'attribution per-turn, le handoff et la déduplication des totaux.

ACCEPTANCE : 3 agents dans le registre ; /agents/<id>/* peuplé pour chacun ;
≥ quelques conversations multi-agents présentes dans les données.
```

---

## Phase 2 — Routeur / superviseur + handoff (le joyau)

**Objectif** : le cœur agentique — router chaque tour, permettre le handoff, tout tracer.

```
CONTEXTE — 3 agents seedés.

À FAIRE : un orchestrateur superviseur (pattern routeur, type LangGraph) :
- reçoit CHAQUE tour ; route vers l'agent adéquat (contexte/parcours = défaut,
  intention = ajustement) ; peut FAIRE UN HANDOFF en cours de conversation.
- enregistre agent_id PAR MESSAGE dans le journal (per-turn attribution).
- émet des événements de HANDOFF (agent→agent), DISTINCTS de l'escalade humaine.
Le client garde UNE seule porte (un chat unifié) ; le routage est invisible.

ACCEPTANCE : (1) une conversation peut s'étendre sur 2 agents ; (2) le journal
montre agent_id par message ; (3) les événements de handoff apparaissent ;
(4) État à date / Session detail affichent quel agent a répondu à quel tour ;
(5) cette conversation apparaît dans le scope opérateur des DEUX agents.
```

---

## Phase 3 — Machinerie cockpit (UI multi-agent)

**Objectif** : surfacer le multi-agent dans le cockpit, sans casser le settled.

```
CONTEXTE — routeur + handoff + per-turn attribution en place.

À FAIRE :
1. SÉLECTEUR D'AGENT dans le header (scope la section AGENT). Défaut = support-client.
   "Tous les agents →" mène à la flotte.
2. PAGE FLOTTE /agents : liste/compare tous les agents (santé, volume, taux de
   résolution, handoffs), bouton "+ Nouvel agent" (RBAC admin/opérateur, action auditée).
3. SYNTHÈSE : ajouter la métrique HANDOFF (entrant/sortant), distincte de l'escalade
   humaine ; AT-01 affiche les événements de handoff. Structure de page INCHANGÉE.
4. ROLLUPS CROSS-AGENT : dans la flotte /agents ET dans SURVEILLER, totaux org
   en comptant les conversations DISTINCTES (dédup ; ne PAS sommer les per-agent).

CONTRAINTES : sidebar reste le settled (AGENT/GOUVERNER/PLATEFORME) ; la Synthèse
d'un agent = SA tranche (grain tour) ; les totaux org vivent en flotte/SURVEILLER.

ACCEPTANCE : (1) le sélecteur change le scope AGENT ; (2) la flotte liste les 3
agents avec santé ; (3) Synthèse montre les handoffs sans changer de structure ;
(4) totaux org dédupliqués ≠ somme naïve des per-agent ; (5) sidebar settled intact.
```

---

## Ordre & validation

1. **Phase 0** (fondation) — *bloquant* : rien d'autre tant qu'elle n'est pas verte.
2. **Phase 1** (seed) — données réalistes, incluant des conversations partagées.
3. **Phase 2** (routeur + handoff) — le différenciateur ; valider l'attribution per-turn dans l'audit.
4. **Phase 3** (machinerie cockpit) — surfacer, sans toucher au settled.

À chaque phase : valider l'acceptance **avant** de passer à la suivante. C'est ce qui transforme « tout maintenant » en atout plutôt qu'en dette.
