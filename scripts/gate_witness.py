#!/usr/bin/env python
"""The gate's witness: what tree did it run on, and did that tree hold still?

2026-07-12, process **P0**. Two ``make gate`` runs returned **exit 0** — on two *different
trees*. A concurrent agent had stashed the working changes and switched the worktree to its own
branch between the passes; the test counts differed (1862, then 1858) and nobody noticed,
because a gate reports a verdict and never says **what it looked at**. A later run showed 51
failures that belonged to the other agent's half-written code.

CI is billing-blocked, so the local gate is the *only* witness this project has. A witness that
cannot name what it saw is not a witness: its verdict is unfalsifiable. This module gives the
gate a subject, and makes twice-green a **machine assertion** instead of an operator's memory.

Usage (wired into the Makefile — never called by hand in normal work):

    gate_witness.py run --slot 1 -- make gate-py gate-web   # fingerprints, runs, records
    gate_witness.py twice                                    # refuses if the trees differ
    gate_witness.py fingerprint                              # print this tree's identity
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

#: Where a pass records what it saw. Gitignored: it is evidence about *this* checkout, and it
#: must never travel to another one — a fingerprint that could be committed would be a claim
#: about a tree the reader is not standing in.
RECORD_DIR = Path(".gate")

#: How much of the sha256 a human line shows. The full digest stays in the record.
_SHORT = 12

#: The exit code for VOID — the verdict is neither pass nor fail, it is *unusable*, because the
#: tree it describes did not exist for the whole run. Distinct from 1 (the gate genuinely
#: failed) on purpose: conflating them would let a void run be read as an honest red.
EXIT_VOID = 3

#: How far apart two passes of one `make gate-twice` may be recorded. Generous — a full gate
#: is minutes, and a slow machine running both passes back to back stays far inside it — but
#: finite, so a slot left over from a previous day can never be read as today's second pass.
_MAX_PASS_SEPARATION_S = 4 * 60 * 60


def _git(*args: str) -> str:
    """Run git and return stdout; ``""`` when git cannot answer.

    Never raises. A fingerprint is taken around a gate run, and an exploding fingerprint must
    not become the thing that fails the gate. A missing field degrades the identity — and a
    degraded identity is *visible in the record*, which is the entire point.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else ""


@dataclass(frozen=True, slots=True)
class TreeIdentity:
    """What a gate ran on — the subject of the verdict, recorded beside it."""

    worktree: str
    branch: str
    head: str
    dirty: bool
    dirty_files: int
    digest: str

    def line(self) -> str:
        """The one line printed next to the exit code, for a human in a hurry."""
        state = f"DIRTY({self.dirty_files})" if self.dirty else "clean"
        return (
            f"tree={self.digest[:_SHORT]} branch={self.branch} "
            f"head={self.head[:_SHORT]} {state} worktree={self.worktree}"
        )


def fingerprint() -> TreeIdentity:
    """Identify the tree as it is *right now*.

    Every part is load-bearing, and one of them is the whole lesson:

    * ``worktree`` — which checkout. Two worktrees on the same commit are different trees.
    * ``branch`` — the incident's actual mechanism: it was switched *under* the run.
    * ``head`` — the commit.
    * ``status`` + ``diff`` — the **content**. A commit id is not a tree, and "dirty" as a mere
      boolean would have read ``true`` both before and after the stash that removed 241 lines
      under an unchanged ``M src/tessera/guard/audit.py``. So the digest hashes the porcelain
      status *and* the patch of tracked modifications.

    Untracked files are captured by their *presence* in the status, not by their content. Said
    here rather than hidden: the identity is strong on tracked code, which is what a gate judges.
    """
    root = _git("rev-parse", "--show-toplevel") or str(Path.cwd())
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head = _git("rev-parse", "HEAD") or "(unknown)"
    status = _git("status", "--porcelain=v1", "--untracked-files=normal")
    diff = _git("diff", "HEAD")
    lines = sorted(ln for ln in status.splitlines() if ln.strip())

    payload = "\n".join([root, branch, head, *lines, diff])
    return TreeIdentity(
        worktree=root,
        branch=branch,
        head=head,
        dirty=bool(lines),
        dirty_files=len(lines),
        digest=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )


