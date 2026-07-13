# ── The shell every recipe runs under ───────────────────────────────────────
#
# A PIPELINE'S EXIT CODE IS ITS LAST COMMAND'S. Nothing else in this file matters
# as much, because that sentence is the origin of ADR 0026: `git merge 2>&1 | tail -1`
# printed `Updating a..b` while the error went to stderr, the pipe ate the status,
# and two gates read green over a failed merge.
#
# GNU make defaults SHELL to `/bin/sh`, which has no `pipefail` at all on a Linux
# runner (dash) and does not enable it on macOS (bash-as-sh). So every `cmd | filter`
# in this file reported the FILTER's success. Measured, on 2026-07-13, in this very
# file: `make ledger-backup` against a container that does not exist printed a ✓,
# exited 0, and wrote a SHA-256-notarised archive of ZERO BYTES — because `gzip`
# compresses a failed `pg_dump`'s empty output with complete success.
#
# `-o pipefail` makes a pipeline report the FIRST command that failed. It is set here,
# once, for every recipe, rather than remembered at each pipe — a discipline that must
# be remembered at each site is a discipline that will be missed at one.
#
# `-e` is deliberately NOT set: `dev-up`'s port guard is a `lsof … && { exit 1; }` whose
# NEGATIVE case (port free ⇒ lsof exits 1) is the healthy one, and `-e` would abort the
# target on it — a false red, which trains you to ignore reds. Verdicts do not live in
# `;`-chains here; `tests/unit/test_exit_witness_debt.py` is what keeps it that way.
SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

.PHONY: install lint typecheck format test test-integration test-all \
        coverage eval eval-demo seed ingest bootstrap run run-on-prem precommit check ci help \
        obs-up obs-down obs-logs dev-secrets \
        gate gate-twice gate-checks gate-py gate-web \
        claim release whoowns session landed

# ── Dependencies ────────────────────────────────────────────────────────────

install: hooks
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

# ── The trunk, and the guard that keeps there being exactly one ─────────────
#
# On 2026-07-13 `main` FORKED:
#
#     5a0e9065 ──┬── 34b59c0d   origin/main   (+10, the eval lane, pushed)
#                └── c6a2048c   main          (+15, the witness lane, never pushed)
#
# Neither an ancestor of the other; no fast-forward left in either direction. It was not
# caused by a bad merge. Each lane advanced ITS OWN `main` from a base it believed was
# current — and the belief was a CACHED REF. Nobody fetched.
#
# "Only one agent touches main" was the rule, and it was written down, and writing it down
# has now failed to stop every single instance in this repo's history of a green light over
# a hole. So it is mechanical now, and it is one sentence:
#
#     origin/main must be an ANCESTOR of whatever main is about to become.
#
# `hooks` INSTALLS `.githooks/reference-transaction` — it copies it into the repository's
# COMMON `.git/hooks/`. It fires on ANY update to refs/heads/main: a `git merge --ff-only`, a
# bare `git merge`, a `git commit` straight onto the branch, a `git reset`. NOT a target
# somebody has to remember: the fork was made of not remembering. (`pre-merge-commit` would
# have been useless — a FAST-FORWARD CREATES NO COMMIT, so it never fires for the exact
# operation that forked the trunk.)
#
# AND THE FIRST VERSION OF THIS TARGET DUG THE HOLE IT WAS BUILT TO FILL. It did
# `git config core.hooksPath .githooks`, and:
#
#   * a RELATIVE core.hooksPath resolves against EACH WORKTREE'S OWN ROOT — so the hook existed
#     only in trees whose branch carried `.githooks/`, and `main` did not. THE GUARD DID NOT RUN
#     IN THE CHECKOUT WHERE THE TRUNK LIVES. An uninstalled guard is not a weak guard; it is a
#     WITNESS THAT DOES NOT RUN. It refuses nothing, and it protects the trees that opted in —
#     and the fork was made of not opting in.
#   * it hijacked git's entire hook lookup, so `.git/hooks/pre-commit` (where `pre-commit
#     install` writes) became unreachable. A silently disabled hook, armed and waiting.
#
# `hooks/` is a COMMON path: git resolves it to the shared `.git/hooks/` from EVERY linked
# worktree — verified by asking git (`git rev-parse --git-path`), not assumed from its docs. So
# ONE installed file guards every worktree whatever branch it carries, and pre-commit keeps its
# own slot. core.hooksPath is unset here, deliberately, to undo the damage.
#
# And the guard asks the REMOTE — `git ls-remote` — never `refs/remotes/origin/main`, which is a
# photograph of the remote taken at your last fetch, and the last fetch is the event that did not
# happen. Offline ⇒ CANNOT SAY ⇒ refused: "probably nothing moved" is the bug in its purest form.
# Deliberate override: TESSERA_MAIN_GUARD_BYPASS=1, which says so aloud.
hooks:
	@if [ "$$(git config --get core.hooksPath || true)" = ".githooks" ]; then \
	  git config --unset core.hooksPath; \
	  echo "  (unset core.hooksPath — it hid .git/hooks/pre-commit and did not reach main)"; \
	fi
	@install -m 0755 .githooks/reference-transaction \
	  "$$(git rev-parse --path-format=absolute --git-common-dir)/hooks/reference-transaction"

