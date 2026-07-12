#!/usr/bin/env python
"""Did this branch's work LAND? Answered by CONTENT, file by file — never by the graph.

2026-07-12, ratified doctrine: **sha ancestry is not landing.**

``git merge-base --is-ancestor`` answers *"is this SHA in main's history?"*. That is not the
question anyone actually asks, which is *"is this WORK on main?"* — and the two diverge the
moment a lane rebases or re-implements another's commits, which in this repo is routine.

The trap is perfect, and it cost us a live P1. Six of `claude/fix-ratchet-and-gdpr-identity`'s
seven commits had landed on main under **different shas**; the seventh — the GDPR erasure's
author — had not. `--is-ancestor` said "not merged" for **all seven**, so its answer *looked
like* an answer while hiding exactly which one was missing. The GDPR erasure stayed anonymous on
main for a day, on the most legally consequential act in the system.

So this tool refuses to look at the graph at all. For every file the branch touches, it compares
the branch's **blob** against main's, and reports the ones whose content is not there. Nothing
else tells the truth once work has been replayed under new shas.

Three verdicts, and the third is the one that matters:

* ``LANDED``    — the branch's version of the file is byte-identical on main.
* ``MISSING``   — main does not have this file at all.
* ``DIVERGED``  — main has it, with different content. This is the honest "I cannot tell you":
                  main may have moved on legitimately, or the branch's change may be absent.
                  It is reported, never silently counted as landed.

Usage:
    landed.py --branch claude/gdpr-actor-attribution [--base origin/main]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

#: Exit code when something the branch carries is not on the base. Distinct from 1 (the tool
#: itself failed) so a caller — a Makefile, a human — can tell "work is missing" from "I broke".
EXIT_NOT_LANDED = 4


def _git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


def _blob(ref: str, path: str) -> str | None:
    """The blob hash of ``path`` at ``ref``, or ``None`` when the file does not exist there."""
    code, out = _git("rev-parse", f"{ref}:{path}")
    return out.strip() if code == 0 else None


def touched_files(base: str, branch: str) -> list[str]:
    """Every file the branch's own commits touch — from the merge-base forward.

    This is the one place the graph is used, and only to enumerate *what to compare*: the
    merge-base tells us which files are the branch's business. The VERDICT on each of them is
    then taken from content alone. Using the graph to decide "landed?" is the mistake; using it
    to decide "which files did you touch?" is just reading the diff.
    """
    code, out = _git("diff", "--name-only", f"{base}...{branch}")
    if code != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def classify(base: str, branch: str, path: str) -> str:
    """``LANDED`` / ``MISSING`` / ``DIVERGED`` for one file — decided on blobs, not ancestry."""
    on_branch = _blob(branch, path)
    on_base = _blob(base, path)
    if on_branch is None:
        # The branch DELETES this file. It has landed iff the base no longer has it either.
        return "LANDED" if on_base is None else "DIVERGED"
    if on_base is None:
        return "MISSING"
    return "LANDED" if on_branch == on_base else "DIVERGED"


def main(argv: list[str] | None = None) -> int:
    """Exit 0 when every file's content is on the base; 4 when anything is missing or diverged."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)

    for ref in (args.base, args.branch):
        if _git("rev-parse", "--verify", "--quiet", ref)[0] != 0:
            sys.stderr.write(f"unknown ref: {ref!r}\n")
            return 1

    files = touched_files(args.base, args.branch)
    if not files:
        sys.stdout.write(f"{args.branch} touches nothing {args.base} does not already have.\n")
        return 0

    verdicts = {path: classify(args.base, args.branch, path) for path in files}
    not_landed = {p: v for p, v in verdicts.items() if v != "LANDED"}

    landed = len(files) - len(not_landed)
    sys.stdout.write(
        f"\n{args.branch} vs {args.base} — decided by CONTENT, file by file "
        f"(sha ancestry is not landing):\n\n"
        f"  {landed}/{len(files)} files have their content on {args.base}\n"
    )
    if not not_landed:
        sys.stdout.write("\n  Everything this branch carries is on the base. Safe to delete.\n")
        return 0

    sys.stdout.write(f"\n  {len(not_landed)} file(s) are NOT on {args.base}:\n\n")
    for path, verdict in sorted(not_landed.items(), key=lambda kv: (kv[1], kv[0])):
        sys.stdout.write(f"    {verdict:9s} {path}\n")
    sys.stdout.write(
        "\n  MISSING  = the base does not have this file at all.\n"
        "  DIVERGED = the base has it, with different content. That is not a verdict, it is an\n"
        "             honest 'I cannot tell you': the base may have moved on legitimately, or\n"
        "             this branch's change may simply be absent. Read the diff — do NOT delete\n"
        "             the branch on a DIVERGED alone.\n"
    )
    return EXIT_NOT_LANDED


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
