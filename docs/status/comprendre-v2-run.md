# Refonte `/comprendre` v2 — statut de run

- **Date :** 2026-07-22
- **Worktree :** `agents/codex`
- **Branche :** `codex/comprendre-v2`
- **Base fraîche :** `origin/main` à `679d8d82`
- **Source fermée :** `Tessera_private/contenu-page-comprendre-v2.md`
- **Maquettes lues :** `E.png` (page cible), `D.png` (schéma uniquement). `C.png` n'a pas été ouverte : hors lot.
- **HALT :** obligatoire après le `dev-preview` supervisé et les captures FR/DE/EN, avant tout merge.

## Préconditions et discipline

- `AGENTS.md`, la spec privée, puis `docs/functional-page-playbook.md` ont été lus dans cet ordre avant tout code.
- Le worktree `agents/codex` était garé sur `codex/headers-refonte`, branche antérieure aux cibles `make session` / `make claim` et aux scripts du garde. La première tentative a donc refusé avec « No rule to make target » ; le garde de `main` a ensuite refusé honnêtement un checkout qui ne portait pas son fichier de référence. Bootstrap consigné : identité de session créée depuis la cible de `main`, branche coupée de `origin/main`, puis `make claim` vert sur le checkout frais.
- Bail sole-writer acquis par la session `e911d673-305e-4b5f-a47d-61e9cc643c63`.
- Staging ciblé uniquement ; jamais `git add -A`.
- `make gate-twice` à la fin de chaque lot, résultat et arbre nommés ci-dessous.

## Écarts de noms de seams constatés avant code

Ces écarts ne changent ni les définitions ni les décisions de la spec ; ils nomment le chemin réel trouvé sur `main`.

1. **T1/T2 — flotte observée et fraîcheur.** Aucun read seam unique ne retourne aujourd'hui « agents ayant publié dans les dernières 24 h + max horodatage ». Le seam flotte existant combine le registre, le transcript, la preuve de tours Prometheus et des descripteurs de quality nets. La preuve Prometheus actuelle est cumulative et documente explicitement qu'elle ne mesure pas une fenêtre. Le lot étendra ce read model de flotte sur les événements horodatés déjà lus par la spine ; aucun compteur de process ne sera présenté comme une fraîcheur.
2. **T3 — contrôlés / bloqués aujourd'hui.** Le read seam journal existe (`read_ledger_entries(since=…)`) et les entrées guard portent le résultat et les décisions. En revanche, les entrées `tessera.guard.audit` ne portent pas encore le booléen `synthetic`, même si le contexte de tour le connaît et si les événements d'invocation synthétique le portent. Le lot fermera ce trou au point d'émission, puis comptera uniquement les entrées guard réelles depuis minuit `Europe/Paris`. Aucun compteur Prometheus n'entre dans ce chemin.
3. **T4 — prêts / à évaluer ou réévaluer.** Sur le `main` frais, `/eval` redirige vers la vue Évaluations ; la tuile publique correspondante lit les `AgentRelease` du payload flotte et calcule ses buckets depuis `agent_release.py`, lequel applique déjà `eval_floor.py`. Il n'existe pas de bucket équivalent dans `routes/observability/evals.py`. Le lot factorisera et réutilisera le seam `AgentRelease` existant pour que la tuile et `/comprendre` partagent exactement les mêmes buckets, sans recalcul concurrent.
4. **T5 — intégrité.** Le seam attendu existe : `api/routes/audit.py::audit_integrity`, avec vérification incrémentale et `AuditIntegrity.full_verified_at`.

## Récolte de `b1dcd5d5`

- Lecture seule effectuée via `git show` ; la branche `codex/comprendre-3-minutes` reste intacte.
- Récoltables confirmés : le bloc `journey` (mini-cas), les cartes `roles`, et leurs sous-arbres i18n FR/DE/EN dans `comprendreCodex.content`.
- `timeline-nav.tsx` a été inspecté uniquement par son import ; il ne sera ni repris ni recréé.
- Le tag `archive/comprendre-A-codex` et la suppression de branche restent strictement après merge, donc hors de ce run avant HALT.

## Ledger des lots

| Lot | Statut | Commit | Gate twice | Preuves |
|---|---|---|---|---|
| 1 — backend | terminé | `49828247` | `8f3f9f9a7fc6` · twice-green | 59 tests ciblés verts ; mutations T1/T3/T4/T5 ; synthétique inchangé ; égalité T4 |
| 2 — page | terminé | en préparation | `355e7e1404c3` · twice-green | FR verbatim ; DE/EN ; BFF + zod ; 5 liens ; `/en-detail` |
| 3 — ratchets | à faire | — | — | mutation `214` rouge ; e2e vide/liens/langues |

## Mutations et captures

### Lot 1 — backend

