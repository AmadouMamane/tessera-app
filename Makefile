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

# EVERY target is phony here, and the list is enforced by a test
# (tests/unit/test_makefile_targets_are_phony.py). A target absent from this list whose name
# happens to match a file or directory is considered UP TO DATE by make and silently does
# nothing. `hooks` is the one that mattered: `install` depends on it and `gate` depends on
# `install`, so a stray `hooks/` directory would have stopped installing the trunk guard
# without a word. `eval` was protected once, by hand, because `eval/` exists — the precaution
# was taken and never generalised. Audit 2026-08-03.
.PHONY: install install-all lint lint-fix typecheck format format-check test test-integration \
        test-all coverage eval eval-demo eval-case eval-lang eval-sweep eval-noise \
        eval-null eval-null-write eval-power eval-power-write eval-contribution eval-bundle \
        eval-calibrate-weak seed generate-corpus ingest-regulations reindex-embeddings \
        bootstrap run run-on-prem \
        precommit check ci help hooks land memory-check \
        obs-up obs-up-core obs-down obs-logs obs-guard obs-secrets obs-retention dev-secrets \
        obs-verify obs-realign obs-wait eval-regrade eval-regrade-noise \
        gate gate-twice gate-checks gate-py gate-web tooling \
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
	@# THE VERDICT AND THE MUTATION MUST NAME THE SAME REF (audit 2026-08-03).
	@# `main_guard advance` answers "may MAIN become this commit?" and prints "One trunk,
	@# still" — then the merge below ran `--ff-only` on whatever branch this checkout
	@# happened to be on. From `claude/foo`, `make land BRANCH=claude/bar` printed a verdict
	@# about main and fast-forwarded foo onto bar; and since .githooks/reference-transaction
	@# filters `refs/heads/main`, that merge was guarded by nothing at all. A witness that
	@# judges one object while the command mutates another is ADR 0026's exact failure.
	@cur=$$(git rev-parse --abbrev-ref HEAD); \
	  if [ "$$cur" != "main" ]; then \
	    echo "✗ land refuses: HEAD is '$$cur', not 'main'."; \
	    echo "  The guard's verdict is about main; landing from another branch would move"; \
	    echo "  '$$cur' instead, unguarded. Run it from the main checkout."; \
	    exit 2; \
	  fi
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
claim: tooling
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
gate: tooling
	@uv run python scripts/main_guard.py installed
	@uv run python scripts/worktree_owner.py check
	@uv run python scripts/gate_witness.py run --slot $(or $(GATE_SLOT),1) -- $(MAKE) gate-checks

# ── The gate must be able to SEE before it may say anything ─────────────────────────────────────
#
# `gate` and `claim` open by asking `scripts/main_guard.py` whether the trunk is guarded. That
# question cannot be ASKED if the tool that asks it is not in this checkout — and on 2026-07-13 it
# was not. The hook was installed; its tool lived on a branch that had not landed. The guard
# therefore refused EVERY advance of the trunk, including the one branch that carried the tool: a
# BOOTSTRAP LOCK, and it took a written derogation from Amadou to break it.
#
# The gate did refuse in that state. It refused like this:
#
#     .venv/bin/python3: can't open file '.../scripts/main_guard.py': [Errno 2] No such file
#     make: *** [gate] Error 2
#
# THAT IS A REFUSAL THAT IS RIGHT BY ACCIDENT. Non-zero, yes — but it publishes no verdict, it
# names no condition, and it gives no command that repairs it. A red nobody can act on is a red
# people learn to ignore, and a false red is the same disease as a false green. ADR 0026 says a
# witness that cannot see reports a BLIND SPOT and may never report "ok" — it may not report
# gibberish either, because gibberish is how a blind spot gets mistaken for noise.
#
# So the tooling is interrogated FIRST, and in SHELL — a check for a missing interpreter cannot be
# written in the language that interpreter runs. It asks the THING (is the file here? is the
# interpreter executable?), never its neighbourhood, and it says exactly what repairs it. It is a
# check, never an install: `tooling: install` would make it unfailable, which is the same mistake
# `gate: hooks` would have been.
tooling:
	@root="$$(git rev-parse --show-toplevel)"; \
	rc=0; \
	for f in scripts/main_guard.py scripts/worktree_owner.py; do \
	  if [ ! -r "$$root/$$f" ]; then \
	    rc=2; \
	    echo ""; \
	    echo "[tooling] [CANNOT SAY] the gate cannot judge the trunk: its own tool is missing."; \
	    echo "  absent: $$f"; \
	    if git cat-file -e "HEAD:$$f" 2>/dev/null; then \
	      echo "  It IS tracked at HEAD, so it was deleted from the working tree. Restore it:"; \
	      echo "      git checkout -- $$f"; \
	    else \
	      echo "  THIS BRANCH DOES NOT CARRY IT — the bootstrap lock of 2026-07-13. The hook is"; \
	      echo "  installed, its tool is not here, so the guard refuses every advance of the trunk"; \
	      echo "  including the branch that would fix it. The trunk carries it; rebase onto it:"; \
	      echo "      git fetch origin && git rebase origin/main"; \
	    fi; \
	  fi; \
	done; \
	if [ ! -x "$$root/.venv/bin/python" ]; then \
	  rc=2; \
	  echo ""; \
	  echo "[tooling] [CANNOT SAY] no interpreter at .venv/bin/python."; \
	  echo "  The trunk hook runs THAT python and no other: the guard needs 3.11+ (match,"; \
	  echo "  assert_never), and macOS's system python3 is 3.9 — falling back to it put an"; \
	  echo "  ImportError traceback where a verdict belonged."; \
	  echo "      make install"; \
	fi; \
	if [ "$$rc" -ne 0 ]; then \
	  echo ""; \
	  echo "  A witness that cannot see reports a blind spot. It may never report 'ok' (ADR 0026)."; \
	  exit $$rc; \
	fi

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

# Re-derive a report's JUDGEMENTS from its recorded responses, under today's criteria.
#
# A report holds two different things: what the model SAID (a fact, fixed when the run ended)
# and what that was WORTH (a judgement, made by the grader of the day). `catalogue_version`
# pins the first and is blind to the second. On 2026-08-03 fifty-nine criteria changed and the
# null floor was re-measured; the agents' reports were not, and the release gate — comparing an
# August floor against July judgements — reported three models as *worse than no model at all*.
# Two of those were refusals the old grader could not read.
#
# This spends NO tokens and draws NO sample: the responses are on disk. It is more reproducible
# than a replay, which would sample a stochastic model afresh and answer a different question.
# Cases whose criteria turn on `confidence` or `citations` — which a report does not record —
# come back CANNOT SAY rather than quietly passing.
#
#   make eval-regrade                          # every latest_<agent>.json
#   make eval-regrade REPORT=path DRY_RUN=1    # one, saying what it would change
eval-regrade: install
	uv run python scripts/regrade_reports.py $(if $(REPORT),--report $(REPORT)) $(if $(DRY_RUN),--dry-run)