# The sanctioned way to advance the trunk. `git merge --ff-only` still works and is still guarded
# (that is the whole point of the hook); this target exists so the verdict is printed BEFORE the
# merge rather than discovered by it.
#   make land BRANCH=claude/some-branch
land: install
	@test -n "$(BRANCH)" || { echo "BRANCH= is required (e.g. make land BRANCH=claude/x)"; exit 2; }
	@uv run python scripts/main_guard.py installed
	@uv run python scripts/main_guard.py advance $$(git rev-parse $(BRANCH))
	@git merge --ff-only $(BRANCH)

# ── Worktree ownership ──────────────────────────────────────────────────────
#
# `make dev-status` says which checkout a SERVER serves. Nothing said which agent
# owns a TREE — and on 2026-07-12 two agents wrote into `agents/claude` at once:
# one stashed the other's uncommitted work mid-flight and switched the branch under
# it. Advisory by design (nothing on a shared filesystem can truly lock), and that
# is enough: it turns a silent collision into a loud refusal.
#
# EXCEPT IT DID NOT. The first version resolved an agent's identity from THE NAME OF
# THE DIRECTORY IT STOOD IN. `agents/claude/` ⇒ owner "claude" — for every Claude
# session alive. On 2026-07-13 SEVEN of them had their cwd in that tree; each read the
# marker, found its own name, and concluded it was home. The marker was identifying a
# ROLE, and a role is not a writer. (ADR 0026's fourth instance, inside the very tool
# built to police the third.)
#
# So identity is now ASSERTED BY THE SESSION and never derived from a path:
#
#   eval "$(make session)"     ← mint TESSERA_SESSION_ID once, keep it for the session
#
# A caller with no session id gets CANNOT SAY and exit 2 — never "you are home". The
# role survives in the marker for a HUMAN to read; it decides nothing.

session:
	@uv run python scripts/worktree_owner.py session

# A GUARD NOBODY INSTALLED IS A DECORATION. `claim` says "I am working here"; the first thing an
# agent working here needs to know is whether the trunk it may land on is actually protected. So
# it is checked, and a missing hook REFUSES (exit 2) — never a warning printed above an exit 0.
#
# That distinction is the whole week's lesson, and this repo has now paid for it three times:
# `dev-status` printed `⚠ STALE · RESTART` and returned 0; the trunk hook, moved to git's
# `committed` phase, printed its refusal IN FULL while `git merge --ff-only` answered
# `Fast-forward` and exited 0. PUBLISHING A VERDICT IS NOT ENFORCING IT.
claim:
	@uv run python scripts/main_guard.py installed
	@uv run python scripts/worktree_owner.py claim $(if $(FORCE),--force,)

