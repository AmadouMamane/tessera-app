# Runbook

Operational reference for deploying, observing, and recovering the Tessera
agent on Google Cloud Run. The infrastructure is described in
`infra/terraform/` and the deploy is automated through the `deploy.yml` GitHub
Actions workflow. This document is the on-call companion: how to ship it, how to
watch it, and what to do when it misbehaves.

For the self-hosted path see `docs/on_prem.md`; for the local quickstart see the
last section here.

**Two Cloud Run services** are provisioned (`infra/terraform/`): the FastAPI
**agent** (`tessera-agent`, port 8080) and the Next.js **front-end**
(`tessera-frontend`, port 3000) which is the public entry point. The browser
only ever talks to the front-end; it proxies API calls to the agent
server-side, injecting the shared bearer token. See **Security model** and
**Exposing a local stack to the web** below. To put a local stack online
quickly (before any cloud deploy), jump to **Exposing a local stack to the
web**.

## Deployment prerequisites

- A GCP project with billing enabled.
- The following APIs enabled: **Cloud Run**, **Cloud SQL Admin**, **Secret
  Manager**, **Vertex AI**, and **Serverless VPC Access** (the service uses
  private VPC egress to reach Cloud SQL).
- **Terraform ≥ 1.7**.
- `gcloud` authenticated against the target project with rights to manage Cloud
  Run, Cloud SQL, Secret Manager, and IAM.
- A container image for the agent, built from `infra/docker/Dockerfile.agent`
  and pushed to a registry the Cloud Run service account can read.
- A container image for the front-end, built from
  `infra/docker/Dockerfile.frontend`, pushed to the same registry (passed to
  Terraform as `frontend_image`).

## Deploy steps

### 1. Provision infrastructure

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

This creates the Cloud Run service, the Cloud SQL Postgres instance (pgvector
enabled via the `cloudsql.enable_pgvector` flag), the Secret Manager secrets,
the log bucket retention, the audit log sink to a dedicated GCS bucket, the
log-based metrics, the monitoring dashboard, and the alert policies.

### 2. Populate secrets

Terraform creates the secret *containers* and placeholder versions; you add the
real values. The application reads these as secret-backed environment variables
at container start.

```bash
gcloud secrets versions add bearer_token        --data-file=-   # API auth token
gcloud secrets versions add postgres_url         --data-file=-   # full Postgres DSN
gcloud secrets versions add audit_signing_key     --data-file=-   # audit log signing key
gcloud secrets versions add vertex_project_id      --data-file=-   # Vertex AI project id
```

(Pipe the value into each command, e.g. `printf '%s' "$TOKEN" | gcloud secrets
versions add bearer_token --data-file=-`.)

### 3. Build and push the image

```bash
# Agent
docker build -f infra/docker/Dockerfile.agent -t REGION-docker.pkg.dev/PROJECT/tessera/agent:TAG .
docker push REGION-docker.pkg.dev/PROJECT/tessera/agent:TAG

# Front-end (pass the resulting tag to Terraform as `frontend_image`)
docker build -f infra/docker/Dockerfile.frontend -t REGION-docker.pkg.dev/PROJECT/tessera/frontend:TAG .
docker push REGION-docker.pkg.dev/PROJECT/tessera/frontend:TAG
```

### 4. Deploy to Cloud Run

Trigger the `deploy.yml` workflow (push to the deploy branch or run it manually).
It points the Cloud Run service at the new image tag and shifts 100% of traffic
to the latest revision (`TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST`).

## Environment variables

Plain values are set on the Cloud Run container directly; secret-backed values
are resolved from Secret Manager at start. Defaults are from
`src/tessera/settings.py`.

