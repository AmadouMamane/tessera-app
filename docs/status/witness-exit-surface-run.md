# The exit-code surface — the one the doctrine was born on, and the one nothing watched

2026-07-13 · branch `claude/witness-exit-surface` · cut from `main` @ `b0a2254d`

## Why this lot existed

[ADR 0027](../decisions/0027-a-verdict-carries-its-evidence.md) froze a debt: `OWED_VERDICTS = 44`,
the witnesses in this repo that still publish a verdict as a bare `bool`. The number was computed by
an AST walk over `-> bool` annotations in `src/` and `scripts/`, and the docstring said so plainly.

But a **name is a claim**. `OWED_VERDICTS` claims *the verdicts*. And a witness can publish its
verdict as a dict with an `ok` key, as the string `"PASS"`, as `None`-and-raise — **or as an exit
code**, which is what it was *the first time*: the empty `${PIPESTATUS[0]}` of ADR 0026's origin
instance. Every `make` target, every script, every CI step is an exit-code witness. There were
**110** of them, and not one was registered.

So the registry that embodies the doctrine was **blind to the surface the doctrine was born on** —
the same shape as the memory-registry ratchet that policed `## Insight N` and *reported on the whole
file*. One storey up, and this time inside the instrument built to police the storey below.

## What was found OPEN — three live false greens, measured, not reasoned about

These were **fixed, not filed**. A hole you have just watched swallow a verdict does not get a line
in a debt register.

### F-1 · `make ledger-backup` was structurally incapable of failing

The backup of the audit ledger — *the opposable memory*. Run against a container that does not
exist:

```
Error response from daemon: No such container: tessera-does-not-exist
Error response from daemon: No such container: tessera-does-not-exist
✓ …/audit_ledger-tessera_local-20260713T120216Z.sql.gz (4.0K,  rows) sha256=1ff72a3b…
$? = 0
```

It printed a tick, exited **0**, wrote an archive that decompresses to **zero bytes**, and wrote a
`.sha256` sidecar **authenticating the empty archive** — notarised useless. And it becomes
`_latest_backup()`, the one the restore drill reaches for.

Three laundered exit codes on one recipe line, each sufficient alone:

1. `pg_dump … | gzip -9 > $out` — a pipeline's exit code is its **last** command's, and the Makefile
   declared no `SHELL`, so recipes ran under `/bin/sh` with no `pipefail`. `gzip` compresses a
   failed dump's empty output with complete success. *ADR 0026's origin instance, verbatim.*
2. One backslash-continued `;`-chain with **no `set -e`** — every command after the failure ran.
3. Its **last command was `echo "✓ …"`**, and a recipe line's exit code is its last command's.

**Fixed** by `scripts/ledger_backup.py`, which **reopens the archive it wrote** and requires the
ledger's own `COPY <schema>.audit_ledger` header to be in it. An empty *ledger* passes (a fresh
install has no rows; `pg_dump` still emits the header). A failed *dump* cannot pretend to be one, and
leaves **no file at all** — a backup that does not exist is an honest absence; a backup that exists
and is empty is a lie with a checksum.

| | before | after |
|---|---|---|
| dead container | exit **0**, ✓, 2 files (empty archive + its sha256) | exit **2**, `[NOT OK] no backup was taken — pg_dump exited 1: …`, **0 files** |
| real container | exit 0 | exit 0, `[OK] … (3 588 748 bytes, 28 716 rows) sha256=3f2d59ff…` |

### F-2 · `make eval-null` graded **yesterday's** report — and it is a per-push CI gate

With `scripts/run_eval.py` replaced by `raise SystemExit("BOOM")`:

```
BOOM — runner mort
make: [eval-null] Error 1 (ignored)
[ratchet PASS] null_control: 122/174 vs baseline 122/174
$? = 0
```

The `-` prefix is deliberate and documented — 52 of the 174 runs need a model and fail without one,
so the runner exits 1 *by design* and that code is not the verdict. What was not noticed: **`-`
swallows everything**, and a crash exits 1 too. An exit code genuinely **cannot** tell "52 cases
failed, as designed" from "the harness died at import" — that is a real blind spot, not a fixable
one.

**Fixed** by making the witness ask the **artefact**: the control directory is deleted before the
run, so the report `check_ratchet` grades can only have come from *this* run. No report ⇒ the run did
not happen ⇒ a **named** red. `eval-null-write` had the same hole and it mattered more: it
**overwrites the committed baseline** from the report it finds.

CI never saw it — a fresh checkout has no stale report. **CI's immunity was an accident of the
runner being clean, not a design**, and the hole was armed on every developer machine.

### F-3 · `make dev-status` exited **0** on `STALE` and on `CANNOT SAY`