release:
	@uv run python scripts/worktree_owner.py release

whoowns:
	@uv run python scripts/worktree_owner.py check

# ── Landing (did this work actually land?) ──────────────────────────────────
#
# RATIFIED DOCTRINE: sha ancestry is NOT landing.
#
# `git merge-base --is-ancestor` answers "is this SHA in main's history?". Nobody
# asks that. The question is "is this WORK on main?", and the two diverge the moment
# a lane rebases or re-implements another's commits — routine in this repo.
#
# It cost a live P1: six of a branch's seven commits had landed under DIFFERENT shas,
# the seventh (the GDPR erasure's author) had not, and `--is-ancestor` said "not
# merged" about ALL SEVEN — an answer that looked like an answer while hiding exactly
# which one was missing. The erasure stayed anonymous on main for a day.
#
#   make landed BRANCH=claude/some-branch [BASE=origin/main]
#
# Compares BLOBS, file by file. Never delete a branch on ancestry alone.

landed:
	@test -n "$(BRANCH)" || (echo "BRANCH= is required (e.g. make landed BRANCH=claude/x)" && exit 2)
	@uv run python scripts/landed.py --branch $(BRANCH) $(if $(BASE),--base $(BASE),)

# The insight registry has ONE source of truth. On 2026-07-12 it had two, under the same
# name, in two harness directories — and the BIGGER one was the DEAD one, so "keep the most
# recent" would have destroyed 98 insights in silence. This target refuses a second registry
# and refuses two insights sharing a number. It also runs inside `make gate`.
memory-check:
	@uv run pytest tests/unit/test_memory_registry_single_source.py -q

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
# EVERY GATE NAMES THE TREE IT RAN ON. A bare exit 0 proves nothing: on
# 2026-07-12 two `make gate` runs returned exit 0 having run on two DIFFERENT
# trees (a concurrent agent stashed the changes and switched the branch between
# the passes), the test counts silently differed — 1862, then 1858 — and it read
# as a clean twice-green. With CI billing-blocked, the local gate is this
# project's ONLY witness, and a witness that cannot say what it saw is not one.
#
# So `gate` fingerprints the tree (worktree · branch · HEAD · dirty · a digest of
# the actual CONTENT) before AND after the run — the incident happened *during* a
# pass, not only between passes — and VOIDS the verdict (exit 3, distinct from a
# red 1) if the tree moved underneath it.
#
# The discipline is *twice*-green, and `gate-twice` is now the only honest way to
# claim it: it asserts BY MACHINE that both passes were green **on one and the
# same tree**. Running `make gate` twice by hand and remembering that both were
# green is precisely what failed.

# An agent does not run the gate in a worktree another agent owns: the gate MUTATES
# (uv sync, a pnpm install, caches), and a second writer is how the 2026-07-12 witness
# was corrupted. Unclaimed trees are allowed on purpose — the marker must not become a
# ceremony that stops the operator's own hands; what it stops is the SILENT second writer.
# A GREEN GATE IS A LICENCE TO LAND. So before it certifies anything, it establishes that the
# trunk it licences you to touch is actually guarded — asked of GIT (`git rev-parse --git-path`),
# never re-derived from `core.hooksPath`, and the installed hook is hashed against the one this
# checkout ships, because what git runs is the COPY and a copy drifts.
#
# Deliberately NOT a prerequisite that would install it: `gate: hooks` would make this check
# unfailable, and a check that cannot fail is a green light with a name. It REFUSES, and it names
# the one command that fixes it.
gate:
	@uv run python scripts/main_guard.py installed
	@uv run python scripts/worktree_owner.py check
	@uv run python scripts/gate_witness.py run --slot $(or $(GATE_SLOT),1) -- $(MAKE) gate-checks

