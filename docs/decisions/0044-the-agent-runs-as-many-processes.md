# 0044 — L'agent tourne en plusieurs process, et un seul fait les choses singulières

**Statut : accepté — 2026-07-28**
**Applique :** ADR 0014 (isolation par schéma / par chemin) · ADR 0023 (le journal est un magasin, pas un sink)
**Complète :** ADR 0015 (§Amendment 3 — la tête de chaîne est assignée sous verrou consultatif)

## Contexte

Le cockpit tire ~14 lectures concurrentes par page à travers le tunnel jusqu'à l'agent on-prem.
Les handlers de lecture d'observabilité ont déjà été rendus synchrones (`def`) pour que leurs
lectures DB bloquantes tournent dans le threadpool de Starlette et non sur la boucle d'événements ;
mais **un seul process partage un seul GIL**, donc le travail CPU Python de ces lectures concurrentes
se resérialise. Le threadpool ne parallélise que l'ATTENTE I/O. Mesuré : 22 requêtes concurrentes ≈
22 séquentielles (~4 s), et seulement ~1,8× plus rapide après le threadpool — le GIL borne le CPU.

Le levier restant est d'exécuter l'agent en **N process workers** : N GIL indépendants = vrai
parallélisme CPU pour l'éventail du tableau de bord. uvicorn le fait nativement (`workers=N`). Mais
passer de 1 à N process n'est gratuit pour rien de ce qui, dans un process unique, était singulier
par construction. Trois choses cessent d'être gratuites, et deux se dégradent de façon acceptable.

## Décision

### 1. Un réglage, un défaut identique à hier

`TESSERA_API__WORKERS` (défaut **1**). À 1, `cli()` ne passe **aucun** argument `workers` à uvicorn et
ne pose aucune variable d'environnement multiprocess : le modèle de service est **octet-pour-octet**
celui d'avant cette ADR (un process, dans la boucle courante). À >1, uvicorn lance N workers via son
contexte **spawn** (interpréteur frais par worker, héritant de `os.environ`). On-prem : ~4.
Contrainte de connexions : `pool_max_size × workers` doit rester sous `max_connections` (4×10 = 40 < 100).

### 2. Les métriques Prometheus s'agrègent sur le groupe de process

Chaque worker traite des tours, donc chaque worker incrémente les compteurs — et les pastilles de
niveau L1/L2 lisent `tessera_agent_turns_total` **depuis Prometheus**. Un worker ne voit que 1/N du
trafic. `metrics.configure()` liait aussi le port 9090 dans **chaque** process : les workers 2..N
planteraient sur « address already in use ».

On adopte le **mode multiprocess de `prometheus_client`** : `cli()` exporte `PROMETHEUS_MULTIPROC_DIR`
**avant** le spawn (répertoire **vidé au boot** — des fichiers résiduels seraient sommés dans chaque
compteur). Les objets métriques de chaque worker écrivent leurs valeurs en mmap par-pid ; le seul
**leader** lie 9090 et sert un registre agrégé (`MultiProcessCollector`) qui somme sur tout le groupe.
L'enregistrement ne demande aucune coordination ; seul le serveur d'exposition est singulier. En mode
mono-worker la variable est absente et tout se comporte exactement comme avant.

### 3. Un leader élu par verrou consultatif fait les actes singuliers

Les boucles de fond du lifespan — cycle de scellé Hica, tours canary, purge de rétention RGPD,
re-vérification complète de la chaîne du journal — et les balayages de convergence uniques (archive de
gating, drain/backfill du journal) doivent tourner **une fois**, pas une fois par worker. N scelleurs
concurrents, N boucles de purge : ce n'est pas un gain d'échelle, c'est un bug de correction.

`tessera/api/leader.py` résout ça comme le magasin résout déjà la course de création de schéma — par
un **verrou consultatif Postgres** :

* `try_become_leader()` prend un verrou **de session** sur une connexion **dédiée** (jamais le pool,
  dont les connexions doivent cycler) et le rend à **un seul** worker. Le gagnant garde la connexion
  ouverte toute sa vie (les boucles tournent sous ce leader) ; les perdants servent le trafic de
  requêtes seulement. Si le leader meurt, sa connexion tombe, Postgres relâche le verrou, et un worker
  respawné le ré-acquiert à son prochain boot — le leadership **s'auto-répare**.