The fifth instance of ADR 0026, **inside the witness ADR 0026 built.**

`scripts/dev_status.py` prints `⚠ STALE — this server is NOT running the code in this checkout ·
RESTART`. It prints `⚠ CANNOT SAY (this server predates the code-identity witness)`. And `main()`
ended in `return 0`, unconditionally. It published the right answer in the channel a *human* reads
and the word **"ok"** in the only channel a *Makefile* can hear.

The doctrine had been implemented in the **rendering** and forgotten in the **exit code** — which is
to say forgotten on the exact surface it was born on.

**And its tests were green.** Every assertion in `TestTheWitnessReportsItsBlindSpots` was about the
*string* the witness printed. The tests asked **the same question the tool did** — *what does it
say?* — and nobody asked *what does it return?*

**Fixed:** the exit code IS the verdict (`Ok | NotOk | CannotSay` → `0 | 2 | 2`). Verified on the
operator's live stale backend: **exit 2** (was 0). Two smaller instances beside it: `_listening_pid`
collapsed "lsof refused to run" and "lsof found nothing" into one `None` (a machine that could not be
interrogated, reported as a machine that is not there); and the frontend row now **casts no vote**
rather than voting `Ok` on a question it cannot answer.

### F-4 · `detect-secrets` — a permanently-green job that checked nothing

`.secrets.baseline` **has never been committed**, so the job always took the `else` branch:
`detect-secrets scan > /dev/null` — a command that **exits 0 whatever it finds**, with its output
discarded. The Makefile quotes *this exact failure*, by its audit id, as a lesson already learned:
*"F-14: detect-secrets with no baseline was a permanently-green job that checked nothing"*. **The
lesson was written down and the job was never fixed.** It only never fired because CI is
billing-blocked; it was armed the whole time.

**Fixed:** the gating command is `detect-secrets-hook` (`scan --baseline` *rewrites* the baseline and
exits 0 — it could never gate). A **missing baseline is now a blind spot**, and a blind spot does not
get to pass: the job exits 1 with an instruction. ⚠ **This job will be RED until somebody creates and
audits `.secrets.baseline`** — deliberately. Generating it here would mean *fabricating* an assertion
("these are all known non-secrets") that nobody has reviewed, which is the thing this whole doctrine
forbids.

### F-5 · `scripts/perf-probe.mjs` says it is a gate. Nothing calls it.

Its header: *"A performance budget is a GATE, not a hope… **It runs inside the twice-green gate from
Phase A**."* It is invoked from **nowhere** — not the Makefile, not a workflow, not `package.json`.
Only prose mentions it. A gate that is never called cannot fail. The header is **corrected** (wiring
it needs a live backend — a lot of its own) and the debt is **named** rather than pretended.

## What was delivered

| | before | after |
|---|---|---|
| the `bool` registry's name | `OWED_VERDICTS = 44` | **`OWED_BOOL_VERDICTS = 44`** — the name carries the scope |
| its blind spots | undeclared | **`BLIND_SPOTS`**, in the code, beside the number: exit codes (covered), dict/str verdicts (`None` — nobody), `None`-and-raise (`None` — nobody) |
| the exit-code surface | **0 of 110** registered | **110 of 110**, two-sided frozen, `OWED_EXIT_WITNESSES = 10` |
| pipeline laundering | `/bin/sh`, no pipefail, anywhere | `SHELL := /bin/bash`, `.SHELLFLAGS := -o pipefail -c`; `set -o pipefail` in CI's piped steps; `PIPESTATUS` **banned** |

`-e` is deliberately **not** set in `.SHELLFLAGS`: `dev-up`'s port guard is an `lsof && { exit 1; }`
whose *negative* case (port free ⇒ `lsof` exits 1) is the healthy one, and `-e` would abort on it. **A
false red is the same disease as a false green** — and it is worse in one way: a false green lulls
you, a false red trains you to ignore reds.

### `OWED_EXIT_WITNESSES = 10` — what is frozen, and why

| witness | why it cannot fail for the reason it exists |
|---|---|
| `Makefile::test-integration` | `pytest` exits 0 when **every** test skips. No Postgres, no ClickHouse ⇒ green, having run nothing |
| `scripts/run_eval.py` | a dead backend does not crash it: it completes every case and reads a clean 70 % |
| `scripts/check_contribution.py` | discards `subprocess.run(...).returncode`; grades whatever report exists. **Not touched — the live `claude/eval-gate-lift` lane owns this file** |
| `scripts/ledger_restore_drill.py` | a raising `finally:` (a failing `DROP DATABASE`) **replaces** the verdict with a traceback |
| `scripts/perf-probe.mjs` | claims to gate; is invoked from nowhere (F-5) |
| `ci.yml::e2e` | `continue-on-error: true` — 182 Playwright specs that cannot fail CI. Declared as owed in its own header |
| `eval.yml::model-replay` | `if: workflow_dispatch && inputs.model != ''` — skipped on every push/PR/nightly, and a skipped job reports **success** |
| `integration.yml::integration` | `exit 0` when ClickHouse never becomes ready |
| `deps.yml::python`, `deps.yml::frontend` | `\|\| true` on every audit command, inside a brace group whose last line is a closing fence. Double-laundered |

