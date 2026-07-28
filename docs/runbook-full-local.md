# Runbook — Full-local deployment (front co-located with the agent)

**What this is.** An alternative to the Cloud Run cutover: run the Next.js **front in a
container next to the agent**, on-prem. The front reaches the agent over the **local Docker
network** (`http://agent:8080`), so the ~14 front→agent calls a cockpit page makes stay
local instead of crossing a public tunnel. Only the **browser→front** hop is exposed — once,
multiplexed, on your own domain via a Cloudflare Tunnel. See ADR 0045 for the why.

**Why.** Measured end-to-end, the free tunnel between Cloud Run (front) and the on-prem agent
was the dominant ceiling: even a 0.05 s endpoint cost ~0.3 s single / ~1 s at 10-concurrent
through it, and every page fires ~14 such calls. Co-locating the front collapses those 14
tunnelled round-trips to local ones — which is what lets the agent-side work (multi-worker,
the chrome/timeline/fleet memos) actually be felt.

```
  BEFORE (cutover):  browser → [tunnel] → Cloud Run front → [TUNNEL ×14] → on-prem agent
  AFTER  (full-local): browser → [tunnel] → local front → [local net ×14] → local agent
```

Nothing about the agent changes: it stays `TESSERA_ENVIRONMENT=local`, the same 4-worker
cutover container on the same live data + obs stacks and the same durable state volume.

---

## 0. Prerequisites

- The live **data + obs stacks are up** (Postgres, ClickHouse, …) — the same ones the cutover
  agent joins. `make fulllocal-up` runs with `--no-deps`, so it never starts the base `postgres`
  service (which would clash on 5432); it relies on the live one already running.
- **`TESSERA_AGENT_STATE` exported** to the durable state dir, exactly as for the cutover —
  `make fulllocal-up` refuses without it, because an unset value would recreate the running agent
  onto an empty volume.
- **`frontend.secret.env`** — copy the example and fill the **three** secrets, each of which
  must MATCH the agent's side (or operator pages 401):

  ```
  cp frontend.secret.env.example frontend.secret.env
  # TESSERA_BACKEND_TOKEN                        == agent TESSERA_API__BEARER_TOKEN
  # AUTH_SECRET                                  (openssl rand -base64 33)
  # TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY   == agent TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY
  ```

- **`infra/docker/fulllocal.env`** — only needed for the flip (step 3); holds the tunnel token.

---

## 1. Bring the pair up — LOCAL only (no tunnel, nothing public)

```
make fulllocal-up
```

Builds the front image, brings up the agent (unchanged) + the front, waits for health, and
prints `http://localhost:3090`. **No tunnel is started**; your domain is untouched.

## 2. Validate on localhost

- Open `http://localhost:3090` — the login page loads.
- Log in as an operator; the cockpit pages load and show real data (the front is reaching the
  local agent). `make fulllocal-status` shows both `healthy` and the tunnel as *not running*.
- The felt latency here has **no tunnel between front and agent** — this is the point.

**Before exposing publicly:** set real operator passwords in `frontend.secret.env`
(`TESSERA_AUTH_*`) — the demo defaults are shown in the login UI and are unsafe on a public
domain. The superadmin password is yours to set and keep; it is never in the repo.

## 3. THE FLIP — publish on your domain (gated; do only when ready)

This is the equivalent of the Cloud Run traffic flip. Do it only after step 2 is clean.

### Cloudflare Tunnel (recommended — free; domain stays registered at OVH)

Your domain stays at OVH. You delegate its **DNS** (nameservers) to Cloudflare; the domain
itself never leaves OVH.

1. Cloudflare Zero Trust dashboard → **Networks → Tunnels → Create a tunnel** (token type).
2. Add a **Public Hostname** on the tunnel: your host (e.g. `cockpit.example.com`) →
   **Service: `http://frontend:3000`**.
3. Copy the connector **token** into `infra/docker/fulllocal.env` (`TUNNEL_TOKEN=…`).
4. Flip:
   ```
   make fulllocal-tunnel
   ```
5. Visit your domain over HTTPS (Cloudflare provides the certificate). The front auto-adapts
   to the host (`trustHost` + forwarded headers) — no rebuild, no domain baked in.

### ngrok alternative (keep OVH DNS entirely — one CNAME)

With a paid ngrok custom domain you add **one CNAME at OVH** and skip cloudflared:
```
ngrok http --domain=<your domain> 3090
```

## 4. Rollback

```
make fulllocal-tunnel-down     # stop the tunnel — the domain stops resolving to this front
```
Then point DNS back to the previous target (Cloud Run) if the domain was moved. The Cloud Run
green/blue revisions are untouched by anything here; the cutover flip remains separately gated.

## Stop / status

```
make fulllocal-status          # front + agent health, ports, tunnel state
make fulllocal-down            # stop front (+ tunnel); leaves the agent. AGENT=1 also stops it
```

## Notes

- **Uptime is your machine.** Publicly serving from a local container means the site is up
  while the machine is — the same property the on-prem agent already has. Fine for a piloted
  demo; not a managed-uptime replacement for Cloud Run.
- **TLS** is terminated by the tunnel (valid cert at the edge); the local front serves plain
  HTTP inside the network.
- **No secret is in the repo:** `frontend.secret.env` and `infra/docker/fulllocal.env` are
  gitignored (`*.env`); only their `.example` templates are tracked.
