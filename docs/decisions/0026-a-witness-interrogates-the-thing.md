# 26. A witness interrogates the thing, never its neighbourhood

Date: 2026-07-13

## Status

Accepted. The methodological twin of [ADR 0024](0024-every-governed-act-names-its-author.md).
0024 governs what the system **records** about an act; this one governs what the system's
**guard-rails are allowed to accept as evidence** about themselves. Neither supersedes the other,
and both were discovered the same way: by finding a green light over a hole.

## Context

Three times in one week, a guard-rail reported success while the thing it guarded was broken.
Each was fixed locally, and each fix carried, in its own comment, a sentence that turns out to be
the same sentence. They are one finding.

| | what we believed we were measuring | what we were actually measuring |
|---|---|---|
| **The gate** | whether the checks passed | **the last line printed by a pipeline.** `git merge 2>&1 \| tail -1` shows `Updating a..b` — on *stdout* — while the error went to *stderr* and the pipe ate the exit code. `$PIPESTATUS[0]` is **empty in zsh**. Two greens, neither of which had looked at a status. |
| **A guard** | whether a route refused a stranger | **whether a function's name was in a list.** `require_bearer` sat in `KNOWN_AUTH_GUARDS`, so the ratchet written to forbid the anonymous writer *certified* `DELETE /memory/{id}` — the erasure of any subject's memory — as guarded. Measured on `main`: an anonymous caller received **204 No Content**. Membership of that list had been asserted by **nobody**. |
| **A server** | which code it was running | **the git head of its working directory.** `make dev-status` did `lsof` → the process's `cwd` → `git -C "$cwd" rev-parse HEAD`, and printed it in a column labelled `git`. On 2026-07-13 the operator's backend had booted at 23:56 the previous night — before the ledger fix landed — and `dev-status` printed the sha **of the fix**. His browser paid 1 087 ms for a badge that costs 20 ms, and every witness on the machine said all was well. |

In every case the witness asked a question **adjacent** to the one it claimed to answer, and the
adjacency held right up until the moment it mattered. A pipeline's last line usually does track
its exit code. A guard's name usually does track what it guards. A directory's head usually does
track what the process in it loaded. **Usually** is what a guard-rail exists to not depend on.

Two earlier lots had already found the same shape and closed it without naming it:

* the audit-sink ratchet enumerates the sinks with `typing.get_args(_Sink)` — **from the type,
  not from a hand-maintained list**, so a sink added tomorrow is swept in and one that forgets its
  obligation cannot pass by being absent from a list nobody maintained;
* the PII canary sweep **reads the response payload** rather than reviewing the code that builds
  it — it found three leaks a human review had passed. *The payload is the judge.*

So the rule already exists in this codebase, three times, each time rediscovered locally and
written down in a comment. This ADR names it once.

## Decision

> **A witness interrogates the thing, never its neighbourhood.**

Concretely, and these are the four forms it has taken so far:

1. **A gate reports its own exit code** — not the output of the command it ran, not the last line
   of a pipeline, not what an `echo` afterwards happened to print.
2. **A guard is what refuses a stranger** — not what appears in a list of guards. The list is a
   claim; the refusal is the fact. So every member of the list is *called with the request a
   stranger actually sends* and must refuse it.
3. **A server states which code it loaded** — not what is in the directory it happens to run from.
   The statement is captured **when the code is loaded** and frozen, because a value recomputed
   later describes the disk, and the disk is not the process.
4. **A contract is what it honours** — not what it declares. A schema is checked against a real
   payload; a level is computed from observed evidence, never asserted.

And the corollary that makes it operational, because the failure is not usually a wrong answer —
it is a **confident answer to a question nobody asked**:

> **A witness that cannot see must report a blind spot. It may never report "ok".**

`None` is an answer. `"unknown"` is an answer. A default that reads like knowledge is a lie, and
this is exactly [ADR 0024](0024-every-governed-act-names-its-author.md)'s rule about identity
fields, arriving from the other direction: *there, no act may be recorded without naming its
author; here, no verdict may be published without naming what it actually examined.*

## Enforcement

A doctrine that only lives in an ADR is a preference. Each clause is a test that fails.

| clause | where it is enforced | mutation that must turn it red |
|---|---|---|
| the gate reports its own exit code | `scripts/gate_witness.py` — the tree fingerprint is taken **before and after** the run and the verdict is VOID (exit 3, deliberately not the red 1) if the tree moved underneath it | run two passes on two trees and claim twice-green |
| a guard refuses a stranger | `tests/unit/test_mutation_routes_carry_auth.py` — every member of `IDENTITY_GUARDS` is **called** with the request a stranger sends, and must refuse | put a provenance-only guard back in the set: it fails on the spot |
| a server states what it loaded | `tests/unit/test_code_identity.py` — a source file is slipped into the package while the process runs; the identity it reports must **not move**, while the live re-hash of the same directory **must** | make `identity()` recompute ("it's cheap"): two tests go red |
| a witness reports its blind spots | same file — a server that publishes no digest must be reported as **CANNOT SAY · RESTART**, never as `ok` | return a green tick for a silent server: red |
| `make dev-status` may not re-derive a sha from a directory | same file — the Makefile recipe is read and must contain no `rev-parse` | put `git rev-parse` back into the recipe: red |

## Consequences

**We lose the cheap answer.** Asking the thing is more work than asking its neighbourhood: the
server had to be given an identity it did not have; the guard list had to become a set of calls;
the gate had to fingerprint its own tree twice per run. Every one of these was, at the time it was
skipped, "obviously equivalent".

**We gain a witness that can be wrong out loud.** The three incidents above share one property
that made them expensive: none of them *failed*. They all reported success. A witness that can
only be right is indistinguishable from a witness that is not looking, and this project's local
gate is — with CI billing-blocked — its **only** witness.

**The unknown becomes visible, and that is a feature.** `code_sha: null` in a container without a
build stamp, `dirty: null` when `git status` did not answer, `CANNOT SAY` for a server that
predates this ADR: each of these is a hole the operator can now see. Before, every one of them
rendered as a confident value, and the confidence was the bug.

**What this does NOT claim.** The class is not closed by construction — nothing structurally
prevents the fourth instance of "ask the neighbourhood" from being written tomorrow, because the
pattern is semantic, not syntactic. What is enforced is the three known instances, plus the shape
to look for. When the fourth appears, it will appear the same way the first three did: as a green
light over a hole, found by someone who checked the thing itself.

## References

* [ADR 0023](0023-audit-chain-independent-of-sink.md) — no transport may disable the store; the
  sink list is derived from the type, never maintained by hand.
* [ADR 0024](0024-every-governed-act-names-its-author.md) — every governed act names its author
  (verified) and its reason (declared); an identity field may not have a default that names
  somebody.
* `docs/status/perf-fleet-run.md` — the 2026-07-13 measurements: how a stale process and a
  confident witness cost 1 087 ms on every cockpit page for a day.
* `src/tessera/code_identity.py` — the process's own account of what it loaded.
* `tests/unit/test_mutation_routes_carry_auth.py` — "A guard is what refuses a stranger",
  written before this ADR existed, and the reason it does.
