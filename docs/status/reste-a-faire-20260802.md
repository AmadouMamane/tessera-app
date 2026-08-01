# Ce qui reste, au 2026-08-02

Successeur de `reste-a-faire-20260801.md`, qui reste valable pour ce qu'il n'a pas soldé. Écrit
après le chantier des rails temporels (`docs/status/rails-temporels-et-courbes-20260801.md`).

Même règle que le précédent : **chaque ligne est adossée à une mesure ou à une commande**, jamais
à une intention. Une dette dont personne ne connaît la taille est une dette que quelqu'un finit
par troquer.

---

## 1. Opérateur — hors périmètre par décision, toujours ouvert

`admin` / `tessera-admin`, publiés dans le dépôt, ouvrent `https://tessera.amadoumamane.fr`. Le
garde-fou vérifie qu'un mot de passe est **déclaré**, pas qu'il **diffère du défaut**.

Inchangé depuis le 2026-08-01. C'est toujours le seul élément de l'audit qui n'a **rien** reçu :
ni correctif, ni cliquet, ni mesure.

---

## 2. Cloud Run n'a pas été redéployée — sur consigne

```
gcp.amadoumamane.fr → {"sha":"e9f6c9fa","builtAt":"2026-07-31T19:15:40Z"}
```

Elle sert l'image du **31 juillet**, d'avant tout le travail des rails temporels. Rien de ce qui
suit n'y est : ni la période câblée, ni les courbes, ni l'as-of qui atteint les cartes, ni la
correction de `55_tool_misuse`.

La procédure est celle du dépôt : buildx **amd64**, tag épinglé, `update-traffic`, puis
`make deploy-diff` — et l'on vérifie le **digest de l'image de la révision servante**, jamais la
phrase de `gcloud`.

**Note nouvelle :** depuis le 2026-08-02 `deploy-diff` peut enfin comparer, parce que l'image
on-prem nomme son commit. Un déploiement gcp devra donc *aussi* graver le SHA sur son agent,
sans quoi ce host répondra `unverified:<sha>` — ce qui est le verdict correct, pas un bug.

---

## 3. `fiabilite-cout` a DEUX rails de période — arbitrage à rendre

La page affiche le sélecteur d'entête (**24 h / 7 j / 30 j**) *et* possède son propre
`PeriodRail` (**7 / 14 / 30 jours**). Deux contrôles, deux vocabulaires, une seule fenêtre à
piloter.

Les cinq autres pages de SURVEILLER sont câblées sur le sélecteur d'entête. Celle-ci ne l'est
délibérément pas : choisir lequel possède la fenêtre est une décision de design — le 14 jours a
une raison d'être pour la fiabilité — et non un défaut à rustiner en silence.

Trois issues possibles, aucune gratuite : unifier sur l'entête (on perd le 14 j) · ajouter 14 j
à l'entête (on l'impose aux six pages) · masquer l'entête sur cette page (un contrôle qui
disparaît d'une page est sa propre surprise).

---

## 4. Le plancher nul bloque toujours la release

`55_tool_misuse_destructive_no_auth` est **clos** (3/3, déterministe, au garde-fou). Mais la
règle 1 d'ADR 0021 refuse toujours, sur des cas d'hallucination et de citation notés par un LLM
qui **diffèrent entre deux exécutions du même code** — 48/49 sur un run, 26/53 sur le suivant.

Le gate dit lui-même comment trancher :

    make eval-contribution REPORT=eval/reports/local/latest_support-client.json

⚠️ Le rendre vert passe par le modèle ou par le cas, **jamais par le gate**.
`tests/unit/test_eval_floor_is_non_derogable.py` lit les rapports réels sur disque, par
conception — c'est ce qui a permis à un réamorçage de faire remonter une régression au lieu de
l'enterrer.

---

## 5. Sondes : une réparée, deux encore aveugles

**`/observability/embedding-skew` voit désormais le corpus** — l'ingestion tamponne
`(embedding_model, embedding_dimension)`. Mais en vrai :

```
severity: "unknown", corpus_known: false, corpus_rows: 241, unfingerprinted_rows: 241
```

Les 241 lignes ont été ingérées **avant** les colonnes. La sonde le dit et les compte ; elle ne
mesurera qu'après une **ré-ingestion du corpus**. C'est la seule action qui manque.

**Toujours non mesurants :**

- `embedding_inversion` — fixture `DEMO_MEMORIES`, cinq phrases inventées ;
- `redteam._SNAPSHOTS` — liste en mémoire de processus, vidée à chaque redémarrage.

Les deux demandent la même chose : **un magasin d'exécutions de sondes, daté et durable**. Il
débloquerait aussi les **cinq courbes** aujourd'hui absentes (`refusal`, `firewall`,
`crossTenant`, `privilege`, `inversion`), qui disent honnêtement « corpus fixe » faute d'un
historique d'exécutions à tracer.

---

## 6. Dettes gelées — chacune ne peut que baisser

| classe | reste | cliquet |
|---|---|---|
| **B** chaînes françaises hors mécanisme | **306** dans 29 fichiers | `tests/unit/test_i18n_mechanism.py` |
| **B** 2ᵉ mécanisme `pick(locale,…)` | **342** | idem |
| **D** `na` sans cause | **1** (la légende) | `lib/cockpit-honesty.test.ts` |
| **I** orphelins non montés | **9** | `lib/orphan-components.test.ts` |
| **I** doublons morts | **2** | idem |

Classes **A** et **C** à zéro, cartes gelées gardées vides exprès.

---

## 7. Perf / déploiement — inchangé, gaté opérateur

- ngrok → Cloudflare pour le saut **Cloud-Run → agent** ;
- agent co-localisé sur Cloud Run (le seul vrai gain restant) ;
- `OWED` lectures ledger : **10**, toutes des sous-ensembles qui exigeraient un index GIN.

---

## 8. Un piège que ce chantier a créé puis refermé — à ne pas rouvrir

`.agent-state/` est l'état d'exécution durable de l'agent : le journal d'audit, les compteurs
Prometheus multiprocess, un dump SQL de 19 Mo. Un `git add -A` l'a fait entrer dans un commit le
2026-08-02 ; il en est ressorti et il est désormais **gitignoré**.

Au-delà du poids, l'agent **réécrit `read_snapshot.json` en tournant**. Tracké, il rendait l'arbre
définitivement sale — donc `make fulllocal-up` aurait gravé `-dirty` sur **toutes** les images,
pour toujours. *Un signal toujours allumé n'est pas un signal.*

⚠️ Corollaire pour la suite : `git add -A` dans ce dépôt ramasse des choses qui n'y ont rien à
faire. C'est le deuxième incident du genre en deux jours (le premier avait embarqué 13 scripts
non formatés qui ont rougi le gate). Préférer un ajout par chemins.

---

## Ce qui n'est PAS à faire

- **Ne pas supprimer les orphelins** pour vider la liste.
- **Ne pas toucher au gate d'éval** pour reverdir la release.
- **Ne pas abaisser un plancher d'anti-vacuité** sans que la valeur gardée soit mesurée ailleurs.
- **Ne pas graver un SHA sur une seule moitié de la paire.** Un `sha` qui ne couvre que le front
  fait dire « ça correspond » à un comparateur qui n'a vu que la moitié — strictement pire que le
  `CannotSay` qu'il remplace.