# Two passes, one tree — asserted, never remembered.
gate-twice:
	@$(MAKE) gate GATE_SLOT=1
	@$(MAKE) gate GATE_SLOT=2
	@uv run python scripts/gate_witness.py twice

# The checks themselves. Kept as their own target so the witness wraps the whole
# run as a unit, and so CI can call the checks directly when it has no worktree to
# be confused about.
#
# gate-WEB FIRST, AND THAT ORDER IS LOAD-BEARING. The python suite contains a test
# that judges the frontend (tests/unit/test_zod_codegen.py regenerates the zod schema,
# and the generator formats through `biome`). With `gate-py` first, a virgin worktree —
# where `pnpm install` has never run — went RED on that test, and the red said "the
# checked-in zod is stale": an accusation against code that was perfectly fine, while
# the truth (`Command "biome" not found`, exit 254) was three subprocess layers down and
# in none of the output. A false red is the same disease as a false green, and it is in
# one way worse: a false green lulls you, a FALSE RED TRAINS YOU TO IGNORE REDS.
#
# So the toolchain is installed BEFORE the suite that needs it. The test's own guard
# (`require_node_tool`) then reports a named blind spot outside the gate — and inside it,
# where the tooling is guaranteed, refuses to skip at all. See tests/tooling.py.
gate-checks: gate-web gate-py

# TESSERA_GATE=1 means exactly one thing: THE TOOLCHAIN IS ALREADY INSTALLED (gate-web
# ran first). Under it, a test that cannot find its tool does not skip — it goes RED and
# names the tool, because here its absence cannot mean "bare machine", it can only mean
# the gate is broken. A skip that hides is a green light over a hole (F-14: detect-secrets
# with no baseline was a permanently-green job that checked nothing).
#
# mypy runs over `src/tessera` and the WHOLE of `eval/`. Both lean on `assert_never` to make
# an exhaustive `match` a *proof* rather than a hope — `eval/discrimination.py` over the run
# taxonomy, `scripts/check_discrimination.py` over the Verdict union. A proof mypy never runs
# is decoration, and claiming it in a docstring while the gate looks the other way is exactly
# the false assurance ADR 0026 is about. So the gate looks.
#
# `eval/` was NOT typed until 2026-07-13 (`eval/runner.py` carried 6 `--strict` errors), which
# means every `assert_never` in the harness was decoration for as long as it existed. The debt
# was declared out loud in this same Makefile and then PAID, in the next lot, which is the only
# honest fate for a declared debt.
#
# What is left is `scripts/` — 10 files, frozen BY NAME in `tests/unit/test_typing_debt.py`,
# where the set may only shrink. A debt nobody has to argue with is a debt nobody pays.
gate-py: install
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/tessera eval scripts/check_discrimination.py
	TESSERA_GATE=1 uv run pytest -m "not integration" --cov=src/tessera --cov-report=term-missing --cov-fail-under=0

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

# Run the full 63-case regression harness against the live agent (needs a model)
eval: install
	uv run python scripts/run_eval.py

# The modelless control — the deterministic guard/router layer scored on its own,
# with every LLM backend pointed at a closed port. No model, no services, ~5s.
# This is the half of the harness CI can actually run, and it is a real gate:
# `check_ratchet` demands an EXACT match against the committed baseline, so any
# movement in the guard, the router or the pass criteria fails the build.
# The control's report is written OUTSIDE eval/reports/. That tree is the
# dashboard's and the wiring probes' read surface (ADR 0014: writes go to
# eval/reports/<env>/ exclusively), and the runner always drops a sibling
# `latest.json` next to --report. Pointing the control at eval/reports/ therefore
# publishes a modelless 70% as the project's latest eval result — it silently
# flipped `test_eval_pass_rate_reactive_and_invariant` to DEAD when this target
# was first written. The control is a control, not a result: it stays out.
NULL_HOST := http://127.0.0.1:59999
NULL_REPORT := .eval-control/null-control.json
NULL_BASELINE := eval/baselines/null-control.json

