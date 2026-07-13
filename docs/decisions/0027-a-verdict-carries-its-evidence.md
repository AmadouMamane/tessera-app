# 27. A verdict carries its evidence — and is taken on a tree that holds still

Date: 2026-07-13

## Status

Accepted. The structural half of [ADR 0026](0026-a-witness-interrogates-the-thing.md), which
named the disease and then said, honestly, that it could not close the class:

> **What this does NOT claim.** The class is not closed by construction — nothing structurally
> prevents the fourth instance of "ask the neighbourhood" from being written tomorrow, because the
> pattern is semantic, not syntactic. […] When the fourth appears, it will appear the same way the
> first three did: as a green light over a hole, found by someone who checked the thing itself.

The fourth was already there, green, **while that paragraph was being written** — inside the very
tool built to police the third. This ADR records it, and closes the part of the class that *does*
have a syntactic handle.

## Context

### The fourth instance: `make claim` asked the directory who was working here

`scripts/worktree_owner.py` exists because on 2026-07-12 two agents wrote into `agents/claude` at
once: one stashed the other's uncommitted work mid-flight and switched the branch under it, and two
`make gate` runs returned exit 0 **on two different trees**. The marker was the fix. It resolved an
agent's identity like this:

```python
def whoami() -> str:
    """This agent's name: TESSERA_AGENT, else THE WORKTREE'S DIRECTORY NAME.

    The fallback is not a guess — it is the repo's own topology (`agents/<name>/`), so an agent
    that never sets the variable still gets a stable, meaningful identity rather than "unknown".
    """
```

It is not a guess. It is worse: it is a **confident answer to a question nobody asked**. The
question is *"who is writing here?"*. The answer given is *"what is this directory called?"*. The
topology names a **role** — `claude`, `codex`, `antigravity` — and **a role is not a writer.**

On 2026-07-13, `lsof` showed **seven** live Claude sessions with their working directory in
`agents/claude/`. All seven resolved to the owner `"claude"`. Each would read the marker, find its
own name in it, and conclude it was home. The marker refused nobody. It never had.

And it did not stay hypothetical for the length of the fix. While this ADR was being drafted, a
second Claude session landed **three commits** in that worktree — `4753afec`, `84e086fd`,
`e1b0102f` — moving HEAD from `98808ba0` to `e1b0102f` underneath a session that was working
there. `make claim` said nothing, because both sessions are `claude`.

### The fifth, in the same eighteen lines: a liveness field guaranteed to be false

The marker recorded `"pid": os.getpid()` — the pid of the ephemeral `python worktree_owner.py
claim` **subprocess**, which exits about one second after the marker is written. Every marker on
disk therefore names a dead process, and a staleness check built on it would report every tree in
the repo as abandoned. The pid described the *writer's helper process*; the directory described the
*writer's location*. Two fields, two neighbourhoods, zero writers.

### The same shape, inverted: a red that accuses the code for an environment's fault

On a worktree where `pnpm install` had never run, `make gate` went red, and every layer laundered
the cause:

```
corepack pnpm exec biome  → 254  ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL  Command "biome" not found
  └─ scripts/generate_zod.py     (check=True)  → 1   CalledProcessError
      └─ tests/unit/test_zod_codegen.py (check=True)  → FAILED
          └─ pytest → make gate-py → Error 1  →  make gate → exit 2
```

The operator is told **"the checked-in zod is stale"** — an accusation against code that is
perfectly fine. `Command "biome" not found` appears nowhere in the output. This is the gate
answering, with total confidence, a question about the **code** when the question it was asked was
about the **environment**.

**A false red is the same disease as a false green, and worse in one respect: a false green lulls
you; a false red trains you to ignore reds.** It is the mechanism by which a test suite becomes
decorative — and `gate-checks: gate-py gate-web` guaranteed it on every fresh worktree, because the
target that installs the toolchain ran *after* the suite that needs it. `.github/workflows/ci.yml`
had the identical ordering, armed and never fired only because CI is billing-blocked.

