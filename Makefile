.PHONY: install lint typecheck format test test-integration test-all \
        coverage eval seed ingest run run-on-prem demo-observability demo-llmops demo-secrets \
        llmops-secrets \
        precommit check ci help

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

# Full local setup: boot Postgres, ingest all corpora
bootstrap: install
	docker compose up -d postgres
	sleep 3
	$(MAKE) ingest-regulations
	$(MAKE) seed

# ── Local development ───────────────────────────────────────────────────────

# Start the FastAPI agent (frontier path via Vertex AI)
run: install
	uv run python scripts/run_local.py

# Start the FastAPI agent (on-premises path via Ollama)
run-on-prem: install
	TESSERA_LLM_PROFILE=on_prem uv run python scripts/run_local.py

# Create local-only frontend secrets for Auth.js and the superadmin demo account.
demo-secrets: frontend.secret.env
	@echo "Local frontend secrets ready in frontend.secret.env"

frontend.secret.env:
	@auth_secret="$$(openssl rand -base64 32)"; \
	super_password="$$(openssl rand -base64 18)"; \
	{ \
		printf 'AUTH_SECRET=%s\n' "$$auth_secret"; \
		printf 'AUTH_URL=http://localhost:3190\n'; \
		printf 'TESSERA_AUTH_SUPERADMIN_PASSWORD=%s\n' "$$super_password"; \
	} > $@; \
	chmod 600 $@; \
	echo "Created $@ (gitignored). Superadmin password is inside it."

# Start the full local production-like observability demo stack.
demo-observability: frontend.secret.env
	docker compose \
		-f docker-compose.yml \
		-f docker-compose.unix.yml \
		-f docker-compose.observability.yml \
		--profile full up -d --build

# Create local-only secrets for the isolated Langfuse LLMOps stack.
llmops-secrets:
	@if test -f llmops.secret.env && grep -q '^LLMOPS_LANGFUSE_PUBLIC_KEY=' llmops.secret.env; then \
		echo "Local LLMOps secrets ready in llmops.secret.env"; \
	else \
		$(MAKE) -B llmops.secret.env; \
	fi

llmops.secret.env:
	@postgres_password="$$(openssl rand -hex 24)"; \
	clickhouse_password="$$(openssl rand -hex 24)"; \
	redis_auth="$$(openssl rand -hex 24)"; \
	minio_user="tessera_llmops"; \
	minio_password="$$(openssl rand -hex 24)"; \
	nextauth_secret="$$(openssl rand -base64 32)"; \
	salt="$$(openssl rand -hex 32)"; \
	user_password="$$(openssl rand -base64 18)"; \
	public_key="pk-lf-$$(openssl rand -hex 16)"; \
	secret_key="sk-lf-$$(openssl rand -hex 32)"; \
	{ \
		printf 'LLMOPS_POSTGRES_PASSWORD=%s\n' "$$postgres_password"; \
		printf 'LLMOPS_DATABASE_URL=postgresql://langfuse:%s@llmops-postgres:5432/langfuse\n' "$$postgres_password"; \
		printf 'LLMOPS_CLICKHOUSE_PASSWORD=%s\n' "$$clickhouse_password"; \
		printf 'LLMOPS_REDIS_AUTH=%s\n' "$$redis_auth"; \
		printf 'LLMOPS_MINIO_ROOT_USER=%s\n' "$$minio_user"; \
		printf 'LLMOPS_MINIO_ROOT_PASSWORD=%s\n' "$$minio_password"; \
		printf 'LLMOPS_NEXTAUTH_SECRET=%s\n' "$$nextauth_secret"; \
		printf 'LLMOPS_SALT=%s\n' "$$salt"; \
		printf 'LLMOPS_INIT_USER_PASSWORD=%s\n' "$$user_password"; \
		printf 'LLMOPS_LANGFUSE_PUBLIC_KEY=%s\n' "$$public_key"; \
		printf 'LLMOPS_LANGFUSE_SECRET_KEY=%s\n' "$$secret_key"; \
	} > $@; \
	chmod 600 $@; \
	echo "Created $@ (gitignored). Langfuse admin password is inside it."

# Start the same demo with an isolated Langfuse cockpit wired to tessera-llmops.
demo-llmops: frontend.secret.env llmops-secrets
	docker compose --env-file llmops.secret.env \
		-f docker-compose.yml \
		-f docker-compose.unix.yml \
		-f docker-compose.observability.yml \
		-f docker-compose.llmops.yml \
		--profile full up -d --build

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
	@echo "  demo-secrets       Create local Auth.js/superadmin secrets for the demo"
	@echo "  demo-observability Local prod-like stack: UI + agent + OTel + Jaeger + Prometheus + Grafana"
	@echo "  llmops-secrets     Create local secrets for the isolated Langfuse LLMOps stack"
	@echo "  demo-llmops        Local prod-like stack plus isolated Langfuse on :3081"
	@echo ""
	@echo "  ci                 Local CI simulation (no integration tests)"
