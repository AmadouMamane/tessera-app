# `main` forked — and the guard that would have refused it

2026-07-13 · branch `claude/fork-guard` · rebased onto the **reconciled** `main` @ `6ac0d8d8`

**The fork is closed.** `claude/eval-catalogue-discrimination` landed carrying *both* lanes as
ancestors, so the trunk became a descendant of both; this branch was then rebased cleanly onto it.
The halt below is kept, unedited, because the reasoning that produced it is the point — not the
outcome.

## The fork

```
5a0e9065 ──┬── 34b59c0d   origin/main   (+10, the eval lane, pushed)
           └── c6a2048c   main          (+15, the witness lane, never pushed)
```

Neither is an ancestor of the other. No fast-forward exists in either direction, in a repository
whose stated convention is *trunk-based: one long-lived branch, advanced only by fast-forward*.

**It was not caused by a bad merge.** Both lanes were, at every moment, doing the right thing. Each
advanced `main` by an ordinary `git merge --ff-only` from a base it believed was current — and the
belief came from `refs/remotes/origin/main`, **a local cache of a remote fact**, exactly as fresh as
your last `git fetch`. The fetch is the event that did not happen. In both lanes. At once.

The rule *"only one agent touches `main`"* was written down. Writing it down has now failed to stop
**every** instance in this repository's history of a green light over a hole. It is a **social**
rule, and the fork is what a social rule looks like when it is load-bearing.

## ⛔ HALT — `main` was not touched, and here is why

The prompt for this lot asked for a rebase of the 15 local commits onto `origin/main`. **I did not
do it**, and the reason is a fact, not a preference:

`claude/eval-catalogue-discrimination` committed **`437a3977` at 15:34**, ten minutes before I
looked:

```
437a3977  Merge branch 'main' into claude/eval-catalogue-discrimination
  parents:  02d30eba  +  c6a2048c        ← the exact tip a rebase would rewrite
```

Its worktree carried uncommitted work (`Makefile`, `src/tessera/verdict.py`,
`scripts/check_discrimination.py`, `eval/discrimination.py`). And its branch **already contains both
lanes** — `34b59c0d` *and* `c6a2048c` are both ancestors of `437a3977`. A reconciliation was already
in flight, in another agent's tree.

Rebasing `main` gives all 15 commits **new shas**. `c6a2048c` becomes unreachable from `main` — but
it is a **merge parent** of a live branch. When that branch lands, git sees the 15 old commits as
absent from `main` and reintroduces them under their old shas, alongside the 15 new ones: **the
whole lot, duplicated on the trunk**, plus a conflict storm on the two files both lanes touch.

That is the 2026-07-12 incident one storey up: **rewriting history under a live writer who has
already built on it.** Amadou's ruling: she lands first; I build the guard meanwhile.

*A note on the liveness evidence, because it matters.* Her worktree marker declares `pid 45805`, and
that pid reads **dead**. It exonerates nothing: ADR 0027 established that this pid is the *claim
subprocess's* — "a fact about a corpse". A commit ten minutes ago and modified files in the tree are
far stronger evidence of life than a dead pid is of death. **CannotSay on her liveness ⇒ refuse.**

## The guard

> **`origin/main` must be an ancestor of whatever `main` is about to become.**

`scripts/main_guard.py`. Three properties, and the first is the whole of ADR 0026:

**1. It asks the REMOTE, not the ref that is named after it.** `git ls-remote`, over the wire, every
time. `refs/remotes/origin/main` is a *photograph of the remote taken at your last fetch* — the
neighbourhood. A guard consulting it would have said "all clear" to both lanes, twice, with total
composure, because both caches were stale in exactly the way that mattered.

**2. It fails closed.** Unreachable remote ⇒ `CannotSay` ⇒ exit 2. *"I could not reach origin, so
probably nothing moved"* is the bug in its purest and most tempting form — and assuming nothing had
moved is **literally** what forked the trunk. `TESSERA_MAIN_GUARD_BYPASS=1` overrides, and says so
in its own evidence: an override that passes quietly is how a temporary exception becomes the
permanent state of a repository.

