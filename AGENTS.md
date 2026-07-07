# Tessera — Codex context

This file is read automatically by Codex at the start of every session in this repository. Its purpose is to give the assistant a stable, versioned understanding of what Tessera is, what it is not, and how work must be done here. Keep it concise. When a decision becomes load-bearing enough to deserve its own page, capture it as an ADR under `docs/decisions/` and link it from this file instead of expanding the prose here.

## Pitch

Tessera is a production-grade reference implementation of a multilingual (FR / DE / EN) banking support LLM agent for the European retail market. The agent is grounded in EU regulatory corpora (DORA, CNIL, BaFin, GDPR), enforces runtime guardrails through the `mcp-firewall` dependency, ships with a non-regression harness over forty publicly documented agent failures, and is deployed on Google Cloud Run with an alternate on-premises mode running Llama 3.3 70B locally on Apple Silicon. The name comes from the Roman *tessera*, an identification token granting access — the semantic theme is identity and permission check at every call.

## Honest positioning (non-negotiable, first page of README)

Tessera is neither a new firewall, nor a new test framework, nor a new safety methodology. The firewall layer is `mcp-firewall` consumed as a dependency. The harness draws its patterns from AgentAssay and Promptfoo. The audit approach is inspired by AEGIS. What Tessera contributes is a complete, opinionated, deployed assembly of the four quality layers — runtime guard, offline regression harness, structured audit trail, human-in-the-loop escalation — wired end to end for one specific use case: European retail banking customer support in three languages with explicit regulatory grounding. The value is in the assembly and the EU business semantics, not technical invention. Any framing of the project that drifts toward "new framework" must be rejected.

Competitors and inspirations cited explicitly on the front page: `mcp-firewall` (ressl), AEGIS, DFAH, AgentAssay, Promptfoo, STING, Bernstein, ALTK. External academic citations must be verified against the actual papers before being committed to `docs/differentiation.md`.

## Stack (frozen)

Python 3.12. Dependency management via `uv` exclusively — no `requirements.txt`, no `pip`, no `poetry`. Code quality via `ruff` (lint + format) and `mypy` in strict mode. Testing via `pytest` with `pytest-asyncio` for the agent paths. Pre-commit hooks enforce all of the above at commit time.

Agent orchestration via LangGraph. Retrieval via PostgreSQL with `pgvector`, run locally on M1 Ultra for development and on Cloud SQL for the deployed demo. Embeddings from Vertex AI for the frontier path and from a local Ollama setup for the on-premises path. The frontier LLM is reached through Vertex AI; the local LLM is Llama 3.3 70B served by Ollama. Runtime guardrails through `mcp-firewall`, consumed as a pinned dependency. At least one upstream contribution to `mcp-firewall` must land within the project window — this is what defends the "reuse, don't reinvent" positioning, and is non-negotiable.

The HTTP layer is FastAPI. The dashboard is a Next.js application under `webapp/frontend/`. The infrastructure is described in Terraform under `infra/terraform/` and deployed to Google Cloud Run with Cloud SQL, Secret Manager, and Cloud Logging / Cloud Monitoring. CI is GitHub Actions, with four separate workflows: `ci.yml`, `eval.yml`, `deploy.yml`, `security.yml`.

## Non-negotiable disciplines

Ship-or-die at day twenty. If schedule slips, cut scope, never extend time. The repository's daily commit cadence is enforced — one commit minimum per day, using Conventional Commits formatting (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `perf:`).

The README must document tests that pass and tests that fail with their root causes. No marketing fluff, no hidden failures. Every external citation must point to a verified, reachable source. No notebooks, ever.

OSS dependencies and inspirations must be cited explicitly on the README front page, with links. At least one upstream PR on `mcp-firewall` must land before day twenty.

## Conventions

Commit messages follow Conventional Commits. Branches follow `kebab/short-purpose` style with the author prefix optional. Pull requests use the template in `.github/PULL_REQUEST_TEMPLATE.md` and are reviewed against the checklist there before merge.