- Endpoint ajouté : `GET /observability/comprendre`, agrégat de lecture sans store propre.
- T1/T2 : `turn_evidence.recent_turn_evidence` interroge le store Prometheus du spine par
  incréments bornés à la fenêtre ; le nombre ne retient que les identifiants du registre et la
  fraîcheur est le maximum des horodatages d'incrément, jamais la valeur courante du compteur.
  Le seuil de silence est classifié par le backend afin que le frontend ne l'invente pas.
- T3 : `guard_activity.exchange_counts_since` replie `read_ledger_entries(since=…)`, depuis
  minuit civil `Europe/Paris`, et ignore `synthetic=true`. Les nouvelles entrées guard-audit sont
  estampillées au point d'émission ; l'historique sans ce champ reste réel, sans rétrofiction.
- T4 : `agent_release.fleet_release_buckets` porte les buckets exclusifs `ready/review` et reste
  le seam unique à raccorder à la tuile `/eval` au lot 2 ; le test compare directement le payload
  à ce résultat sans recalcul.
- T5 : la route appelle effectivement `routes/audit.py::audit_integrity`; aucune date n'est
  servie si la vérification effective est absente, rouge ou vide.
- Mutation synthétique : une entrée `denied` avec `synthetic=true` injectée dans le journal laisse
  `controlled=2` et `blocked=1` strictement inchangés.
- Mutation par tuile : flotte vide → ajout d'un signal enregistré ne change ni guard ni eval ; un
  signal d'agent hors registre ne change pas T1 ; vérification rouge avec date forgée → T5 reste
  vide ; buckets T4 égaux au seam partagé.
- Preuves exécutées :
  - `uv run pytest tests/unit/test_observability_comprendre.py tests/unit/test_governed_acts_name_their_author.py tests/unit/test_guard_activity.py -q` → **59 passed**.
  - Ruff ciblé → **vert** ; format ciblé → **vert** ; mypy strict ciblé → **vert**.
- Mémoire : Insight 201 ajouté aux mémoires privées sur l'obligation de porter l'exclusion
  synthétique dans le contrat durable de l'événement.

- Premier essai du gate : rouge attendu des deux inventaires figés de routes publiques
  (`131→132` et `126→127`) ; les cliquets ont imposé la déclaration explicite du nouveau read
  aggregate sans donnée sujet. Mise à jour ciblée puis **56 tests de posture + endpoint verts**.
- `make gate-twice` final : **TWICE-GREEN sur un seul arbre `8f3f9f9a7fc6`** ; chaque passage
  valide TypeScript, Biome (27 warnings historiques), 429 tests frontend, Ruff, format, mypy
  strict et 2 560 tests backend hors intégration.

### Lot 2 — page

- Récolte en lecture seule depuis `b1dcd5d5` : structure visuelle du mini-cas et des cartes de
  rôles, plus les traductions FR/DE/EN des sous-arbres `journey` et `roles`. Les divergences de
  la branche A face au texte fermé (titre `Direction · DRH`, prochaine action proposée côté
  manager) n'ont pas été reprises ; le texte de la spec reste souverain.
- `/comprendre` lit l'agrégat côté serveur, le rafraîchit via `GET /api/comprendre`, et valide les
  deux chemins avec le même schéma Zod discriminé. Une indisponibilité ou un payload invalide
  devient `{available:false}` et conserve les honest-empty par tuile.
- La tuile publique `/eval` du launcher consomme désormais les buckets `ready/review` de ce même
  agrégat ; le test de mutation lui injecte un ancien rollup `passedAgents=99` et prouve qu'il est
  ignoré au profit du seam partagé.
- La prose v1 et ses catalogues existants sont servis par `/comprendre/en-detail`. Le nouveau shell
  public partagé maintient une seule occurrence d'autorisation explicite. `timeline-nav.tsx` n'a
  été ni copié ni recréé.
- Les cinq liens fermés sont câblés vers `/recouvrement`, `/agents`, `/surveiller`, `/eval` et
  `/prouver`. L'index `/prouver`, absent sur `main`, est matérialisé comme redirection locale vers
  le journal d'audit afin que la route demandée résolve sans texte supplémentaire.
- Preuves ciblées pré-gate : **42 tests verts** (`comprendre.test.ts` + `signal-band.test.tsx`) ;
  TypeScript strict frontend vert ; catalogues JSON valides ; Biome ciblé remis en forme.
- Premier essai du gate : rouge attendu du ratchet de nature de page sur le nouvel index
  `/prouver`. La route et son snapshot figé sont désormais explicitement déclarés `redirect` ;
  `page-nature.test.ts` repasse avec **12 tests verts**.
- `make gate-twice` final : **TWICE-GREEN sur un seul arbre `355e7e1404c3`** ; chaque passage
  valide TypeScript, Biome (27 avertissements historiques), 436 tests frontend, Ruff, format,
  mypy strict et 2 560 tests backend hors intégration.

## Questions bloquantes / déviations proposées

Aucune. Si une déviation de contenu, de contrat ou de structure devenait nécessaire, elle sera écrite ici et le run s'arrêtera avant de la prendre.