* `bootstrap_lock()` prend un verrou **bloquant** le temps du bloc d'`ensure_*_schema`, pour que des
  workers frais concurrents sérialisent leurs `CREATE ... IF NOT EXISTS` au lieu de courir vers une
  erreur de clé dupliquée sur le catalogue (la même course qu'`_isolate_environment` gardait déjà pour
  `CREATE SCHEMA`). Chaque worker exécute le bloc (idempotent), donc sa propre vue a les tables avant
  de servir sa première lecture.

Les deux verrous sont clés par `hashtext(<schéma env>)` : deux environnements partageant un Postgres
ne se contendent jamais (miroir de l'isolation ADR 0014). En mono-worker le process unique gagne
trivialement le leadership et le verrou de bootstrap n'est pas contendu — comportement identique.

### 4. Les magasins-fichiers du cockpit écrivent atomiquement

Une famille de petits documents JSON sur le volume durable (incidents, configs d'agent, automatisations,
curation, packs de preuve, snapshots as-of, bundles de rejeu, …) est réécrite **en entier** à chaque
mutation opérateur via `Path.write_text`, qui **tronque puis écrit**. Avec un process, cette fenêtre
n'est vue que par la requête qui l'a ouverte ; avec N workers, une **lecture** cockpit concurrente sur
un autre worker peut y atterrir et lire un document tronqué — un 500 transitoire qui ressemble à une
perte de données sans en être une.

`tessera/fsutil.py:atomic_write_text` ferme la fenêtre : écriture dans un fichier temporaire voisin,
fsync, puis `os.replace` (atomique quand le temp est sur le même système de fichiers). Un lecteur voit
toujours l'ancien document entier ou le nouveau entier, jamais une écriture déchirée. Appliqué aux 14
magasins concernés (drop-in de leurs `write_text`).

### 5. Ce qui reste sûr sans changement, et ce qui se dégrade en connaissance de cause

* **Sink audit fichier — sûr par construction.** `ledger_source()` vaut `postgres` par défaut, donc
  `_emit_file` est **sauté** et la tête de chaîne est assignée par le drain **dans** un
  `pg_advisory_xact_lock` (ADR 0015 §Amendment 3) : deux writers ne peuvent jamais étendre la même
  tête. Rien à faire.
* **`budget.json` (compteur de coût) — dégradation cosmétique acceptée.** Le tracker est un singleton
  par process ; entre workers, c'est du last-writer-wins. Mais le profil on-prem = Ollama → coût
  marginal 0 → le disjoncteur de budget quotidien (ADR 0034) est **inerte** et le budget affiché reste
  ~0. Si un modèle **payant** revient un jour, migrer le compteur-jour vers un magasin Postgres partagé.
* **Rate limiter in-memory — dégradation acceptée.** Par-worker → limites chat ~N× plus permissives.
  Ollama coût 0 → c'est une garde anti-surcharge locale, pas un budget cloud. Correctif scalable :
  store partagé (Redis via `rate_limit_storage_uri`) — hors périmètre, à ouvrir en ADR si besoin.

## Conséquences

* Le plafond du GIL sur l'éventail cockpit tombe : les lectures concurrentes tournent sur N GIL. Le
  goulot restant devient le tunnel (ngrok gratuit sérialise les rafales de connexions) — un choix
  d'infra (tunnel payant / VPN), pas de code.
* Une nouvelle connexion Postgres persistante par process (le leader) s'ajoute au pool : `workers ×
  (pool_max_size + 1)` doit rester sous `max_connections`. Documenté sur le réglage.
* Le leadership est advisory : si le leader meurt, les boucles de fond pausent jusqu'au respawn du
  worker (qui ré-acquiert). Acceptable pour une démo on-prem `restart: unless-stopped`.
* `atomic_write_text` supprime la classe « lecture tronquée » mais ne sérialise pas le
  read-modify-write entre mutations concurrentes du même document. À cadence humaine mono-opérateur,
  la dernière écriture gagne — acceptable ; un verrou fichier reste ouvrable si la cadence change.
* Invariant préservé : le défaut `workers=1` laisse le modèle de service, les métriques et les boucles
  strictement inchangés. Le multi-worker est un opt-in on-prem.