Python code is type-hinted under `mypy --strict`. All public functions have docstrings in the Google style. Module-level docstrings are required on every package entry point. Tests are split between `tests/unit/` for isolated, fast tests and `tests/integration/` for tests that hit Postgres, the LLM, or external services; integration tests are tagged with `pytest.mark.integration` so they can be skipped in fast CI loops.

Prompts live in YAML under `src/tessera/agent/prompts/{fr,de,en}.yaml` — never hardcoded in Python. Policies live in YAML under `src/tessera/guard/`. Failures cataloged for the regression harness live as individual JSON files under `eval/failures/NN_short_name.json`, validated against `eval/failures/_schema.json`.

Secrets never enter the repository. The deployment expects them in GCP Secret Manager, resolved at container start time. Local development uses a gitignored `.env.local` derived from `.env.example`.

## Repository structure (canonical)

This is the canonical tree. Codex must scaffold to this layout and refuse to introduce alternative structures without an ADR documenting the deviation.

```
tessera/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── LICENSE                                        # Apache-2.0
├── AGENTS.md                                      # this file
├── pyproject.toml
├── uv.lock
├── .pre-commit-config.yaml
├── .python-version
├── .gitignore
├── Makefile
├── docker-compose.yml
│
├── docs/
│   ├── design.md
│   ├── compliance.md
│   ├── multilingual.md
│   ├── safety.md
│   ├── eval.md
│   ├── on_prem.md
│   ├── differentiation.md
│   ├── threat-model.md
│   ├── runbook.md
│   ├── decisions/                                 # ADRs
│   │   ├── 0001-record-architecture-decisions.md
│   │   ├── 0002-license-apache-2.md
│   │   ├── 0003-ci-github-actions.md
│   │   ├── 0004-package-layout-src.md
│   │   └── 0005-tools-vs-workers-separation.md
│   └── images/
│       ├── architecture.svg
│       ├── agent_graph.svg
│       └── eval_flow.svg
│
├── src/
│   └── tessera/
│       ├── __init__.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── graph.py
│       │   ├── state.py
│       │   ├── router.py
│       │   ├── planner.py
│       │   ├── reviewer.py
│       │   ├── reporter.py
│       │   ├── workers/                           # LangGraph nodes (orchestration)
│       │   │   ├── __init__.py
│       │   │   ├── product_lookup.py
│       │   │   ├── regulation_lookup.py
│       │   │   ├── account_lookup.py
│       │   │   ├── simulator.py
│       │   │   └── escalation.py
│       │   ├── tools/                             # LLM-callable function-call targets
│       │   │   ├── __init__.py
│       │   │   ├── account_balance.py
│       │   │   ├── card_block.py
│       │   │   ├── transaction_search.py
│       │   │   ├── loan_simulate.py
│       │   │   └── ticket_escalate.py
│       │   └── prompts/
│       │       ├── fr.yaml
│       │       ├── de.yaml
│       │       └── en.yaml
│       ├── memory/                                # agent memory (ADR 0007)
│       │   ├── __init__.py                         # get_memory_backend() factory + scope_for()
│       │   ├── protocol.py                        # MemoryBackend Protocol + scope/context types
│       │   ├── transcript.py                       # Mechanism A — durable conversation transcript
│       │   ├── window.py                          # Tier 0 — sliding window (default)
│       │   ├── summary.py                         # Tier 1 — summary buffer + entity ledger
│       │   ├── persistent.py                      # Tier 2 — cross-session, dedicated pgvector table
│       │   ├── entities.py                        # literal entity extraction (amounts, IBAN, dates, refs)
│       │   ├── governance.py                      # PII screening, TTL, erasure, consent, audit hooks
│       │   ├── reflector.py                       # post-turn background memory formation (cold path)
│       │   └── adapters/                          # external engines behind the same Protocol (optional)
│       │       ├── __init__.py
│       │       ├── langmem.py                     # extra: memory-langmem
│       │       ├── mem0.py                        # extra: memory-mem0
│       │       └── zep.py                         # extra: memory-zep
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── embeddings.py
│       │   ├── store.py
│       │   ├── chunking.py
│       │   ├── reranking.py
│       │   └── hybrid_search.py
│       ├── corpus/
│       │   ├── __init__.py
│       │   ├── generator.py
│       │   ├── translator.py
│       │   ├── ingestion.py
│       │   └── data/
│       │       ├── credit_aurore_fr.json
│       │       ├── credit_aurore_de.json
│       │       ├── credit_aurore_en.json
│       │       ├── regulations_dora.json
│       │       ├── regulations_cnil.json
│       │       ├── regulations_bafin.json
│       │       └── regulations_gdpr.json
│       ├── guard/
│       │   ├── __init__.py
│       │   ├── policy.yaml
│       │   ├── adapter.py
│       │   ├── audit.py
│       │   └── decisions.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── frontier.py
│       │   ├── local.py
│       │   ├── router.py
│       │   └── budget.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py
│       │   │   └── audit.py
│       │   └── middleware.py
│       └── observability/
│           ├── __init__.py
│           ├── traces.py
│           ├── metrics.py
│           └── logging.py
│
├── eval/
│   ├── __init__.py
│   ├── failures/
│   │   ├── _schema.json
│   │   ├── 01_prompt_injection.json
│   │   ├── 02_pii_leak.json
│   │   ├── 03_hallucination_fact.json
│   │   ├── 04_overconfident_action.json
│   │   └── 05_citation_hallucination.json
│   ├── runner.py
│   ├── scorecard.py
│   ├── translator.py
│   └── reports/
│       └── .gitkeep
│
├── webapp/
│   ├── frontend/
│   │   ├── package.json
│   │   └── app/
│   │       ├── page.tsx
│   │       ├── audit/page.tsx
│   │       └── eval/page.tsx
│   └── api/
│       └── main.py                                # thin entrypoint, imports from src/tessera/api/
│
├── infra/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── cloud_run.tf
│   │   ├── postgres.tf
│   │   ├── secrets.tf
│   │   ├── observability.tf
│   │   └── variables.tf
│   └── docker/
│       ├── Dockerfile.agent
│       └── Dockerfile.frontend
│
├── scripts/
│   ├── generate_corpus.py
│   ├── ingest_regulations.py
│   ├── run_eval.py
│   ├── run_local.py
│   └── seed_demo.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_agent_graph.py
│   │   ├── test_retrieval.py
│   │   ├── test_guard.py
│   │   ├── test_corpus_generator.py
│   │   └── test_llm_router.py
│   └── integration/
│       ├── test_agent_e2e.py
│       └── test_firewall_adapter.py
│
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   ├── eval.yml
    │   ├── deploy.yml
    │   └── security.yml
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    ├── PULL_REQUEST_TEMPLATE.md
    ├── CODEOWNERS
    └── dependabot.yml
```

