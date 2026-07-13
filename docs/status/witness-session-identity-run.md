# Run — the marker asked the directory who was working here (`claude/witness-session-identity`)

**Date:** 2026-07-13 · **Cut from:** `origin/main` @ `5a0e9065` · **Model:** Opus 4.8

---

## The headline: the incident happened again, during the fix, and the tool said nothing

The brief said `make claim` cannot tell two Claude sessions apart, because it resolves an agent's
identity from the **name of the worktree directory**. That is true, and it is
[ADR 0026](../decisions/0026-a-witness-interrogates-the-thing.md)'s fourth instance, inside the tool
built to police its third.

It is also not hypothetical. `lsof` on 2026-07-13 showed **seven live Claude sessions** with their
working directory in `agents/claude/`. All seven resolve to the owner `"claude"`. And while this lot
was being written, **a second session landed three commits in that worktree**:

```
4753afec  12:52:33   test(cockpit): the door to /eval is guarded
84e086fd  13:02:13   fix(eval): the weak-model calibration was run, and it FAILED
e1b0102f  13:05:07   docs(eval): the floor is a release condition
```

HEAD moved from `98808ba0` to `e1b0102f` **underneath a session that was working there**, and
`make claim` never refused anybody, because both sessions are `claude`. The marker on disk read:

```json
{ "agent": "claude", "pid": 98111, "claimed_at": "2026-07-13T09:56:44+00:00" }
```

`pid 98111` was already dead — it always is. It is the pid of the ephemeral
`python worktree_owner.py claim` **subprocess**, which exits about a second after writing the file.
A liveness field guaranteed to be false: the fifth instance, in the same eighteen lines as the
fourth. Both fields described the writer's *neighbourhood* — its directory, its helper process — and
neither described the writer.

**What this lot did about the live collision:** nothing destructive. No stash, no checkout, no
reset. The work was moved to a dedicated worktree (`agents/claude-witness`, cut from `origin/main`),
every file was verified byte-identical before being reverted out of the contested tree, and the
other session's two in-flight files were confirmed safe in *their* commits. `agents/claude` was
handed back clean. That is now [ADR 0027](../decisions/0027-a-verdict-carries-its-evidence.md) §4.

---

## The incident, replayed: two sessions, one role, one tree

The old tool (`origin/main`) and the new one, on the same temp repo at `…/agents/claude`:

```
BEFORE — identity = the worktree's directory name
  Session A claims:
      [worktree] …/agents/claude is now owned by 'claude'                         EXIT 0
  Session B — a DIFFERENT session, SAME lane — asks if the tree is its own:
                                                                                  EXIT 0
      ↑ no output at all. It did not even speak. It simply waved a stranger through.

AFTER — identity = asserted by the session
  Session A claims:
      [worktree] [OK] … is now held by session 3797cfdf-…-60ca6fc9e4e5 (role 'claude')   EXIT 0
  Session B — SAME ROLE ('claude'), different session:
      [worktree] [NOT OK] you are session 9f2c1a04-…; … is held by ANOTHER SESSION.      EXIT 2
        holder: session 3797cfdf-… · role 'claude' · pid 18338 is ALIVE · held for 0s …
  A caller that does not say who it is at all:
      [worktree] [CANNOT SAY] I cannot tell WHO you are: no TESSERA_SESSION_ID …         EXIT 2
```

The marker now records the facts it actually has:

```json
{
  "session_id": "3797cfdf-afc0-419f-8584-60ca6fc9e4e5",
  "role": "claude",
  "pid": 14340,
  "claimed_at": "2026-07-13T11:10:54+00:00",
  "host": "mac.home",
  "worktree": "/Users/amadou/local/apps/tessera-app/agents/claude-witness"
}
```

