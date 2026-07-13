#!/usr/bin/env python
"""`main` may not be advanced past a remote nobody looked at.

On 2026-07-13, `main` **forked**. Two lanes, one base:

    5a0e9065 ──┬── 34b59c0d   origin/main   (+10, the eval lane, pushed)
               └── c6a2048c   main          (+15, the witness lane, never pushed)

Neither is an ancestor of the other. No fast-forward exists in either direction, and the repo's
trunk-based convention — *one long-lived branch, `main`, advanced only by fast-forward* — was not
violated by a bad merge. It was violated by **nobody asking**. Each lane advanced *its own* `main`
from a base it believed was current, and the belief was a **cached ref**.

The rule "only one agent touches `main`" was written down, and it is a **social** rule. Social rules
have now failed to stop *every* instance in this repository's short history of green lights over
holes: the gate that read a pipeline's last line, the guard that checked a name in a list, the
server that asked git about a directory, the `claim` that asked the *directory* who was writing,
and the `dev-status` that printed `CANNOT SAY` and exited 0. Each was, at the time, "obviously fine
because we all know the rule".

So this one is mechanical, and it is one sentence:

> **`origin/main` must be an ancestor of whatever `main` is about to become.**

If the remote has commits you do not have, your `main` cannot legally move: you would be building a
second trunk. The refusal is not advice, it is `exit 2`, and `.githooks/reference-transaction` fires
it on **any** update to `refs/heads/main` — a `git merge --ff-only`, a bare `git merge`, a `git
commit` straight onto the branch, a `git reset`. Not a Makefile target somebody has to remember to
use: the fork was *made of* somebody not remembering.

.. rubric:: And it asks the REMOTE, not the ref that is named after it

This is the whole of [ADR 0026](../docs/decisions/0026-a-witness-interrogates-the-thing.md), and it
is very easy to get wrong here, because git hands you a ref that *looks* like the answer:

    git merge-base --is-ancestor refs/remotes/origin/main HEAD     # ← WRONG

`refs/remotes/origin/main` is **a local cache of a remote fact**. It is the neighbourhood. It is
exactly as fresh as your last `git fetch`, which — in the incident this file exists for — was *the
thing nobody did*. A guard that consults the cache would have said "all clear" to both lanes, twice,
with total composure, because both caches were stale in exactly the way that mattered.

So the guard runs `git ls-remote`. It asks the **remote** where its `main` is, over the wire, every
time. It is slower. It is correct.

.. rubric:: And it fails CLOSED

If the remote cannot be reached — offline, credentials, a hung network — the answer is **not**
"probably nothing moved". That sentence is the bug, in its purest and most tempting form: it is
`CannotSay` dressed as `Ok`, and it exits 2. *A witness that cannot see may never report "ok".*

Exit codes: ``0`` the advance is legal · ``2`` refused, or unknowable.
Escape hatch: ``TESSERA_MAIN_GUARD_BYPASS=1`` — deliberate, loud, and it says so in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

from tessera.verdict import CannotSay, NotOk, Ok, Verdict, exit_code, render

#: The trunk. The only branch this guard has an opinion about.
TRUNK: Final = "main"

#: The hook whose exit code aborts a ref transaction on `refs/heads/main`.
HOOK: Final = "reference-transaction"

#: The tracked source of that hook. What is *installed* is a COPY of this, and the copy is the
#: thing git runs — so the copy is what gets interrogated, never this.
HOOK_SOURCE: Final = Path(".githooks") / HOOK

#: The remote whose `main` is the truth. Not the local ref that is named after it.
REMOTE: Final = "origin"

#: Set it to take `main` somewhere the remote does not agree with. It is a decision, so it is
#: spelled out in the output — never a silent pass.
BYPASS_ENV: Final = "TESSERA_MAIN_GUARD_BYPASS"

#: `git ls-remote` talks over the network. A guard that hangs is a guard people rip out.
_TIMEOUT_S: Final = 20.0

#: A ref update whose old value is all-zeros is a *creation* (clone, initial fetch). Nothing to
#: protect: there is no history to fork.
_ZERO: Final = "0" * 40


def _git(*args: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def remote_trunk() -> str | None:
    """Where the REMOTE's `main` actually is, asked of the remote. ``None`` when it will not say.

    Deliberately **not** ``git rev-parse refs/remotes/origin/main``. That ref is a photograph of
    the remote taken at the time of your last fetch, and in the incident this file exists for, the
    last fetch was the event that did not happen. A photograph of a room is not the room.

    ``None`` is an answer — *"I could not look"* — and its caller turns it into a refusal, never
    into a pass.
    """
    try:
        proc = _git("ls-remote", "--heads", REMOTE, TRUNK, timeout=_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    line = proc.stdout.strip()
    if not line:
        # The remote answered, and it has no `main`. That is a fact, not a silence — a fresh
        # repository. It is distinguished from "could not ask" by the empty string, and the
        # caller treats the two differently, because they ARE different.
        return ""
    return line.split()[0]


def _is_ancestor(older: str, newer: str) -> bool | None:
    """Is ``older`` in ``newer``'s history? ``None`` when git cannot tell (an unknown object).

    `--is-ancestor` exits 0 for yes, 1 for no, and something else when it could not answer — and
    the third case is the one that matters: after a `git fetch`, the remote's tip is a real object
    locally; without one, it is not, and asking about an object you do not have must not read as
    "no, it is not an ancestor" (which would produce a *false refusal*, and a false red is the same
    disease as a false green).
    """
    proc = _git("merge-base", "--is-ancestor", older, newer)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def _behind(remote_tip: str, local_tip: str) -> int | None:
    """How many commits the remote has that ``local_tip`` does not. ``None`` if git cannot count."""
    proc = _git("rev-list", "--count", f"{local_tip}..{remote_tip}")
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def check_advance(new_tip: str) -> Verdict:
    """May `main` legally become ``new_tip``?

    Args:
        new_tip: The commit `main` is about to point at.

    Returns:
        ``Ok`` when the remote's `main` is contained in ``new_tip`` — the advance keeps one trunk.
        ``NotOk`` when the remote has commits ``new_tip`` does not: taking it would create a second.
        ``CannotSay`` when the remote could not be asked. **This is a refusal**, deliberately: the
        alternative is to assume nothing moved, which is precisely what forked `main`.
    """
    if os.environ.get(BYPASS_ENV, "").strip() not in ("", "0"):
        return Ok(
            f"{BYPASS_ENV} is set — the guard was told to stand down, and it is saying so out loud "
            f"rather than passing quietly. `{TRUNK}` → {new_tip[:12]} was NOT checked against "
            f"{REMOTE}."
        )

    remote_tip = remote_trunk()
    if remote_tip is None:
        return CannotSay(
            f"I could not ask {REMOTE} where `{TRUNK}` is (`git ls-remote` did not answer).\n"
            f"  I will NOT assume it has not moved. That assumption is what forked `{TRUNK}` on "
            "2026-07-13: two lanes, one base, neither aware of the other, no fast-forward left in "
            "either direction.\n"
            f"  Get the network back, or take the branch deliberately: {BYPASS_ENV}=1"
        )

    if remote_tip == "":
        return Ok(f"{REMOTE} has no `{TRUNK}` — there is no trunk to fork. Nothing to protect yet.")

    ancestor = _is_ancestor(remote_tip, new_tip)
    if ancestor is None:
        return CannotSay(
            f"{REMOTE}'s `{TRUNK}` is {remote_tip[:12]}, and I do not have that object locally, so "
            "I cannot tell whether your history contains it.\n"
            f"  `git fetch {REMOTE}` and try again. (An object I have never seen is not the same "
            "fact as an object that is not an ancestor, and reading one as the other would be a "
            "FALSE REFUSAL — which trains you to ignore refusals.)"
        )

    if ancestor:
        return Ok(
            f"`{TRUNK}` → {new_tip[:12]} contains {REMOTE}/{TRUNK} ({remote_tip[:12]}), asked of "
            f"{REMOTE} just now. One trunk, still."
        )

    behind = _behind(remote_tip, new_tip)
    count = "some" if behind is None else str(behind)
    return NotOk(
        f"REFUSED — this would fork `{TRUNK}`.\n"
        f"  {REMOTE}/{TRUNK} is {remote_tip[:12]} (asked of {REMOTE} just now, not read from the "
        "local cache).\n"
        f"  It carries {count} commit(s) that {new_tip[:12]} does not, so `{TRUNK}` would become a "
        "SECOND trunk and no fast-forward would exist in either direction.\n"
        "  That is not a hypothetical. It happened on 2026-07-13, exactly here, and cost a day:\n"
        "      5a0e9065 ──┬── 34b59c0d  origin/main   (+10)\n"
        "                 └── c6a2048c  main          (+15)\n"
        f"  Fix it before you move `{TRUNK}`:\n"
        f"      git fetch {REMOTE}\n"
        f"      # then rebase or merge YOUR branch onto {REMOTE}/{TRUNK}, gate it, and land that.\n"
        f"  Or take it deliberately, and own it: {BYPASS_ENV}=1"
    )


_INSTALL: Final = "make hooks"


def check_installed() -> Verdict:
    """**Is the guard actually RUNNING in this tree?** — the question the guard forgot to ask.

    An uninstalled guard is not a weak guard. It is **a witness that does not run**: it refuses
    nothing at all, and it protects only the trees that opted in — and *the fork was made of not
    opting in*. The first version of this file shipped a hook and never checked that git would ever
    reach it, which is the same shape as `dev-status` printing ``⚠ STALE`` and returning ``0``:
    **publishing a verdict is not enforcing it.**

    So the question is asked of **git**, not of the config:

        git rev-parse --git-path hooks/reference-transaction

    That is git's *own* answer to "where would I look for this hook?" — it honours
    ``core.hooksPath``, the common-dir redirect for linked worktrees, everything. Reading
    ``core.hooksPath`` ourselves and re-deriving the path would be re-implementing git's
    resolution and then trusting our copy of it: the neighbourhood, once more.

    And the file found there is **hashed against the tracked source**. The installed hook is a
    *copy*; a copy drifts, and what git runs is the copy. A guard that verified the repository's
    `.githooks/` file while git ran a stale copy from `.git/hooks/` would be checking a thing nobody
    executes.

    Returns:
        ``Ok`` with the path git resolved and the digest it matched. ``NotOk`` when the hook is
        absent, unreadable, not executable, or not ours — we looked, and it is not there.
        ``CannotSay`` when git itself would not answer.
    """
    proc = _git("rev-parse", "--path-format=absolute", "--git-path", f"hooks/{HOOK}")
    if proc.returncode != 0 or not proc.stdout.strip():
        return CannotSay(
            f"git will not say where it looks for the `{HOOK}` hook "
            f"(`git rev-parse --git-path` exited {proc.returncode}), so I cannot tell whether the "
            "trunk is guarded at all. A blind spot is not a pass."
        )
    installed = Path(proc.stdout.strip())

    source = Path(_git("rev-parse", "--show-toplevel").stdout.strip() or ".") / HOOK_SOURCE
    if not source.is_file():
        return CannotSay(
            f"{HOOK_SOURCE} is not in this checkout, so I have nothing to compare the installed "
            "hook against. Check out a branch that carries the guard."
        )
    want = hashlib.sha256(source.read_bytes()).hexdigest()

    if not installed.is_file():
        return NotOk(
            f"THE TRUNK IS UNGUARDED. git would run `{installed}` on every update to "
            f"refs/heads/{TRUNK}, and that file does not exist — so nothing would stop a "
            f"`git merge --ff-only` from forking `{TRUNK}`, which is exactly what happened on "
            "2026-07-13.\n"
            f"  An uninstalled guard is a WITNESS THAT DOES NOT RUN. Install it:  {_INSTALL}"
        )
    if not os.access(installed, os.X_OK):
        return NotOk(
            f"`{installed}` is not executable, and **git skips a non-executable hook in silence** "
            f"— so the trunk is unguarded and nothing anywhere says so.  {_INSTALL}"
        )

    got = hashlib.sha256(installed.read_bytes()).hexdigest()
    if got != want:
        return NotOk(
            f"the hook git would run is NOT the one this checkout ships.\n"
            f"  git runs : {installed}  (sha256 {got[:12]})\n"
            f"  we ship  : {source}  (sha256 {want[:12]})\n"
            "  The installed hook is a COPY, and a copy drifts. What git executes is the copy, so "
            f"the copy is what must be right.  {_INSTALL}"
        )

    return Ok(f"git runs {installed} on refs/heads/{TRUNK}; it is ours (sha256 {got[:12]})")


def _publish(verdict: Verdict) -> int:
    stream = sys.stdout if isinstance(verdict, Ok) else sys.stderr
    stream.write(f"\n[main-guard] {render(verdict)}\n")
    stream.flush()
    return exit_code(verdict)


def main(argv: list[str] | None = None) -> int:
    """Exit code is the verdict. ``2`` = do not proceed — refused, or unknowable.

    Two subcommands, and the second exists because the first was useless without it:

    * ``advance <new-tip>`` — may `main` become this? Called by ``.githooks/reference-transaction``
      on **any** update to ``refs/heads/main``, and by `make land`.
    * ``installed`` — **is the hook actually wired up in this tree?** Called by `make gate` and
      `make claim`, which REFUSE when it is not. A guard nobody installed is a decoration, and
      this repository has spent a week learning that a verdict which is published but not
      *enforced* is worth nothing at all.
    """
    parser = argparse.ArgumentParser(description="Keep there being exactly one trunk.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    advance = sub.add_parser("advance", help="may `main` become this commit?")
    advance.add_argument("tip", help="the commit `main` is about to point at")
    sub.add_parser("installed", help="is the trunk guard actually running in this tree?")

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.cmd == "installed":
        return _publish(check_installed())

    if args.tip == _ZERO:  # a creation, or a deletion. There is no history here to fork.
        return 0
    return _publish(check_advance(args.tip))


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
