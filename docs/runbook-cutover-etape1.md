# Runbook — Étape 1 : mettre le nouveau build en ligne (blue-green)

> Portée : déployer le **nouveau build Tessera** sur la topologie **actuelle** — front sur Cloud Run, agent + Postgres + Ollama on-prem, tunnelés — **sans rien changer à la posture de l'agent**. Bascule du front en **blue-green** (pas de canari : à trafic portfolio, un ramp ne mesure rien).
>
> **Ce qu'on NE fait PAS en étape 1** (tout ça = étape 2, passage tout-GCP) : pas de `TESSERA_ENVIRONMENT=production`, pas de Terraform, pas de `cloud_logging` ni aucun service GCP au-delà du Cloud Run du front, pas de schéma neuf, pas de re-seed. L'agent reste en `local` / `on_prem` / sink `file`, **sa donnée est préservée**. On remplace le **code**, pas la **posture**.

---

## 0. Pré-vol

- **Fenêtre à faible trafic.** L'update de l'agent implique un court redémarrage (~1 min) pendant lequel le front live parle à un agent qui reboote. Acceptable pour une démo ; fais-le à une heure creuse.
- **Ordre imposé** : agent d'abord (le nouveau front sera testé contre l'agent déjà à jour, pas contre l'ancien), front ensuite.
- **Rollback prêt à chaque étape** : DB sauvegardée, révision front précédente gardée chaude 48 h.
- Remplace les `<PLACEHOLDERS>` avec ce que te rend la section 1.

---

## 1. Découvrir l'état courant (lecture seule — ne devine rien)

```bash
# Front Cloud Run : nom du service, révision qui sert le trafic, variables d'env
gcloud run services list --project <PROJ> --region europe-west1
gcloud run services describe <FRONT_SERVICE> --project <PROJ> --region europe-west1 \
  --format='value(status.traffic, spec.template.spec.containers[0].env)'

# Comment le domaine est attaché → décide la forme du cutover (§5)
gcloud run domain-mappings list --project <PROJ> --region europe-west1
#   + regarde l'enregistrement DNS `tessera` dans Cloudflare :
#     - CNAME -> ghs.googlehosted.com ........ domain-mapping Cloud Run  → Cas A
#     - CNAME (proxy orange) -> *.run.app .... CNAME direct              → Cas A
#     - CNAME -> *.cfargotunnel.com .......... tunnel nommé              → Cas B
```

Note trois choses : `<FRONT_SERVICE>`, la **révision live actuelle** (= ton rollback, appelons-la `<PREV_REV>`), et l'URL du **tunnel agent** que le front porte dans `TESSERA_BACKEND_URL` (elle ne doit pas changer).

---

## 2. Sauvegardes (avant de toucher à quoi que ce soit)

Sur la box on-prem, à la racine du repo :

```bash
mkdir -p backups
TS=$(date +%Y%m%d-%H%M%S)

# Base : le schéma racine historique = toute ta donnée de démo + le ledger
docker exec tessera-local-postgres pg_dump -U tessera tessera > backups/db_$TS.sql

# Volume d'état de l'agent (audit file /tmp/tessera/audit.log + budget)
docker run --rm -v tessera_agent_state:/data -v "$PWD/backups:/backup" alpine \
  tar czf /backup/agent_state_$TS.tgz -C / data

ls -lh backups/   # vérifie que les deux fichiers sont non vides
```

`<PREV_REV>` (révision front live) est déjà noté en §1 : c'est ton rollback côté cloud.

---

## 3. Mettre à jour l'agent on-prem — **nouveau code, posture identique**

Identique en tout (env `local`, `on_prem`/Ollama, sink `file`, **même volume de données** `tessera_agent_state`, même tunnel) — **seul le code change**.

```bash
git pull                      # le nouveau build (gate F-1/F-6/F-9 fermé, correctifs audit)

# Migrations SI le build en apporte — tu as le dump de §2 en filet.
# Vérifie la continuité du ledger (hash-chain) et les compteurs de lignes APRÈS.
make migrate                  # ou la commande de migration du repo, si applicable

# Rebuild + restart de l'agent SEUL, même config, même volume (commande du runbook)
docker compose -f docker-compose.yml -f docker-compose.unix.yml up -d --build --no-deps agent
```

Vérifier avant d'aller plus loin :

```bash
curl -fsS http://localhost:8099/api/healthz        # agent vivant (adapte le path si besoin)
# tunnel up + un vrai aller-retour de chat via le tunnel → réponse cohérente
# la chaîne d'audit se vérifie (pas de rupture après migration)
```

