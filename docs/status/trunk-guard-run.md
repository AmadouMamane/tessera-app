# `main` forked — and the guard that would have refused it

2026-07-13 · branch `claude/fork-guard`, cut from `main` @ `c6a2048c` · **NOT LANDED** (see the halt)

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

## Ratchets — and their reds

Four mutations, each producing the quoted red, each restored byte-exact.

| # | mutation | what went red |
|---|---|---|
| **m1** | the guard reads `refs/remotes/origin/main` instead of asking the remote | `test_a_stale_cache_does_not_fool_it` |
| m2 | unreachable remote ⇒ `Ok("assuming it has not moved")` | `test_an_unreachable_remote_is_a_blind_spot_not_a_pass` |
| m3 | `chmod -x` the hook | `test_the_hook_is_executable_and_delegates_to_the_guard` |
| m4 | the hook acts in the `committed` phase instead of `prepared` | `test_a_real_forking_merge_is_refused_by_git_itself` |

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

## What is owed

* **The reconciliation itself.** When `claude/eval-catalogue-discrimination` lands, `main` will
  contain both lanes and this branch rebases cleanly behind it. The guard cannot be installed
  *before* it lands (a relative `core.hooksPath` resolves against each worktree's own checkout, and
  `main` does not carry `.githooks/` until this branch is in).
* **Landing this branch is therefore itself an unguarded trunk advance** — the last one. Stated,
  rather than quietly done.
* **`.secrets.baseline`** — still owed, still Amadou's to audit (see `witness-exit-surface-run.md`).