`pid 14340` is the **session's** pid, declared by the session, and `check` reports `pid 14340 is
ALIVE`. When a session declares no pid, the field is `null` — an honest gap
([ADR 0024](../decisions/0024-every-governed-act-names-its-author.md)), never a fabricated number.

---

## LOT 2 — the false red, reproduced, and its exact path

The brief could not find the offending test on `origin/main`. It **is** there — reached
**indirectly**, through a script, which is why grepping `tests/` for "biome" finds nothing:

| layer | file | what it does |
|---|---|---|
| 1 | `tests/unit/test_zod_codegen.py:28` | `subprocess.run([… generate_zod.py …], check=True)` |
| 2 | `scripts/generate_zod.py:228` | calls `_biome_format(args.out)` **unconditionally** |
| 3 | `scripts/generate_zod.py:240` | `corepack pnpm exec biome format --write` — `check=True`, no guard |

Reproduced on a **virgin worktree at `origin/main`** (`node_modules`: absent · `biome`: absent):

```
1 failed, 1953 passed          FAILED tests/unit/test_zod_codegen.py::test_the_checked_in_zod_matches_the_current_openapi
make[1]: *** [gate-py] Error 1
make: *** [gate] Error 2                >>> TRUE EXIT CODE OF `make gate`: 2
```

**The exit code is 2, not 254** — 254 is pnpm's, and it is laundered twice on the way up:

```
corepack pnpm exec biome  → 254  ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL  Command "biome" not found
  └─ generate_zod.py (check=True)      → 1   CalledProcessError
      └─ test_zod_codegen.py (check=True)  → FAILED …matches_the_current_openapi
          └─ pytest → make gate-py → Error 1  →  make gate → exit 2
```

The red is worse than "unhelpful". The test it names is
`test_the_checked_in_zod_matches_the_current_openapi` — so the gate tells the operator **"your
generated code is stale"** when the truth is **"node was never installed here"**. It does not merely
fail to explain; **it accuses the wrong culprit.**

`.github/workflows/ci.yml` had the identical ordering (`make gate-py` before `make gate-web`, and
only the pnpm **store** is cached — never `node_modules`). It never fired because CI is
billing-blocked. It was armed the whole time. Fixed.

**The fix, and the trap avoided.** A silent skip would be F-14 (a green job that checks nothing is
worse than an absent one, because an absent one is visible). So:

* **named** — the probe *runs* `biome` and quotes its own last line of stderr;
* **counted** — `census()` prints at the end of **every** run, including `0 tooling blind spot(s)`;
* **impossible in the gate** — `gate-checks: gate-web gate-py` (the toolchain installs first) and
  `gate-py` exports `TESSERA_GATE=1`, under which a missing tool is a **red that names the tool**.

Seen working, live, on the fresh worktree before the toolchain was installed:

```
1 skipped
[tooling] ===== TOOLING BLIND SPOTS — TESTS THAT COULD NOT LOOK =====
[CANNOT SAY] 1 test(s) could not run for missing tooling — this run has HOLES, and its green
is not a full green.
    · 'biome' could not be run — `corepack pnpm exec biome --version` exited 254:
      ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL  Command "biome" not found
      UNCHECKED: whether …/generated/fleet.ts still matches the backend's OpenAPI
      Install the toolchain:  make gate-web
```

---

## The four ratchets, each seen RED under its own mutation

| # | ratchet | mutation | the red |
|---|---|---|---|
| **a** | two sessions, same role, same tree → the second is REFUSED, naming the first | `check()` compares `role()` not `session_id()` | *"a second Claude session in agents/claude was told the tree was ITS OWN. This is the 2026-07-13 incident, and it is green again."* + *"`make gate` proceeded in another session's tree"* (`main(['check']) == 0`) |
| **b** | no session identity → CANNOT SAY, exit 2, never "you are home" | anonymous caller on an unclaimed tree gets `Ok` | *"an anonymous caller was told an unclaimed tree was fine to work in"* — the mutation resurrects the exact old sentence: `is unclaimed — proceeding as 'claude'`. And *"anonymous `make whoowns` exited 0"* |
| **c** | `Ok` cannot be built without evidence — **at the type level** | `evidence: str = ""` | *"mypy ACCEPTED `Ok()` — an Ok that observed nothing is now constructible, and the type is decoration"* (mypy `returncode=0`) + *"Ok.evidence has a default"* |
| **d** | zero tests skipped for missing tooling **in the full gate** | the in-gate census returns `CannotSay` instead of `NotOk` | *"a test was skipped for missing tooling INSIDE THE GATE and the session stayed green. That is a green light over a hole."* |
| **d′** | (the other half) the toolchain installs before the suite | `gate-checks: gate-py gate-web` | *"gate-py runs before gate-web … and its one node-dependent test blames the code for it"* |

Tree restored clean after every mutation (0 dirty files).

---

## The debt: 44, and it may only go down

`tests/unit/test_verdict_debt.py` AST-scans every `-> bool` function in `src/` and `scripts/` — **97
of them** — and requires the registry to hold **all** of them, classified. **44 are verdicts**: they
decide whether something *passes* and say it with one bit.

```
OWED_BOOL_VERDICTS = 44      # this may only go down
```

The freeze is two-sided (nothing new may appear unclassified; nothing converted may rot in the
registry), so the debt shrinks **on the record** or not at all. It caught its first stale entry
immediately: `eval_floor.py::FloorGrade.releasable` exists on the *eval* branch and not on
`origin/main`.

> **Note for whoever lands `claude/eval-gate-lift`:** it adds `FloorGrade.releasable` — a release
> verdict returning `bool`. The freeze will demand it be registered. Add
> `"src/tessera/observability/eval_floor.py::FloorGrade.releasable": "VERDICT"` and raise
> `OWED_BOOL_VERDICTS` to 45 — **or**, better, have it return a `Verdict` and leave the number alone.

---

## The sixth instance, found while writing the memory note for the fifth

Appending an insight to the registry meant reading the highest number in it. The repo's own gate
ratchet, `test_no_two_insights_share_a_number`, matched headings like `## Insight N`. **The registry
uses two conventions:**