# Re-grade the FROZEN discrimination passes in .eval-noise/ — the recordings the release gate's
# power measurement is derived from. They are gitignored scratch, but they are evidence: the
# committed matrix carries their verdicts verbatim. On 2026-08-04 a re-measure re-graded 13 of
# the 30 and left 17 under the previous rule, and the mixture certified the models and blocked
# two agents with no file able to say so. `make eval-power-write` now REFUSES a mixture, so this
# is the step that precedes it. Zero tokens: the responses are already on disk.
#
#   make eval-regrade-noise            # all thirty passes
#   make eval-regrade-noise DRY_RUN=1  # say what would change; write nothing
eval-regrade-noise: install
	uv run python scripts/regrade_reports.py --dir .eval-noise $(if $(DRY_RUN),--dry-run)

# Rebuild the frontend's bundled eval snapshot FROM the repo. `data/eval/` is the ONLY eval
# source inside the standalone image (no pyproject.toml above /app), and it used to be a second
# hand-maintained original: on 2026-08-05 it shipped 36 of 63 cases with criteria the grader no
# longer applied, no power baseline at all, and a blind-run list SHORTER than the repo's. Run
# this after any change under eval/ and commit the result — `test_eval_bundle_is_derived` fails
# when what is committed is not what this writes.
eval-bundle: install
	uv run python scripts/build_eval_bundle.py

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

# Repair legacy vectors whose ingestion did not record model/dimension provenance.
# Dry-run by default; pass ARGS="--apply --expect-rows N --expect-plan-digest SHA" only after
# reviewing the exact plan printed by a preceding dry run.
reindex-embeddings: install
	uv run python scripts/reindex_embeddings.py $(ARGS)

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
	@# WRITE ASIDE, THEN MOVE (audit 2026-08-03). `> $(FIXTURE_DUMP)` truncates the target
	@# BEFORE the pipeline runs, and the target is a TRACKED 1.2 MB fixture. A missing
	@# container or an empty database therefore left a zero-byte file on disk — the notarised
	@# empty archive this Makefile opens by warning about, and the very input `ci.yml`
	@# describes restoring as a silent green (`gunzip | psql` applies the valid prefix).
	@# pipefail already stops make; it cannot un-truncate the file.
	@docker exec $(FIXTURE_PG_CONTAINER) pg_dump -U tessera -d $(FIXTURE_DB) \
	  --no-owner --no-privileges | gzip -9 > $(FIXTURE_DUMP).tmp
	@test -s $(FIXTURE_DUMP).tmp || { echo "✗ dump is empty — refusing to replace the fixture"; rm -f $(FIXTURE_DUMP).tmp; exit 1; }
	@gzip -t $(FIXTURE_DUMP).tmp || { echo "✗ dump is not a valid gzip stream — fixture untouched"; rm -f $(FIXTURE_DUMP).tmp; exit 1; }
	@mv $(FIXTURE_DUMP).tmp $(FIXTURE_DUMP)
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

.PHONY: ledger-backup ledger-restore-drill ledger-reset

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

# Reset the LOCAL demo ledger (a bloated demo ledger was the OOM trigger; this makes the manual
# backup+TRUNCATE+restart safe and repeatable). A VERIFIED backup goes FIRST — ledger_backup.py's
# own verdict gates the wipe — then TRUNCATE … RESTART IDENTITY, a re-read proving the tables are
# empty, and an agent restart. Refuses any non-`_local` schema and needs CONFIRM=<schema> so it
# cannot be fat-fingered. See scripts/ledger_reset.py.
ledger-reset: install
	@LEDGER_PG_CONTAINER=$(LEDGER_PG_CONTAINER) LEDGER_DB=$(LEDGER_DB) \
	 LEDGER_SCHEMA=$(LEDGER_SCHEMA) LEDGER_BACKUP_DIR=$(LEDGER_BACKUP_DIR) \
	 AGENT_CONTAINER=$(or $(AGENT_CONTAINER),tessera-$(or $(TESSERA_ENV),local)-agent) \
	 LEDGER_RESET_CONFIRM=$(CONFIRM) \
	 uv run python scripts/ledger_reset.py

# Full local setup: boot Postgres, ingest all corpora, populate eval demo data
bootstrap: install
	docker compose up -d postgres
	sleep 3
	$(MAKE) ingest-regulations
	$(MAKE) seed
	$(MAKE) eval-demo

# ── Dev secrets ─────────────────────────────────────────────────────────────
# Generate the local Auth.js secret plus the shared operator-assertion HMAC secret in
# gitignored .env.local files. The operator key is one trust boundary with two names: the
# agent loads the nested delimiter (double underscore), while Next reads the single-underscore
# name verbatim. A one-sided existing key is copied to the missing side; two different values
# fail loudly instead of minting assertions the agent can never verify.
dev-secrets:
	@set -eu; \
	  umask 077; \
	  root_env=.env.local; front_env=webapp/frontend/.env.local; \
	  touch "$$root_env" "$$front_env"; \
	  agent_key=$$(sed -n 's/^TESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY=//p' "$$root_env" | tail -n 1); \
	  front_key=$$(sed -n 's/^TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY=//p' "$$front_env" | tail -n 1); \
	  if [ -n "$$agent_key" ] && [ -n "$$front_key" ] && [ "$$agent_key" != "$$front_key" ]; then \
	    echo "✗ operator assertion keys differ between root and frontend .env.local"; \
	    exit 1; \
	  fi; \
	  shared_key="$$agent_key$$front_key"; \
	  if [ -z "$$shared_key" ]; then shared_key=$$(openssl rand -hex 32); fi; \
	  if [ -z "$$agent_key" ]; then printf '\nTESSERA_API__OPERATOR_ASSERTION_SIGNING_KEY=%s\n' "$$shared_key" >> "$$root_env"; fi; \
	  if [ -z "$$front_key" ]; then printf '\nTESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY=%s\n' "$$shared_key" >> "$$front_env"; fi; \
	  auth_secret=$$(sed -n 's/^AUTH_SECRET=//p' "$$front_env" | tail -n 1); \
	  if [ -z "$$auth_secret" ]; then \
	    printf '\nAUTH_SECRET=%s\n' "$$(openssl rand -hex 32)" >> "$$front_env"; \
	  fi; \
	  echo "✓ local session + operator assertion secrets present and consistent"

