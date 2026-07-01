.PHONY: install lint typecheck format test test-integration test-all \
        coverage eval eval-demo seed ingest bootstrap run run-on-prem precommit check ci help \
        obs-up obs-down obs-logs dev-secrets

# ── Dependencies ────────────────────────────────────────────────────────────

install:
	uv sync

install-all:
	uv sync --all-extras

# ── Code quality ────────────────────────────────────────────────────────────

lint: install
	uv run ruff check .

lint-fix: install
	uv run ruff check . --fix

format: install
	uv run ruff format .

format-check: install
	uv run ruff format --check .

typecheck: install
	uv run mypy src/tessera

precommit: install
	uv run pre-commit run --all-files

# All quality checks in sequence (used locally before pushing)
check: format-check lint typecheck

# ── Tests ───────────────────────────────────────────────────────────────────

# Fast unit-test loop (no external dependencies)
test: install
	uv run pytest tests/unit/ -q

# Integration tests (requires Docker Postgres)
test-integration: install
	uv run pytest tests/integration/ -m integration -ra

# Full suite: unit + integration
test-all: install
	uv run pytest tests/ -ra

# Coverage report for the unit suite
coverage: install
	uv run pytest tests/unit/ \
		--cov=src/tessera \
		--cov-report=term-missing \
		--cov-report=html:build/coverage-html \
		--cov-fail-under=80

# ── Eval harness ────────────────────────────────────────────────────────────

# Run the full 40-case regression harness against the live agent
eval: install
	uv run python scripts/run_eval.py

# Run one case: make eval-case CASE=07_prompt_injection_roleplay
eval-case: install
	uv run python scripts/run_eval.py --case $(CASE)

# Run one language: make eval-lang LANG=de
eval-lang: install
	uv run python scripts/run_eval.py --lang $(LANG)

# Populate the Evaluations demo data (eval/reports + governed waivers) on a fresh
# environment: runs the agent's FR/DE/EN eval, then seeds its waivers. Idempotent.
# This is the post-deploy step for the demo (see docs/runbook.md).
eval-demo: install
	PYTHONPATH=src uv run python scripts/bootstrap_eval_demo.py

# ── Corpus management ───────────────────────────────────────────────────────

# Re-generate the Crédit Aurore product pages (overwrites data/ JSON files)
generate-corpus: install
	uv run python scripts/generate_corpus.py

# Ingest EU regulatory corpus into pgvector
ingest-regulations: install
	uv run python scripts/ingest_regulations.py

# Ingest Crédit Aurore product corpus into pgvector
seed: install
	uv run python scripts/seed_demo.py

# Full local setup: boot Postgres, ingest all corpora, populate eval demo data
bootstrap: install
	docker compose up -d postgres
	sleep 3
	$(MAKE) ingest-regulations
	$(MAKE) seed
	$(MAKE) eval-demo

# ── Dev secrets ─────────────────────────────────────────────────────────────
# Generate the shared operator-assertion HMAC secret and write it to BOTH dev
# .env.local files (gitignored). Idempotent — skips if already present. The agent
# loads it from dotenv via the nested delimiter (double underscore); Next reads
# process.env verbatim (single underscore). Same VALUE, different name per side.
# Without it the operator path is inert and the recouvrement console mis-attributes.
dev-secrets:
	@if grep -q '^TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY=' .env.local 2>/dev/null \
	   && grep -q '^TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY=' webapp/frontend/.env.local 2>/dev/null; then \
	  echo "operator key already set in both .env.local — nothing to do"; \
	else \
	  KEY=$$(openssl rand -hex 32); \
	  touch .env.local webapp/frontend/.env.local; \
	  grep -q '^TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY=' .env.local 2>/dev/null \
	    || printf '\nTESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY=%s\n' "$$KEY" >> .env.local; \
	  grep -q '^TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY=' webapp/frontend/.env.local 2>/dev/null \
	    || printf '\nTESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY=%s\n' "$$KEY" >> webapp/frontend/.env.local; \
	  echo "wrote operator key to .env.local + webapp/frontend/.env.local (restart agent + front)"; \
	fi

# ── Observability stack (OTel collector -> Phoenix + Langfuse + Grafana) ─────
# The agent only feeds traces when TESSERA_OBSERVABILITY__OTEL_ENDPOINT points at the
# collector (see .env.example). `obs-up` boots the full stack:
#   Phoenix    http://localhost:16006   (LLM traces — canonical)
#   Langfuse   http://localhost:3900    (cost / tokens / latency / sessions)
#   Prometheus http://localhost:19090   (ops metrics)
#   Grafana    http://localhost:13000   (SLO dashboards; admin / claude-demo-pw)
# Langfuse v3 + ClickHouse + MinIO are memory-hungry — use `obs-up-core` for the
# lean trace-only path (collector + Phoenix) when Docker memory is tight.
obs-up:
	docker compose -f docker-compose.obs.claude.yml up -d

obs-up-core:
	docker compose -f docker-compose.obs.claude.yml up -d otel-collector phoenix prometheus grafana

obs-down:
	docker compose -f docker-compose.obs.claude.yml down

obs-logs:
	docker compose -f docker-compose.obs.claude.yml logs -f otel-collector phoenix prometheus grafana

# ── Local development ───────────────────────────────────────────────────────

# Start the FastAPI agent (frontier path via Vertex AI)
run: install
	uv run python scripts/run_local.py

# Start the FastAPI agent (on-premises path via Ollama)
run-on-prem: install
	TESSERA_LLM_PROFILE=on_prem uv run python scripts/run_local.py

# ── CI simulation ───────────────────────────────────────────────────────────

# Replicate what ci.yml does locally (fast path — no integration tests)
ci: format-check lint typecheck test

# ── Utilities ───────────────────────────────────────────────────────────────

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup"
	@echo "  install            Install runtime + dev dependencies"
	@echo "  install-all        Install all optional extras too"
	@echo ""
	@echo "Code quality"
	@echo "  lint               ruff check"
	@echo "  lint-fix           ruff check --fix"
	@echo "  format             ruff format (auto-fix)"
	@echo "  format-check       ruff format --check"
	@echo "  typecheck          mypy --strict"
	@echo "  precommit          pre-commit run --all-files"
	@echo "  check              format-check + lint + typecheck"
	@echo ""
	@echo "Tests"
	@echo "  test               Unit tests only (fast, no external deps)"
	@echo "  test-integration   Integration tests (needs Docker Postgres)"
	@echo "  test-all           Unit + integration"
	@echo "  coverage           Unit tests with HTML coverage report"
	@echo ""
	@echo "Eval"
	@echo "  eval               Full 40-case regression harness"
	@echo "  eval-case CASE=XX  One case by id"
	@echo "  eval-lang LANG=fr  One language slice"
	@echo ""
	@echo "Corpus"
	@echo "  generate-corpus    Re-generate product JSON pages"
	@echo "  ingest-regulations Ingest EU regulatory corpus into pgvector"
	@echo "  seed               Ingest product corpus into pgvector"
	@echo "  bootstrap          Boot Postgres + ingest all corpora"
	@echo ""
	@echo "Run"
	@echo "  run                Local agent (Vertex AI path)"
	@echo "  run-on-prem        Local agent (Ollama / on-prem path)"
	@echo ""
	@echo "  ci                 Local CI simulation (no integration tests)"
