<div align="center">

# Tessera

**A multilingual (FR / DE / EN) banking support LLM agent for the European retail market.**

Grounded in EU regulatory corpora (DORA, CNIL, BaFin, GDPR).
Guarded at runtime by [`mcp-firewall`](https://github.com/ressl/mcp-firewall).
Validated by a non-regression harness over 63 publicly documented agent failures.
Deployed on Google Cloud Run with an alternate on-premises mode running Llama 3.3 70B locally on Apple Silicon.

[![CI](https://github.com/AmadouMamane/tessera/actions/workflows/ci.yml/badge.svg)](https://github.com/AmadouMamane/tessera/actions/workflows/ci.yml)
[![Eval](https://github.com/AmadouMamane/tessera/actions/workflows/eval.yml/badge.svg)](https://github.com/AmadouMamane/tessera/actions/workflows/eval.yml)
[![Security](https://github.com/AmadouMamane/tessera/actions/workflows/security.yml/badge.svg)](https://github.com/AmadouMamane/tessera/actions/workflows/security.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-2A6DB2.svg)](https://mypy.readthedocs.io/)
[![ruff](https://img.shields.io/badge/ruff-checked-261230.svg)](https://docs.astral.sh/ruff/)

</div>

---

## Positioning

Tessera is a **complete, opinionated, deployed assembly** of four quality layers — runtime guard, offline regression harness, structured audit trail, and human-in-the-loop escalation — wired end to end for one specific, demanding use case: **European retail banking customer support in three languages (FR / DE / EN) with explicit regulatory grounding** (DORA, CNIL, BaFin, GDPR).

It builds deliberately on proven components rather than reinventing them:

- Runtime guarding via [`mcp-firewall`](https://github.com/ressl/mcp-firewall), consumed as a pinned dependency.
- A non-regression harness whose patterns draw on [AgentAssay](https://github.com/agentassay) and [Promptfoo](https://github.com/promptfoo/promptfoo).
- An audit-trail design informed by the AEGIS research line.

The engineering work is the end-to-end integration and the EU banking domain semantics: multilingual regulatory retrieval, deterministic policy short-circuits on the critical failure cases, a per-model evaluation scorecard, and a production deployment with an on-premises fallback.

### Built on / inspired by

| Project / Paper        | Role                                          |
| ---------------------- | --------------------------------------------- |
| `mcp-firewall` (ressl) | Runtime guardrail layer — pinned dependency   |
| AEGIS                  | Audit-trail design pattern                    |
| DFAH                   | Failure taxonomy for agent harnesses          |
| AgentAssay             | Regression-test scaffolding patterns          |
| Promptfoo              | YAML-driven prompt evaluation / interop       |
| STING                  | Tool-use stress testing                       |
| Bernstein              | Multilingual evaluation framing               |
| ALTK                   | Agent-level toolkit comparisons               |

Academic citations in [`docs/differentiation.md`](./docs/differentiation.md) are verified against the source papers.

---

## What's working, what isn't

This section reports the real test status, not a marketing surface. Failures are documented, not hidden.

### Green in CI — the gate

One job decides whether a commit is green, and it is the same command you run on your machine:

```bash
make gate      # run it twice; a check that passes once and fails once is a red check
```

`make gate` is the definition, `.github/workflows/ci.yml` job `gate` is a caller — there is no second, drifting copy of the command list. It is hermetic: no secrets, no services, no browser.

- **Python — 1,573 tests pass** (`pytest -m "not integration"`). Agent graph, router/policy deterministic short-circuits (including the policy/scope refusal guard, the third-party-PII guard, the auth redirect and the DORA corrections with their false-positive contracts), retrieval, guard, corpus generation, the LLM router, the memory tiers (window / summary / persistent / entity ledger / governance), and reasoning-trace stripping. Plus `ruff check`, `ruff format --check`, `mypy --strict`.
- **Frontend — 132 tests pass** (`vitest run`), plus `tsc --noEmit` and `biome check`, with `pnpm` pinned by `packageManager` (9.15.0).
- **Security workflow.** `bandit`, `pip-audit`, Trivy. The supply-chain workflow builds, signs (cosign), and attaches SLSA provenance + an SBOM to the agent image.

Until 2026-07-10 this section claimed the frontend `biome` and `tsc` ran in CI. They did not — no workflow invoked `pnpm`, `biome`, `tsc`, `vitest` or Playwright, so the entire frontend could rot without a witness. The `gate` job is what makes the claim true.

### Not gating CI (needs live services)

- **End-to-end suite** (`webapp/frontend/e2e/`, Playwright). The `e2e` job runs it against a **production build** (`next build` + `next start`), one worker, with PostgreSQL from a service container. Against a seeded local stack the suite is **182 passed / 0 failed / 0 skipped**, twice in a row. On the bare runner it is **160 / 19 / 2**, and those 19 are an empty database, not spec debt: the catalogue expects 17 sources and finds the 2 memory tables, because the fifteen corpus categories live in a pgvector index the runner has never been fed. So the job stays **non-blocking**. It flips when CI gets a seeded dataset — which needs embeddings, hence a model, hence a secret the gate must never hold. Narrowing the job to the data-independent subset would be a weaker gate wearing the name of the gate, and that is not something we do.
- **Integration suite** (`tests/integration/`, `pytest.mark.integration`) exercises the full graph and the persistent memory backend. A subset needs a seeded PostgreSQL and a live LLM (Ollama / Vertex AI) that the hosted runner does not provide, so the job runs for visibility but is **non-blocking**. Locally, with services up: `uv run pytest tests/integration/ -m integration` (currently 16 pass / 3 require seeded Postgres + a running model).

### Regression harness — fleet release gates (llama3.2:3b, 2026-07-04)

Each agent is replayed against **its own bound evaluation set** (curated domain subset + the shared security floor), in all three languages. Domain rates are only meaningful against the agent's own set — the single inter-agent comparison is the **shared security floor (socle)**. There is deliberately no fleet-wide percentage: averaging different sets would manufacture a number with no referent.

| Agent          | Security floor (socle) | Domain — own set | Release gate                          |
| -------------- | ---------------------- | ---------------- | ------------------------------------- |
| support-client | 18/18                  | 93/101 (92.1%)   | **PASS** — 0 blocking criticals, 0 waivers |
| recouvrement   | 18/18                  | 57/62 (91.9%)    | **PASS** — 0 blocking criticals, 0 waivers |
| onboarding     | 18/18                  | 41/51 (80.4%)    | **PASS** — 0 blocking criticals, 0 waivers |

Every critical case (T0 socle and T1: third-party PII, tool authorisation, vulnerable-customer escalation, DORA misstatements) is closed **deterministically** — router short-circuits and refusals carrying audited guard decisions, planner escalation intents, and sourced corrections whose facts were verified against the actual EU texts (Regulation (EU) 2022/2554 art. 2(1)/19(4)/64, Delegated Regulation (EU) 2025/301). Zero governed waivers are in effect. The deterministic layer was calibrated on real replay: 1,559 real transcript user turns produce zero false positives, and the closed cases are byte-identical across consecutive runs.

**What still fails (documented, not hidden).** On the latest full replay, 5 case×language runs are red — 26-de, 39-fr, 49-de, 53-de (support-client) and 56-de (recouvrement). All are T2 (domain-graded, non-blocking) and all sit in known llama3.2:3b sampling-noise families: self-declared "I could not find…" answers that miss a scored token, and language-mixing drift. None carries the signature of a deterministic guard — they flip from run to run and are model noise, not guard regressions.

Run an agent's gate: `uv run python scripts/run_eval.py --agent support-client --model llama3.2:3b` (the exit code is the gate verdict).

An earlier multi-model FR comparison (June 2026, **before** the deterministic guard layers landed — kept for the model-choice picture, not as current status):

| Model                  | FR score   |
| ---------------------- | ---------- |
| Llama 3.3 70B          | 95% (36/38) |
| Gemma 3 27B            | 87%        |
| Llama 3.2 3B (default) | 74%        |
| Mistral 7B             | 68%        |
| DeepSeek-R1 7B         | 58%        |

---

## Architecture at a glance

```
┌────────────────────────────────────────────────────────────────────┐
│                       FastAPI (Cloud Run)                          │
│  /chat (SSE)                                /audit (read-only)     │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                ┌────────────────▼────────────────┐
                │     LangGraph orchestration     │
                │                                 │
                │  router → planner → workers ──▶ reviewer → reporter
                │             │                                 │
                │             ▼                                 ▼
                │      [product_lookup,                  audit trail
                │       regulation_lookup,               (structured)
                │       account_lookup,
                │       simulator,
                │       escalation]
                │             │
                │             ▼
                │   LLM-callable tools  ◀── guarded by mcp-firewall
                │   (account_balance, card_block,
                │    transaction_search, loan_simulate,
                │    ticket_escalate)
                └────────────────┬────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   Vertex AI                 Cloud SQL                Ollama (on-prem)
   (frontier path)         + pgvector             Llama 3.3 70B on M1
```

A larger SVG version lives in [`docs/images/architecture.svg`](./docs/images/architecture.svg).

---

## Quickstart

### Prerequisites

- Python 3.12 (managed by [`uv`](https://docs.astral.sh/uv/))
- PostgreSQL 16 with `pgvector` extension — `docker compose up postgres` suffices for local dev
- A Google Cloud project with Vertex AI enabled, **or** an Ollama install with `llama3.3:70b` pulled
- Pre-commit (`pipx install pre-commit`)

### Install

```bash
git clone https://github.com/AmadouMamane/tessera.git
cd tessera
uv sync                       # installs runtime + dev dependencies
uv run pre-commit install     # enables ruff + mypy + hooks at commit time
cp .env.example .env.local    # then edit secrets
```

### Run the agent locally

```bash
# Boot Postgres + pgvector
docker compose up -d postgres

# Ingest the regulatory corpus + the seed product corpus (Crédit Aurore)
uv run python scripts/ingest_regulations.py
uv run python scripts/seed_demo.py

# Start the FastAPI agent
uv run python scripts/run_local.py
# → POST http://localhost:8080/chat   (SSE streaming)
# → GET  http://localhost:8080/audit  (read-only audit trail)
```

### Run the dashboard

```bash
cd webapp/frontend && pnpm install && pnpm dev
# → http://localhost:3000
```

### Run the regression harness

```bash
uv run python -m eval.runner                 # full suite
uv run python -m eval.runner --lang de       # one language
uv run python -m eval.runner --case 02_pii_leak  # one case
```

### Switch to the on-premises path

```bash
ollama pull llama3.2:3b      # default — small and fast
ollama pull llama3.3:70b     # flagship (optional; ~40 GB)
TESSERA_LLM_PROFILE=on_prem uv run python scripts/run_local.py
```

On-prem serves several selectable Ollama models — **Llama 3.2 3B (default)**, Mistral 7B, DeepSeek-R1 7B, Gemma 3 27B, and Llama 3.3 70B — chosen per request (Settings picker in the dashboard, or the `model` field on `/chat`). The router falls back to local automatically when Vertex AI credentials are absent — see [`docs/on_prem.md`](./docs/on_prem.md) for the trade-off table.

---

## Stack (frozen)

| Concern                | Choice                                          | ADR / docs                              |
| ---------------------- | ----------------------------------------------- | --------------------------------------- |
| Language               | Python 3.12                                     | —                                       |
| Dependency manager     | `uv` (exclusively — no pip/poetry/requirements) | [ADR 0004](./docs/decisions/0004-package-layout-src.md) |
| Lint + format          | `ruff`                                          | —                                       |
| Type-check             | `mypy --strict`                                 | —                                       |
| Test                   | `pytest` + `pytest-asyncio`                     | —                                       |
| Agent orchestration    | LangGraph                                       | [ADR 0005](./docs/decisions/0005-tools-vs-workers-separation.md) |
| Retrieval              | PostgreSQL + `pgvector`                         | [docs/design.md](./docs/design.md)      |
| Frontier LLM           | Vertex AI                                       | [docs/design.md](./docs/design.md)      |
| Local LLM              | Selectable Ollama models (Llama 3.2 3B default → Llama 3.3 70B), Apple Silicon | [docs/on_prem.md](./docs/on_prem.md) |
| Runtime guardrails     | `mcp-firewall` (pinned dependency)              | [docs/safety.md](./docs/safety.md)      |
| HTTP                   | FastAPI                                         | —                                       |
| Dashboard              | Next.js (under `webapp/frontend/`)              | —                                       |
| Infrastructure         | Terraform → Cloud Run + Cloud SQL + Secret Manager | [docs/runbook.md](./docs/runbook.md) |
| CI                     | GitHub Actions (5 workflows: ci, eval, deploy, security, supply-chain) | [ADR 0003](./docs/decisions/0003-ci-github-actions.md) |

The stack is **frozen**. Changes require an ADR under [`docs/decisions/`](./docs/decisions/).

---

## Multilingual (FR / DE / EN)

Prompts live in YAML under [`src/tessera/agent/prompts/`](./src/tessera/agent/prompts/) — never hardcoded in Python. The language router lives in `src/tessera/agent/router.py` and dispatches on detected user-input language; the reviewer and reporter nodes pick the matching prompt set.

Regulatory grounding by jurisdiction:

| Language | Primary regulators / corpora             | Corpus file                            |
| -------- | ---------------------------------------- | -------------------------------------- |
| FR       | CNIL, ACPR, AMF, GDPR                    | `src/tessera/corpus/data/regulations_cnil.json`, `regulations_gdpr.json` |
| DE       | BaFin, GDPR (DSGVO)                      | `src/tessera/corpus/data/regulations_bafin.json`, `regulations_gdpr.json` |
| EN       | DORA, GDPR (English consolidation)       | `src/tessera/corpus/data/regulations_dora.json`, `regulations_gdpr.json` |

See [`docs/multilingual.md`](./docs/multilingual.md) for the full evaluation methodology per language.

---

## Repository layout

The canonical tree lives in [`docs/structure.md`](./docs/structure.md). Notable conventions:

- `src/` layout (ADR 0004) — `import tessera` works only after `uv sync`.
- LangGraph **nodes** (orchestration) live under `src/tessera/agent/workers/`.
- **Tools** (LLM-callable function-call targets) live under `src/tessera/agent/tools/`.
  This separation is binding — see [ADR 0005](./docs/decisions/0005-tools-vs-workers-separation.md).
- Failure cases for the regression harness live as **one JSON file per failure** under `eval/failures/`, validated against `eval/failures/_schema.json`.

---

## Discipline

Engineering standards enforced across this repository:

- **No notebooks.** If you need a scratchpad, use a script under `scripts/`.
- **No hidden failures.** Failing tests stay visible in this README until they are fixed or formally accepted with an issue link.
- **No fabricated citations.** Every external reference must point to a verified source.
- **Secrets never enter the repo.** GCP Secret Manager in prod, gitignored `.env.local` in dev.

---

## Security

Vulnerability disclosure policy and threat model:

- [`SECURITY.md`](./SECURITY.md) — disclosure and contact.
- [`docs/threat-model.md`](./docs/threat-model.md) — assets, adversaries, mitigations.

On every push, `security.yml` runs CodeQL, `pip-audit`, `bandit`, `gitleaks`, a Trivy image scan, and a guard-policy lint; `supply-chain.yml` produces an SBOM and signs the image (cosign + SLSA provenance).

---

## License

Apache-2.0 — see [`LICENSE`](./LICENSE). Choice justified in [ADR 0002](./docs/decisions/0002-license-apache-2.md).

---

## Acknowledgements

Tessera stands on the shoulders of `mcp-firewall`, LangGraph, the AEGIS and DFAH research lines, and the open evaluation ecosystem around Promptfoo and AgentAssay. The EU regulatory corpora it grounds against are public-domain texts from CNIL, BaFin, EBA, and the European Commission. Crédit Aurore is a fictional retail bank invented for demonstration purposes and bears no relation to any real institution.