# ── Observability stack (OTel collector -> Phoenix + Langfuse + Grafana) ─────
# The agent only feeds traces when TESSERA_OBSERVABILITY__OTEL_ENDPOINT points at the
# collector (see .env.example). `obs-up` boots the full stack:
#   Phoenix    http://127.0.0.1:16006   (LLM traces — canonical)
#   Langfuse   http://127.0.0.1:3900    (cost / tokens / latency / sessions)
#   Prometheus http://127.0.0.1:19090   (ops metrics)
#   Grafana    http://127.0.0.1:13000   (SLO dashboards)
# Langfuse v3 + ClickHouse + MinIO are memory-hungry — use `obs-up-core` for the
# lean trace-only path (collector + Phoenix) when Docker memory is tight.
#
# ⚠ THIS STACK HOLDS THE LLM TRACES, AND THE LLM TRACES ARE CUSTOMER CONVERSATIONS.
#
# Every credential in it used to be a literal (`clickhouse/clickhouse`, `minio/miniosecret`,
# `claude-demo-pw`, and an `ENCRYPTION_KEY` of SIXTY-FOUR ZEROS), and every port was published on
# 0.0.0.0 — every interface. On any shared network a stranger could open Langfuse and read every
# transcript with a password that is readable on GitHub. That is **F-9** — "default accounts stay
# valid when the env vars are missing" — closed in the app, and left wide open in the plane that
# holds the transcripts. The question is never "is this production?"; it is **"can a stranger
# reach it?"**.
#
# So there is NO DEFAULT CREDENTIAL, anywhere, and the stack REFUSES to boot without explicit
# ones. `make obs-secrets` is the escape hatch, and it is deliberately narrow: it generates
# RANDOM credentials into a gitignored `.env.obs.local`. **It removes the typing, never the
# security** — which is why dev/CI may use it and a reachable stack loses nothing by it.
OBS_ENV_FILE := .env.obs.local
# `--env-file` is passed ONLY when the file is there: `docker compose --env-file <missing>` exits 1
# ("couldn't find env file") EVEN WHEN the variables are exported — so hard-coding the flag would
# have made the guard advertise a road it then blocks ("or export them yourself"). Recursive `=`,
# not `:=`, so the test is made when the recipe runs, not when the Makefile is parsed.
OBS_ENV_ARG   = $(if $(wildcard $(OBS_ENV_FILE)),--env-file $(OBS_ENV_FILE),)
OBS_COMPOSE   = docker compose $(OBS_ENV_ARG) -f docker-compose.obs.claude.yml

# The credentials the stack cannot run without. A username is not a credential and is not here.
OBS_SECRETS := TESSERA_OBS_LANGFUSE_DB_PASSWORD TESSERA_OBS_SALT TESSERA_OBS_ENCRYPTION_KEY \
               TESSERA_OBS_CLICKHOUSE_PASSWORD TESSERA_OBS_MINIO_PASSWORD \
               TESSERA_OBS_REDIS_PASSWORD TESSERA_OBS_NEXTAUTH_SECRET \
               TESSERA_OBS_LANGFUSE_PUBLIC_KEY TESSERA_OBS_LANGFUSE_SECRET_KEY \
               TESSERA_OBS_LANGFUSE_OTEL_BASIC_AUTH TESSERA_OBS_LANGFUSE_USER_PASSWORD \
               TESSERA_OBS_GRAFANA_PASSWORD