| Variable                          | Default (settings)            | Source in prod                    |
| --------------------------------- | ----------------------------- | --------------------------------- |
| `TESSERA_ENVIRONMENT`             | `local`                       | plain (`production`)              |
| `TESSERA_LLM_PROFILE`             | `auto`                        | plain (`frontier` on Cloud Run)   |
| `TESSERA_DEFAULT_LANGUAGE`        | `fr`                          | plain                             |
| `TESSERA_VERTEX__PROJECT_ID`      | unset                         | plain (project id)                |
| `TESSERA_VERTEX__LOCATION`        | `europe-west1`                | plain (region)                    |
| `TESSERA_VERTEX__CHAT_MODEL`      | `gemini-2.0-flash-001`        | plain                             |
| `TESSERA_VERTEX__EMBEDDING_MODEL` | `text-multilingual-embedding-002` | plain                         |
| `TESSERA_OBS__CLOUD_LOGGING_PROJECT` | unset                      | plain (project id)                |
| `TESSERA_GUARD__AUDIT_SINK`       | `file`                        | plain (`cloud_logging`)           |
| `TESSERA_POSTGRES__DSN`           | local DSN                     | **secret** `postgres_url`         |
| `TESSERA_API__BEARER_TOKEN`       | unset                         | **secret** `bearer_token`         |
| `TESSERA_API__RATE_LIMIT_CHAT`    | `20/hour`                     | plain (per-session /chat limit)   |
| `TESSERA_API__RATE_LIMIT_CHAT_GLOBAL` | `200/hour`                | plain (hard global /chat cap)     |
| `TESSERA_API__TRUST_FORWARDED_HEADERS` | `false`                  | plain (`true` behind a proxy)     |

