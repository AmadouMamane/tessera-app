# 0043 — Toute entrée du conteneur est un contrat vérifié au démarrage, jamais un défaut silencieux

**Statut : accepté — 2026-07-26**
**Applique :** ADR 0026 (un témoin interroge la chose ; un témoin qui ne voit pas ne dit jamais « ok »)
**Complète :** ADR 0014 (isolation par chemin des rapports d'éval)

## Contexte

Le cutover blue-green fait tourner l'agent on-prem sous la MÊME image de production que Cloud Run,
et non plus via `run_local.py`. Trois régressions se sont succédé au démarrage du conteneur, et
c'était **la même panne trois fois** :

1. le paquet first-party `eval/` n'était pas embarqué dans la roue → `ModuleNotFoundError` au boot ;
2. l'archive `eval/reports/` était présente dans le repo mais **strippée de l'image** par
   `.dockerignore` (`eval/reports/*`) → le chargeur d'éval ne trouvait « aucun rapport utilisable » ;
3. la clé de signature d'assertion opérateur ne vivait que dans `.env.local`, que le conteneur ne
   charge pas → toutes les pages opérateur en 401.

Chaque fois, `run_local.py` avait masqué le trou parce qu'il tourne depuis le repo avec
l'environnement du développeur ; le conteneur était la première chose à exercer le chemin d'image
nu. Et surtout : chaque fois, **l'application a caché le manque derrière une dégradation
silencieuse** — `{"available": false}`, un tableau vide, un 401 — découverte page par page par
l'opérateur au lieu d'être refusée au démarrage. C'est exactement le trou qu'ADR 0026 interdit.

Le gate ne construit aucune image ; ces régressions lui étaient donc invisibles jusqu'au déploiement.

## Décision

### 1. Un preflight-témoin : chaque entrée déclarée est affirmée, ou refusée bruyamment

`src/tessera/preflight.py` (console-script `tessera-preflight`) transforme chaque manque possible en
**un verdict unique dont le CODE DE SORTIE est la réponse** :

* `0` — toutes les entrées satisfaites (OK/SKIP uniquement) ;
* `1` — au moins un FAIL (une entrée est observablement absente, une dépendance est tombée) ;
* `2` — aucun FAIL, mais au moins un BLIND : le témoin n'a pas pu observer, il ne dira donc jamais
  « ok » (ADR 0026).

Il **interroge la chose elle-même**, jamais un voisin : l'archive d'éval par le chargeur exact que
les tableaux appellent (`load_eval_snapshot`), Postgres par le même `psycopg.connect` que le magasin
du journal, ClickHouse / Prometheus / Ollama par leurs propres clients. Un répertoire qui *existe*
n'est pas une archive qui *charge*. Un check qui ne peut même pas tenter son observation est BLIND,
jamais un OK confortable ni un FAIL mal attribué.

Trois modes : `--image-only` (ce que l'image DOIT contenir, sans service externe — le témoin CI),
défaut (image + config opérateur + dépendances vivantes), `--http BASE` (sonde `/healthz` + `/readyz`
d'un serveur vivant). Cibles : `make preflight` (témoin complet DANS le conteneur cutover),
`make image-preflight` (build + `--image-only`).

### 2. Le CI construit et auto-teste l'image

Un job `image-preflight` (`.github/workflows/ci.yml`) construit l'image agent et lance le preflight
`--image-only`. La classe « régression Dockerfile / `.dockerignore` » est ainsi attrapée au build,
pas au cutover. Via `make image-preflight`, sans dérive entre le runner et le poste.

### 3. Un plancher de rapports committé (`eval/reports/seed/`)

Les rapports générés par environnement restent de l'état hôte, jamais embarqués. Mais un **seed**
committé — sortie réelle `llama3.2:3b` de catalogue, ~0,5 Mo — voyage dans l'image (`.dockerignore`
ré-inclut explicitement `eval/reports/seed/`). `iter_report_files` ne le lit **qu'en dernier
recours, quand l'archive d'environnement est vide** : un vrai run d'environnement l'emporte toujours,
et le pin `TESSERA_REPORTS_DIR` le court-circuite. Il ne fabrique aucun chiffre ; il empêche une
*archive absente* de dégrader les pages en `available: false` sur un déploiement sans archive propre
(Cloud Run).

### 4. La configuration cutover du conteneur est trackée, sans secret

`docker-compose.cutover.yml` (racine) déclare la posture cutover — réseaux data + obs joints, câblage
par nom de service, montage lecture-seule de `eval/reports`, métriques + turn-evidence. Tout ce qui
est machine- ou secret-spécifique est paramétré : noms de réseaux et chemins interpolés depuis le
shell / un `.env`, les deux secrets (mot de passe ClickHouse, clé opérateur) via un `env_file`
gitignoré dérivé de `infra/docker/cutover.env.example`. La glue opérationnelle cesse d'être un
artefact scratchpad non tracké — c'était la cause de la troisième surprise.

## Conséquences

* Le smoke-test du cutover s'adosse au preflight : un input manquant est refusé AVANT tout flip de
  trafic, plus jamais découvert par l'opérateur après.
* Sur Cloud Run (étape 2), le seed garantit un plancher aux tableaux d'éval sans hôte à monter ;
  localement, le bind-mount fournit l'archive complète et l'emporte.
* Le preflight est un témoin : il doit rester capable de voir. Un check qui deviendrait incapable
  d'interroger sa cible doit rapporter BLIND, jamais être supprimé pour « verdir » — sinon il rejoint
  la liste des garde-fous verts au-dessus d'un trou (ADR 0026).
* Portée volontairement limitée : le preflight vérifie la PRÉSENCE et l'ACCESSIBILITÉ des entrées,
  pas leur exactitude sémantique (il ne peut pas voir la clé du front pour prouver l'égalité — il le
  dit explicitement). L'égalité de clé reste une consigne opérateur.