# A guard, never an install. `obs-guard: obs-secrets` would generate the very credentials it is
# meant to demand — a check that repairs what it checks has checked nothing (F-14, `gate: hooks`).
obs-guard:
	@missing=""; \
	env_file="$(OBS_ENV_FILE)"; \
	case "$$env_file" in /*) ;; *) env_file="./$$env_file" ;; esac; \
	if [ -f "$$env_file" ]; then \
	  seen="$(OBS_ENV_FILE) (present)"; \
	  set -a; . "$$env_file"; set +a; \
	else \
	  seen="$(OBS_ENV_FILE) (ABSENT)"; \
	fi; \
	for v in $(OBS_SECRETS); do \
	  [ -n "$${!v}" ] || missing="$$missing $$v"; \
	done; \
	if [ -n "$$missing" ]; then \
	  echo ""; \
	  echo "[obs-guard] [NOT OK] REFUSING to start the observability stack: it has no credentials."; \
	  echo "  This stack holds the LLM traces, and the LLM traces are customer conversations."; \
	  echo "  Looked at: the environment, and $$seen"; \
	  echo "  Unset:"; \
	  for v in $$missing; do echo "      $$v"; done; \
	  echo ""; \
	  echo "  Generate random ones (gitignored, never committed):"; \
	  echo "      make obs-secrets"; \
	  echo "  Or export them yourself. There is no default, because A DEFAULT THAT IS A"; \
	  echo "  CREDENTIAL IS THE BUG — it is F-9, and it was open in this file until 2026-07-14."; \
	  exit 2; \
	fi

# The narrow, declared escape hatch. It writes RANDOM credentials — it removes the TYPING, not the
# security, so there is no weak default left anywhere for anyone to forget.
obs-secrets:
	@if [ -f "$(OBS_ENV_FILE)" ]; then \
	  echo "$(OBS_ENV_FILE) already exists — nothing to do (delete it to rotate)."; \
	else \
	  umask 077; \
	  pk="pk-lf-$$(openssl rand -hex 12)"; \
	  sk="sk-lf-$$(openssl rand -hex 24)"; \
	  { \
	    echo "# Written by \`make obs-secrets\`. GITIGNORED — never commit this."; \
	    echo "# Random, not weak: the escape hatch removes the typing, never the security."; \
	    echo "TESSERA_OBS_LANGFUSE_DB_PASSWORD=$$(openssl rand -hex 24)"; \
	    echo "TESSERA_OBS_SALT=$$(openssl rand -hex 24)"; \
	    echo "TESSERA_OBS_ENCRYPTION_KEY=$$(openssl rand -hex 32)"; \
	    echo "TESSERA_OBS_CLICKHOUSE_PASSWORD=$$(openssl rand -hex 24)"; \
	    echo "TESSERA_OBS_MINIO_PASSWORD=$$(openssl rand -hex 24)"; \
	    echo "TESSERA_OBS_REDIS_PASSWORD=$$(openssl rand -hex 24)"; \
	    echo "TESSERA_OBS_NEXTAUTH_SECRET=$$(openssl rand -hex 32)"; \
	    echo "TESSERA_OBS_LANGFUSE_PUBLIC_KEY=$$pk"; \
	    echo "TESSERA_OBS_LANGFUSE_SECRET_KEY=$$sk"; \
	    echo "TESSERA_OBS_LANGFUSE_OTEL_BASIC_AUTH=$$(printf '%s:%s' "$$pk" "$$sk" | base64 | tr -d '\n')"; \
	    echo "TESSERA_OBS_LANGFUSE_USER_PASSWORD=$$(openssl rand -hex 16)"; \
	    echo "TESSERA_OBS_GRAFANA_PASSWORD=$$(openssl rand -hex 16)"; \
	  } > "$(OBS_ENV_FILE)"; \
	  echo "wrote $(OBS_ENV_FILE) (umask 077) — 12 random credentials, gitignored."; \
	  echo "  ENCRYPTION_KEY is 64 hex chars, as Langfuse requires. It used to be sixty-four ZEROS."; \
	  echo "  The OTLP basic-auth header is DERIVED from the key pair, so the two cannot drift."; \
	fi

# ── The credential the ENV declares, and the credential the VOLUME remembers ────────────────
#
# `obs-guard` asks whether a credential is SET. It cannot ask whether it is ACCEPTED — and on
# 2026-08-04 that gap cost fourteen hours: `tessera-claude-langfuse` restarted **818 times**
# against `P1000 Authentication failed`, and no witness in this repository said a word.
#
# Postgres and ClickHouse bake their password when the VOLUME IS INITIALISED and ignore the env
# for ever after. Regenerate `.env.obs.local`, or keep a volume older than it, and the two
# diverge in silence: every variable is set, `obs-guard` is green, and the stack cannot log in.
#
# The trap that hid it for a whole morning: `docker exec … psql -U langfuse` SUCCEEDS with the
# wrong password, because the image's local socket is `trust`. So this witness interrogates THE
# DATABASE, **over TCP, from the stack's own network, with the env credential** — the exact path
# Langfuse takes, and the only one that can tell the two apart (ADR 0026).
#
# Nothing here repairs. The repair is `obs-realign`, separate and deliberate, because a witness
# that heals its own condition reports "ok" for ever — the same reason `obs-guard` may not
# depend on `obs-secrets`.
#
# Three verdicts, never two (ADR 0027): OK · NOT OK (names the divergence and the repair) ·
# CANNOT SAY (the stack is not up, or docker is not answering — a witness that cannot see may
# not say "ok"). They are carried by the printed TAG, not by the exit code, because **make
# collapses every failing recipe to exit 2** whatever the recipe exits with — so `obs-verify`
# offers exactly two codes, 0 and 2, and claiming a third here would make this comment the
# false witness. Read the tag; the code only tells you green from not-green.
OBS_NETWORK := tessera-claude-obs

obs-verify:
	@env_file="$(OBS_ENV_FILE)"; \
	case "$$env_file" in /*) ;; *) env_file="./$$env_file" ;; esac; \
	if [ -f "$$env_file" ]; then set -a; . "$$env_file"; set +a; fi; \
	if ! docker info >/dev/null 2>&1; then \
	  echo "[obs-verify] [CANNOT SAY] docker is not answering — no credential was tried."; \
	  exit 2; \
	fi; \
	bad=""; unseen=""; \
	if [ -n "$$(docker ps -q -f name='^tessera-claude-langfuse-db$$')" ]; then \
	  img=$$(docker inspect tessera-claude-langfuse-db --format '{{.Config.Image}}'); \
	  if docker run --rm --network $(OBS_NETWORK) \
	       -e PGPASSWORD="$$TESSERA_OBS_LANGFUSE_DB_PASSWORD" "$$img" \
	       psql -h langfuse-db -U langfuse -d langfuse -c 'select 1' >/dev/null 2>&1; then \
	    echo "[obs-verify] [OK] postgres accepts TESSERA_OBS_LANGFUSE_DB_PASSWORD over TCP."; \
	  else \
	    bad="$$bad langfuse-db/TESSERA_OBS_LANGFUSE_DB_PASSWORD"; \
	  fi; \
	else unseen="$$unseen langfuse-db"; fi; \
	if [ -n "$$(docker ps -q -f name='^tessera-claude-clickhouse$$')" ]; then \
	  img=$$(docker inspect tessera-claude-clickhouse --format '{{.Config.Image}}'); \
	  if docker run --rm --network $(OBS_NETWORK) --entrypoint clickhouse-client "$$img" \
	       --host clickhouse --user clickhouse --password "$$TESSERA_OBS_CLICKHOUSE_PASSWORD" \
	       --query 'SELECT 1' >/dev/null 2>&1; then \
	    echo "[obs-verify] [OK] clickhouse accepts TESSERA_OBS_CLICKHOUSE_PASSWORD over TCP."; \
	  else \
	    bad="$$bad clickhouse/TESSERA_OBS_CLICKHOUSE_PASSWORD"; \
	  fi; \
	else unseen="$$unseen clickhouse"; fi; \
	if [ -n "$$bad" ]; then \
	  echo ""; \
	  echo "[obs-verify] [NOT OK] the stack's own credential is REFUSED by the store it unlocks:"; \
	  for b in $$bad; do echo "      $$b"; done; \
	  echo "  The variable is set, so \`obs-guard\` is green. The VOLUME was initialised with a"; \
	  echo "  different password, and neither store re-reads the env after that. Langfuse will"; \
	  echo "  crash-loop on P1000 for as long as this holds, and the traces stay unreadable."; \
	  echo "  Realign the store to the env (keeps every trace, drops no volume):"; \
	  echo "      make obs-realign"; \
	  exit 1; \
	fi; \
	if [ -n "$$unseen" ]; then \
	  echo "[obs-verify] [CANNOT SAY] not running, so not asked:$$unseen"; \
	  exit 2; \
	fi

# The declared repair `obs-verify` names. Deliberately NOT run by anything automatically: it
# changes a stored credential, and a store that silently rewrites itself to match whatever the
# caller brought is not a store you can trust. It drops no volume — the traces survive.
obs-realign:
	@env_file="$(OBS_ENV_FILE)"; \
	case "$$env_file" in /*) ;; *) env_file="./$$env_file" ;; esac; \
	if [ -f "$$env_file" ]; then set -a; . "$$env_file"; set +a; fi; \
	[ -n "$$TESSERA_OBS_LANGFUSE_DB_PASSWORD" ] || { \
	  echo "[obs-realign] [CANNOT SAY] no TESSERA_OBS_LANGFUSE_DB_PASSWORD — nothing to align to."; \
	  exit 2; }; \
	printf 'ALTER USER langfuse WITH PASSWORD :pw;\n' \
	  | docker exec -i tessera-claude-langfuse-db psql -U langfuse -d langfuse \
	      -v pw="'$$TESSERA_OBS_LANGFUSE_DB_PASSWORD'" \
	  || { echo "[obs-realign] [NOT OK] postgres refused the ALTER."; exit 1; }; \
	echo "[obs-realign] postgres role realigned. Restarting the containers that were refused:"; \
	docker restart tessera-claude-langfuse tessera-claude-langfuse-worker >/dev/null; \
	echo "  now run \`make obs-verify\` — this command does not grade itself."

obs-up: obs-guard
	$(OBS_COMPOSE) up -d
	@$(MAKE) --no-print-directory obs-wait
	@$(MAKE) --no-print-directory obs-verify

obs-up-core: obs-guard
	$(OBS_COMPOSE) up -d otel-collector phoenix prometheus grafana

# `up -d` returns when the containers are CREATED, not when the stores answer. Without this the
# verify above would read a starting database and report a divergence that is only a stopwatch.
obs-wait:
	@for i in $$(seq 1 60); do \
	  ok=1; \
	  for c in tessera-claude-langfuse-db tessera-claude-clickhouse; do \
	    [ -n "$$(docker ps -q -f name="^$$c$$" -f health=healthy)" ] || ok=0; \
	  done; \
	  [ "$$ok" = 1 ] && exit 0; \
	  sleep 2; \
	done; \
	echo "[obs-wait] the stores did not become healthy in 120s — verifying anyway."

obs-down:
	$(OBS_COMPOSE) down

obs-logs:
	$(OBS_COMPOSE) logs -f otel-collector phoenix prometheus grafana

# ── Trace retention: bound what grows without bound ─────────────────────────
#
# Measured 2026-08-14, after the operator asked "why 2 million rows?": the trace
# store had **no TTL at all**, while Prometheus next door already kept 15 days.
# ~140 000 traces land per DAY and almost none of them are conversations — the
# top operations are `store.read prometheus.instant`, `store.read
# business_events.rows`, `store.read audit_ledger.head_seq`: the platform
# instrumenting its own reads. Two months had accumulated 2.06 M traces and
# 2.44 M observations.
#
# TWO DECISIONS, measured rather than assumed:
#
#  · **15 days, to match Prometheus.** Two observability stores with different
#    memories make every cross-reading beyond the shorter one silently wrong.
#  · **`scores` is EXCLUDED.** All 2 435 of them are older than 15 days, so a
#    uniform TTL would have deleted 100 % of the judged signal to reclaim 25 %
#    of the noise — and they weigh 172 KiB. Retention bounds what grows without
#    bound; it must not erase what is rare and expensive to reproduce.
#
# Retention lives in the STORE, never in the view — this repo learned that from
# the GDPR purge that filtered at read time while the rows lived on for ever
# (docs/status/overnight-security-run.md, A5). Idempotent, so it is safe to
# re-run, and it MUST be re-run after any Langfuse migration that rewrites the
# schema; `make obs-retention CHECK=1` asks without writing.
#
# Verdicts: 0 = TTL in place · 1 = missing/refused · 2 = CANNOT SAY (blind).
OBS_TRACE_RETENTION_DAYS ?= 15
obs-retention:
	@ch="tessera-claude-clickhouse"; days="$(OBS_TRACE_RETENTION_DAYS)"; \
	if ! docker info >/dev/null 2>&1; then \
	  echo "[obs-retention] [CANNOT SAY] docker is not answering — no TTL was read or written."; \
	  exit 2; \
	fi; \
	if [ -z "$$(docker ps -q -f name="^$$ch$$")" ]; then \
	  echo "[obs-retention] [CANNOT SAY] $$ch is not running — the store could not be asked."; \
	  exit 2; \
	fi; \
	if [ -z "$(CHECK)" ]; then \
	  docker exec "$$ch" clickhouse-client -q \
	    "ALTER TABLE default.traces MODIFY TTL toDateTime(timestamp) + INTERVAL $$days DAY" || exit 1; \
	  docker exec "$$ch" clickhouse-client -q \
	    "ALTER TABLE default.observations MODIFY TTL toDateTime(start_time) + INTERVAL $$days DAY" || exit 1; \
	fi; \
	missing=""; \
	for t in traces observations; do \
	  ttl=$$(docker exec "$$ch" clickhouse-client -q \
	    "SELECT extractAll(create_table_query, 'toIntervalDay\\(([0-9]+)\\)')[1] FROM system.tables WHERE database='default' AND name='$$t'" 2>/dev/null); \
	  if [ -z "$$ttl" ]; then missing="$$missing $$t"; \
	  else echo "[obs-retention] [OK] default.$$t keeps $$ttl days."; fi; \
	done; \
	scored=$$(docker exec "$$ch" clickhouse-client -q \
	  "SELECT position(create_table_query, ' TTL ') FROM system.tables WHERE database='default' AND name='scores'" 2>/dev/null); \
	if [ -z "$$scored" ]; then \
	  echo "[obs-retention] [CANNOT SAY] default.scores could not be read — its TTL is unknown."; \
	  exit 2; \
	fi; \
	if [ "$$scored" != "0" ]; then \
	  echo "[obs-retention] [REFUSED] default.scores carries a TTL — the judged signal must not expire."; \
	  exit 1; \
	fi; \
	echo "[obs-retention] [OK] default.scores has no TTL, deliberately: it is the judged signal, not the volume."; \
	if [ -n "$$missing" ]; then \
	  echo "[obs-retention] [MISSING]$$missing — re-run 'make obs-retention' (a Langfuse migration may have rewritten the schema)."; \
	  exit 1; \
	fi

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

.PHONY: dev-up dev-down dev-status dev-preview preflight image-preflight \
        fulllocal-up fulllocal-down fulllocal-status fulllocal-tunnel fulllocal-tunnel-down \
        responsive-check \
        deploy-diff served-check

# Start backend + frontend from THIS checkout, detached; wait for health.
dev-up: dev-secrets
	@echo "▶ dev-up from $(CURDIR) (git $$(git rev-parse --short HEAD 2>/dev/null)) — front :$(DEV_FPORT) / back :$(DEV_BPORT) / metrics :$(DEV_MPORT)"
	@# The refusal must NAME what holds the port. It used to say "'make dev-down' first" for
	@# any holder, including a container — and dev-down then killed Docker (see dev-down).
	@for p in $(DEV_FPORT) $(DEV_BPORT) $(DEV_MPORT); do \
	  pid=$$(lsof -nP -tiTCP:$$p -sTCP:LISTEN 2>/dev/null | head -1); \
	  [ -z "$$pid" ] && continue; \
	  comm=$$(ps -o comm= -p $$pid 2>/dev/null | sed 's|.*/||'); \
	  if echo "$$comm" | grep -Eq '^($(_DEV_KILLABLE))$$'; then \
	    echo "✗ port $$p held by a dev server ($$pid $$comm) — 'make dev-down' first"; \
	  else \
	    echo "✗ port $$p held by $$pid ($$comm), which is NOT a dev server."; \
	    echo "  Probably the container stack; stop it with docker compose, or use dev-preview PORT=…"; \
	  fi; \
	  exit 1; \
	done; true
	@# The app-side ClickHouse READER drinks from the same canonical file as the stack it reads.
	@# Found live (2026-07-15): the F-9 rotation secured the containers, and nobody taught the
	@# backend the new password — its adapter fell back to the default and every ClickHouse-backed
	@# read answered 403 (three postures "indisponible", five naked-500 routes). Absent file ⇒
	@# defaults, unchanged (a fresh clone without an obs stack still boots).
	@echo "  backend  → $(DEV_BACKEND_LOG)"; \
	  obs_env="$(OBS_ENV_FILE)"; \
	  if [ ! -f "$$obs_env" ]; then \
	    case "$$obs_env" in \
	      /*) ;; \
	      *) common_dir=$$(git rev-parse --git-common-dir 2>/dev/null || true); \
	         case "$$common_dir" in /*) ;; *) common_dir="$(CURDIR)/$$common_dir" ;; esac; \
	         primary_obs_env="$$(dirname "$$common_dir")/$$obs_env"; \
	         if [ -f "$$primary_obs_env" ]; then obs_env="$$primary_obs_env"; fi ;; \
	    esac; \
	  fi; \
	  if [ -f "$$obs_env" ]; then \
	    case "$$obs_env" in /*) ;; *) obs_env="$(CURDIR)/$$obs_env" ;; esac; \
	    obs_ch_pw=$$(. "$$obs_env" && printf %s "$$TESSERA_OBS_CLICKHOUSE_PASSWORD"); \
	    export TESSERA_CLICKHOUSE_PASSWORD="$${TESSERA_CLICKHOUSE_PASSWORD:-$$obs_ch_pw}"; \
	  fi; \
	  TESSERA_API__PORT=$(DEV_BPORT) TESSERA_OBS_METRICS_PORT=$(DEV_MPORT) nohup $(_SETSID) uv run python scripts/run_local.py >$(DEV_BACKEND_LOG) 2>&1 </dev/null &
	@echo "  frontend → $(DEV_FRONT_LOG)"; cd webapp/frontend && PORT=$(DEV_FPORT) TESSERA_BACKEND_URL=http://localhost:$(DEV_BPORT) nohup $(_SETSID) corepack pnpm dev >$(DEV_FRONT_LOG) 2>&1 </dev/null &
	@printf "  backend :$(DEV_BPORT)/healthz … "; curl -sf --retry 60 --retry-connrefused --retry-delay 1 --max-time 120 http://localhost:$(DEV_BPORT)/healthz >/dev/null && echo ok || { echo "FAIL (see $(DEV_BACKEND_LOG))"; exit 1; }
	@printf "  frontend :$(DEV_FPORT)/api/healthz … "; curl -sf --retry 90 --retry-connrefused --retry-delay 1 --max-time 240 http://localhost:$(DEV_FPORT)/api/healthz >/dev/null && echo ok || { echo "FAIL (see $(DEV_FRONT_LOG))"; exit 1; }
	@$(MAKE) --no-print-directory dev-status

# Stop the dev servers on DEV_FPORT/DEV_BPORT/DEV_MPORT (graceful, then hard).
#
# IT KILLS A DEV SERVER, OR IT KILLS NOTHING (audit 2026-08-03, P0). :8099 is ALSO the host
# port the agent CONTAINER publishes, so on a machine running the full-local stack the pid
# holding it is `com.docker.backend`. This target therefore sent SIGTERM then SIGKILL to
# Docker Desktop itself, taking down the agent, the frontend, Postgres, Redis, the whole
# observability stack — and `tessera-cloudflared`, which is the public domain. It had already
# happened once (2026-08-02) and been written down as a trap to remember. A trap you have to
# remember is a defect you have not fixed.
#
# Worse, `dev-up` refuses on a busy port with the message "'make dev-down' first": the guard
# pointed the operator straight at the destructive command.
#
# So the pid is interrogated before it is signalled. A port is not a licence to kill whatever
# sits behind it — the only processes this target may end are ones it could have started.
# `next-server` renames its own process, and `ps -o comm=` reports the renamed title:
# `next-server (v15.0.4)`, with a space and a version. Anchored with `$$`, the entry
# `next-server` matched none of it, so `dev-up` started a frontend `dev-down` could not stop —
# twice in one session, each time leaving the port held and the next `dev-preview` refused.
# `[ (]*` absorbs the suffix without loosening the anchor into a prefix match.
_DEV_KILLABLE = node|next-server[ (].*|next-server|python|python3|uvicorn|uv|pnpm|npm|corepack|perl
dev-down:
	@for p in $(DEV_FPORT) $(DEV_BPORT) $(DEV_MPORT); do \
	  pids=$$(lsof -nP -tiTCP:$$p -sTCP:LISTEN 2>/dev/null); \
	  if [ -z "$$pids" ]; then echo "  :$$p free"; continue; fi; \
	  for pid in $$pids; do \
	    comm=$$(ps -o comm= -p $$pid 2>/dev/null | sed 's|.*/||'); \
	    if echo "$$comm" | grep -Eq '^($(_DEV_KILLABLE))$$'; then \
	      echo "  SIGTERM :$$p $$pid ($$comm)"; kill $$pid 2>/dev/null || true; \
	    else \
	      echo "  ✗ REFUSED :$$p $$pid ($$comm) — not a dev server, dev-down leaves it alone"; \
	      echo "    (if a container publishes this port, stop it with docker compose, never here)"; \
	      echo "    NOTE: this names a POSSIBILITY, not a finding — nothing here asked Docker."; \
	    fi; \
	  done; \
	done; true
	@perl -e 'select(undef,undef,undef,1.5)'
	@for p in $(DEV_FPORT) $(DEV_BPORT) $(DEV_MPORT); do \
	  for pid in $$(lsof -nP -tiTCP:$$p -sTCP:LISTEN 2>/dev/null); do \
	    comm=$$(ps -o comm= -p $$pid 2>/dev/null | sed 's|.*/||'); \
	    if echo "$$comm" | grep -Eq '^($(_DEV_KILLABLE))$$'; then \
	      echo "  SIGKILL :$$p $$pid ($$comm)"; kill -9 $$pid 2>/dev/null || true; \
	    fi; \
	  done; \
	done; true
	@echo "✓ dev-down: dev servers on :$(DEV_FPORT) :$(DEV_BPORT) :$(DEV_MPORT) stopped (foreign holders untouched)"

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