def describe_drift(before: TreeIdentity, after: TreeIdentity) -> list[str]:
    """Name what moved — one sentence per difference.

    A refusal that only says "the trees differ" sends the reader hunting. These are the
    incident's own symptoms, said out loud.
    """
    if before.digest == after.digest:
        return []
    reasons: list[str] = []
    if before.worktree != after.worktree:
        reasons.append(f"WORKTREE CHANGED: {before.worktree} → {after.worktree}")
    if before.branch != after.branch:
        reasons.append(
            f"BRANCH SWITCHED: {before.branch} → {after.branch} "
            "— another writer re-pointed this worktree"
        )
    if before.head != after.head:
        reasons.append(f"HEAD MOVED: {before.head[:_SHORT]} → {after.head[:_SHORT]}")
    if before.dirty_files != after.dirty_files:
        reasons.append(
            f"WORKING TREE CHANGED: {before.dirty_files} dirty file(s) → {after.dirty_files}"
        )
    if not reasons:
        # Same branch, same HEAD, same dirty-file COUNT — and a different digest. This is the
        # stash's signature: content rewritten in place. It is named explicitly because a coarser
        # check (branch + head + a dirty boolean) would have called these two trees identical.
        reasons.append(
            "CONTENT REWRITTEN IN PLACE: branch, HEAD and the dirty-file count are unchanged, "
            "but the files' contents are not — a stash, a checkout, or another agent's edit"
        )
    return reasons


def _record_path(slot: int) -> Path:
    return RECORD_DIR / f"pass-{slot}.json"


