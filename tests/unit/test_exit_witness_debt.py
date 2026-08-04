"""The surface the whole doctrine was born on — and the one nothing was watching.

`tests/unit/test_verdict_debt.py` froze the witnesses that publish a verdict as a bare ``bool``.
It is honest about what it scans and it says so, but what it scans is an **AST annotation**, and
a verdict does not have to be a Python return value. It can be a dict with an ``ok`` key. It can
be the string ``"PASS"``. It can be ``None``-and-raise.

**And it can be an exit code — which is what it was, the first time.**

The origin instance of [ADR 0026](../../docs/decisions/0026-a-witness-interrogates-the-thing.md)
is ``git merge 2>&1 | tail -1``: a pipeline whose exit code came from ``tail``, printing
``Updating a..b`` on stdout while the error went to stderr, and ``$PIPESTATUS[0]`` — **empty in
zsh** — quietly agreeing. Two gates read green over a failed merge. Every ``make`` target, every
script, every CI step in this repository is that same shape: *a witness whose entire verdict is a
number nobody looks at*. There were 110 of them and not one was registered.

So this is the exit-code registry, built the same way and for the same reason as its ``bool``
sibling: **complete, two-sided-frozen, and classified by hand.**

Mechanical (airtight):
    Every target in the ``Makefile``, every file in ``scripts/``, every job in
    ``.github/workflows/*.yml`` is enumerated from the artefact itself and must appear below. A new
    one cannot be added without its author writing down what kind of thing it is, and one that is
    deleted cannot rot here. A set that may only shrink is a ratchet; a set that may grow is a wish.

A judgement (recorded per entry, never hidden in a heuristic):
    ``VERDICT``   — its exit code decides whether something PASSES, and **the code is its own**:
                    not laundered through a pipe or a trailing ``echo``, and a blind spot cannot
                    read as ``0``.
    ``OWED``      — a VERDICT that **cannot fail for the reason it exists**, or cannot tell "I
                    looked and it is fine" from "I could not look". **This is the debt.**
    ``delegate``  — a thin shim over a registered script or target. It launders nothing and judges
                    nothing of its own; *the witness is the thing it calls*, and that thing is
                    registered separately. Counting both would inflate the debt with shims.
    ``action``    — it changes the world (install, seed, run, deploy). Its exit code reports the
                    action, not a judgement about the code.
    ``report``    — it prints. It judges nothing and claims nothing.

When a call is genuinely close it is counted as a VERDICT, and a VERDICT that smells is counted as
OWED. The asymmetry is the same one the `bool` registry states: over-counting costs a migration
nobody needed, under-counting hides a hole.

.. rubric:: What was FOUND OPEN while this was being written — and fixed, not filed

Three of these were live false greens, measured, not reasoned about. They are not in the debt
below, because a hole you have just watched swallow a verdict does not get *filed*:

* **``make ledger-backup`` could not fail.** Against a container that does not exist it printed
  ``✓``, exited **0**, and wrote a SHA-256-notarised archive of **zero bytes**. Three laundered
  codes on one line: a ``pg_dump | gzip`` pipeline (exit = ``gzip``'s, and gzip compresses nothing
  with complete success), a ``;``-chain with no ``set -e``, and a closing ``echo``. The backup of
  the audit ledger — *the opposable memory* — was structurally incapable of returning non-zero.
  Now: `scripts/ledger_backup.py`, which reopens the archive it wrote and requires the ledger's own
  ``COPY`` header to be in it.
* **``make eval-null`` graded a report from a previous run.** With ``run_eval.py`` replaced by
  ``raise SystemExit("BOOM")``, the ratchet found yesterday's report still on disk, printed
  ``[ratchet PASS] 122/174``, and the target — *a per-push CI gate* — exited **0** with a harness
  that could not start. CI never saw it: a fresh checkout has no stale report, so CI's immunity was
  an accident of the runner being clean.
* **``make dev-status`` exited 0 on ``STALE`` and on ``CANNOT SAY``.** The witness ADR 0026 *itself*
  built, printing the exact verdict it was written to publish and then telling its caller — in the
  one channel a Makefile can hear — **ok**. The doctrine had been implemented in the rendering and
  forgotten in the exit code, which is to say forgotten on the surface it was born on.

.. rubric:: And one that is still open, and is not ours to close

``.github/workflows/supply-chain.yml``'s ``detect-secrets`` job ran ``detect-secrets scan >
/dev/null`` because ``.secrets.baseline`` does not exist — a command that **exits 0 whatever it
finds**, with its output thrown away. A permanently-green job that checked nothing. The Makefile's
own comment (``gate-py``) cites this exact failure, by its audit id, as a lesson already learned:
*"F-14: detect-secrets with no baseline was a permanently-green job that checked nothing"*. The
lesson was written down and the job was never fixed. It is fixed here — the missing baseline is now
a **blind spot**, and a blind spot does not get to pass.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import yaml

_ROOT: Final = Path(__file__).resolve().parents[2]
_MAKEFILE: Final = _ROOT / "Makefile"
_SCRIPTS: Final = _ROOT / "scripts"
_WORKFLOWS: Final = _ROOT / ".github" / "workflows"

#: A FOURTH surface, added 2026-07-13 with the trunk guard. A git hook's exit code *aborts a ref
#: transaction* — it is an exit-code witness by the purest definition, and it was about to be an
#: **unregistered** one, which is the exact hole this registry exists to close. The surface is
#: scanned, not the file: a second hook added tomorrow cannot slip in unclassified.
_HOOKS: Final = _ROOT / ".githooks"

#: Every exit-code witness in the three surfaces, and what kind of thing it is.
#: Keys are the artefact's own names: ``Makefile::<target>``, ``scripts/<file>``,
#: ``.github/workflows/<file>::<job>``.
_EXIT_WITNESSES: dict[str, str] = {
    # ══ Makefile ═══════════════════════════════════════════════════════════════════════════════
    # ── the gate: the only witness this project has, CI being billing-blocked ──────────────────
    "Makefile::gate": "VERDICT",
    "Makefile::gate-twice": "VERDICT",
    "Makefile::gate-checks": "VERDICT",
    "Makefile::gate-py": "VERDICT",
    "Makefile::gate-web": "VERDICT",
    "Makefile::check": "VERDICT",
    "Makefile::ci": "VERDICT",
    "Makefile::memory-check": "VERDICT",
    "Makefile::precommit": "VERDICT",
    # ── quality: each is one tool's own exit code, unpiped ─────────────────────────────────────
    "Makefile::lint": "VERDICT",
    "Makefile::format-check": "VERDICT",
    "Makefile::typecheck": "VERDICT",
    "Makefile::test": "VERDICT",
    "Makefile::test-all": "VERDICT",
    "Makefile::coverage": "VERDICT",
    # `pytest` exits 0 when EVERY test skips. With no Postgres and no ClickHouse this target is
    # green having run nothing — the one condition it exists to detect is the one it reads as a
    # pass. Needs `--strict-markers` + an all-skipped guard, or a collected-count assertion.
    "Makefile::test-integration": "OWED",
    # ── the eval harness ───────────────────────────────────────────────────────────────────────
    "Makefile::eval-null": "VERDICT",  # fixed: it now grades only what THIS run produced
    "Makefile::eval": "delegate",  # → scripts/run_eval.py
    "Makefile::eval-contribution": "delegate",  # → scripts/check_contribution.py
    "Makefile::eval-null-write": "action",  # it WRITES the baseline; that is not a judgement
    "Makefile::eval-power": "delegate",  # → scripts/check_discrimination.py
    "Makefile::eval-power-write": "action",  # it RE-MEASURES and writes; that is not a judgement
    "Makefile::eval-noise": "action",  # it produces passes (a GPU-hour); it judges nothing
    "Makefile::eval-sweep": "action",
    "Makefile::eval-calibrate-weak": "action",
    "Makefile::eval-case": "action",
    "Makefile::eval-lang": "action",
    "Makefile::eval-demo": "action",
    # ── the trunk. `main` FORKED on 2026-07-13 because nobody fetched, and "one agent touches
    #    main" is a SOCIAL rule — which has now failed to stop every instance in this repo's
    #    history of a green light over a hole. So it is mechanical. ─────────────────────────────
    "Makefile::hooks": "action",  # installs core.hooksPath; wired into `install`
    "Makefile::land": "action",  # it ADVANCES the trunk. Its verdict is scripts/main_guard.py's
    # `gate` and `claim` open by asking main_guard.py whether the trunk is guarded — a question
    # that CANNOT BE ASKED when the tool asking it is absent. It was absent: the hook was on
    # `main`, its tool was on an unlanded branch, and the guard refused every advance of the trunk
    # including the branch that would fix it. In that state `make gate` refused with `python3:
    # can't open file` — non-zero, and RIGHT BY ACCIDENT: no verdict, nothing named, no repair.
    # Now it is a CannotSay with the exact command. Honest from birth, so the debt does not move.
    "Makefile::tooling": "VERDICT",
    # ── the ledger ─────────────────────────────────────────────────────────────────────────────
    "Makefile::ledger-backup": "delegate",  # → scripts/ledger_backup.py  (was a live false green)
    "Makefile::ledger-restore-drill": "delegate",  # → scripts/ledger_restore_drill.py
    "Makefile::ledger-reset": "delegate",  # → scripts/ledger_reset.py
    # ── worktree ownership: all four publish a Verdict and exit 2 on a refusal ──────────────────
    "Makefile::claim": "delegate",  # → scripts/worktree_owner.py
    "Makefile::release": "delegate",
    "Makefile::whoowns": "delegate",
    "Makefile::session": "delegate",
    "Makefile::landed": "delegate",  # → scripts/landed.py
    "Makefile::dev-status": "delegate",  # → scripts/dev_status.py  (was a live false green)
    # ── actions: they change the world. Their exit code reports the ACT, not a judgement. ──────
    "Makefile::install": "action",
    "Makefile::install-all": "action",
    "Makefile::format": "action",
    "Makefile::lint-fix": "action",
    "Makefile::bootstrap": "action",
    "Makefile::seed": "action",
    "Makefile::seed-fixture": "action",
    "Makefile::generate-corpus": "action",
    "Makefile::ingest-regulations": "action",
    "Makefile::reindex-embeddings": "delegate",  # → scripts/reindex_embeddings.py
    "Makefile::run": "action",
    "Makefile::run-on-prem": "action",
    "Makefile::dev-up": "action",
    "Makefile::dev-down": "action",
    "Makefile::dev-preview": "action",
    "Makefile::dev-secrets": "action",
    # ── full-local (ADR 0045): they start/stop containers, they do not judge a test. The exit 2
    #    in `-up`/`-tunnel` is a missing-precondition REFUSAL (no frontend.secret.env /
    #    fulllocal.env), the same shape dev-up has, not a pass/fail verdict. `-tunnel` is THE FLIP
    #    (starts the tunnel); it is gated and reversible, an act. `-status` only prints.
    "Makefile::fulllocal-up": "action",
    "Makefile::fulllocal-down": "action",
    "Makefile::fulllocal-tunnel": "action",
    "Makefile::fulllocal-tunnel-down": "action",
    "Makefile::fulllocal-status": "report",
    # responsive-check (2026-08-01): 19 cockpit routes x 4 widths, asking whether any content
    # is cut off with no way to reach it. Its exit code IS the verdict, and it can report the
    # failure it exists to detect: `npx playwright test` is the LAST command in the recipe, so
    # its non-zero reaches make unlaundered — nothing pipes it, nothing swallows it. The two
    # ways it could have gone falsely green are both closed. It needs a SERVED build, so a
    # missing server would make every page load fail into some other error; instead it probes
    # `/fr/login` first and REFUSES with exit 2 rather than run blind — a witness that cannot
    # look may never say "ok" (ADR 0026). And "no findings" could have meant "the query stopped
    # matching", which is exactly how the first version of this probe certified eight widths
    # over a visibly broken phone layout; so the spec's first test injects three known nodes
    # (clipped / scrollable / ellipsed) and fails unless the detector separates them.
    # Deliberately NOT in `make gate`: the gate must not depend on something being up.
    "Makefile::responsive-check": "VERDICT",
    # deploy-diff (ADR 0048): fetches /api/version on every declared host and refuses on a SHA
    # mismatch. A thin shim over the script whose exit code IS the verdict.
    "Makefile::deploy-diff": "delegate",  # → scripts/deploy_diff.py
    # ── preflight: assert every declared container input, or refuse (ADR 0043) ─────────────────
    # Its exit code IS the verdict (0 clear / 1 FAIL / 2 BLIND), passed through unlaundered:
    # `docker exec … tessera-preflight` returns the command's OWN code, and a missing container
    # (nothing to exec) is a non-zero docker error, never a false 0.
    "Makefile::preflight": "VERDICT",
    # `docker build …` then `docker run … tessera-preflight --image-only`: a build regression OR a
    # failed image-only check aborts the target non-zero. Closes the gate's image blind spot.
    "Makefile::image-preflight": "VERDICT",
    "Makefile::obs-up": "action",
    "Makefile::obs-up-core": "action",
    "Makefile::obs-down": "action",
    "Makefile::obs-logs": "action",
    # The observability stack holds the LLM traces, and the LLM traces are customer conversations.
    # Every credential in it was a literal and every port was published on 0.0.0.0 — F-9, in the one
    # plane that holds the transcripts. `obs-guard` REFUSES the boot when a credential is unset, and
    # a refusal is a verdict: exit 2, naming what is missing and the command that fixes it.
    "Makefile::obs-guard": "VERDICT",
    # `obs-guard` asks whether a credential is SET. This asks the STORE whether it is ACCEPTED,
    # over TCP, from the stack's own network — the only question that can tell the two apart,
    # because the postgres image trusts its local socket and `docker exec psql` succeeds with any
    # password. Missing it cost 818 silent Langfuse restarts over fourteen hours on 2026-08-04.
    # Its verdict lives in the printed tag (OK / NOT OK / CANNOT SAY): make collapses every
    # failing recipe to exit 2, so the code only separates green from not-green.
    "Makefile::obs-verify": "VERDICT",
    # It REWRITES a stored database password to match the environment. An act, deliberately not
    # wired into anything — `obs-verify` names it in its refusal and never runs it, for the same
    # reason `obs-guard` may not depend on `obs-secrets`.
    "Makefile::obs-realign": "action",
    # It WRITES the credentials. That is an act, not a judgement — and it must never become a
    # prerequisite of the guard, or the guard would generate the very thing it demands.
    "Makefile::obs-secrets": "action",
    # `up -d` returns when containers are CREATED, not when the stores answer. This waits, so the
    # verify above judges a started database rather than a stopwatch. It reports nothing.
    "Makefile::obs-wait": "action",
    # → scripts/regrade_reports.py → eval.regrade.main
    "Makefile::eval-regrade": "delegate",
    "Makefile::help": "report",
    # ══ scripts/ ═══════════════════════════════════════════════════════════════════════════════
    # ── witnesses that publish a Verdict, or their own unlaundered code ────────────────────────
    # Fetches /api/version on every declared host and returns 0 match / 1 divergent / 2 blind
    # (unreachable, un-stamped, or domain unset). A blind witness never says ok (ADR 0026).
    # Re-derives a report's JUDGEMENTS from its recorded responses under today's criteria. It
    # returns 0 when every report was re-graded and 1 when one was REFUSED — the refusal being
    # the point: it cannot establish that no unrecorded criterion moved, so it declines rather
    # than carrying a stale verdict forward. A case a recording cannot re-ask leaves the whole
    # report unstamped, and the floor comparison then says CANNOT SAY rather than trusting a
    # mixture of two rulers.
    "scripts/regrade_reports.py": "VERDICT",
    "scripts/deploy_diff.py": "VERDICT",
    "scripts/gate_witness.py": "VERDICT",  # EXIT_VOID=3: "unusable" is not "failed"
    "scripts/worktree_owner.py": "VERDICT",  # Ok | NotOk | CannotSay
    # It asks the REMOTE (`git ls-remote`), never `refs/remotes/origin/main` — which is a
    # PHOTOGRAPH of the remote taken at your last fetch, and the last fetch is the event that
    # did not happen. Unreachable remote ⇒ CannotSay ⇒ exit 2: "probably nothing moved" is the bug.
    "scripts/main_guard.py": "VERDICT",
    # ── the fourth surface: a hook's exit code ABORTS the ref transaction ──────────────────────
    ".githooks/reference-transaction": "VERDICT",  # → scripts/main_guard.py, on refs/heads/main
    "scripts/dev_status.py": "VERDICT",  # fixed: the exit code IS the verdict now
    # check_power() returns a Verdict; `_exit_code` maps it exhaustively under assert_never, and
    # keeps 3 for CannotSay (the catalogue moved — unusable is not failed).
    "scripts/check_discrimination.py": "VERDICT",
    # It runs N passes of the catalogue and writes them to a scratch dir. It reports whether the
    # passes RAN, never whether they were good — the judging is check_discrimination.py's job.
    "scripts/measure_contribution_noise.py": "action",
    "scripts/ledger_backup.py": "VERDICT",  # new: it interrogates the artefact it wrote
    # A VERDICT with three states and it needs all three: 0 = no subject data outside the
    # active schema · 1 = there IS, and erasure cannot reach it (a compliance finding, not an
    # error) · 2 = REFUSED, the schema named is the active one. Collapsing 1 into 0 would make
    # "erasure is total" unfalsifiable, which is the condition it ran for months in.
    "scripts/purge_orphan_schema.py": "VERDICT",
    # Gates the wipe on ledger_backup.py's OWN verdict, then RE-READS the row counts to prove the
    # tables are empty — never trusts psql's exit code. Refuses a non-`_local` schema (NotOk) and a
    # missing/mismatched confirmation (CannotSay), exit 2.
    "scripts/ledger_reset.py": "VERDICT",
    "scripts/check_ratchet.py": "VERDICT",  # fixed: a missing report is a named red
    "scripts/landed.py": "VERDICT",  # EXIT_NOT_LANDED=4, distinct from a crash
    "scripts/seed_fixture.py": "VERDICT",  # --check; refuses a dump with no `vector(N)` column
    "scripts/assert_model_spoke.py": "VERDICT",
    # Interrogates one date's gating runs (the archive's tokens + the rows' own spread),
    # prints the evidence per run, deletes only under --apply. Its exit code is its own and
    # can report the failure it exists to detect: 1 = the AFTER counts diverge from what it
    # deleted, 2 = the store cannot be seen (a tool that cannot look never reports "ok").
    "scripts/purge_modelless_gating_runs.py": "VERDICT",
    "scripts/phoenix_retrieval.py": "VERDICT",  # exits 1 on zero spans
    # ── OWED: they claim a verdict and cannot deliver one ──────────────────────────────────────
    # A dead backend does not crash the runner: it completes every case, still writes
    # `model: "llama3.2:3b"` into the report, and reads a clean 70%. The exit code cannot tell
    # "52 cases failed, as designed" from "no model ever answered" — and `make eval-null` exists
    # precisely because of that. The witness is tokens; it is never the exit code.
    "scripts/run_eval.py": "OWED",
    # Discards `subprocess.run(...).returncode` entirely and derives its verdict from
    # `report.exists()` — the same stale-artefact hole `make eval-null` was just fixed for, in the
    # replay loop that decides whether a floor regression is real. NOT TOUCHED HERE: it is the
    # live `claude/eval-gate-lift` lane's file (FloorGrade.releasable → Verdict).
    "scripts/check_contribution.py": "OWED",
    # Returns a bare bit, and an exception in its `finally:` (a failing DROP DATABASE) REPLACES
    # the verdict with a traceback. Fails closed, but the verdict is destroyed rather than told.
    "scripts/ledger_restore_drill.py": "OWED",
    # Its own header: "A performance budget is a GATE, not a hope… It runs inside the twice-green
    # gate from Phase A." IT IS INVOKED FROM NOWHERE — not the Makefile, not a workflow, not
    # package.json. A gate that is never called cannot fail. The header is corrected; the wiring
    # is a lot of its own (it needs a live backend), so the debt is named rather than pretended.
    "scripts/perf-probe.mjs": "OWED",
    # ── actions: producers, seeders, backfills, generators ─────────────────────────────────────
    "scripts/run_local.py": "action",
    "scripts/run_model_sweep.py": "action",
    "scripts/bootstrap_eval_demo.py": "action",
    "scripts/compare_eval.py": "report",
    "scripts/config_inventory.py": "action",
    "scripts/consolidate_memory.py": "action",
    "scripts/probe_retrieval.py": "report",
    "scripts/reseal_audit_chain.py": "action",
    "scripts/calibrate_pan_mask.py": "action",
    "scripts/capture-ribbon.cjs": "action",
    "scripts/generate_corpus.py": "action",
    "scripts/generate_agent_enums.py": "action",
    "scripts/generate_traffic.py": "action",
    "scripts/generate_zod.py": "action",
    "scripts/ingest_regulations.py": "action",
    # Dry-run reports the exact target; --apply replaces its vectors atomically. Exit 2 refuses
    # an obsolete/unreadable plan and exit 3 reports a failed repair. Those codes describe the
    # controlled action, not whether the repository passes a quality judgement.
    "scripts/reindex_embeddings.py": "action",
    "scripts/ingest_transcript_traffic.py": "action",
    "scripts/seed_agents.py": "action",
    "scripts/seed_demo.py": "action",
    "scripts/seed_eval_waivers.py": "action",
    "scripts/backfill_agent_attribution.py": "action",
    "scripts/backfill_agent_judge.py": "action",
    "scripts/backfill_calibration.py": "action",
    "scripts/backfill_compliance_trend.py": "action",
    "scripts/backfill_judge_metrics.py": "action",
    "scripts/backfill_langfuse_traces.py": "action",
    "scripts/backfill_model_judge.py": "action",
    "scripts/backfill_owned_business_events.py": "action",
    "scripts/backfill_owned_scores.py": "action",
    # ══ .github/workflows/ ═════════════════════════════════════════════════════════════════════
    # NOTE, said once and loudly: **GitHub Actions is billing-blocked.** Every job below has been
    # failing in seconds since ~2026-07-10, so none of them is a live witness of anything today.
    # They are registered because they are what CI *will* be the day billing is restored, and a
    # laundered witness that nobody has run yet is a laundered witness.
    # Format/init/validate are blocking and their native exit codes decide whether the deployable
    # Terraform contract passes. This is a verdict, not an artefact-producing action.
    ".github/workflows/ci.yml::terraform": "VERDICT",
    ".github/workflows/ci.yml::gate": "VERDICT",
    # Builds the agent image and runs its --image-only preflight (via `make image-preflight`, no
    # drift from the laptop). Catches the Dockerfile/.dockerignore class at build — billing-blocked
    # today like every job here, registered for the day billing returns.
    ".github/workflows/ci.yml::image-preflight": "VERDICT",
    ".github/workflows/ci.yml::precommit": "VERDICT",
    # `continue-on-error: true`. 182 Playwright specs against a production build, a seeded
    # Postgres and a real backend — and the workflow's conclusion ignores every one of them. The
    # job's own header declares the flip as owed, which is honest, and it is still a witness that
    # cannot fail. The largest one in the repo.
    ".github/workflows/ci.yml::e2e": "OWED",
    ".github/workflows/eval.yml::null-control": "VERDICT",
    # `if: github.event_name == 'workflow_dispatch' && inputs.model != ''` — skipped on every push,
    # every PR and every nightly. A skipped job reports SUCCESS in the checks UI, so the workflow
    # named "Eval" is green while the model half of the eval has never run once.
    ".github/workflows/eval.yml::model-replay": "OWED",
    # `exit 0` when ClickHouse never becomes ready, and `pytest` exits 0 when every test skips. The
    # job is green with zero integration coverage — for exactly the reason it exists.
    ".github/workflows/integration.yml::integration": "OWED",
    # `|| true` on every audit command, inside a brace group whose last line is a closing ``` fence.
    # Double-laundered: a CVE reaches a human only via the job summary, and the tick is green. The
    # header declares them non-gating, and a declared non-gate is still a green tick in the UI.
    ".github/workflows/deps.yml::python": "OWED",
    ".github/workflows/deps.yml::frontend": "OWED",
    ".github/workflows/security.yml::dependency-audit": "VERDICT",
    ".github/workflows/security.yml::bandit": "VERDICT",
    ".github/workflows/security.yml::gitleaks": "VERDICT",
    ".github/workflows/security.yml::trivy-image": "VERDICT",
    ".github/workflows/security.yml::guard-policy-lint": "VERDICT",
    ".github/workflows/supply-chain.yml::detect-secrets": "VERDICT",  # fixed: no baseline ⇒ red
    ".github/workflows/supply-chain.yml::sbom": "action",
    ".github/workflows/supply-chain.yml::sign-and-provenance": "action",
    ".github/workflows/deploy.yml::build-and-deploy": "action",
}

#: How many exit-code witnesses claim a verdict and cannot deliver one.
#: **THIS MAY ONLY GO DOWN.**
#:
#: The sibling number is `OWED_BOOL_VERDICTS` (tests/unit/test_verdict_debt.py). Neither is "the
#: debt": each is the debt *of one shape*, and they say so in their names — which is the whole
#: lesson of the lot that created this file.
OWED_EXIT_WITNESSES = 10

_KINDS: Final = frozenset({"VERDICT", "OWED", "delegate", "action", "report"})

#: A make target name, at the start of a line, followed by `:` — but not by `:=` (an assignment)
#: and not starting with `.` (`.PHONY`, `.SHELLFLAGS`).
_TARGET: Final = re.compile(r"^(?P<name>[a-zA-Z0-9_][a-zA-Z0-9_.-]*):(?!=)")


def _make_targets() -> set[str]:
    """Every target in the Makefile, read from the Makefile."""
    found: set[str] = set()
    for line in _MAKEFILE.read_text(encoding="utf-8").splitlines():
        match = _TARGET.match(line)
        if match:
            found.add(f"Makefile::{match.group('name')}")
    return found


def _script_files() -> set[str]:
    """Every file in `scripts/`. Not "every file with a `__main__`" — that would be a heuristic,
    and a script that grows an entry point tomorrow must not slip in unclassified.
    """
    return {
        f"scripts/{path.name}"
        for path in _SCRIPTS.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }


def _hook_files() -> set[str]:
    """Every git hook. Its exit code ABORTS A REF TRANSACTION — it is an exit-code witness."""
    if not _HOOKS.is_dir():
        return set()
    return {
        f".githooks/{path.name}"
        for path in _HOOKS.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }


def _ci_jobs() -> set[str]:
    """Every job in every workflow, parsed from the YAML — never grepped.

    A regex over `^  \\w+:` would also match the `on:` triggers (`push`, `pull_request`, …) and
    quietly register four phantom witnesses. The jobs are a *structure*; ask the structure.
    """
    found: set[str] = set()
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in document.get("jobs") or {}:
            found.add(f".github/workflows/{path.name}::{job}")
    return found


def _all_witnesses() -> set[str]:
    return _make_targets() | _script_files() | _ci_jobs() | _hook_files()


class TestTheDebtIsANumber:
    """It is 10. It may only go down."""

    def test_the_owed_count_is_the_number_of_owed_entries(self) -> None:
        """The count IS the list, counted. A frozen number you can improve by editing the number
        is a decoration.
        """
        owed = sorted(key for key, kind in _EXIT_WITNESSES.items() if kind == "OWED")

        assert len(owed) == OWED_EXIT_WITNESSES, (
            f"the debt moved ({len(owed)} vs {OWED_EXIT_WITNESSES}):\n"
            + "\n".join(f"  {key}" for key in owed)
            + "\nIf you made one of these able to fail for the reason it exists, reclassify it and "
            "LOWER the number."
        )

    def test_the_debt_never_grows(self) -> None:
        """A new witness that cannot fail may not be born."""
        assert OWED_EXIT_WITNESSES <= 10, (
            "the debt went UP. A witness was added whose exit code cannot report the failure it "
            "exists to detect. That is not a check — it is a green light with a name."
        )


class TestTheFreeze:
    """The registry may shrink. It may not grow. That is what makes it a ratchet and not a list."""

    def test_no_exit_witness_escapes_the_registry(self) -> None:
        """**The teeth.** Every make target, every script and every CI job is classified, by hand.

        Without this the number is a decoration: a new `make audit-everything` whose recipe is
        `cmd | tee log` would simply not be in the dict, `OWED_EXIT_WITNESSES` would still read 10,
        and the ratchet would be green over a hole — which is, precisely and exactly, every
        incident in ADR 0026.

        Mutation: add a target to the Makefile, or drop a file into `scripts/`. Red, by name.
        """
        unregistered = sorted(_all_witnesses() - set(_EXIT_WITNESSES))

        assert not unregistered, (
            "these publish a verdict as an exit code and are NOT in the registry. Say what kind "
            "of thing each one is — and if it decides whether something PASSES, say whether its "
            "exit code can actually report the failure it exists to detect:\n"
            + "\n".join(f"  {key}" for key in unregistered)
        )

    def test_no_stale_entry_survives_in_the_registry(self) -> None:
        """A deleted target/script/job must be DELETED here, so the debt actually shrinks."""
        stale = sorted(set(_EXIT_WITNESSES) - _all_witnesses())

        assert not stale, (
            "these are in the registry and no longer exist. Delete them — and if they were OWED, "
            "lower OWED_EXIT_WITNESSES so the debt shrinks ON THE RECORD:\n"
            + "\n".join(f"  {key}" for key in stale)
        )

    def test_every_entry_is_classified(self) -> None:
        """An unlabelled entry is a decision not taken."""
        unknown = {key: kind for key, kind in _EXIT_WITNESSES.items() if kind not in _KINDS}

        assert not unknown, f"unclassified entries: {unknown}"


def _pipes(block: str) -> bool:
    """Does this shell block contain a real pipeline?

    ``||`` is not a pipe, and a ``|`` inside single quotes (an ``awk`` program, a ``grep -E``
    alternation) is not one either. Both are stripped before looking, because a ratchet that cries
    wolf gets an allowlist, and an allowlist is where holes go to live.
    """
    stripped = re.sub(r"'[^']*'", "''", block)  # single-quoted args: awk programs, regexes
    stripped = stripped.replace("||", "")
    return "|" in stripped


class TestNoPipelineDecidesAVerdict:
    """**A pipeline's exit code is its LAST command's.** The sentence this whole story starts with.

    ``git merge 2>&1 | tail -1`` printed ``Updating a..b`` on stdout while the error went to
    stderr; the pipe ate the status; ``$PIPESTATUS[0]`` — *empty in zsh* — agreed; and two gates
    read green over a failed merge. Everything since has been that same shape wearing a different
    hat.

    So it is closed at the only level where it stays closed: **the shell**, once, for every
    recipe and every step — not at each pipe, remembered. A discipline that must be remembered at
    every site is a discipline that will be missed at one, and the one is the one that matters.
    """

    def test_the_makefile_runs_every_recipe_under_pipefail(self) -> None:
        """`/bin/sh` has no pipefail. GNU make defaults to `/bin/sh`. That is the whole bug.

        Measured before this line existed: `make ledger-backup` against a container that does not
        exist exited **0** and wrote a notarised archive of zero bytes, because `pg_dump | gzip`
        reports *gzip*, and gzip compresses nothing with complete success.

        Mutation: delete the `.SHELLFLAGS` line. Red — and every pipeline in the file silently
        goes back to reporting the wrong command.
        """
        text = _MAKEFILE.read_text(encoding="utf-8")

        shell = re.search(r"^SHELL\s*:?=\s*(?P<path>\S+)", text, re.MULTILINE)
        assert shell is not None and shell.group("path").endswith("bash"), (
            "the Makefile does not pin SHELL to bash. Without it, recipes run under `/bin/sh` — "
            "`dash` on a Linux runner — which HAS NO `pipefail` AT ALL, and every `cmd | filter` "
            "in this file reports the filter's success."
        )

        flags = re.search(r"^\.SHELLFLAGS\s*:?=\s*(?P<flags>.+)$", text, re.MULTILINE)
        assert flags is not None and "pipefail" in flags.group("flags"), (
            "the Makefile does not set `-o pipefail` in .SHELLFLAGS. A pipeline's exit code is "
            "its LAST command's, so `pg_dump | gzip` reports GZIP, `psql | tee` reports TEE, and "
            "`git merge | tail` reports TAIL — which is the incident ADR 0026 is named for."
        )

    def test_no_workflow_step_pipes_without_pipefail(self) -> None:
        """GitHub runs `run:` under **`bash -e {0}`**: `-e` is on, and **pipefail is not**.

        The `-e` is what makes this one so easy to get wrong. The block looks defended, and every
        *simple* command in it is. A pipeline is not a simple command.

        Mutation: drop the `set -o pipefail` from ci.yml's seed step. Red, by name.
        """
        offenders: list[str] = []
        for path in sorted(_WORKFLOWS.glob("*.yml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job_name, job in (document.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    block = step.get("run")
                    if not isinstance(block, str) or not _pipes(block):
                        continue
                    if "pipefail" in block or "pipefail" in str(step.get("shell", "")):
                        continue
                    name = step.get("name", "(unnamed step)")
                    offenders.append(f"{path.name}::{job_name} → {name!r}")

        assert not offenders, (
            "these CI steps decide a verdict from a PIPELINE, and GitHub's default shell "
            "(`bash -e {0}`) does not set pipefail — so the exit code they publish is the LAST "
            "command's, not the one that failed:\n"
            + "\n".join(f"  {who}" for who in offenders)
            + "\nAdd `set -o pipefail` as the block's first line."
        )

    def test_nothing_reads_a_verdict_out_of_pipestatus(self) -> None:
        """`${PIPESTATUS[0]}` is **empty in zsh** — and that is not a footnote, it is *instance №1*.

        It is the array that was consulted, found empty, coerced to nothing, and read as success.
        `pipefail` is strictly better and cannot be silently empty, so the broken tool is simply
        not available here.

        Mutation: put `${PIPESTATUS[0]}` back into any recipe or workflow. Red.
        """
        surfaces = [_MAKEFILE, *sorted(_WORKFLOWS.glob("*.yml"))]
        offenders = [
            f"{path.relative_to(_ROOT)}:{number}"
            for path in surfaces
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if "PIPESTATUS" in line
        ]

        assert not offenders, (
            "PIPESTATUS is being used to read a pipeline's verdict:\n"
            + "\n".join(f"  {who}" for who in offenders)
            + "\nIt is EMPTY IN ZSH — which is how the first false green in this repository's "
            "history was manufactured. Use `set -o pipefail`; it cannot be quietly absent."
        )