# ── Preflight: assert every declared input, or refuse loudly (ADR 0026, ADR 0043) ─
#
# Three cutover regressions each hid a missing container input behind a silent
# {available:false} — the eval package, the eval/reports archive, the operator key —
# discovered by the operator page by page instead of refused at boot. `tessera-preflight`
# turns every such hole into ONE loud, checked verdict whose EXIT CODE is the answer
# (0 clear · 1 a FAIL · 2 a BLIND spot the witness could not see, never "ok"). It
# interrogates the thing itself (ADR 0026): the eval loader the dashboards call, psycopg,
# the ClickHouse / Prometheus / Ollama clients — never a neighbouring proxy.
#
# `preflight` runs the FULL witness inside the running cutover container, so it sees the
# container's real DSN, joined networks, mounts and env — the check to run after `up`
# and before trusting a smoke-test. `HTTP=<base>` also probes a server's health routes.
#
# ⚠ The 0/1/2 above is the WITNESS's; `make preflight` answers 0 or 2, because make exits 2 on
# any failed recipe. A FAIL and a BLIND spot arrive here as the same number. Read the printed
# verdict, or `docker exec … tessera-preflight` directly when the code is what you need.
preflight:
	@docker exec tessera-$(or $(TESSERA_ENV),local)-agent tessera-preflight $(if $(HTTP),--http $(HTTP),)

