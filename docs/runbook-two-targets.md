# Runbook — two deployment targets on one OVH domain (ADR 0048)

Goal: serve the cockpit from **both** the full-local front and the Cloud Run front at once, on
`amadoumamane.fr`, so you can compare their performance; keep one canonical public URL; and never let
the two drift apart.

DNS is at **OVH**. Every hostname below is **one CNAME you add at OVH**. The steps that need
Cloudflare/GCP/ngrok credentials are **yours to run** — Claude cannot enter tokens, touch consoles,
or edit DNS. The config, the version stamp, and the divergence witness are already in the repo.

## The addressing (what points where)

| Host | Serves | OVH record |
|------|--------|-----------|
| `onprem.amadoumamane.fr` | full-local front (ADR 0045), agent over the local Docker net | `CNAME` → your ngrok custom-domain edge |
| `gcp.amadoumamane.fr` | Cloud Run front → on-prem agent via tunnel | `CNAME` → `ghs.googlehosted.com.` |
| `tessera.amadoumamane.fr` | **the canonical public URL** (the switch) | `CNAME` → the `primary` target's host |

`tessera.` is where people go; it is the switch. A bare-apex `CNAME` (`amadoumamane.fr` with no
subdomain) is invalid DNS, which is exactly why the switch lives on `tessera.`, not the apex.

Declared once in `infra/deploy/targets.yaml` (`domain`, `canonical`, `primary`, `image`). Flipping
which target is canonical = repoint the `tessera` CNAME **and** set `primary:` to match.

## 0. The single image (prevents divergence at the source)

Both fronts must run the **same** image. CI (`deploy.yml`) builds and pushes
`…/tessera-frontend:<sha>` with the commit SHA **baked in** (`ARG TESSERA_BUILD_SHA`). 

- **Cloud Run** already deploys that tag.
- **Full-local** must *pull* it instead of building locally:
  ```sh
  export TESSERA_FRONTEND_IMAGE=<region>-docker.pkg.dev/<project>/<repo>/tessera-frontend:<sha>
  gcloud auth configure-docker <region>-docker.pkg.dev   # once, for read access
  make fulllocal-up                                       # now pulls the SAME bytes Cloud Run runs
  ```
  Set `image:` in `targets.yaml` to that same `tessera-frontend:<sha>` so the record matches reality.

Leaving `TESSERA_FRONTEND_IMAGE` unset keeps the old local-build path for development — but then the
front reports `sha=dev`, and `make deploy-diff` will (correctly) refuse to call it a match.

## 1. `onprem.amadoumamane.fr` — full-local via ngrok custom domain

You already run ngrok. A **custom domain** needs a paid ngrok plan.

1. In the ngrok dashboard: add the domain `onprem.amadoumamane.fr`. ngrok shows you a **CNAME
   target** to use.
2. At **OVH** (zone `amadoumamane.fr`): add `CNAME  onprem  →  <the ngrok target>`.
3. Bring the full-local pair up and start the tunnel on the front port (3090):
   ```sh
   export TESSERA_AGENT_STATE=/Users/amadou/.tessera/agent-state
   make fulllocal-up                              # front :3090 + agent, LOCAL
   ngrok http --domain=onprem.amadoumamane.fr 3090
   ```
   (The `cloudflared` service in the overlay is the *Cloudflare* path; with OVH DNS + ngrok you use
   the command above instead, so you do **not** run `make fulllocal-tunnel`.)

## 2. `gcp.amadoumamane.fr` — Cloud Run domain mapping

1. Create the mapping (GCP console or gcloud):
   ```sh
   gcloud run domain-mappings create \
     --service=<frontend-service> --domain=gcp.amadoumamane.fr --region=<region>
   ```
2. Cloud Run prints a DNS record (a `CNAME` to `ghs.googlehosted.com.` for a subdomain). Add it at
   **OVH**: `CNAME  gcp  →  ghs.googlehosted.com.`
3. Wait for the managed certificate to go green (a few minutes).

## 3. The canonical switch — `tessera.amadoumamane.fr`

Point it at whichever target is `primary`:
- primary = onprem → `CNAME  tessera  →  <ngrok target>`
- primary = gcp → `CNAME  tessera  →  ghs.googlehosted.com.`

Then set `primary:` in `targets.yaml` to match. That is the whole flip: one OVH record + one field.

## 4. Verify parity — the witness

```sh
make deploy-diff
```
- **exit 0** — every host (`onprem`, `gcp`, `tessera`) serves the same real SHA. Match.
- **exit 1** — the SHAs differ, named per host. This is the "an old version is still served" bug
  (today `tessera.amadoumamane.fr` serves a stale build) — now a loud verdict, not a surprise.
- **exit 2** — blind: a host is unreachable, reports `sha=dev` (un-stamped), or the domain is unset.

Run it after every deploy. To keep the two honest continuously, wire `make deploy-diff` into a cron
(the `schedule` skill) or a post-deploy step — a green here is the standing proof they have not
diverged.

## Anti-divergence discipline (the point of all this)

1. One commit → one SHA-tagged image → **both** targets pull that tag. Never build the front two
   different ways for the two hosts.
2. After any deploy, `make deploy-diff` must be **exit 0** before you consider the deploy done.
3. The agent is a single on-prem process both fronts reach — it cannot diverge from itself; the only
   thing this runbook has to keep aligned is the front image, and `deploy-diff` is what proves it.
