# 0045 — Le mode « full-local » co-localise le front avec l'agent pour supprimer le tunnel de la boucle chaude

**Statut : accepté — 2026-07-28**
**Applique :** ADR 0044 (l'agent multi-process ; les gains agent sont réels mais masqués end-to-end par le tunnel)
**Complète :** ADR 0043 (le cutover : front Cloud Run / agent on-prem via tunnel)

## Contexte

Le cutover (ADR 0043) fait tourner le front sur Cloud Run et l'agent on-prem, reliés par un
tunnel public. Mesuré end-to-end, **ce tunnel est le plafond dominant** : même un endpoint à
0,05 s coûte ~0,3 s en isolé / ~1 s à 10-concurrent à travers le tunnel gratuit, et **chaque page
cockpit tire ~14 appels front→agent** (le BFF proxifie chaque lecture). Les optimisations agent
landées (multi-worker ADR 0044, memos chrome/timeline/fleet) sont réelles — prouvées en direct
sur l'agent — mais **masquées end-to-end** parce que chaque appel paie un aller-retour internet
transeuropéen incompressible, même avec un tunnel parfait.

Le levier restant n'est pas du code : c'est la **topologie**. Si le front tourne à côté de
l'agent, les 14 hops front→agent deviennent **locaux** (réseau Docker, sub-milliseconde) et seul
le hop navigateur→front traverse un tunnel — une fois, multiplexé.

## Décision

Ajouter un mode de déploiement **full-local**, en overlay sur le cutover, où le front Next.js
tourne **dans un conteneur à côté de l'agent** et l'atteint par le réseau Docker local.

### 1. Un overlay qui empile sur le cutover, sans toucher l'agent

`docker-compose.fulllocal.yml` ajoute le service `frontend` (déjà défini en base, câblé sur
`TESSERA_BACKEND_URL=http://agent:8080`) sur le réseau `data` de l'agent, plus un service
`cloudflared`. **Rien de l'agent ne change** : il reste le conteneur cutover 4-workers,
`TESSERA_ENVIRONMENT=local`, sur les mêmes stacks data + obs et le même volume durable.

### 2. Le front s'adapte au domaine, aucun domaine n'est gravé

`auth.ts` a `trustHost: true` et une session JWT : le front dérive son origine des en-têtes
transmis (`X-Forwarded-Host`/`-Proto`) que le tunnel pose. La **même image sert `localhost` et
le domaine** sans reconstruction — le domaine n'est écrit nulle part dans le repo. Les trois
secrets du front (bearer, `AUTH_SECRET`, clé d'assertion opérateur) sont lus au RUNTIME (l'image
ne cuit qu'un `AUTH_SECRET` jetable) depuis `frontend.secret.env`, gitignoré.

### 3. Le tunnel est un service SÉPARÉ et GATÉ — le démarrer EST le flip

`cloudflared` est sous `profiles: [flip]` : `make fulllocal-up` monte le front + l'agent en
**localhost uniquement**, sans jamais toucher le domaine. `make fulllocal-tunnel` publie le front
sur le domaine — c'est l'équivalent du flip de trafic Cloud Run, et il ne se lance jamais tout
seul. Réversible par `make fulllocal-tunnel-down`. Le token du connecteur vit dans
`infra/docker/fulllocal.env`, gitignoré ; l'ingress (domaine → `http://frontend:3000`) se règle
dans le tableau de bord Cloudflare. Le domaine reste **enregistré chez OVH** — seule sa
délégation DNS bascule (nameservers), ou un CNAME OVH pour l'alternative ngrok payante.

## Conséquences

* Les gains agent (multi-worker, memos) cessent d'être masqués : les 14 lectures d'une page sont
  locales, et le tunnel ne porte plus que le navigateur→front (une fois, HTTP/2 multiplexé).
* **L'uptime devient celui de la machine** : servir publiquement depuis un conteneur local rend
  le site en ligne tant que la machine tourne — la propriété qu'a déjà l'agent on-prem. Adapté à
  une démo pilotée, pas un substitut au scaling/uptime managé de Cloud Run. Le cutover Cloud Run
  reste disponible en parallèle ; ce mode ne le supprime pas, il l'alterne.
* **Sécurité avant exposition** : sur un domaine public, les mots de passe opérateur par défaut
  (affichés dans l'UI de login) doivent être remplacés par de vrais (`TESSERA_AUTH_*`) ; le
  runbook l'exige à l'étape de validation. Le mot de passe superadmin est posé et gardé par
  l'opérateur, jamais dans le repo.
* Portée volontairement limitée : aucun changement de code applicatif, aucune ressource GCP, pas
  de Terraform. C'est de la topologie de déploiement — compose + Makefile + runbook — et le flip
  reste un acte manuel gaté.