# `image-preflight` is the CI-time witness: it BUILDS the agent image and runs the
# image-only checks (eval package imports, seed reports load, app factory builds) in a
# throwaway container with no external services — exactly the class the gate could not
# see, so a dropped `COPY eval` or a dockerignored seed is caught at build, not cutover.
image-preflight:
	@docker build -f infra/docker/Dockerfile.agent -t tessera-agent:preflight .
	@docker run --rm --entrypoint tessera-preflight tessera-agent:preflight --image-only

# ── Full-local (front co-located with the agent, on-prem) ────────────────────
#
# ADR 0045 / docs/runbook-full-local.md. Runs the Next.js front in a container NEXT TO the
# cutover agent, reaching it over the local Docker network — so the ~14 front→agent hops per
# page are LOCAL, not tunnelled. `fulllocal-up` brings up the pair on localhost ONLY, no
# tunnel. `fulllocal-tunnel` is THE FLIP (gated): it publishes the front on your domain.
FL_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.unix.yml \
	-f docker-compose.cutover.yml -f docker-compose.fulllocal.yml

# Front + agent, LOCAL only. Builds the front image, brings the pair up, waits for the front
# to report healthy. NO tunnel is started — nothing touches your domain.
#
# `--no-deps` is load-bearing: the agent's compose-declared dependency is the BASE `postgres`
# service, but the cutover agent uses the LIVE external Postgres — starting the base one clashes
# on 5432. And `TESSERA_AGENT_STATE` is REQUIRED (as for the cutover): unset, the agent's durable
# The commit an image is built FROM, as the deploy path computes it — never typed by hand.
#
# `-dirty` is not decoration. A stamp is read as "this image contains that commit", and an image
# built from a tree with uncommitted edits contains something else. Suffixing it keeps the claim
# true and, because `deploy-diff` compares strings, makes a dirty build incapable of matching a
# clean one — which is the correct verdict, not a nuisance.
BUILD_SHA := $(shell git rev-parse --short=8 HEAD 2>/dev/null || echo unknown)$(shell git diff --quiet HEAD 2>/dev/null || echo -dirty)