### What all five have in common

Every one of them **reduced a verdict to a bit and threw the evidence away.** `check()` returned
`0`. The ratchet returned `True`. `dev-status` printed a green tick. And a bit cannot be
interrogated: you cannot ask `True` *what it looked at*, so for three incidents — four, five —
nobody did.

That is the handle. The *question* a witness asks is semantic and cannot be policed. The *shape of
the answer* is syntactic, and can.

## Decision

### 1. A verdict carries its evidence, or it is not a verdict

`src/tessera/verdict.py`:

```python
Verdict = Ok(evidence) | NotOk(reason) | CannotSay(blind_spot)
```

* **`Ok` cannot be constructed without its evidence.** `evidence` is a required field with no
  default, and the empty string is rejected at construction. A witness that observed nothing has
  *nothing to pass to the constructor* — it is **structurally unable to fabricate an `Ok`**. This
  is ADR 0026's corollary ("a witness that cannot see must report a blind spot; it may never report
  *ok*") demoted from a rule people must remember to one the type system enforces. It is also the
  eval screen's first criterion — *never a verdict without its proof* — brought down from the UI
  into the code.
* **`CannotSay` is a first-class state.** Not a soft `NotOk`, and emphatically not an `Ok`. "I
  could not look" and "I looked and it was fine" are different facts, and every incident above is a
  system that could not tell them apart. It exits **2**, like a refusal: to a Makefile both mean
  *stop*, and the reason they mean it is carried in the message, where a human reads it, rather
  than in a third exit code some shell would eventually treat as success.
* **A `Verdict` may not be used as a boolean.** `__bool__` raises `TypeError`. Without that single
  line the type is decoration: every object in Python is truthy, so `if check(tree):` — the most
  natural line a caller will ever write — would read a `NotOk`, *and a `CannotSay`*, as success. We
  would have rebuilt the original bug on top of its own fix.
* The union is **closed**: three `@final` classes, matched exhaustively under `assert_never`, so a
  fourth verdict invented tomorrow cannot be added until every consumer handles it. Illegal states
  unrepresentable ([ADR 0019](0019-cockpit-agent-invocation-binding.md) §I1).

### 2. Identity is asserted by the session; a role is only a label

`TESSERA_SESSION_ID` — a value only the session can know, because only the session lives long
enough to know it. **Never derived from a path, never defaulted, never minted per invocation** (a
fresh uuid on every `make` would make each command its own session, and the tool would refuse
itself on the second call). The marker records `{session_id, role, pid, claimed_at, host}`:

* `session_id` **decides**. It is the only field that does.
* `role` survives **for the human**, so an operator reading the marker sees which lane holds the
  tree. It is never compared.
* `pid` is the **session's** pid, as the session declares it — and `None` when it does not. `None`
  is an answer ([ADR 0024](0024-every-governed-act-names-its-author.md)); a number we made up is
  not. This is why `os.getpid()` is gone: it named a corpse.
* A caller with **no session identity** gets `CannotSay` and exit 2 — never *"unclaimed —
  proceeding as 'claude'"*, which is the sentence that was already wrong.
* A **legacy marker** (role only, no session id) is `CannotSay` too. Silently upgrading it — *"it
  says claude, I am claude, it is mine"* — would re-enact the bug during the migration that fixes
  it.
* A **stale marker** is a fact to *state*: holder, liveness, age, host, and the one command that
  takes the tree. Never ignored, never silently overwritten. The marker stays **advisory** — nothing
  on a shared filesystem truly locks, and that choice is right. What an advisory owes you is the
  truth.

### 3. A test that cannot run is a blind spot, not a failure — and never a silent one

A missing tool is a `CannotSay`, carrying **the tool's own words** (`probe_node_tool` *runs* the
binary rather than looking for its file — the file is the neighbourhood). And because the obvious
repair is F-14 — `detect-secrets` with no baseline was a permanently-green job that checked nothing,
*worse than an absent job because an absent job is visible* — the skip may not hide:

* **counted** — `census()` returns a `Verdict` and is printed at the end of **every** session,
  including when the count is zero. *"0 blind spots"* has to be **said**;
* **impossible inside the gate** — `gate-checks` runs `gate-web` (which installs the toolchain)
  **before** `gate-py`, and `gate-py` exports `TESSERA_GATE=1`, under which a missing tool is not a
  skip but a **red that names the tool**: there, its absence cannot mean "bare machine", only
  "broken gate".

### 4. A verdict is never taken on a tree somebody else is writing in

The rule this repo practised on 2026-07-13 and had not written down. When another writer is in your
worktree:

> **Destroy nothing — no stash, no checkout, no reset — and take the verdict on an ISOLATED COPY AT
> THE EXACT COMMIT.**

The 2026-07-12 incident was made expensive by the *response*, not only the collision: an agent
correctly judged the foreign changes *"NOT MINE"* and then **stashed them** to get a clean tree —
destroying the other's work to obtain a verdict, and producing a verdict about a tree that no longer
existed. Both halves are wrong. A gate wants a still tree; the way to get one is a disposable
worktree at the commit under judgement, not a tree you cleared by force.

This is the operational face of ADR 0026's tree-fingerprint: the fingerprint *detects* a tree that
moved (VOID, exit 3), and this rule says what to do about it.

## The debt, and its number

The type makes it impossible for a **new** witness to publish "ok" without saying what it looked at.
It does nothing about the ones already written, and pretending otherwise would be its own small
false green.

So the debt is declared the way `OWED_COUNT = 17` declared the unbounded ledger reads:
`tests/unit/test_verdict_debt.py` AST-scans every `-> bool` function in `src/` and `scripts/` — **97
of them** — and requires the registry to contain **all** of them, classified. Of those, **44 are
verdicts**: they decide whether something *passes*, and they say it with one bit.

```
OWED_BOOL_VERDICTS = 44      # this may only go down
```

What is mechanical: the completeness. A new bool-returning function cannot appear without its author
writing down which kind it is, and a converted one cannot rot in the registry — the freeze is
two-sided, so the debt shrinks **on the record** or not at all. What is a judgement: the
verdict/predicate line, recorded per entry. When a call is close it is counted as a verdict —
over-counting costs a migration nobody needed, under-counting hides a hole, and those are not
symmetrical.

Paying it down is not a bulk rewrite. It is: when you next touch one of these, return a `Verdict`,
delete its line, lower the number.

### And the number was called `OWED_VERDICTS` for exactly one day

It scanned `-> bool` **annotations**. That is a *syntactic proxy* for a *semantic class*, and the
name claimed the class. A witness can publish its verdict as a dict with an `ok` key, as the string
`"PASS"`, as `None`-and-raise — **or as an exit code**. Which is what it was *the first time*: the
empty `${PIPESTATUS[0]}` of [ADR 0026](0026-a-witness-interrogates-the-thing.md)'s origin instance.
**The registry that embodies this doctrine was blind to the surface the doctrine was born on**, and
`OWED_VERDICTS = 44` was one careless reading — "44 witnesses left to fix" — away from being a lie.

So the number carries its shape in its name, the registry **declares its blind spots in the code,
beside it** (`BLIND_SPOTS`), and a blind spot claimed as *covered* must name a module that exists —
a claim is not a fact, and `KNOWN_AUTH_GUARDS` certified an anonymous `DELETE` because membership of
a list had been asserted by nobody.

The exit-code surface is now open, and it is the bigger one: **110 witnesses** — every `make` target,
every script, every CI job — enumerated from the artefacts, two-sided-frozen, classified by hand in
`tests/unit/test_exit_witness_debt.py`.

```
OWED_EXIT_WITNESSES = 10     # witnesses that claim a verdict and cannot deliver one
```