## Repository topology (multi-agent worktrees)

As of 2026-07-07 this repo lives under a shared umbrella:

```
/Users/amadou/local/apps/
├── tessera-app/
│   ├── tessera/                  ← this repo (origin: AmadouMamane/tessera-app.git, private), branch `main`
│   ├── agents/
│   │   ├── claude/               ← worktree, branches `claude/<sujet>`
│   │   ├── codex/                ← worktree, branches `codex/<sujet>`
│   │   └── antigravity/          ← worktree, branches `antigravity/<sujet>`
│   ├── Tessera_private/          ← private steering docs, never tracked by git
│   └── legacy-tessera-2026-07/   ← archived old repo (origin: AmadouMamane/tessera.git)
```

**Branch model: trunk-based.** `main` is the only long-lived branch, protected by the twice-green
gate (`ruff check` + `ruff format --check` + `mypy` + `tsc --noEmit` + `biome check` +
`pytest -m "not integration"`, run twice in a row). Each agent works in its own dedicated
worktree under `agents/<name>/` on short-lived branches named `<agent>/<sujet>`, cut from a
fresh `main`, and lands (merges into `main`) as soon as the gate is green — no `develop`, no
long-running feature branches. At every slice boundary, resync the worktree's branch from
`main` before starting the next unit of work (once the previous branch has landed, cut the next
one with `git checkout -b <agent>/<next-sujet> main`).

