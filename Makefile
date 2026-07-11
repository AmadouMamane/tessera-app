.PHONY: install lint typecheck format test test-integration test-all \
        coverage eval eval-demo seed ingest bootstrap run run-on-prem precommit check ci help \
        obs-up obs-down obs-logs dev-secrets \
        gate gate-py gate-web

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

# ── The gate ────────────────────────────────────────────────────────────────
#
# `gate` is the single definition of what "green" means in this repository.
# The CI job of the same name (.github/workflows/ci.yml) invokes these very
# targets, so there is no second, drifting copy of the command list: a green
# gate on your machine and a green gate on a runner check the same things.
#
# Hermetic by construction — no secrets, no services, no network beyond the
# dependency install. Anything that needs Postgres, ClickHouse, an LLM or a
# browser lives in `test-integration` or in the `e2e` job, never here.
#
# The discipline is *twice*-green: run `make gate` two complete times before
# merging. A check that passes once and fails once is a red check.

gate: gate-py gate-web

gate-py: install
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/tessera
	uv run pytest -m "not integration" --cov=src/tessera --cov-report=term-missing --cov-fail-under=0

gate-web:
	cd webapp/frontend && corepack pnpm install --frozen-lockfile
	cd webapp/frontend && corepack pnpm run typecheck
	cd webapp/frontend && corepack pnpm run lint
	cd webapp/frontend && corepack pnpm run test

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

# ── e2e seed fixture ────────────────────────────────────────────────────────
# Rebuild `fixtures/e2e/pgvector-seed.sql.gz` — the corpus CI restores instead of
# ingesting. Embeddings are computed HERE, by the local on-prem model, exactly
# once; CI replays the resulting rows. That is what keeps the workflow free of a
# model, of a key, and of any secret at all.
#
# Built in a THROWAWAY database, never in the dev one: a fixture derived from a
# developer's live state is a fixture nobody can reproduce. Requires Ollama up
# (the seed scripts embed) and the pgvector container reachable by name.
#
# Regenerate whenever the corpus sources change — `tests/unit/test_seed_fixture.py`
# fails until you do.
FIXTURE_PG_CONTAINER ?= tessera-postgres
FIXTURE_DB           ?= tessera_fixture
FIXTURE_DSN           = postgresql://tessera:tessera@localhost:5432/$(FIXTURE_DB)
FIXTURE_DUMP          = fixtures/e2e/pgvector-seed.sql.gz

.PHONY: seed-fixture
seed-fixture: install
	@echo "▶ throwaway database $(FIXTURE_DB) (dropped and recreated)"
	@docker exec $(FIXTURE_PG_CONTAINER) psql -U tessera -d postgres -q \
	  -c 'DROP DATABASE IF EXISTS $(FIXTURE_DB)' -c 'CREATE DATABASE $(FIXTURE_DB)'
	@echo "▶ ingesting with the local embedding model"
	@TESSERA_POSTGRES__DSN=$(FIXTURE_DSN) uv run python scripts/ingest_regulations.py >/dev/null
	@TESSERA_POSTGRES__DSN=$(FIXTURE_DSN) uv run python scripts/seed_demo.py >/dev/null
	@mkdir -p $(dir $(FIXTURE_DUMP))
	@docker exec $(FIXTURE_PG_CONTAINER) pg_dump -U tessera -d $(FIXTURE_DB) \
	  --no-owner --no-privileges | gzip -9 > $(FIXTURE_DUMP)
	@docker exec $(FIXTURE_PG_CONTAINER) psql -U tessera -d postgres -q \
	  -c 'DROP DATABASE IF EXISTS $(FIXTURE_DB)'
	@uv run python scripts/seed_fixture.py
	@ls -lh $(FIXTURE_DUMP) | awk '{print "✓ " $$9 " (" $$5 ")"}'

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

# ── Local dev servers (detached, health-checked) ────────────────────────────
# Reference servers run from the MAIN checkout on the canonical ports so the
# operator's browser reflects `main`. Reviewing UNMERGED work at a supervised
# checkpoint = `make dev-preview PORT=3098` from that agent's worktree (a temp
# server on another port, killed after validation). Convention:
# docs/decisions/0017-execution-status.md (Preconditions). macOS has no setsid,
# so servers are detached with `perl -MPOSIX setsid` + nohup. Assumes deps are
# installed (uv sync + pnpm install).

DEV_FPORT       ?= 3097
DEV_BPORT       ?= 8099
DEV_BACKEND_LOG ?= /tmp/tessera-backend.log
DEV_FRONT_LOG   ?= /tmp/tessera-front.log
_SETSID = perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV or die "exec: $$!"'

.PHONY: dev-up dev-down dev-status dev-preview