The distinction that keeps the number honest: `delegate` — a make target that is a thin shim over a
registered script judges nothing of its own, and **the witness is the thing it calls**. Counting both
would inflate the debt with shims.

## Ratchets — and their reds

A ratchet never seen red is not a ratchet. All nine mutations below were run, produced the quoted
red, and were restored **byte-exact** (`git rev-parse HEAD^{tree}` compared before/after).

| # | mutation | what went red |
|---|---|---|
| a1 | delete the `exit code` key from `BLIND_SPOTS` | `test_the_blind_spots_are_declared` |
| a2 | delete `tests/unit/test_exit_witness_debt.py` | `test_a_declared_cover_must_actually_exist` — *a claim is not a fact: the cover is opened, not believed* |
| b1 | add `audit-everything:` to the Makefile | `test_no_exit_witness_escapes_the_registry` |
| b2 | drop a new file into `scripts/` | `test_no_exit_witness_escapes_the_registry` |
| b3 | delete the registered `memory-check` target | `test_no_stale_entry_survives_in_the_registry` |
| b4 | lower `OWED_EXIT_WITNESSES` to 4 without fixing anything | `test_the_owed_count_is_the_number_of_owed_entries` |
| c1 | remove `.SHELLFLAGS` | `test_the_makefile_runs_every_recipe_under_pipefail` |
| c2 | remove `set -o pipefail` from CI's seed step | `test_no_workflow_step_pipes_without_pipefail` |
| c3 | put `${PIPESTATUS[0]}` back into a recipe | `test_nothing_reads_a_verdict_out_of_pipestatus` |

**The pipeline ratchet caught its own author within a minute of being written**: the `git ls-files |
xargs detect-secrets-hook` pipe added three commits earlier, in the F-4 fix.

## Two traps that nearly produced a false conclusion — in the audit of laundering itself

1. **My own proof harness laundered its exit code.** To measure `make eval-null` I wrote
   `make eval-null 2>&1 | tail -5` then `rc=${PIPESTATUS[0]}` — and **`$PIPESTATUS` is empty in
   zsh**. The audit tool fell, live, into instance №1 of the class it was auditing, and printed an
   **empty** exit code. Fix: measure with **no pipe at all** — redirect to a file, read `$?` from the
   thing itself.
2. **I ran the OLD code and read its answer as the new one.** To verify the `dev-status` fix I ran
   `make dev-status` from `tessera/` — the main checkout, which does not carry the fix. `EXIT = 0`,
   and I nearly concluded the fix did not work. That is *precisely* the disease: I interrogated the
   **neighbourhood** (a checkout with the same target name) instead of **the thing** (the worktree
   holding the code) — and `dev-status` exists because a process is not its directory.

The auditor of a class of bugs **is in the class**. Both traps are the two canonical forms of ADR
0026, reproduced by the person hunting them, an hour apart.

## Not touched, on purpose

* **`scripts/check_contribution.py`** — the live `claude/eval-gate-lift` session owns it
  (`FloorGrade.releasable` → `Verdict`). Registered as `OWED`; the fix is theirs.
* **`--cov-fail-under=0` in `gate-py`** — the coverage threshold in the gate is disabled while
  `make coverage` uses 80. It is *visible in the command*, not laundered, so it is a policy call for
  the operator, not a bug for an agent to flip.
* **`webapp/frontend/scripts/sync-eval-bundle.mjs`** — its top-level `.catch()` swallows every error
  and exits 0, so a failed bundle regeneration ships the stale committed bundle. Outside this lot's
  three surfaces; reported, not fixed.
* **The operator's reference servers** — `dev-status` says `STALE`. Restarting them is his gesture.

## Verification

* `make gate-twice` — `[TWICE-GREEN]` on ONE tree (see the commit trail).
* 2 011 unit tests pass; 1 skipped (the `biome` tooling blind spot, correctly reported as a blind
  spot outside the gate — inside it, `gate-web` runs first and the tool is present).
* `mypy --strict` clean on 301 source files.
* The three fixed witnesses driven end-to-end, in **both** directions: they fail when they should and
  pass when they should.