**3. It distinguishes "I have never seen that object" from "no".** Before a fetch, the remote's tip
is not an object we hold, and `git merge-base --is-ancestor` exits 128 there, not 1. Reading that as
"not an ancestor" would produce a refusal that is *right by accident*, on a question that was never
answered. A false red is the same disease as a false green — and it is worse in one way: it trains
you to ignore reds.

### Why a hook, and why *that* hook

`.githooks/reference-transaction`, wired in by `make hooks`, which `install` depends on — and
`install` is a prerequisite of every other target in the Makefile, so the guard is in place before
anything else in this repository can run.

* **Not a make target.** A target is opt-in, and **the fork was made of not opting in**: `main` was
  advanced by an ordinary `git merge --ff-only`, which nobody thought twice about.
* **Not `pre-merge-commit`.** **A fast-forward creates no commit**, so that hook never fires for the
  exact operation that forked the trunk. `reference-transaction` fires on *every* ref update, and a
  non-zero exit in the `prepared` phase **aborts the transaction** — a merge, a bare merge, a commit
  straight onto the branch, a reset.

## ⚠ The guard did not run in the checkout where the trunk lives

The version above shipped `make hooks` as `git config core.hooksPath .githooks`. **It dug the exact
hole it was built to fill**, twice over:

* A **relative** `core.hooksPath` resolves against **each worktree's own root**. So the hook existed
  only in trees whose branch happened to carry `.githooks/` — and **`main` does not**. The main
  checkout (`tessera/`), the one place a human types `git merge --ff-only`, was the one place the
  guard was absent. An uninstalled guard is not a weak guard: it is a **witness that does not run**.
  It refuses nothing, and it protects precisely the trees that opted in — *and the fork was made of
  not opting in.*
* It also hijacked git's **entire** hook lookup, so `.git/hooks/pre-commit` — the slot `pre-commit
  install` writes into — became unreachable. A second hook, silently disabled, armed and waiting.

Fixed by asking git rather than believing its documentation: `hooks/` is a **common** path, so
`git rev-parse --git-path hooks/…` resolves to the *shared* `.git/hooks/` from **every** linked
worktree, whatever branch each one carries. `make hooks` now **copies** the hook there and unsets
`core.hooksPath`. One installed file guards all nine worktrees; pre-commit keeps its slot.

And because what git runs is the **copy**, the copy is what gets interrogated: `main_guard.py
installed` hashes the installed file against the tracked source. A guard that verified `.githooks/`
while git ran a stale `.git/hooks/` would be checking a file nobody executes — *the neighbourhood,
one last time, inside the guard that exists to name it.*

## A guard nobody has seen absent is not a guard

`make gate` and `make claim` call `main_guard.py installed` on their **first line** and **refuse**
when the trunk is unguarded. Not a warning above an exit 0 — this repository has now paid three
times for that distinction (`dev-status` printed `⚠ STALE` and returned 0; this very hook, in git's
`committed` phase, printed its refusal *in full* while `git merge --ff-only` answered `Fast-forward`
and exited 0). **Publishing a verdict is not enforcing it.**

So the ratchet was mutation-tested the only way that means anything — by taking the guard away:

```
$ mv .git/hooks/reference-transaction .git/hooks/reference-transaction.absent

$ uv run python scripts/main_guard.py installed          → EXIT 2
[main-guard] [NOT OK] THE TRUNK IS UNGUARDED. git would run
  `…/tessera/.git/hooks/reference-transaction` on every update to refs/heads/main, and that
  file does not exist — so nothing would stop a `git merge --ff-only` from forking `main`,
  which is exactly what happened on 2026-07-13.
  An uninstalled guard is a WITNESS THAT DOES NOT RUN. Install it:  make hooks

