# Multi-agent — GOUVERNER & PLATEFORME (protocole de surfacing)

> **Objet** : rendre **GOUVERNER** (Surveiller / Agir / Prouver) et **PLATEFORME** (Configurer / Admin)
> multi-agent. **Constat (18/06)** : aucune de ces pages n'a la moindre notion d'agent (`agent_id`,
> filtre, breakdown) — alors que le backbone existe déjà (`webapp/.../agents/page.tsx`, `observability/fleet.py`,
> `agent_id` dans `metrics.py` et la chaîne d'audit). On **surface**, on ne reconstruit pas.

## 0. Le principe (à ne pas rater)

- **GOUVERNER + PLATEFORME sont GLOBAUX, *filtrables* par agent — PAS scopés par le switcher AGENT.**
  Ils ont leur **propre filtre** « Tous les agents ▾ » (défaut = **tous**). Le switcher AGENT de l'en-tête
  scope `AGENT/*` ; il **ne touche pas** à ces sections. **Ne pas confondre les deux** — sinon GOUVERNER
  devient per-agent et on perd la vue flotte.
- **Totaux org = entités DISTINCTES (dédupliquées)**, jamais la somme naïve des per-agent : une conversation
  qui a traversé 2 agents (handoff) compte **une fois** pour l'org.
- **Règle données inchangée** : réel ou vide réel, **jamais de fixture** ; la **dédup doit être réelle**
  (compter le distinct), pas approximée.

## 1. Mécanisme partagé (construire UNE fois, réutiliser partout)

- **`AgentScopeFilter`** global, porté par l'URL (`?agent=all|<agentId>`), **distinct de `useAgentId`**.
  Défaut `all`. Toutes les pages GOUVERNER/PLATEFORME le lisent.
- **Helper backend `dedup_org_total(...)`** : total org au grain entité **distincte** (conversations/cas),
  pas une somme des tranches per-agent.
- **Patron `AgentBreakdown`** : lignes/barres per-agent + ligne **Total org (dédup)** visuellement distincte.

## 2. Priorité (NE PAS faire les ~25 pages à plat)

**Tier 1 — l'histoire multi-agent vit ici :**
1. **Flotte `/agents`** — *vérifier d'abord qu'elle est RÉELLE* (`fleet.py` câblé, pas un scaffold) : liste +
   comparaison des agents (santé, volume, taux de résolution, **handoffs**, état de release), **totaux org
   dédupliqués**, bouton « + Nouvel agent » (RBAC, audité). C'est **LA** surface multi-agent.
2. **SURVEILLER** (vue-ensemble + qualité-ia + sécurité-privacy) : filtre agent + **breakdown per-agent** +
   **total org dédup**.
3. **AGIR / Release Control** : pipeline de release **par agent** + **verdict eval-gate par agent** (chaque
   agent = *package gouverné* versionné/gated). Étend directement le travail eval-gate.

**Tier 2 — boucles de gouvernance (la vraie valeur) :**
4. **CONFIGURER / “used-by”** : chaque item du catalogue (modèle, garde-fou, source, politique) montre
   **quels agents le consomment** ; changer une définition partagée **marque / re-gate les agents affectés**
   (define → consumers → re-valider). C'est l'inverse du binding d'instance d'AGENT.
5. **PROUVER / Journal d'audit** : **filtre `agent_id`** (la chaîne le porte déjà depuis Phase 0 → surfacer le
   filtre + l'État à date par agent). Cheap, et c'est l'opposabilité par agent.

**Tier 3 — complétude :**
6. **ADMIN / Rôles & accès** : **RBAC scopé par agent** (rôle × agent ; ex. « ML Eng sur support-client »,
   « Compliance sur tous »).
7. Reste **SURVEILLER** (conformité, fiabilité-coût, observabilité, amélioration) + **AGIR** (incidents &
   playbooks, replay & shadow, curation eval set, automations) : même patron filtre + breakdown ; incidents
   et replays **taggés par agent**.

## 3. Par section — ce que « multi-agent » veut dire

| Surface | Surfacing multi-agent |
|---|---|
| Flotte `/agents` | liste/compare agents + **totaux org dédup** + nouvel agent (gouverné) |
| Surveiller/* | filtre agent + breakdown per-agent + total org dédup |
| Agir / Release Control | état release + **verdict eval-gate PAR agent** (package gouverné) |
| Agir / Incidents · Replay · Curation | entités **taggées agent** + filtre |
| Prouver / Audit · Evidence | **filtre `agent_id`**, État à date / evidence par agent (ou cross-agent) |
| Configurer/* | **“used-by”** (agents consommateurs) + changement → **re-eval des agents affectés** |
| Admin / Rôles & accès | **RBAC rôle × agent** |
| Admin / Profil système | la **flotte** d'agents |

## 4. Méthode (autonome, §9)

Même discipline que la passe conformance : **autonome jusqu'au bout, auto-revue §9 avant chaque commit**
(données réelles ou vide réel ; cohérence numérique ; pas de chrome cassé ; 1 commit/page). Ordre = la
priorité §2. **Invariant à vérifier à CHAQUE page** : le filtre GOUVERNER/PLATEFORME est **global et distinct
du switcher AGENT** ; les **totaux org sont dédupliqués** (≠ somme des per-agent). Rapport final, **Flotte +
Release Control en tête**.

## 5. Super-prompt (à coller)

```
RÔLE — Tu rends GOUVERNER (Surveiller/Agir/Prouver) et PLATEFORME (Configurer/Admin) MULTI-AGENT.
Constat : ces pages n'ont aucune notion d'agent ; le backbone existe (agents/page.tsx, fleet.py,
agent_id dans metrics + chaîne d'audit). On SURFACE, on ne reconstruit pas.

LIS D'ABORD : docs/design/multi-agent-gouverner-plateforme.md (ce protocole),
docs/design/ui-contract.md (modèle multi-agent + portée). Restitue ta compréhension + l'ordre, puis go.

PRINCIPE NON NÉGOCIABLE :
- GOUVERNER/PLATEFORME = GLOBAUX, filtrables par agent, via un filtre PROPRE (?agent=all|<id>),
  DISTINCT du switcher AGENT (qui ne scope qu'AGENT/*). Défaut = tous.
- Totaux org = entités DISTINCTES (dédup), jamais la somme des per-agent (handoff = 1 conv).
- Données réelles ou vide réel, JAMAIS de fixture ; dédup réelle.

MÉCANISME PARTAGÉ (construire d'abord) : AgentScopeFilter (URL) + helper dedup_org_total + patron
AgentBreakdown. Puis appliquer dans l'ordre de priorité.

ORDRE :
  1. Flotte /agents — vérifie qu'elle est RÉELLE (fleet.py câblé) ; sinon, c'est la 1re à finir.
  2. Surveiller (vue-ensemble, qualité-ia, sécurité-privacy) : filtre + breakdown + total dédup.
  3. Agir / Release Control : release + verdict eval-gate PAR agent.
  4. Configurer : “used-by” (agents consommateurs) + changement → re-eval des agents affectés.
  5. Prouver / Audit : filtre agent_id + État à date par agent.
  6. Admin / Rôles : RBAC rôle × agent.
  7. Reste Surveiller + Agir : même patron.

MÉTHODE (boucle, autonome, AUCUN stop) : auto-revue §9 avant chaque commit ; 1 commit/page ;
capture ; à chaque page vérifie l'invariant « filtre global ≠ switcher AGENT » + « totaux dédupliqués ».
Si une donnée par-agent n'est pas réelle → vide réel + log, jamais fabriquée.
Ne pousse pas. RAPPORT FINAL (Flotte + Release Control en tête) : par page, statut, données réel/vide,
dédup vérifiée, invariants, e2e ou non.
```