# The public host this deployment answers on — read from `infra/deploy/targets.yaml`, which
# already owns it, and handed to the agent as the address of its thirteenth probed component
# (ADR 0052 §Amendment 2). The twelve others are asked over the private compose network, so all
# twelve can be green while the public URL serves 502; on 2026-08-12 they were, for 32 hours.
#
# Not baked into any image: `docker-compose.fulllocal.yml` is explicit that the same image must
# serve localhost and a domain unchanged. Not typed here either — a second copy of a hostname is
# a second thing to forget when the canonical moves, which is exactly the drift `targets.yaml`
# exists to end.
#
# Failing to EMPTY is deliberate and is not a hole: the probe then reports BLIND ("no address
# declared"), never OK. A `make` that refused to bring the stack up because a monitoring address
# would not parse would trade a missing measurement for a real outage.
PUBLIC_CANONICAL := $(shell uv run python -c "from scripts.deploy_diff import load_targets as t; c = t(); print(f'{c.canonical}.{c.domain}')" 2>/dev/null)

# volume resolves to a different default path, so compose would recreate the running agent onto
# an empty state dir. Guarded, then the already-running agent's config matches → it is untouched.
fulllocal-up:
	@test -f frontend.secret.env || { echo "missing frontend.secret.env — cp frontend.secret.env.example frontend.secret.env and fill it"; exit 2; }
	@test -n "$(TESSERA_AGENT_STATE)" || { echo "export TESSERA_AGENT_STATE=<durable state dir> first (same value as the cutover), else the agent would be recreated onto an empty volume"; exit 2; }
	@echo "▶ stamping the pair with $(BUILD_SHA)"
	@test -n "$(PUBLIC_CANONICAL)" \
	  && echo "▶ public edge watched at https://$(PUBLIC_CANONICAL)/api/version (13th component)" \
	  || echo "▶ public edge NOT declared — that row will read BLIND, never ok (targets.yaml unreadable?)"
	@TESSERA_BUILD_SHA=$(BUILD_SHA) TESSERA_BUILD_TIME=$$(date -u +%Y-%m-%dT%H:%M:%SZ) \
	  $(FL_COMPOSE) --profile full build agent frontend
	@TESSERA_STACK_PUBLIC_CANONICAL=$(PUBLIC_CANONICAL) \
	  TESSERA_STACK_UI_PUBLIC_CANONICAL=$(if $(PUBLIC_CANONICAL),https://$(PUBLIC_CANONICAL),) \
	  $(FL_COMPOSE) --profile full up -d --no-deps agent frontend
	@printf 'waiting for the front to report healthy'; \
	for i in $$(seq 1 40); do \
	  st=$$(docker inspect -f '{{.State.Health.Status}}' tessera-$(or $(TESSERA_ENV),local)-frontend 2>/dev/null); \
	  [ "$$st" = "healthy" ] && { echo " OK"; break; }; \
	  printf '.'; sleep 3; \
	done
	@echo "front (LOCAL, no tunnel): http://localhost:$${TESSERA_FRONTEND_PORT:-3090}  →  agent: http://agent:8080"
	@echo "validate it, set real operator passwords, THEN 'make fulllocal-tunnel' when ready to flip."

# Stop the front (and the tunnel if running). Leaves the AGENT up — it is the shared
# reference, managed independently. Add AGENT=1 to also stop the agent.
fulllocal-down:
	@$(FL_COMPOSE) --profile full --profile flip rm -sf frontend cloudflared 2>/dev/null || true
	@if [ -n "$(AGENT)" ]; then $(FL_COMPOSE) rm -sf agent; fi
	@echo "front + tunnel stopped$(if $(AGENT), + agent stopped,)."

fulllocal-status:
	@echo "front : $$(docker inspect -f '{{.State.Health.Status}}' tessera-$(or $(TESSERA_ENV),local)-frontend 2>/dev/null || echo 'not running') · http://localhost:$${TESSERA_FRONTEND_PORT:-3090}"
	@echo "agent : $$(docker inspect -f '{{.State.Health.Status}}' tessera-$(or $(TESSERA_ENV),local)-agent 2>/dev/null || echo 'not running') · workers=$$(docker exec tessera-$(or $(TESSERA_ENV),local)-agent printenv TESSERA_API__WORKERS 2>/dev/null || echo '?')"
	@echo "tunnel: $$(docker inspect -f '{{.State.Status}}' tessera-cloudflared 2>/dev/null || echo 'not running (domain not flipped)')"
	@# "healthy" answers whether the container is UP, never whether it runs THIS commit — and a
	@# status that says healthy over a stack three commits stale is how landing without rebuilding
	@# stays invisible (ADR 0051). Non-gating here: the verdict is printed, the exit code belongs
	@# to `make served-check`.
	@uv run python scripts/served_check.py --url http://localhost:$${TESSERA_FRONTEND_PORT:-3090} || true

# THE DESCENT — does the cockpit still work on a smaller screen?
#
# NOT in `make gate`, and the reason is the gate's own doctrine rather than laziness:
# this needs a SERVED build, and a check that silently passes when nothing is
# listening is worse than no check. So it refuses instead — a witness that cannot
# look may never report "ok" (ADR 0026). Point it at whatever is running:
#
#   make responsive-check                          # the full-local front on :3090
#   RESP_URL=http://localhost:3097 make responsive-check
#
# It asks ONE question over 19 cockpit routes × 4 widths (14", small laptop, tablet,
# phone): is there content cut off with no way to reach it? And it tests its own
# detector on every run, because "0 findings" and "the query stopped matching" are
# otherwise the same sentence.
responsive-check:
	@url="$(or $(RESP_URL),http://localhost:3090)"; \
	code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$$url/fr/login" 2>/dev/null); \
	if [ "$$code" != "200" ]; then \
	  echo "[responsive] CANNOT LOOK — nothing serving $$url (got $$code)."; \
	  echo "[responsive] start one first: TESSERA_AGENT_STATE=\$$PWD/.agent-state make fulllocal-up"; \
	  exit 2; \
	fi; \
	echo "[responsive] looking at $$url"; \
	cd webapp/frontend && E2E_BASE_URL="$$url" npx playwright test e2e/responsive-descent.spec.ts --reporter=line

# THE FLIP — publishes the local front on your domain via the Cloudflare Tunnel. GATED:
# run ONLY when you have validated locally, set real operator passwords, created the tunnel
# in the Cloudflare dashboard (hostname → http://frontend:3000) and put its token in
# infra/docker/fulllocal.env. Reversible with `make fulllocal-tunnel-down`.
#
# BOTH profiles are activated: `cloudflared` (profile `flip`) declares `depends_on: frontend`,
# and `frontend` lives in profile `full` — with only `--profile flip`, compose rejects the
# project ("service cloudflared depends on undefined service frontend"). `--no-deps` still keeps
# it from starting/restarting the front; the `full` profile only makes it DEFINED so the
# dependency resolves. Same reason on `-down`.
fulllocal-tunnel:
	@test -f infra/docker/fulllocal.env || { echo "missing infra/docker/fulllocal.env — cp infra/docker/fulllocal.env.example infra/docker/fulllocal.env and set TUNNEL_TOKEN"; exit 2; }
	@echo "FLIP: publishing the local front on your domain via Cloudflare Tunnel."
	@$(FL_COMPOSE) --profile full --profile flip up -d --no-deps cloudflared
	@echo "tunnel up. Verify your domain serves, then it is live. Rollback: make fulllocal-tunnel-down"

# Rollback the flip: stop the tunnel. The domain stops resolving to this front (point DNS
# back to Cloud Run / the previous target as needed).
fulllocal-tunnel-down:
	@$(FL_COMPOSE) --profile full --profile flip rm -sf cloudflared 2>/dev/null || true
	@echo "tunnel stopped — the domain no longer resolves to the local front."

# Anti-divergence witness (ADR 0048): fetch /api/version on every host declared in
# infra/deploy/targets.yaml (the two targets + the canonical) and REFUSE if the served build
# SHAs differ. The SCRIPT exits 0 = match · 1 = divergent · 2 = blind (unreachable / un-stamped /
# domain unset). Through make, 1 and 2 both surface as 2 — see the note on `served-check` below;
# read the printed line, or call `scripts/deploy_diff.py` when the number is what you need.
deploy-diff:
	@uv run python scripts/deploy_diff.py

# Staleness witness (ADR 0051): does the RUNNING stack serve what this checkout has landed?
#
# `deploy-diff` asks whether the two targets agree with EACH OTHER — and two hosts three commits
# stale agree perfectly. This asks the stack about the thing instead of about its neighbour:
# `/api/version` names the served commit, `infra/deploy/served-surfaces.yaml` says which paths
# are baked into the image and which are bind-mounted live, and every file changed since is
# classified. The SCRIPT exits 0 = the stack serves this commit (or only unserved paths moved) ·
# 1 = REFUSED, baked code is stale and/or mounted data has already moved under it (the chimera
# that put the cockpit into `CannotSay`: fresh reports, frozen grader) · 2 = blind (nothing
# serving, or the stack cannot name its commit).
#
# ⚠ THROUGH MAKE, THAT TRI-STATE IS GONE. Measured, not assumed (GNU Make 3.81, and it is in the
# manual): make exits **2 on any failed recipe** — a recipe exiting 1, 2 or 4 all leave make at 2.
# So `make served-check` answers 0 or 2, and "REFUSED" and "blind" are the same code. They are
# opposite instructions — rebuild the image, versus go find out why nothing answered — and only
# the printed line tells them apart. A caller that wants the verdict as a NUMBER must run the
# script: `uv run python scripts/served_check.py [--url …]`. See
# `tests/unit/test_make_flattens_exit_codes.py`, which measures it rather than trusting this note.
#
# Point it anywhere: SERVED_URL=https://tessera.<domain> make served-check
served-check:
	@uv run python scripts/served_check.py $(if $(SERVED_URL),--url $(SERVED_URL),)

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
	@echo "  eval               Full 63-case regression harness"
	@echo "  eval-case CASE=XX  One case by id"
	@echo "  eval-lang LANG=fr  One language slice"
	@echo ""
	@echo "Corpus"
	@echo "  generate-corpus    Re-generate product JSON pages"
	@echo "  ingest-regulations Ingest EU regulatory corpus into pgvector"
	@echo "  seed               Ingest product corpus into pgvector"
	@echo "  reindex-embeddings Dry-run/repair legacy embedding provenance (ARGS=...)"
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
