#!/usr/bin/env python
"""Who owns this worktree? Until 2026-07-12, nothing in this repo could answer.

`make dev-status` tells you which checkout a **server** is serving. Nothing told you which
agent owns a **tree** — and on 2026-07-12 two agents wrote into `agents/claude` at once. One
of them stashed the other's uncommitted work (politely, with restore instructions, having
correctly judged it *"NOT MINE"*), switched the worktree to its own branch, and left. The
consequence was silent and expensive: two `make gate` runs returned exit 0 on two different
trees, 51 failures were attributed to the wrong author, and a commit landed on a stranger's
branch.

The marker is deliberately **advisory, not a lock**: it declares an owner and refuses a
mutating command from anyone else, but it does not pretend to enforce anything against a
process that ignores it (nothing in a shared filesystem can). Its job is to turn a silent
collision into a loud one — which is all that was missing.

Identity comes from ``TESSERA_AGENT``, falling back to the worktree's directory name, because
the repo topology already names its agents that way (`agents/claude`, `agents/codex`, …).

Usage:

    worktree_owner.py claim            # I am working here
    worktree_owner.py check            # refuse (exit 2) if someone else owns this tree
    worktree_owner.py release          # I am done
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Gitignored, at the worktree root. It describes THIS checkout and must never travel to
#: another one — an owner marker that could be committed would claim every clone at once.
MARKER = ".worktree-owner"

#: Refusal. Distinct from 1 so a caller can tell "you do not own this tree" from "the command
#: failed", which matters when the caller is a Makefile.
EXIT_NOT_YOURS = 2


def _worktree_root() -> Path:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return Path.cwd()
    root = proc.stdout.strip()
    return Path(root) if proc.returncode == 0 and root else Path.cwd()


def whoami() -> str:
    """This agent's name: ``TESSERA_AGENT``, else the worktree's directory name.

    The fallback is not a guess — it is the repo's own topology (`agents/<name>/`), so an agent
    that never sets the variable still gets a stable, meaningful identity rather than "unknown".
    """
    declared = os.environ.get("TESSERA_AGENT", "").strip()
    return declared or _worktree_root().name


def _marker_path() -> Path:
    return _worktree_root() / MARKER


def read_owner() -> dict[str, Any] | None:
    """The current owner record, or ``None`` when the tree is unclaimed."""
    try:
        raw: dict[str, Any] = json.loads(_marker_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw


def cmd_claim(*, force: bool) -> int:
    """Declare this agent the owner. Refuses to steal a tree someone else holds."""
    me = whoami()
    current = read_owner()
    if current and current.get("agent") not in (me, None) and not force:
        sys.stderr.write(
            f"[worktree REFUSED] {_worktree_root()} is owned by "
            f"{current.get('agent')!r} since {current.get('claimed_at')}.\n"
            "  Use another worktree, or --force if you know that owner is gone.\n"
        )
        return EXIT_NOT_YOURS

    _marker_path().write_text(
        json.dumps(
            {
                "agent": me,
                "pid": os.getpid(),
                "claimed_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "worktree": str(_worktree_root()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"[worktree] {_worktree_root()} is now owned by {me!r}\n")
    return 0


def cmd_check() -> int:
    """Exit 0 if this tree is unclaimed or mine; exit 2 — loudly — if it belongs to someone else.

    This is what a mutating target calls before it touches anything. An UNCLAIMED tree is
    allowed on purpose: the marker must not become a ceremony that stops the operator's own
    hands. What it stops is the *silent* second writer.
    """
    me = whoami()
    current = read_owner()
    if current is None:
        sys.stdout.write(f"[worktree] {_worktree_root()} is unclaimed — proceeding as {me!r}\n")
        return 0
    owner = current.get("agent")
    if owner == me:
        return 0
    sys.stderr.write(
        f"\n[worktree REFUSED] you are {me!r}; {_worktree_root()} is owned by {owner!r} "
        f"(since {current.get('claimed_at')}, pid {current.get('pid')}).\n"
        "  An agent does not mutate a worktree it does not own. On 2026-07-12 two agents wrote\n"
        "  into one tree: work was stashed mid-flight, a commit landed on the wrong branch, and\n"
        "  TWO `make gate` runs returned exit 0 on TWO DIFFERENT TREES.\n"
        "  Use your own worktree, or take this one deliberately: `make claim FORCE=1`.\n"
    )
    return EXIT_NOT_YOURS


def cmd_release() -> int:
    """Give the tree back. Silent when it was not claimed — releasing twice is not an error."""
    path = _marker_path()
    current = read_owner()
    me = whoami()
    if current and current.get("agent") not in (me, None):
        sys.stderr.write(
            f"[worktree REFUSED] {path.parent} is owned by {current.get('agent')!r}, not {me!r} "
            "— releasing another agent's claim is exactly the move this file exists to stop.\n"
        )
        return EXIT_NOT_YOURS
    path.unlink(missing_ok=True)
    sys.stdout.write(f"[worktree] {path.parent} released by {me!r}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Exit code is the verdict. ``2`` means: this tree is not yours."""
    parser = argparse.ArgumentParser(description="Declare and check worktree ownership.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    claim = sub.add_parser("claim", help="declare this agent the owner")
    claim.add_argument("--force", action="store_true", help="take a tree another agent holds")
    sub.add_parser("check", help="exit 2 if another agent owns this tree")
    sub.add_parser("release", help="give the tree back")

    args = parser.parse_args(argv)
    if args.cmd == "claim":
        return cmd_claim(force=args.force)
    if args.cmd == "release":
        return cmd_release()
    return cmd_check()


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