# The runner exits 1 here by design — 52 of the 174 runs need a model and fail
# without one. That exit code is NOT the verdict for the control; the ratchet is.
#
# AND THE `-` SWALLOWS EVERYTHING, NOT ONLY THE EXPECTED 1. A crash exits 1 too, and an
# exit code genuinely cannot tell "52 cases failed, as designed" from "the runner died on
# an import error" — that is a real blind spot, not a fixable one. So the witness stops
# asking the runner's exit code and asks THE ARTEFACT: the report it grades must have been
# produced by THIS run. Measured, 2026-07-13, before the `rm -rf` below existed: with
# `run_eval.py` replaced by `raise SystemExit("BOOM")`, the previous run's report was still
# on disk, `check_ratchet` graded it, printed `[ratchet PASS] 122/174`, and `make eval-null`
# — a per-push CI gate — exited **0** with a runner that could not start.
#
# CI never saw it: a fresh checkout has no stale report. It was armed on every developer
# machine, and CI's immunity was an accident of the runner being clean, not a design.
eval-null: install
	@rm -rf $(dir $(NULL_REPORT))
	-TESSERA_LLM_PROFILE=on_prem TESSERA_OLLAMA_HOST=$(NULL_HOST) \
		uv run python scripts/run_eval.py --report $(NULL_REPORT)
	uv run python scripts/check_ratchet.py \
		--report $(NULL_REPORT) --baseline $(NULL_BASELINE)

# Refresh the control's baseline after a DELIBERATE change to the deterministic
# layer. Commit the diff — it is the evidence of what moved and why.
# Same `rm -rf`, and here it matters even more: this target OVERWRITES THE COMMITTED
# BASELINE from the report it finds. A stale report would have been promoted to the
# reference every future run is graded against.
eval-null-write: install
	@rm -rf $(dir $(NULL_REPORT))
	-TESSERA_LLM_PROFILE=on_prem TESSERA_OLLAMA_HOST=$(NULL_HOST) \
		uv run python scripts/run_eval.py --report $(NULL_REPORT)
	uv run python scripts/check_ratchet.py \
		--report $(NULL_REPORT) --baseline $(NULL_BASELINE) --write

# Grade a model on its CONTRIBUTION over the null floor, not on its absolute rate
# (ruling 2026-07-12). llama3.2:3b and gemma3:27b both score 157/174 — the absolute rate
# cannot tell apart a model that degrades the agent from one that does not.
#   make eval-contribution REPORT=eval/reports/sweep/gemma3-27b.json MIN=30
eval-contribution: install
	@test -n "$(REPORT)" || (echo "REPORT= is required" && exit 2)
	uv run python scripts/check_contribution.py --report $(REPORT) $(if $(MIN),--min-contribution $(MIN))

# Replay the catalogue against every local model and compare them against the null floor
eval-sweep: install
	uv run python scripts/run_model_sweep.py

# What the CATALOGUE measures — the question a pass rate cannot answer. The null control
# passes 122 of the 174 runs with no model at all, so most of the score is the deterministic
# layer; each run is classified by what it SEPARATES (Fisher exact, Holm-corrected over the
# whole catalogue), derived from the null floor and repeated passes of a strong and a weak
# model. No case declares its own power.
#
# This is the CHECK: it re-derives the classification from the COMMITTED evidence, so it needs
# no model, no GPU and no services — CI runs it on every push. Exit 3 (not 1) when the
# catalogue has moved: the classification was not judged, which is not the same as failing.
eval-power: install
	uv run python scripts/check_discrimination.py

# RE-MEASURE. Needs the raw passes in .eval-noise/ (make eval-noise MODEL=… PASSES=15) — a
# GPU-hour. Rewrites both the evidence and the classification derived from it, and prints the
# new power floor to freeze in scripts/check_discrimination.py.
eval-power-write: install
	uv run python scripts/check_discrimination.py --write