# Start backend + frontend from THIS checkout, detached; wait for health.
dev-up:
	@echo "▶ dev-up from $(CURDIR) (git $$(git rev-parse --short HEAD 2>/dev/null)) — front :$(DEV_FPORT) / back :$(DEV_BPORT)"
	@for p in $(DEV_FPORT) $(DEV_BPORT); do lsof -nP -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1 && { echo "✗ port $$p in use — 'make dev-down' first (never two servers on one port)"; exit 1; }; done; true
	@echo "  backend  → $(DEV_BACKEND_LOG)"; TESSERA_API__PORT=$(DEV_BPORT) nohup $(_SETSID) uv run python scripts/run_local.py >$(DEV_BACKEND_LOG) 2>&1 </dev/null &
	@echo "  frontend → $(DEV_FRONT_LOG)"; cd webapp/frontend && PORT=$(DEV_FPORT) TESSERA_BACKEND_URL=http://localhost:$(DEV_BPORT) nohup $(_SETSID) corepack pnpm dev >$(DEV_FRONT_LOG) 2>&1 </dev/null &
	@printf "  backend :$(DEV_BPORT)/healthz … "; curl -sf --retry 60 --retry-connrefused --retry-delay 1 --max-time 120 http://localhost:$(DEV_BPORT)/healthz >/dev/null && echo ok || { echo "FAIL (see $(DEV_BACKEND_LOG))"; exit 1; }
	@printf "  frontend :$(DEV_FPORT)/api/healthz … "; curl -sf --retry 90 --retry-connrefused --retry-delay 1 --max-time 240 http://localhost:$(DEV_FPORT)/api/healthz >/dev/null && echo ok || { echo "FAIL (see $(DEV_FRONT_LOG))"; exit 1; }
	@$(MAKE) --no-print-directory dev-status

# Stop the servers on DEV_FPORT/DEV_BPORT (by port — graceful, then hard).
dev-down:
	@for p in $(DEV_FPORT) $(DEV_BPORT); do pids=$$(lsof -nP -tiTCP:$$p -sTCP:LISTEN 2>/dev/null); [ -n "$$pids" ] && { echo "  SIGTERM :$$p ($$pids)"; kill $$pids 2>/dev/null; } || echo "  :$$p free"; done; true
	@perl -e 'select(undef,undef,undef,1.5)'
	@for p in $(DEV_FPORT) $(DEV_BPORT); do pids=$$(lsof -nP -tiTCP:$$p -sTCP:LISTEN 2>/dev/null); [ -n "$$pids" ] && { echo "  SIGKILL :$$p ($$pids)"; kill -9 $$pids 2>/dev/null; }; done; true
	@echo "✓ dev-down: :$(DEV_FPORT) and :$(DEV_BPORT) free"

# Ports, PIDs, git head of the served checkout, health.
dev-status:
	@for row in "frontend $(DEV_FPORT) /api/healthz" "backend $(DEV_BPORT) /healthz"; do set -- $$row; pid=$$(lsof -nP -tiTCP:$$2 -sTCP:LISTEN 2>/dev/null | head -1); if [ -n "$$pid" ]; then cwd=$$(lsof -a -p $$pid -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1); head=$$(git -C "$$cwd" rev-parse --short HEAD 2>/dev/null || echo -); h=$$(curl -sf --max-time 5 http://localhost:$$2$$3 >/dev/null 2>&1 && echo ok || echo DOWN); printf "  %-8s :%-5s pid %-7s git %-9s %s\n" "$$1" "$$2" "$$pid" "$$head" "$$h"; else printf "  %-8s :%-5s (not running)\n" "$$1" "$$2"; fi; done

# Temporary validation server from a worktree on a custom port.
#   make dev-preview PORT=3098 [API_PORT=8098]
dev-preview:
	@test -n "$(PORT)" || { echo "usage: make dev-preview PORT=3098 [API_PORT=8098]"; exit 1; }
	@api="$(API_PORT)"; [ -n "$$api" ] || api=$$(( $(PORT) + 5000 )); $(MAKE) --no-print-directory dev-up DEV_FPORT=$(PORT) DEV_BPORT=$$api DEV_BACKEND_LOG=/tmp/tessera-preview-backend-$(PORT).log DEV_FRONT_LOG=/tmp/tessera-preview-front-$(PORT).log

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
	@echo "Dev servers (detached, health-checked)"
	@echo "  dev-up             Backend :8099 + frontend :3097 from THIS checkout"
	@echo "  dev-down           Stop them (by port)"
	@echo "  dev-status         Ports, PIDs, served git head, health"
	@echo "  dev-preview PORT=n Temp validation server from a worktree (e.g. 3098)"
	@echo ""
	@echo "  ci                 Local CI simulation (no integration tests)"