> **Option « ne pas toucher l'agent du tout »** : si tu veux vraiment le laisser intact en étape 1, saute la §3 — **mais** assure-toi alors que le nouveau front est compatible avec le contrat d'API de l'agent actuel (sinon skew de version). Par défaut, mets le nouveau build partout : c'est ce que « passer en prod » veut dire.

---

## 4. Déployer le nouveau front en blue-green (Cloud Run, sans trafic)

```bash
TAG=$(git rev-parse --short HEAD)
IMG=europe-west1-docker.pkg.dev/<PROJ>/tessera/tessera-frontend:$TAG

# Build + push de l'image front (Dockerfile du repo, contexte = racine)
docker build -f infra/docker/Dockerfile.frontend -t "$IMG" .
docker push "$IMG"

# Déploie une révision SANS trafic, taguée `green`.
# Cloud Run reporte automatiquement les env vars + secrets de la révision actuelle :
# SEULE l'image change (donc TESSERA_BACKEND_URL/tunnel, TESSERA_ENVIRONMENT=local, etc. inchangés).
gcloud run deploy <FRONT_SERVICE> --project <PROJ> --region europe-west1 \
  --image "$IMG" --no-traffic --tag green
```

Smoke-test **de bout en bout** l'URL taguée (elle traverse le tunnel jusqu'au nouvel agent) :

```bash
GREEN=https://green---<FRONT_SERVICE>-<hash>.europe-west1.run.app   # rendu par la commande
curl -fsS "$GREEN/api/healthz"
curl -fsS -L "$GREEN/fr" >/dev/null && curl -fsS -L "$GREEN/en" >/dev/null && curl -fsS -L "$GREEN/de" >/dev/null
```

Puis à la main, sur `$GREEN` : un vrai message de chat (aller-retour complet), le cockpit **peuplé** (ta donnée de démo est là, pas de tableaux vides), la trace d'exécution gardée, et un panneau honest-empty là où c'est attendu.

---

## 5. Bascule (le cutover) — selon la §1

**Cas A — le domaine pointe déjà sur `<FRONT_SERVICE>`** (domain-mapping ou CNAME → run.app). La bascule est atomique et instantanée côté Cloud Run :

```bash
gcloud run services update-traffic <FRONT_SERVICE> --project <PROJ> --region europe-west1 \
  --to-tags green=100
```

**Cas B — le domaine pointe ailleurs** (ancien stack / tunnel séparé). Pointe l'enregistrement Cloudflare `tessera` vers le nouveau front (cible du domain-mapping, ou CNAME proxifié → le service). **Laisse l'ancienne cible vivante** le temps de la fenêtre de rollback.

Dans les deux cas : **garde l'ancien chaud ~48 h.**

---

## 6. Vérifier en prod + rollback armé

Sur `https://tessera.amadoumamane.fr` directement : `/fr /en /de`, un aller-retour de chat, les panneaux du cockpit peuplés, la trace gardée, la bannière « démo · données fictives » toujours là.

Rollback en une commande, prêt à coller :

```bash
# Cas A — retour à la révision précédente, instantané
gcloud run services update-traffic <FRONT_SERVICE> --project <PROJ> --region europe-west1 \
  --to-revisions <PREV_REV>=100
# Cas B — repointe le DNS Cloudflare sur l'ancienne cible
# Agent — restaure depuis backups/db_$TS.sql + agent_state_$TS.tgz si nécessaire
```

---

## 7. Après 48 h stables — décommissionner l'ancien

- Cas A : l'ancienne révision reste comme historique de rollback ; rien d'urgent à supprimer.
- Cas B : coupe l'ancien chemin (ancien service / ancien tunnel).
- **Archive v1** : un tag git + 2–3 captures ou une vidéo de 60 s dans `docs/`. Le « avant » existe comme preuve, sans second site vivant.

---

## Récap des invariants (ce qui n'a pas bougé)

`TESSERA_ENVIRONMENT=local` · `TESSERA_LLM_PROFILE=on_prem` (Ollama) · sink d'audit `file` · schéma racine historique · **données de démo préservées** · tunnel agent inchangé · aucun Terraform · aucun service GCP nouveau · aucun `cloud_logging`. La « prod » de l'étape 1 est une affaire de **topologie + domaine**, pas de l'enum. Le reste attend l'étape 2.
