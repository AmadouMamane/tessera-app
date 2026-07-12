# Security Policy

Tessera is a reference implementation, not a product with a security SLA — but it
handles banking-shaped data and models a real threat surface, so we treat
security reports seriously and document our posture honestly. The full threat
model lives in [`docs/threat-model.md`](docs/threat-model.md) and the operational
safety reference in [`docs/safety.md`](docs/safety.md). The hardening rationale is
[`docs/decisions/0020-security-hardening.md`](docs/decisions/0020-security-hardening.md).

## Supported versions

Security fixes target the `main` branch. There is no long-term support branch;
deployments should track `main` or pin a commit and re-base for fixes.

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security vulnerability.**

Report privately, by either:

- **GitHub Security Advisories** — *Security → Report a vulnerability* on the
  repository (preferred; gives us a private collaboration space), or
- **Email** — `mamanesarki@yahoo.fr` with subject `SECURITY: Tessera`.

Please include, as far as you can:

- a description of the issue and its impact,
- the affected component (e.g. guard policy, chat endpoint, corpus pipeline),
- reproduction steps or a proof of concept,
- any suggested remediation.

Encrypt sensitive details if you can; ask in your first email and we will share a
key.

### What to expect

| Stage | Target |
|---|---|
| Acknowledgement of your report | within **3 business days** |
| Initial assessment & severity | within **10 business days** |
| Fix or documented mitigation | severity-dependent; we keep you updated |
| Public disclosure | coordinated, after a fix or mitigation is available |

We follow **coordinated disclosure**. We will credit reporters who wish to be
named once a fix ships. We will not pursue legal action against good-faith
research that respects the scope below.

## Scope

**In scope:** the agent and API code under `src/`, the guard policy, the
regression harness, the corpus pipeline, the Terraform/infra definitions, and
the dashboard under `webapp/`.

**Out of scope:** third-party services and dependencies (report those upstream —
`mcp-firewall`, Vertex AI, Ollama, Postgres), findings that require a compromised
host or insider access already modelled in the threat model, and the documented
open risks below.

## Known, documented limitations

These are intentionally **not** claimed as solved (see the threat model and
`docs/safety.md`); reports that simply restate them are welcome but already
tracked:

- **Cross-lingual indirect injection** (eval case 09).
- **Base64 / encoded injection bypass** (eval case 11).
- **Re-identification by correlated quasi-identifiers** (eval case 16).
- **Ollama model-weight provenance** on the on-prem path — pin the digest and
  pull on a trusted host (see `docs/threat-model.md`).

## Security practices in this repository

- Runtime guard (`mcp-firewall`) on every tool call; PII redaction at the guard.
- Bearer-token auth (`secrets.compare_digest`); route-level authz on the read
  surfaces; deployment-aware security headers (ADR 0020).
- Rate limiting and a request-size ceiling on the API (ADR 0020).
- Deployment-aware secret resolution: GCP Secret Manager (cloud), SOPS+age
  (on-prem standard), or Vault/OpenBao (on-prem premium) — never secrets in git.
- CI security gate: CodeQL, `pip-audit`, Bandit, gitleaks + detect-secrets,
  Trivy (container), a CycloneDX **SBOM**, and **cosign** keyless signing with
  SLSA provenance for the agent image.
- A non-regression harness of 40 documented agent-failure cases gating merges.