| convention | headings | the ratchet |
|---|---|---|
| `## Insight 12` | **139** | reads them |
| `### 12. Some Title` | **60** | **blind** |

It policed **139 of 199** headings and published a verdict about *the registry*. And in the 30 % it
could not see, `### 2.` already named **two different insights**. Green, for as long as the ratchet
has existed. The corollary, exactly: *a witness that cannot see may never report "ok"*.

Made to see, it found **58 numbers that each name more than one insight** (`2` names three) — two
numbering spaces that grew side by side for months with nothing reading both.

**It caught me first.** "The highest number in the file" is **140**, not 59. An agent counting only
the headings that look like the recent ones answers **60** — and `## Insight 60` has existed for
months. I did exactly that, and created collision 59. Renumbered to **141**; `next_free_number()`
now answers from the whole file, and CLAUDE.md no longer tells the next agent to do what I did.

The 58 are **frozen, not renumbered** (a number is cited from other insights, from
`synthesis_tessera.md`, and from commit messages — CLAUDE.md forbids renumbering an existing one).
A 59th is red. And the freeze is two-sided, so the ratchet **cannot go quietly blind again**: narrow
the pattern back and it reports all 58 as "resolved", which is red.

| mutation | the red |
|---|---|
| restore the literal `Insight ` in the pattern | *"collision(s) [1, 2, 4 … 59] are RESOLVED — remove them from `_FROZEN_COLLISIONS`"* |
| drop `2` from the frozen set | *"A NEW NUMBER NAMES TWO INSIGHTS: [2]"* |

---

## Two more things, worth their own lines

**1. The ratchet caught its own author, twice.** The first version of the CI-ordering test did
`_CI.index("make gate-py")` — and matched the words inside the *comment I had just written* to
explain the ordering, reporting the fix as broken. A witness reading a file's **prose** is reading
the neighbourhood of the thing that **runs**. It now parses the workflow's steps.

**2. I walked into the trap in my own memory.** Undoing a mutation with `git checkout -- <file>`
reverts to **HEAD**, and my memory-ratchet rewrite was not committed — so it was eaten. I had
committed before the first four mutation tests precisely for this reason, and then forgot for the
fifth. **Commit, then mutate.** Written here because the next person will forget too.

**3. `claude/eval-gate-lift` is currently RED on ruff** — `tests/unit/test_eval_no_domain_bar.py:105`,
`N802` (`test_an_unrestricted_floor_is_REFUSED_not_misgraded`). Not mine, not fixed here; flagged so
the owning session sees it before merging.

---

## What is NOT closed

* **`make gate` now refuses a caller with no `TESSERA_SESSION_ID`.** That is the intended cost.
  `eval "$(make session)"` once per shell; agents and CI export it. The refusal prints both forms.
* **44 witnesses still publish a bit.** Named and counted; not converted. That is an ADR's work.
* **Nothing stops a witness asking the wrong question.** What is closed is publishing the answer
  without saying what was examined.
* The marker stays **advisory**. Nothing on a shared filesystem truly locks — and an advisory that
  tells the truth would have turned today's silent collision into a loud refusal, which is all that
  was ever missing.

---

## Gate

`make gate-twice` — machine-asserted: two green passes on **one** tree. Taken in
`agents/claude-witness`, a worktree with exactly one writer, claimed by session
`3797cfdf-afc0-419f-8584-60ca6fc9e4e5`. Never in `agents/claude`, where another session was
committing. That rule is now written down (ADR 0027 §4); today it was practised first.
