# Tessera — Repository structure & conventions

The canonical layout of the repository and the conventions contributors follow.
ADRs under `docs/decisions/` may supersede parts of this document; where they do,
they say so explicitly and this file should be read together with them.

## Conventions

- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `perf:`).
- **Branches** follow `kebab/short-purpose`.
- **Python** is type-hinted under `mypy --strict`; public functions carry Google-style
  docstrings; package entry points have module-level docstrings.
- **Tests** split between `tests/unit/` (isolated, fast) and `tests/integration/`
  (Postgres, the LLM, external services), the latter tagged `pytest.mark.integration`
  so fast CI loops can skip them.
- **Prompts** live in YAML under `src/tessera/agent/prompts/{fr,de,en}.yaml` — never
  hardcoded in Python. **Policies** live in YAML under `src/tessera/guard/`.
- **Failure cases** for the regression harness live as one JSON file per failure under
  `eval/failures/NN_short_name.json`, validated against `eval/failures/_schema.json`.
- **Secrets** never enter the repository: GCP Secret Manager in production, a gitignored
  `.env.local` (derived from `.env.example`) in development.

## Canonical tree

```
tessera/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── LICENSE                                        # Apache-2.0
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
│   ├── structure.md                               # this file
│   ├── decisions/                                 # ADRs
│   └── images/
│
├── src/
│   └── tessera/
│       ├── agent/
│       │   ├── graph.py / state.py / router.py / planner.py / reviewer.py / reporter.py
│       │   ├── workers/                           # LangGraph nodes (orchestration)
│       │   ├── tools/                             # LLM-callable function-call targets
│       │   └── prompts/{fr,de,en}.yaml
│       ├── memory/                                # agent memory (ADR 0007)
│       ├── retrieval/                             # embeddings, store, chunking, reranking, hybrid_search
│       ├── corpus/                                # generator, translator, ingestion + data/
│       ├── guard/                                 # policy.yaml, adapter, audit, decisions
│       ├── llm/                                   # frontier, local, router, budget
│       ├── api/                                   # FastAPI app, routes/, middleware
│       └── observability/                         # traces, metrics, logging
│
├── eval/
│   ├── failures/                                  # one JSON per failure + _schema.json
│   ├── runner.py / scorecard.py / translator.py
│   └── reports/
│
├── webapp/
│   ├── frontend/                                  # Next.js dashboard (app/[locale]/, ADR 0006)
│   └── api/                                        # thin entrypoint into src/tessera/api/
│
├── infra/
│   ├── terraform/                                 # main, cloud_run, postgres, secrets, observability, variables
│   └── docker/                                    # Dockerfile.agent, Dockerfile.frontend
│
├── scripts/                                        # generate_corpus, ingest_regulations, run_eval, run_local, seed_demo
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── .github/
    ├── workflows/                                  # ci.yml, eval.yml, deploy.yml, security.yml
    ├── ISSUE_TEMPLATE/
    ├── PULL_REQUEST_TEMPLATE.md
    ├── CODEOWNERS
    └── dependabot.yml
```

## Decision records

Architecture-shaping decisions are recorded as ADRs under `docs/decisions/`:

- `0001-record-architecture-decisions.md` — why and how decisions are recorded
- `0002-license-apache-2.md` — Apache-2.0 license choice
- `0003-ci-github-actions.md` — GitHub Actions over GitLab CI and Cloud Build
- `0004-package-layout-src.md` — `src/` layout over flat layout
- `0005-tools-vs-workers-separation.md` — LangGraph nodes versus LLM-callable tools
- `0006-locale-prefixed-routing.md` — dashboard pages under `app/[locale]/`
- `0007-agent-memory-architecture.md` — agent memory architecture and the `memory/` package
- `0020-security-hardening.md` — security hardening for deployment