def _write(slot: int, payload: dict[str, Any]) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    _record_path(slot).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _read(slot: int) -> dict[str, Any] | None:
    try:
        raw: dict[str, Any] = json.loads(_record_path(slot).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw


def cmd_run(slot: int, command: list[str]) -> int:
    """Fingerprint, run the gate, fingerprint again, record — and VOID the run if the tree moved.

    Both fingerprints, deliberately. The incident happened **during** a pass, not only between
    passes, so an identity taken only at the start would certify a tree that no longer existed
    by the time the verdict printed.
    """
    before = fingerprint()
    proc = subprocess.run(command, check=False)
    after = fingerprint()

    drift = describe_drift(before, after)
    exit_code = EXIT_VOID if drift else proc.returncode

    _write(
        slot,
        {
            "slot": slot,
            "command": command,
            "gate_exit_code": proc.returncode,
            "verdict_exit_code": exit_code,
            "void": bool(drift),
            "drift": drift,
            # WHEN this pass ran. Without it, `twice` compared two records that could be days
            # apart and still call them one twice-green: `make gate` alone rewrites slot 1,
            # `gate-twice` never clears .gate/, and a stale slot 2 from Monday matched
            # Tuesday's tree exactly (same branch, same HEAD, same clean digest). Two green
            # passes on one tree, one of which did not happen today. Audit 2026-08-03.
            "recorded_at": time.time(),
            "tree_before": asdict(before),
            "tree_after": asdict(after),
        },
    )

    sys.stdout.write("\n")
    if drift:
        sys.stdout.write(
            f"[gate pass {slot}] VOID — the tree MOVED while the gate was running.\n"
            f"  the gate itself exited {proc.returncode}, and that number means nothing: it "
            f"describes a tree that no longer exists.\n"
        )
        for reason in drift:
            sys.stdout.write(f"    · {reason}\n")
        sys.stdout.write(f"  before: {before.line()}\n  after:  {after.line()}\n")
        sys.stdout.write(
            "  Fix: make sure you are the only writer in this worktree "
            "(`make claim`), then run the gate again.\n"
        )
    else:
        verdict = "GREEN" if exit_code == 0 else "RED"
        sys.stdout.write(f"[gate pass {slot}] {verdict} exit={exit_code}\n")
        sys.stdout.write(f"  {before.line()}\n")
    sys.stdout.flush()
    return exit_code


def cmd_twice() -> int:
    """Twice-green, asserted by machine: two GREEN passes **on one and the same tree**.

    The ritual always meant this. It was never checked, and under two writers it is theatre:
    the run that motivated this file had two green passes on two different trees, and read as
    a clean twice-green.
    """
    first, second = _read(1), _read(2)
    missing = [n for n, rec in ((1, first), (2, second)) if rec is None]
    if missing or first is None or second is None:
        sys.stderr.write(
            f"[twice-green REFUSED] no record for pass {missing} — "
            "run `make gate-twice`, which records each pass as it goes.\n"
        )
        return 1

    problems: list[str] = []
    for name, rec in (("pass 1", first), ("pass 2", second)):
        if rec.get("void"):
            problems.append(f"{name} is VOID — the tree moved while it ran: {rec.get('drift')}")
        elif rec.get("verdict_exit_code") != 0:
            problems.append(f"{name} is RED — exit {rec.get('verdict_exit_code')}")

    before_1 = TreeIdentity(**first["tree_before"])
    before_2 = TreeIdentity(**second["tree_before"])
    drift = describe_drift(before_1, before_2)
    if drift:
        problems.append("the two passes ran on DIFFERENT TREES")

    # ...and on the same OCCASION. A record with no clock let a leftover slot certify a run
    # that never happened: `make gate` alone rewrites slot 1, `gate-twice` never clears
    # `.gate/`, so yesterday's slot 2 matched today's tree exactly and `twice` reported
    # TWICE-GREEN over a single pass. Same shape as the drift bug, on the time axis.
    stamps = [rec.get("recorded_at") for rec in (first, second)]
    if any(not isinstance(s, int | float) for s in stamps):
        problems.append(
            "a pass carries no recorded_at — it predates this check; re-run `make gate-twice`"
        )
    else:
        apart = abs(float(stamps[1]) - float(stamps[0]))  # type: ignore[arg-type]
        if apart > _MAX_PASS_SEPARATION_S:
            problems.append(
                f"the two passes are {apart / 3600:.1f} h apart (max "
                f"{_MAX_PASS_SEPARATION_S / 3600:.0f} h) — this is a stale slot, not a "
                "twice-green; run `make gate-twice`"
            )

    if not problems:
        sys.stdout.write(f"\n[TWICE-GREEN] both passes green, on ONE tree.\n  {before_1.line()}\n")
        return 0

    sys.stderr.write("\n[TWICE-GREEN REFUSED]\n")
    for problem in problems:
        sys.stderr.write(f"  · {problem}\n")
    for reason in drift:
        sys.stderr.write(f"      {reason}\n")
    if drift:
        sys.stderr.write(
            f"  pass 1 ran on: {before_1.line()}\n  pass 2 ran on: {before_2.line()}\n"
            "  Two green passes on two different trees are NOT a twice-green. That is exactly "
            "the failure this check exists for: on 2026-07-12 it read as a clean twice-green "
            "and it was not one.\n"
        )
    sys.stderr.flush()
    return 1


def main(argv: list[str] | None = None) -> int:
    """Exit code is the verdict. ``3`` means VOID — unusable, not merely red."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fingerprint", help="print this tree's identity")

    run = sub.add_parser("run", help="fingerprint, run a command, fingerprint, record")
    run.add_argument("--slot", type=int, required=True, choices=(1, 2))
    run.add_argument("command", nargs=argparse.REMAINDER)

    sub.add_parser("twice", help="assert both recorded passes are green ON THE SAME TREE")

    args = parser.parse_args(argv)

    if args.cmd == "fingerprint":
        sys.stdout.write(fingerprint().line() + "\n")
        return 0
    if args.cmd == "twice":
        return cmd_twice()

    command = [a for a in args.command if a != "--"]
    if not command:
        parser.error("run: a command is required after `--`")
    return cmd_run(args.slot, command)


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