Opening it found **five live false greens**, three of them fixed on the spot, and one of those was
`make dev-status` — *this doctrine's own witness*, printing `⚠ STALE · RESTART`, printing `⚠ CANNOT
SAY`, and then returning **0**. The rule had been implemented in the rendering and forgotten in the
exit code. Its tests were green, and they were green because they asked *the same question the tool
asked*: what does it **say**. Nobody asked what it **returns**.

Full account: `docs/status/witness-exit-surface-run.md`.

## Enforcement

Each clause is a test that fails, and each has been **seen red under its own mutation**.

| clause | ratchet | mutation that turns it red |
|---|---|---|
| two sessions, one role, one tree → the second is REFUSED, naming the first | `test_worktree_owner_session_identity.py::TestTheRoleIsNotTheWriter` | make `check()` compare `role()` instead of `session_id()` → *"a second Claude session was told the tree was ITS OWN"* |
| a caller with no session identity never hears "you are home" | same file, `TestAWitnessThatCannotSeeReportsABlindSpot` | return `Ok` for an anonymous caller on an unclaimed tree → *"anonymous `make whoowns` exited 0"* |
| an `Ok` cannot be built without its evidence | `test_verdict.py::TestOkCarriesItsEvidence` — **mypy is actually run** | give `evidence` a default → *"mypy ACCEPTED `Ok()`"* |
| a `Verdict` is not a boolean | `test_verdict.py::TestAVerdictIsNotABoolean` | delete `__bool__` → `if verdict:` silently reads a refusal as permission |
| zero tooling blind spots inside the full gate | `test_gate_tooling_blind_spots.py` | make the in-gate census a `CannotSay` → *"a green light over a hole"*; or restore `gate-checks: gate-py gate-web` → *"blames the code for it"* |
| the marker records no pid the session did not declare | `test_worktree_owner_session_identity.py::TestTheMarkerRecordsFactsAndNotFabrications` | write `os.getpid()` back → the marker names a process that is already dead |
| the debt only goes down | `test_verdict_debt.py` | add any `-> bool` in `src/` → red, naming the file and the line |

## Consequences

**`make gate` now refuses a caller who has not said who they are.** This is a real cost, and it is
the point. `eval "$(make session)"` once per shell; agents and CI export `TESSERA_SESSION_ID`
themselves. The refusal prints both, so the cost is paid once and never guessed at.

**The gate got slower to first python feedback**, because `gate-web` now installs before `gate-py`
runs. A python-only change waits on a `pnpm install --frozen-lockfile` (cached, seconds). We are
buying, with those seconds, the guarantee that the suite's one node-dependent test can actually run
— and therefore that a skip inside the gate is impossible rather than merely unlikely.

**44 witnesses still publish a bit.** Named, counted, and unable to multiply. This ADR does not
claim the class is closed everywhere; it claims a *new* one cannot be born, and that the old ones
have a number.

**What this still does NOT close.** Nothing stops a witness from asking the wrong question — the
sixth instance will be someone reading a config file to decide whether a service is up. What is
closed is the *publishing* of such an answer as a bare, unfalsifiable `True`. The verdict now has to
carry what it looked at, and a reader who can see what it looked at can see that it looked at the
wrong thing. That is the whole gain, and it is enough: **every one of the five incidents above was
found by a human who asked "and what exactly did it check?"** The type asks that question first.

## References

* [ADR 0026](0026-a-witness-interrogates-the-thing.md) — a witness interrogates the thing, never its
  neighbourhood. This ADR is its fourth and fifth instances, and its structural half.
* [ADR 0024](0024-every-governed-act-names-its-author.md) — no identity field may carry a default
  that names somebody. `pid: None` here is the same rule.
* [ADR 0019](0019-cockpit-agent-invocation-binding.md) §I1 — illegal states unrepresentable, the
  idiom `Verdict` borrows.
* `src/tessera/verdict.py` · `scripts/worktree_owner.py` · `tests/tooling.py`
* `tests/unit/test_verdict_debt.py` — the number, and the only way to lower it.
* `docs/status/witness-session-identity-run.md` — the run: the reproduction, the five mutation reds,
  and the second session that landed three commits in the tree while this was being written.