The **front-end** service takes two of its own variables (`infra/terraform/cloud_run_frontend.tf`): `TESSERA_BACKEND_URL` (set to the agent service URI) and `TESSERA_BACKEND_TOKEN` (the **same** value as the agent's `bearer_token` secret — it is server-only and injected into outbound calls, never exposed to the browser).

The audit signing key and Vertex project id secrets are populated as above; the
guard's audit sink is set to `cloud_logging` in production so entries flow into
the audit GCS bucket via the log sink. Other settings (pool sizes, confidence
threshold, timeouts) keep their defaults unless overridden by their respective
`TESSERA_*` variables.

## Health checks

- **`/healthz`** — liveness. Returns 200 with `{status, version}` as soon as the
  process is up (`src/tessera/api/routes/health.py`). The Cloud Run **liveness
  probe** hits it every 30 s.
- **`/readyz`** — readiness, distinct from liveness so deployments can stagger.
- **Startup probe** — a TCP probe on port 8080, 5 s period, up to 12 failures
  (~60 s) before the revision is considered failed to start
  (`infra/terraform/cloud_run.tf`).
- **Postgres connectivity** is exercised at startup when the app opens its
  connection pool and ensures the `vector` extension / `documents` table; a DB
  that is unreachable will fail the revision before it serves traffic.
- **`/budget`** — running LLM cost estimate (input/output tokens, estimated EUR)
  as `text/plain` for quick scrapes.

## Observability

A Cloud Monitoring dashboard (**Tessera — {environment}**) is provisioned with
six tiles (`infra/terraform/observability.tf`):

1. **Request count** — by response-code class.
2. **Request latency** — p95 (REDUCE_PERCENTILE_95).
3. **CPU utilisation**.
4. **HTTP 5xx errors** — from the `http_5xx` log-based metric.
5. **Guard deny decisions** — from the `guard_denies` log-based metric, grouped
   by target tool.
6. **Active instances**.

Two alert policies are configured:

- **HTTP error rate > 5% over 5 min** — on the built-in Cloud Run
  `request_count` metric filtered to the `5xx` response-code class.
- **Guard deny storm** — fires when `guard_denies` exceeds **20 in a 10-minute
  window**. A spike may indicate a prompt-injection attempt; the alert
  documentation links here.

Both policies have empty `notification_channels` in Terraform — wire your
channels (PagerDuty, email, Slack) before relying on them.

## Audit log

- **Local:** JSON lines written to `/tmp/tessera/audit.log`
  (`GuardSettings.audit_file`, sink `file`).
- **Production:** the guard's audit sink is `cloud_logging`; entries carry
  `jsonPayload.type="tessera.guard.audit"`. A log sink routes exactly those
  entries to the dedicated GCS bucket `PROJECT-SERVICE-audit` for independent
  archiving and review.
- **Format:** one JSON object per entry, including outcome (`denied` / allowed),
  the target tool, and the decision context.
- **Retention / rotation:** the main log bucket honours `log_retention_days`;
  the audit GCS bucket has a 365-day delete lifecycle rule and
  `force_destroy = false` so it cannot be wiped accidentally.

## On-call procedures

### High error rate (5xx alert firing)

1. Read recent logs:
   `gcloud logging read 'resource.type="cloud_run_revision"' --limit 50`.
2. Check for a **guard deny-storm** in the same window — a flood of denies can
   surface as upstream errors. Filter
   `jsonPayload.type="tessera.guard.audit" AND jsonPayload.outcome="denied"`.
3. Check the LLM backend health: Vertex AI quota/availability on the frontier
   path, or the Ollama daemon on the on-prem path.
4. Check the most recent Cloud Run revision in the console — if the error
   started at a deploy, roll back (below).

### Escalation storm (too many turns escalating)

1. Review recent audit entries to see which tool / decision is escalating.
2. Check the **confidence threshold** setting
   (`GuardSettings.escalation_confidence_threshold`, default 0.6). A threshold
   set too high forces benign turns into escalation; a misbehaving LLM backend
   produces uniformly low confidence.
3. Confirm the LLM backend is healthy — degraded generation lowers confidence
   across the board.

### Corpus staleness (wrong or outdated regulatory answers)

1. Re-ingest:
   `uv run python scripts/ingest_regulations.py` then
   `uv run python scripts/seed_demo.py`.
2. Verify the chunk count after ingest — **expected ~238 chunks**. A materially
   different count signals a partial or duplicated ingest.

## Rollback

Shift traffic back to the last known-good revision:

```bash
gcloud run services update-traffic SERVICE \
  --region REGION \
  --to-revisions PREVIOUS_REVISION=100
```

Because traffic normally tracks `LATEST`, pinning to an explicit prior revision
takes effect immediately and freezes auto-promotion until you re-point at
`LATEST`.

## Local development

```bash
docker compose up -d postgres
uv run python scripts/run_local.py
```

This starts the `pgvector/pgvector:pg16` container and runs the agent locally.
With no Vertex project configured, the `auto` profile falls back to the on-prem
Ollama path — see `docs/on_prem.md` for the Ollama setup. Set
`TESSERA_LLM_PROFILE=on_prem` to force it.

## Security model (login-less public demo)

The agent can be exposed to the public web without forcing visitors to
authenticate, while still protecting the backend and bounding LLM cost.

- **Bearer token = service-to-service secret, not user auth.** When
  `TESSERA_API__BEARER_TOKEN` is set, `AuthMiddleware` rejects any request to a
  non-exempt path without a matching `Authorization: Bearer` header (401).
  Exempt paths: `/healthz`, `/readyz`, `/metrics`, `/docs`, `/openapi.json`.
  The **front-end holds the same value** in `TESSERA_BACKEND_TOKEN` (server
  side) and injects it on every backend call. The end user never sees it and
  never logs in; a script hitting the agent URL directly gets 401.
- **Rate limiting (`src/tessera/api/ratelimit.py`).** `POST /chat` is guarded by
  two buckets that must both pass: a **per-session** limit
  (`TESSERA_API__RATE_LIMIT_CHAT`, default `20/hour`, keyed by the
  `X-Session-Id` cookie the front sets) and a **hard global cap**
  (`TESSERA_API__RATE_LIMIT_CHAT_GLOBAL`, default `200/hour`) that bounds total
  cost across all sessions. The limiter keys on the session id rather than the
  shared bearer token (which would collapse every caller into one bucket).
- **Behind a proxy / tunnel**, set `TESSERA_API__TRUST_FORWARDED_HEADERS=true`
  so the identity falls back to `X-Forwarded-For` / `CF-Connecting-IP` when no
  session header is present.
- **Where secrets live locally.** Keep them out of the root `.env`/`.env.local`
  (the app's Settings reads those, which would leak the token into tests):
  - backend container: `agent.secret.env` (gitignored), loaded via the compose
    `env_file:` directive;
  - front: `webapp/frontend/.env.local` (gitignored), read by Next only.

## Exposing a local stack to the web (tunnel)

Put the local stack online without a domain, DNS, or port-forwarding — useful
for a portfolio demo. Only the front-end is exposed; the agent, Postgres and
Ollama stay on localhost.

```bash
# 1. Postgres (already seeded; idempotent) + agent container on host port 8099.
#    The unix overlay lets the container reach host-native Ollama.
docker compose -f docker-compose.yml -f docker-compose.unix.yml up -d --build --no-deps agent

# 2. Front-end (dev) on 3099, proxying to the agent on 8099. Reads
#    webapp/frontend/.env.local (TESSERA_BACKEND_URL + TESSERA_BACKEND_TOKEN).
npm --prefix webapp/frontend run dev

# 3. Public HTTPS URL for the front (no account needed for a quick tunnel).
cloudflared tunnel --url http://localhost:3099   # -> https://<random>.trycloudflare.com
```

Flow: `Web → cloudflared → Next :3099 → (server-side proxy, token injected) →
agent :8099 → Ollama + Postgres`. Stop with `pkill -f "cloudflared tunnel"`,
`pkill -f "next dev"`, and `docker compose ... stop agent`.

Notes: local host ports are **8099 (agent) / 3099 (front)** to avoid collisions
on frequent local runs; container-internal ports and Cloud Run stay on the
defaults (8080/3000). A quick tunnel URL is ephemeral and unauthenticated — for
a durable/private share use a **named** Cloudflare tunnel with **Cloudflare
Access** (login gate) or rely on the bearer token + rate limits above.

## Phase 2 — front on Vercel + Postgres on Neon (config-driven)

The local → cloud switch is environment variables only, no code changes:

| Concern        | Variable                     | Local                         | Phase 2                                  |
| -------------- | ---------------------------- | ----------------------------- | ---------------------------------------- |
| Database       | `TESSERA_POSTGRES__DSN`      | `…@localhost:5432`            | Neon DSN (`…neon.tech`, `pgvector` ext)  |
| Front → agent  | `TESSERA_BACKEND_URL`        | `http://localhost:8099`       | agent tunnel / Cloud Run URL             |
| Service secret | `TESSERA_API__BEARER_TOKEN` / `TESSERA_BACKEND_TOKEN` | unset/local | strong secret, same on both sides   |
| LLM            | `TESSERA_LLM_PROFILE`        | `on_prem` (Ollama)            | `on_prem` (tunnelled) or `frontier` (API)|

Steps: (1) create a Neon project, enable `CREATE EXTENSION vector;`, run
ingestion locally pointed at the Neon DSN (`TESSERA_POSTGRES__DSN=… uv run
tessera-ingest` + `… python scripts/seed_demo.py`); (2) deploy the front to
Vercel, setting `TESSERA_BACKEND_URL` and `TESSERA_BACKEND_TOKEN` as Vercel env
vars (server-only, **not** `NEXT_PUBLIC_*`); (3) expose the agent (Cloud Run, or
a named tunnel from the on-prem box for the Ollama path) and point
`TESSERA_BACKEND_URL` at it.

**Evaluations demo data (required, else the page is empty).** `eval/reports` and
the governed waiver journal are **runtime artifacts** (reports gitignored; the
waiver store lives in the guard audit directory). A fresh environment therefore
serves an empty Evaluations page until the candidate run + waivers exist. Run the
idempotent bootstrap **against the deployed agent's environment** (same
`TESSERA_LLM_PROFILE` / audit dir the API reads) as a post-deploy step:
`make eval-demo` (≡ `PYTHONPATH=src uv run python scripts/bootstrap_eval_demo.py`)
— it runs the agent's FR/DE/EN evaluation, then seeds the governed waivers bound
to that run. `make bootstrap` now includes this for local setup. Note: a Claude/OpenAI **consumer subscription is
not API access** — the `frontier` path needs billed API credentials; Anthropic
has no embeddings API (use Ollama locally or OpenAI `text-embedding-3-small`).

## Follow-ups (not yet implemented)

- **Cloudflare Turnstile** — invisible, no-account bot challenge on the chat
  form; verify the token in `app/api/chat/route.ts` before proxying. Strongest
  no-friction abuse defence; needs a Cloudflare site key + secret.
- **Edge nginx locally** — `infra/edge/` already ships `limit_req`/`limit_conn`;
  uncomment the `set_real_ip_from` / `real_ip_header CF-Connecting-IP` block and
  set Cloudflare's CIDRs to recover the true client IP for per-IP limits.
- **CI** — extend `deploy.yml` to build & push the front-end image and pass it
  to Terraform as `frontend_image`.
