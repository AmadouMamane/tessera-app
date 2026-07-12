# Production posture — what changes when this leaves the demo

A single page for the facts that are safe (or deliberately loose) for the login-less public
demo but **must change for a real deployment**. Each item cites the source of truth. This is
the audit P1.5 consolidation — before this, these facts were scattered across four ADRs, the
Terraform, and the settings.

> Scope note: the shipped defaults target the **public demo** (ADR 0008 "login-less public
> demo"). None of the below is a bug in that context; each is a knob the demo leaves at its
> demo value and a real tenant must turn.

## 1. Network exposure

- **Cloud Run is public in the demo.** `infra/terraform/cloud_run_frontend.tf` binds
  `roles/run.invoker` to `var.allowed_invokers` (the demo sets this to public) and
  `ingress = "INGRESS_TRAFFIC_ALL"`. For a private deployment, flip ingress to
  `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` and scope the invokers
  (`infra/terraform/cloud_run.tf:5`, `armor.tf`). Cloud Armor is available behind the flag.
- **TLS / HSTS.** `api.tls_terminated=True` (Cloud Run terminates TLS) drives HSTS
  (`settings.py hsts_enabled`). On-prem behind a proxy that does **not** terminate TLS, set
  `TESSERA_API__TLS_TERMINATED=false` so HSTS is not asserted over plain HTTP (ADR 0020).

## 2. Secrets (never the demo defaults)

- **Secret backend** (`SecretsSettings`, ADR 0008): `TESSERA_SECRETS__PROVIDER` = `env`
  (Cloud Run + GCP Secret Manager, default), `gcp`, `sops` (on-prem standard), or `vault` /
  OpenBao (on-prem premium). Configure the matching block (`gcp_project_id`, `sops_file`,
  `vault_url` + token/mount/path).
- **Signing keys** — required in production, fail-closed:
  - `TESSERA_API__SESSION_SIGNING_KEY` — the customer-session HMAC (ADR 0008/0009). Ephemeral
    fallback in dev only.
  - `TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY` — the operator assertion HMAC (ADR 0010
    Phase B). The Next BFF (mint) and the agent (verify) live in **different processes** and
    MUST share this exact value; **no ephemeral fallback** (a per-process key could never
    match across the trust boundary). Unset ⇒ the operator path is inert.
  - `TESSERA_API__BEARER_TOKEN` — the front→backend shared secret, if used.
- **ClickHouse credentials.** The self-hosted spine adapter defaults to
  `clickhouse` / `clickhouse` (`observability/spine/adapters/clickhouse.py:106-107`, envs
  `TESSERA_CLICKHOUSE_USER` / `TESSERA_CLICKHOUSE_PASSWORD`). **Override in any shared
  environment** — the dev default is a demo convenience, not a credential.

## 3. Opposability seal (TSA)

- `TESSERA_GUARD__SEAL_PROVIDER` = `none` by default — the **honesty invariant** (ADR 0015
  §Amendment 3 / §Corr.3c): with no provider the ledger badge can NEVER read "Scellé" (the
  NoOp provider structurally cannot mint a token). A verified but non-eIDAS TSA renders
  "Scellé (non qualifié)"; only a **qualified** RFC-3161 TSA earns "Scellé · opposable".
  Configure a qualified TSA for a deployment that claims legal opposability.

## 4. The audit ledger (ADR 0015)

- **Source**: `TESSERA_LEDGER_SOURCE=postgres` (the promoted append-only table, default since
  the H2 cut). `file` is the operator escape hatch.
- **Backup**: `make ledger-backup` (nightly) + `make ledger-restore-drill` (weekly) — see
  `docs/runbook.md §Audit log`. In production the durable copies are Cloud SQL managed backups
  + the audit GCS bucket; the make targets are the on-prem / logical-chain path.

## 5. Rate limiting (ADR 0020 + ADR 0019)

- On-prem there is no upstream load balancer, so `rate_limit_required` is forced on
  (`settings.py`). For multi-instance Cloud Run, set `TESSERA_API__RATE_LIMIT_STORAGE_URI` to
  a shared `redis://` so `/chat` global + per-session and the invoke-seam rate window are
  enforced **across instances** (in-memory is per-instance). The invoke concurrency cap
  (`TESSERA_API__INVOKE_MAX_CONCURRENT`) is per-instance by design.

## 6. Retention

- Cloud Logging: `var.log_retention_days` (`infra/terraform/observability.tf`).
- Audit GCS bucket: 365-day delete lifecycle + `force_destroy=false` (cannot be wiped
  accidentally) — `observability.tf:38-44`.
- Ledger backups (`backups/`, gitignored): prune to policy (e.g. 14 daily + 8 weekly).

## 7. CI / supply chain — current state (measured 2026-07-11)

- **GitHub Actions is billing-blocked.** Every workflow run since ~2026-07-10 evening fails
  in seconds: *"The job was not started because recent account payments have failed or your
  spending limit needs to be increased."* **Action: fix GitHub billing** (Billing & plans),
  then re-run the gate on `main`. Until then, CI provides no second pass — merges rest on the
  local `make gate`.
- **Branch protection is absent** (403 — needs GitHub Pro / a public repo). The agent branches
  fast-forward into `main` without a PR gate; the gate is enforced by discipline, not by the
  platform. Enabling branch protection (require the `CI` check) is the durable fix.
- **`security.yml` / `supply-chain.yml` are red** for structural reasons, not code:
  - SLSA provenance **halts on a private repo** (by design — it would leak the repo name to a
    public transparency log). Set `private-repository: true` on the generator to override, or
    accept it as N/A for a private repo.
  - Trivy/CodeQL **SARIF upload** needs GitHub Advanced Security (unavailable on a private repo
    without the add-on).
  - `bandit`: 20 findings (14 Low / 6 Medium, 0 High) — triage separately; the SQL-f-string
    class was closed (audit P0.3) but bandit fails on any finding.
- **Known dependency CVEs** (pip-audit, not patched tonight — the mandate forbade version
  bumps): `starlette 0.52.1` (CVE-2026-48817, CVE-2026-48818 → fix 1.1.0), `vcrpy 8.1.1`
  (GHSA-rpj2-4hq8-938g → fix 8.2.1). Dependabot PRs are open. Bump under a green weekly
  freshness/CVE job (audit P1.6).

## 8. Per-environment isolation (ADR 0014)

Every durable store is partitioned by environment: Postgres schema `tessera_<env>`
(`settings.pg_schema`), the local-state root `/tmp/tessera/<env>/`, and per-env eval report
dirs. Two environments never share an audit chain. Full config inventory:
`docs/configuration.md` (generated).