$ make gate                                              → EXIT 2
make: *** [gate] Error 2
```

The gate **did not run a single check**. It refused to issue a licence to land over a trunk that
nothing protects, and it named the one command that fixes it. Restored ⇒ exit 0.

`gate` deliberately does **not** depend on `hooks`. `gate: hooks` would install the guard and then
verify the guard it had just installed — **a check that repairs what it checks has checked nothing**,
and a check that cannot fail is a green light with a name (F-14: `detect-secrets` scanning into
`/dev/null` and reporting success for a year).

## Ratchets — and their reds

Six mutations, each producing the quoted red, each restored byte-exact.

| # | mutation | what went red |
|---|---|---|
| **m1** | the guard reads `refs/remotes/origin/main` instead of asking the remote | `test_a_stale_cache_does_not_fool_it` · `test_the_unfetched_incident_is_refused_as_a_blind_spot` · +2 |
| m2 | unreachable remote ⇒ `Ok("assuming it has not moved")` | `test_an_unreachable_remote_is_a_blind_spot_not_a_pass` |
| m3 | `chmod -x` the hook | `test_the_hook_is_executable_and_delegates_to_the_guard` |
| m4 | the hook acts in the `committed` phase instead of `prepared` | `test_a_real_forking_merge_is_refused_by_git_itself` |
| **m5** | **the guard is uninstalled** (`mv .git/hooks/reference-transaction`) | `make gate` → **exit 2**, and 4 unit ratchets |
| m6 | the temp repo has no `.venv/bin/python` (the fixture's own old blind spot) | all 3 of `TestTheHookIsWhatActuallyRefuses` |

**m1 is the one.** The cache-reading guard produced, verbatim:

```
Ok(evidence='`main` → 099cb6aede21 contains origin/main (b347b87ed3be), asked of origin just now.
             One trunk, still.')
```

It wrote *"asked of origin just now"* — while reading a stale local ref. That is the lie the fork was
made of, reproduced by the mutation, in its own words.

And the test that catches it does not merely assert "it refused". It asserts that **the refusal names
the remote's actual tip** — a sha the stale cache has never seen, and which a cache-reading guard is
*structurally incapable* of printing. It cannot be faked, only passed.

**m4 is worth reading too.** With the hook moved to the `committed` phase it **printed its refusal in
full** — and `git merge --ff-only` returned **0** and said `Fast-forward`. The trunk forked anyway. *A
witness that speaks and is not heard.*

And the hook is not *read*, it is **run**: a real forking `git merge --ff-only` is executed against a
real temporary repository with the hook installed, and must be aborted with `main` unmoved. *A guard
is what refuses a stranger, not what appears in a list of guards.*

### ⚠ m6 — and that end-to-end test was GREEN FOR THE WRONG REASON

The disease, caught inside the test written to catch it. The fixture built its temp repository
**without an interpreter at `.venv/bin/python`** — and the hook runs that one and no other (macOS's
system `python3` is 3.9; `verdict.py` needs 3.11+). So the hook never reached the guard at all:

```
[main-guard] [CANNOT SAY] refs/heads/main is moving and I could not check it.
  no interpreter at .venv/bin/python (the guard needs 3.11+). Run:  make install
fatal: ref updates aborted by hook
```

git aborted the transaction. `main` did not move. The string `main-guard` duly appeared in stderr —
and the test's only assertion was `assert "main-guard" in merge.stderr`. **Green.** A hook that
*could not run the guard* certified a guard that never ran. The sha of the remote's actual tip
appeared nowhere in that output, for the excellent reason that nobody had asked the remote.

The fix is the shape of every fix in this file: **demand the evidence of what was looked at**, not
the fact that something spoke. The refusal must now name the sha `origin/main` is *actually* at — a
hook that never woke up cannot print it, and a guard reading the stale cache cannot print it either.
`no interpreter` is a hard red. And the fixture now installs into the **common `.git/hooks/`**,
because the old one set `core.hooksPath` — testing the guard through the very wiring that
`test_core_hookspath_is_not_hijacked` forbids the Makefile from using. *A test that installs a thing
the way nobody installs it is testing a fiction.*

**And m1 proved the two hook tests are not redundant.** Under a cache-reading guard, the *fetched*
test stays green — after a fetch the cache and the remote agree, so the wrong implementation is right
by accident. Only the **unfetched** one (the incident verbatim: *nobody fetched*) goes red. Had the
suite carried only the tidy fetched case, the end-to-end path would not have caught the original bug
at all.

Third addition: **the hook must also let a legal advance through.** Nothing proved that, and
`echo main-guard >&2; exit 1` satisfies every refusal assertion in the class. A guard that cries wolf
is torn out by Friday — which leaves the trunk exactly as unguarded as before anyone wrote one.

## Both registries caught their own author

* **The exit-code registry gained a fourth surface.** A git hook's exit code *aborts a ref
  transaction* — it is an exit-code witness by the purest definition, and `.githooks/` was about to
  be an **unregistered** one. Which is the exact hole the registry exists to close.
* **The bool registry caught `_is_ancestor`** (`-> bool | None`) on the day it was born, and demanded
  a classification. It is `data` — a question *about the graph*, not a judgement about whether
  something passes — and it **does not join the debt**: the verdict is `check_advance()`, which
  returns a `Verdict`. *A debt you pay by enrolling in it is not a debt.*

`OWED_BOOL_VERDICTS = 44` (unmoved). `OWED_EXIT_WITNESSES = 10` (unmoved). Both new witnesses are
honest from birth, so neither number moves — which is what those numbers are *for*.

## ⚠ Landing this branch is itself an unguarded trunk advance — the last one

Said out loud, because the alternative is to do it quietly, and doing it quietly is the disease.

`main` @ `6ac0d8d8` **does not carry `scripts/main_guard.py`** — this branch is what brings it. So
when the trunk is fast-forwarded onto this work, the hook fires, finds no guard in the checkout it is
standing in, and **refuses**, correctly: *"scripts/main_guard.py is not in this checkout — check out
a branch that carries it."* It is a `CannotSay`, and a `CannotSay` is a refusal.

That refusal is right, and it must be overridden **deliberately and by name**:

```
TESSERA_MAIN_GUARD_BYPASS=1 git merge --ff-only claude/fork-guard
```

The bypass announces itself in its own evidence (`… was NOT checked against origin`) — an override
that passes quietly is how a temporary exception becomes the permanent state of a repository. This
is the **last** advance of `main` that will not have been checked by anything. After it, `main`
carries the guard, every worktree rebased on it carries the guard, and the hook installed in the
**common** `.git/hooks/` guards all nine of them whatever branch each one holds. It self-heals from
here.

The guard was, of course, run **by hand** against this tip first — `main_guard.py advance` — so the
advance is unchecked *by the hook*, not unchecked *by anybody*.

## What is owed

* **`.secrets.baseline`** — audited and committed in this lot. 57 detections across 38 files, **zero
  real secrets**: local development credentials, i18n labels (`password: Passwort`), Tailwind class
  digests, and two keys belonging to the registry file itself. `tessera-admin` is a **guarded**
  fallback (`seededPassword()` returns null on an exposed deployment, so the account does not exist).
  The CI job's gating command — `git ls-files -z | xargs -0 detect-secrets-hook --baseline
  .secrets.baseline` — was run against the committed baseline and **mutation-tested with a planted
  secret**, because a green job that verifies nothing is worse than an absent one. That was F-14.
* **`pre-commit` is not installed in the common hooks dir.** `core.hooksPath` had been hiding that
  slot; unsetting it *unhides* it, but nothing has written a `pre-commit` hook there. Commits
  therefore run without it, and `make gate` remains this project's only witness (CI is
  billing-blocked). Not this lot's to fix — but it is now visible, which it was not.