Progress across slices/steps is tracked in `docs/decisions/0017-execution-status.md` — read it
first when resuming work, it is the single source of truth for what's done, in flight, and next.

## Serveurs dev

Local dev servers are managed by Makefile targets — never launch `next dev` or
`run_local.py` by hand; the targets encode the ports, the `/healthz` +
`/api/healthz` health gates, macOS-safe detachment, and a pre-flight port guard:

- `make dev-up` — backend **:8099** (FastAPI) + frontend **:3097** (Next.js) from
  the **current checkout**, detached; waits for health. Logs:
  `/tmp/tessera-{backend,front}.log`.
- `make dev-down` — stop both, by port.
- `make dev-status` — ports, PIDs, the git head of the served checkout, health.
- `make dev-preview PORT=3098` — a **temporary** validation server from an agent
  worktree on another port (backend derived, e.g. `:8098`), killed after validation.

Convention: the **reference** servers run from the **main checkout** (`tessera/`)
so the operator's browser reflects `main`; reviewing **unmerged** work at a
supervised checkpoint uses `dev-preview` from that agent's worktree — never a
long-lived server on an agent worktree. Every worktree mutation (checkout / park /
`git worktree remove`) is preceded by a live-process check (`lsof`); `dev-up`
refuses to start if the port is already in use. Full rationale:
`docs/decisions/0017-execution-status.md` (Preconditions).

## Decision records

Read these before making any architecture-shaping change. They are short and binding.

- `docs/decisions/0001-record-architecture-decisions.md` — why and how we record decisions
- `docs/decisions/0002-license-apache-2.md` — Apache-2.0 license choice
- `docs/decisions/0003-ci-github-actions.md` — GitHub Actions over GitLab CI and Cloud Build
- `docs/decisions/0004-package-layout-src.md` — `src/` layout over flat layout
- `docs/decisions/0005-tools-vs-workers-separation.md` — LangGraph nodes versus LLM-callable tools
- `docs/decisions/0006-locale-prefixed-routing.md` — dashboard pages live under `app/[locale]/`, supersedes the single-locale `app/page.tsx` shape in the canonical tree above
- `docs/decisions/0007-agent-memory-architecture.md` — agent memory: durable conversation transcript (Mechanism A) + pluggable `MemoryBackend` (window/summary/persistent tiers on pgvector, with langmem/mem0/zep adapters); adds the `src/tessera/memory/` package to the canonical tree
- `docs/decisions/0016-business-events-fanout-contract.md` — business events fan out to ADR 0015 sinks; no application JSONL store

## Communication rules (permanent, no exception)

Before every significant tool call (Bash, Edit, Write, Agent), output exactly one sentence prefixed with 🟢 in ALL CAPS.
Format: `🟢 UNE PHRASE EN MAJUSCULES.`
Never ask for confirmation unless the action is destructive/irreversible.

## Memory hygiene (permanent)

After fixing a non-obvious bug, discovering an architectural lesson, or solving a tricky UI/CSS problem, update the two memory files (their machine-specific paths live in `AGENTS.local.md`, gitignored): add a numbered Insight to `insights_tessera.md` (Symptom / Root cause / Fix / Architectural lesson), and update the relevant section + the "Statut à jour" block in `synthesis_tessera.md`.

Do this during the session, not at the end. If in doubt whether something is worth saving, save it.

## How Codex should behave in this repository

Default to reading the relevant ADR before changing structural choices. When a request would deviate from the canonical tree above, ask before doing it and propose an ADR draft. When introducing a new dependency, justify it in the relevant ADR or open a new one — Tessera's positioning depends on minimal, well-cited reuse, not feature creep. When in doubt about scope, prefer cutting over extending: the day-twenty deadline takes precedence over completeness.