# DEBT (ADR 0021): rule 2's bar (30) is a reasoned floor, NOT a calibrated one — no weak
# model has ever been run against this catalogue, so nothing bounds it from below except
# the null control at 0/52. This target closes that debt: replay the catalogue against a
# deliberately weak model and see where it lands. ~20 minutes.
#   make eval-calibrate-weak MODEL=llama3.2:1b   (ollama pull it first)
eval-calibrate-weak: install
	@test -n "$(MODEL)" || (echo "MODEL= is required (e.g. llama3.2:1b)" && exit 2)
	uv run python scripts/run_model_sweep.py --models $(MODEL) --out eval/reports/weak-model

# What a bar has to CLEAR: the sampling noise, measured instead of guessed. The T2 sampling
# temperature is 0.2 with no seed, so the same model does not score the same twice — and
# "30 leaves 5-6 cases of margin" (ADR 0021) assumed a spread nobody had counted. One pass
# per model tells you nothing about a distribution; this runs N of them and reports the
# real one, using the gate's OWN population function so what is measured is what is graded.
#   make eval-noise MODEL=llama3.2:3b PASSES=5        # the model the bar must ADMIT
#   make eval-noise MODEL=llama3.2:1b PASSES=5        # the weak model it must REJECT
# Reports land in .eval-noise/ (gitignored): a calibration pass is not a published result.
eval-noise: install
	@test -n "$(MODEL)" || (echo "MODEL= is required (e.g. llama3.2:3b)" && exit 2)
	uv run python scripts/measure_contribution_noise.py \
		--model $(MODEL) --passes $(or $(PASSES),5)

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

# ── Ledger backup + restore drill (audit P1.2) ──────────────────────────────
# The audit ledger is the opposable memory, and nothing scheduled backed it up (only the
# incident freeze existed). `ledger-backup` writes a timestamped, SHA-256-logged, DATA-ONLY
# pg_dump; `ledger-restore-drill` PROVES it serves by restoring into a THROWAWAY database and
# verifying the chain tree-aware — never against the live store. Data-only by design: the
# table + append-only trigger + fork guard are code (ensure_audit_ledger_schema recreates
# them); the chain DATA is the irreplaceable thing. Retention + scheduling: docs/runbook.md.
LEDGER_PG_CONTAINER ?= tessera-postgres
LEDGER_DB           ?= tessera
LEDGER_SCHEMA       ?= tessera_local
LEDGER_BACKUP_DIR   ?= backups/ledger

.PHONY: ledger-backup ledger-restore-drill

# A BACKUP THAT CANNOT FAIL IS NOT A BACKUP. This recipe used to be three laundered exit
# codes stacked on one line — a `pg_dump | gzip` pipeline (exit = gzip's), a `;`-chain with
# no `set -e`, and a closing `echo "✓"` — and against a container that does not exist it
# printed a tick, exited 0, and wrote a SHA-256-notarised archive of zero bytes. The sidecar
# authenticated the emptiness. See scripts/ledger_backup.py, which now does the work and
# INTERROGATES THE ARTEFACT: no `COPY <schema>.audit_ledger` header in the dump ⇒ no file is
# written and the verdict is NOT OK. An empty *ledger* passes; a failed *dump* cannot.
ledger-backup: install
	@LEDGER_PG_CONTAINER=$(LEDGER_PG_CONTAINER) LEDGER_DB=$(LEDGER_DB) \
	 LEDGER_SCHEMA=$(LEDGER_SCHEMA) LEDGER_BACKUP_DIR=$(LEDGER_BACKUP_DIR) \
	 uv run python scripts/ledger_backup.py

# Prove the newest backup restores to a verifying chain (throwaway db, tree-aware verify).
ledger-restore-drill: install
	@LEDGER_PG_CONTAINER=$(LEDGER_PG_CONTAINER) LEDGER_DB=$(LEDGER_DB) \
	 LEDGER_SCHEMA=$(LEDGER_SCHEMA) LEDGER_BACKUP_DIR=$(LEDGER_BACKUP_DIR) \
	 uv run python scripts/ledger_restore_drill.py

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
DEV_MPORT       ?= 9090
DEV_BACKEND_LOG ?= /tmp/tessera-backend.log
DEV_FRONT_LOG   ?= /tmp/tessera-front.log
_SETSID = perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV or die "exec: $$!"'

