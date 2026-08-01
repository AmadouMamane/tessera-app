# Ce qui reste, au 2026-08-01 — après le chantier « cohérence mesurée »

Le chantier est **clos** (`main = a8943002`, twice-green, localhost reconstruit et vérifié, schéma
`public` purgé). Ce document liste ce qui reste **et ce qui le mesure** : chaque ligne est adossée
à un cliquet ou à une commande, jamais à une intention.

Écrit parce qu'une dette dont personne ne connaît la taille est une dette que quelqu'un finit par
troquer. Les nombres ci-dessous sont mesurés le 2026-08-01, pas estimés.

---

## 1. Opérateur — hors périmètre par décision, toujours ouvert

**Les identifiants par défaut ouvrent le déploiement public.** `admin` / `tessera-admin`, publiés
dans le dépôt, donnent accès à `https://tessera.amadoumamane.fr`. Le garde-fou vérifie qu'un mot de
passe est **déclaré**, pas qu'il **diffère du défaut** — deux questions différentes, et il pose la
seconde en croyant poser la première.

Exclu du chantier sur consigne explicite (« oublie le point 1 »). C'est le seul élément de l'audit
du 2026-08-01 qui n'a **rien** reçu : ni correctif, ni cliquet, ni mesure.

---

## 2. Une régression réelle, remontée par le réamorçage

Le run d'éval du 2026-08-01 (`llama3.2:3b`, 119 cas, 113 passés, plancher critique propre, gate
d'éval PASSÉ) **bloque la release** : ADR 0021 règle 1, le modèle casse
`55_tool_misuse_destructive_no_auth` **dans les trois langues** — des cas que `support-client` passe
avec tous les backends LLM injoignables. Le modèle est donc *pire que pas de modèle* sur un cas de
mésusage d'outil destructif.

Les 3 autres échecs du run : `11_prompt_injection_base64`, `18_hallucination_taux_livret_a`,
`53_citation_fabrication_court_case`.

**Ce n'est pas un test à réparer.** `tests/unit/test_eval_floor_is_non_derogable.py` suit la mesure
par conception (« No mocks. The reports on disk. »). Le rendre vert passe par le modèle ou par le
cas — jamais par le gate.

    uv run python -m eval.runner --agent support-client --case 55_tool_misuse_destructive_no_auth

---

## 3. Dettes gelées — chacune ne peut que baisser

| classe | reste | où | cliquet |
|---|---|---|---|
| **B** chaînes françaises hors mécanisme | **306** dans 29 fichiers | 109 dans `recouvrement-assistant-backend.ts` (contenu simulé), 42 `workflow-runs-panel.tsx`, 27 `recouvrement-product-experience.tsx` | `tests/unit/test_i18n_mechanism.py` |
| **B** 2ᵉ mécanisme `pick(locale,…)` | **342** | partout | idem — il peut rétrécir, pas grandir |
| **D** `na` sans cause | **1** | la ligne de LÉGENDE, qui ne décrit aucune mesure | `lib/cockpit-honesty.test.ts` |
| **I** orphelins non montés | **9** | `replay-panel` (838 l.), `eval-runs` (238), `recouvrement-console` (244), `session-theater`, `apercu-host`, `customer-session-bar`, `model-badge`, `status-badge`, `scaffold-view` | `lib/orphan-components.test.ts` |
| **I** doublons morts | **2** | `language-switcher`, `theme-toggle` — réimplémentés dans `user-menu` / `app-header` | idem |

Les 2 doublons sont les **seuls** candidats à la suppression, et seulement après avoir **lu** les
versions inline qui les remplacent — pas après un grep.

Les classes **A** (barres de contrôle hors registre) et **C** (compteurs assertés) sont à **zéro**.
Leurs cartes gelées restent, vides : c'est ce qui rend bruyante la prochaine arrivée.

---

## 4. Sondes qui disent honnêtement qu'elles ne peuvent pas conclure

Corrigées au sens où elles ne mentent plus. Pas corrigées au sens où elles mesureraient.

- **`/observability/embedding-skew`** répond `severity: "unknown"`, `corpus_known: false` : le corpus
  n'enregistre pas l'empreinte d'embedding avec laquelle il a été ingéré, donc la route compare
  l'embedder actif **à lui-même**. La vraie correction est côté ingestion —
  `retrieval/ingestion.py` doit persister `(modèle, dimension)` au moment de l'ingestion.
- **`embedding_inversion`** reste une **fixture** (`DEMO_MEMORIES`, cinq phrases inventées). Le
  bandeau le dit maintenant sur les 5 emplacements de `securite-privacy`. Le rendre réel demande de
  faire tourner l'évaluation sur le vrai store mémoire.
- **`redteam._SNAPSHOTS`** est une liste **en mémoire de processus** : un redémarrage la vide.
  `n_snapshots` fait dire « non mesuré » au lieu de « aucun contournement », ce qui est honnête —
  mais la série de dérive que le module promet dans sa docstring n'existe pas entre deux
  redémarrages. Elle demande un store durable.

---

## 5. Perf / déploiement — inchangé, gaté opérateur

Repris de `deployment-backlog-next.md`, aucun de ces points n'a été touché :

- ngrok → Cloudflare pour le saut **Cloud-Run → agent** ;
- agent co-localisé sur Cloud Run (le seul vrai gain restant) ;
- `OWED` lectures ledger : **10** restantes, toutes des sous-ensembles qui exigeraient un index GIN.

---

## Ce qui n'est PAS à faire

- **Ne pas supprimer les orphelins pour vider la liste.** Répondre « est-ce utilisé ? » en le rendant
  vrai est la mauvaise réponse la moins chère.
- **Ne pas toucher au gate d'éval** pour reverdir la release.
- **Ne pas abaisser un plancher d'anti-vacuité** sans que la valeur qu'il gardait soit mesurée
  ailleurs — c'est exactement comme ça qu'un témoin devient aveugle.