.PHONY: dev-up dev-down dev-status dev-preview

# Start backend + frontend from THIS checkout, detached; wait for health.
dev-up:
	@echo "▶ dev-up from $(CURDIR) (git $$(git rev-parse --short HEAD 2>/dev/null)) — front :$(DEV_FPORT) / back :$(DEV_BPORT) / metrics :$(DEV_MPORT)"
	@for p in $(DEV_FPORT) $(DEV_BPORT) $(DEV_MPORT); do lsof -nP -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1 && { echo "✗ port $$p in use — 'make dev-down' first (never two servers on one port)"; exit 1; }; done; true
	@echo "  backend  → $(DEV_BACKEND_LOG)"; TESSERA_API__PORT=$(DEV_BPORT) TESSERA_OBS_METRICS_PORT=$(DEV_MPORT) nohup $(_SETSID) uv run python scripts/run_local.py >$(DEV_BACKEND_LOG) 2>&1 </dev/null &
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

# Ports, PIDs, and — the point — WHAT CODE THE PROCESS ACTUALLY LOADED, asked of the process.
#
# This target used to do `lsof` → the process's cwd → `git -C "$cwd" rev-parse HEAD`, and print
# the answer in a column labelled `git`. Every reader took that to mean "the code this server is
# serving". It never was: it was the git head of a DIRECTORY, and a directory is not a process.
# Move the checkout under a live server and the witness reported the new sha with complete
# composure — which is exactly what happened on 2026-07-13, while the operator's browser paid
# 1 087 ms for a badge that costs 20 ms and every witness on the machine said all was well.
#
# A witness interrogates the thing, never its neighbourhood (ADR 0026). The server now publishes,
# on /healthz, a digest of the source it loaded — captured at import and frozen, so a moving
# checkout cannot change it — and `dev_status.py` re-hashes the checkout with the SAME function
# and compares. Divergence ⇒ STALE · RESTART, loudly. Cannot ask ⇒ said out loud, never "ok".
dev-status:
	@uv run python scripts/dev_status.py $(DEV_FPORT) $(DEV_BPORT)

# Temporary validation server from a worktree on a custom port. The Prometheus
# metrics port is derived too, not just the API port: it is bound unconditionally
# at boot, so leaving it at the default made a preview collide with the reference
# backend and die on "Address already in use" — never two backends on one host.
#   make dev-preview PORT=3098 [API_PORT=8098] [METRICS_PORT=9098]
dev-preview:
	@test -n "$(PORT)" || { echo "usage: make dev-preview PORT=3098 [API_PORT=8098] [METRICS_PORT=9098]"; exit 1; }
	@api="$(API_PORT)"; [ -n "$$api" ] || api=$$(( $(PORT) + 5000 )); mport="$(METRICS_PORT)"; [ -n "$$mport" ] || mport=$$(( $$api + 1000 )); $(MAKE) --no-print-directory dev-up DEV_FPORT=$(PORT) DEV_BPORT=$$api DEV_MPORT=$$mport DEV_BACKEND_LOG=/tmp/tessera-preview-backend-$(PORT).log DEV_FRONT_LOG=/tmp/tessera-preview-front-$(PORT).log

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
	@echo "  dev-up             Backend :8099 + frontend :3097 + metrics :9090 from THIS checkout"
	@echo "  dev-down           Stop them (by port)"
	@echo "  dev-status         Ports, PIDs, served git head, health"
	@echo "  dev-preview PORT=n Temp validation server from a worktree (e.g. 3098)"
	@echo ""
	@echo "  ci                 Local CI simulation (no integration tests)"
