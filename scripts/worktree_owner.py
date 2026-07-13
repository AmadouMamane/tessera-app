#!/usr/bin/env python
"""Who is working in this worktree? Not *which role* — **which session**.

The first version of this file (2026-07-12) was written to stop two agents writing into one tree.
It could not, and the reason is the fourth instance of [ADR 0026](
../docs/decisions/0026-a-witness-interrogates-the-thing.md), sitting inside the very instrument
built to police the third:

    def whoami() -> str:
        "This agent's name: TESSERA_AGENT, else THE WORKTREE'S DIRECTORY NAME.
         The fallback is not a guess — it is the repo's own topology (agents/<name>/)"

It is not a guess. It is worse: it is a **confident answer to a question nobody asked**. The
question is *"who is writing here?"* and the answer given is *"what is this directory called?"*
The topology names a **role** — `claude`, `codex`, `antigravity` — and a role is not a writer.
On 2026-07-13, **seven** live Claude sessions had their working directory in `agents/claude/`.
Every one of them resolved to the owner `"claude"`, read the marker, **found its own name in it,
and concluded it was home.** The marker refused nobody. It never had.

And the ``pid`` it recorded was the pid of the ephemeral ``python worktree_owner.py claim``
subprocess — a process that is **dead one second after the marker is written**. A liveness field
guaranteed to be false, which is how you build a staleness check that reports every tree as
abandoned. That is the same bug twice in eighteen lines: both fields described the *neighbourhood*
of the writer (its directory, its helper process) and neither described the writer.

So:

* **Identity is ASSERTED BY THE SESSION, never derived from a path.** ``TESSERA_SESSION_ID`` — a
  value only the session can know, because only the session exists long enough to know it. It is
  never defaulted, never inferred, never minted per-invocation (a fresh uuid on every ``make``
  would make each command its own "session", and the tool would refuse *itself*).
* **A caller with no session identity is a blind spot, and blind spots do not get to pass.**
  Not "unclaimed, proceeding" — that is the sentence that was already wrong. It is
  :class:`~tessera.verdict.CannotSay`, and it exits 2. *A witness that cannot see may never report
  "ok"* — the corollary this repo wrote down, and then, one file over, did not obey.
* **The role survives, for the human.** ``role`` is in the marker so an operator reading it sees
  ``claude`` and knows which lane. It **decides nothing**. Only ``session_id`` decides.
* **A stale marker is a fact to STATE**, not to ignore and not to silently overwrite: *previous
  owner: session <id>, role <r>, pid <n>, gone, held since <t> — `make claim FORCE=1` to take it.*

Advisory, not a lock — deliberately, and that choice is right: nothing on a shared filesystem
truly locks, and a ceremony that stops the operator's own hands would be worked around within a
day. What an advisory owes you is the **truth**. This one now tells it.

Usage:

    worktree_owner.py session          # mint a session id (eval "$(make session)")
    worktree_owner.py claim [--force]  # I am working here
    worktree_owner.py check            # refuse (exit 2) if this tree is not verifiably mine
    worktree_owner.py release          # I am done
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tessera.verdict import CannotSay, NotOk, Ok, Verdict, exit_code, render

#: Gitignored, at the worktree root. It describes THIS checkout and must never travel to another
#: one — an owner marker that could be committed would claim every clone at once.
MARKER: Final = ".worktree-owner"

#: The session's own assertion of who it is. The ONLY field that decides anything here.
SESSION_ENV: Final = "TESSERA_SESSION_ID"

#: The session's pid, if the session cares to declare it. Optional, and `None` when it does not:
#: an honest gap beats `os.getpid()`, which would name a process that dies with the claim.
SESSION_PID_ENV: Final = "TESSERA_SESSION_PID"

#: The human-facing lane (`claude`, `codex`, …). Recorded for a human's eyes. Decides NOTHING.
ROLE_ENV: Final = "TESSERA_AGENT"


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


def session_id() -> str | None:
    """This session's asserted identity, or ``None`` — which is an ANSWER, not a gap to be filled.

    There is deliberately no fallback. Every fallback available here (the directory, the pid, the
    tty, the user) names something *adjacent* to the session, and adjacency is the whole bug.
    """
    return os.environ.get(SESSION_ENV, "").strip() or None


def role() -> str:
    """The human-readable lane. For the operator's eyes only — this value decides NOTHING.

    It keeps the directory-name fallback on purpose: as a *label* it was always fine. It was only
    ever a catastrophe as an *identity*.
    """
    return os.environ.get(ROLE_ENV, "").strip() or _worktree_root().name


def session_pid() -> int | None:
    """The session's pid *as the session declares it*, or ``None``.

    Never ``os.getpid()``. This module runs in a subprocess that exits immediately, so its own pid
    is a fact about a corpse. The old marker recorded exactly that.
    """
    raw = os.environ.get(SESSION_PID_ENV, "").strip()
    try:
        return int(raw)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class Claim:
    """A tree's owner, as recorded in the marker."""

    #: The identity that decides. Absent in markers written before 2026-07-13 — see `read_owner`.
    session_id: str
    #: The lane, for a human. Never compared.
    role: str
    #: The session's pid, if it declared one. ``None`` = "it did not say", never a fabricated value.
    pid: int | None
    claimed_at: str
    host: str
    worktree: str


def _marker_path() -> Path:
    return _worktree_root() / MARKER


def read_owner() -> Claim | None:
    """The current owner, or ``None`` when the tree is genuinely unclaimed.

    A marker written by the old code has an ``agent`` key and no ``session_id``. It is NOT
    silently upgraded: it names a role, and a role cannot tell us whether the writer is you. It is
    returned with ``session_id=""``, which no live session can ever match — so it lands in
    :func:`check` as a blind spot, which is exactly what it is.
    """
    try:
        raw: dict[str, Any] = json.loads(_marker_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    pid = raw.get("pid")
    return Claim(
        session_id=str(raw.get("session_id") or ""),
        role=str(raw.get("role") or raw.get("agent") or "(unnamed)"),
        pid=pid if isinstance(pid, int) else None,
        claimed_at=str(raw.get("claimed_at") or "(unknown)"),
        host=str(raw.get("host") or "(unknown)"),
        worktree=str(raw.get("worktree") or ""),
    )


def _process_alive(pid: int | None) -> bool | None:
    """Is that pid running? ``None`` when we cannot know — including "it never told us".

    ``os.kill(pid, 0)`` cannot distinguish the original process from a recycled pid, and this is
    said out loud rather than papered over: liveness here is a *hint* for a human deciding whether
    to ``--force``, never grounds for the tool to take a tree by itself.
    """
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive, owned by another user
    except OSError:
        return None
    return True


_MINUTE: Final = 60
_HOUR: Final = 60 * _MINUTE
_DAY: Final = 24 * _HOUR


def _age(claimed_at: str) -> str:
    """How long ago, in words. ``"an unknown time"`` when the stamp cannot be read."""
    try:
        then = datetime.fromisoformat(claimed_at)
    except ValueError:
        return "an unknown time"
    seconds = int((datetime.now(UTC) - then).total_seconds())
    if seconds < _MINUTE:
        return f"{seconds}s"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h{(seconds % _HOUR) // _MINUTE:02d}"
    return f"{seconds // _DAY}d"


def _liveness(claim: Claim) -> str:
    """The owner's process, described honestly — including when it is not described at all."""
    match _process_alive(claim.pid):
        case True:
            return f"pid {claim.pid} is ALIVE"
        case False:
            return f"pid {claim.pid} is GONE (dead for at most {_age(claim.claimed_at)})"
        case _:
            return "liveness UNKNOWN — that session declared no pid"


def _describe(claim: Claim) -> str:
    """One line naming the holder: everything a human needs to decide whether to take the tree."""
    who = claim.session_id or "(a session that did not name itself)"
    return (
        f"session {who} · role {claim.role!r} · {_liveness(claim)} · "
        f"held for {_age(claim.claimed_at)} (since {claim.claimed_at}) on {claim.host}"
    )


_NO_IDENTITY: Final = (
    f"I cannot tell WHO you are: no {SESSION_ENV} in this environment.\n"
    "  This is a blind spot, and a blind spot is not a pass. The previous version of this tool\n"
    "  answered it with the NAME OF THE DIRECTORY — so seven Claude sessions in agents/claude/\n"
    "  each read the marker, found 'claude' in it, and believed they were home (ADR 0026).\n"
    "  A role is not a writer. Assert who you are:\n"
    f'    a human shell :  eval "$(make session)"\n'
    f"    an agent / CI :  export {SESSION_ENV}=<one uuid, minted ONCE, kept for the session>\n"
    "  Minting a fresh uuid per command would make every command its own session — and this tool\n"
    "  would then refuse you on your own second call. The id must outlive the invocation."
)


def check() -> Verdict:
    """Is this tree verifiably mine? The one witness the whole file exists to make honest.

    Four answers, and the first two are the ones that were missing:

    * no session identity → **CannotSay**. Never "unclaimed, proceeding as claude".
    * a legacy marker (role only) → **CannotSay**. It names a lane, not a writer: it cannot tell
      us whether the holder is you, and pretending otherwise is the original bug.
    * held by another session → **NotOk**, naming that session, its liveness and its age.
    * unclaimed, or held by me → **Ok**, carrying the evidence for the claim.
    """
    me = session_id()
    if me is None:
        return CannotSay(_NO_IDENTITY)

    root = _worktree_root()
    current = read_owner()
    if current is None:
        return Ok(f"{root} is unclaimed — proceeding as session {me} (role {role()!r})")

    if not current.session_id:
        return CannotSay(
            f"{root} carries a LEGACY marker that names only a role ({current.role!r}) — and a "
            "role is not a session.\n"
            "  It cannot tell us whether the writer is you or another session in the same lane; "
            "that ambiguity IS the incident this file was rewritten for.\n"
            f"  Held for {_age(current.claimed_at)}. Take the tree deliberately: `make claim "
            "FORCE=1`."
        )

    if current.session_id == me:
        return Ok(f"{root} is held by YOU — {_describe(current)}")

    return NotOk(
        f"you are session {me} (role {role()!r}); {root} is held by ANOTHER SESSION.\n"
        f"  holder: {_describe(current)}\n"
        "  An agent does not mutate a worktree it does not own. On 2026-07-12 two agents wrote\n"
        "  into one tree: work was stashed mid-flight, a commit landed on the wrong branch, and\n"
        "  TWO `make gate` runs returned exit 0 on TWO DIFFERENT TREES.\n"
        "  Use your own worktree, or take this one deliberately: `make claim FORCE=1`."
    )


def claim(*, force: bool) -> Verdict:
    """Declare this session the owner. Refuses to take a tree another session holds."""
    me = session_id()
    if me is None:
        return CannotSay(_NO_IDENTITY)

    root = _worktree_root()
    current = read_owner()
    held_by_other = current is not None and current.session_id != me
    if current is not None and held_by_other and not force:
        holder = (
            _describe(current)
            if current.session_id
            else f"a LEGACY marker naming only the role {current.role!r} — no session id"
        )
        return NotOk(
            f"{root} is already held.\n"
            f"  holder: {holder}\n"
            "  Use another worktree, or take this one deliberately: `make claim FORCE=1`.\n"
            "  Taking it is a decision, so it is spelled out — never a silent overwrite."
        )

    record = Claim(
        session_id=me,
        role=role(),
        pid=session_pid(),
        claimed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        host=socket.gethostname(),
        worktree=str(root),
    )
    _marker_path().write_text(
        json.dumps(asdict(record), indent=2) + "\n",
        encoding="utf-8",
    )

    taken = ""
    if current is not None and held_by_other and force:
        previous = (
            _describe(current)
            if current.session_id
            else f"a LEGACY marker naming only the role {current.role!r}"
        )
        taken = f" — TAKEN by --force from {previous}"
    return Ok(f"{root} is now held by session {me} (role {record.role!r}){taken}")


def release() -> Verdict:
    """Give the tree back. Releasing a tree you never held is not an error; releasing someone
    else's is exactly the move this file exists to stop.
    """
    me = session_id()
    if me is None:
        return CannotSay(_NO_IDENTITY)

    path = _marker_path()
    current = read_owner()
    if current is not None and current.session_id != me:
        holder = (
            _describe(current)
            if current.session_id
            else f"a LEGACY marker naming only the role {current.role!r}"
        )
        return NotOk(
            f"{path.parent} is held by another session, not by you ({me}).\n"
            f"  holder: {holder}\n"
            "  Releasing another session's claim is exactly the move this file exists to stop."
        )
    path.unlink(missing_ok=True)
    return Ok(f"{path.parent} released by session {me}")


def mint() -> tuple[str, list[str]]:
    """The two lines a shell should ``eval`` to *become* a session, plus a sentence for the human.

    Deliberately NOT a :class:`~tessera.verdict.Verdict`: this command observes nothing and judges
    nothing, it manufactures an identity. Dressing it as a witness would be cargo-cult — the type
    is for things that looked at something.

    ``$$`` is the **shell's** pid, not this subprocess's. An identity must belong to something that
    lives as long as the work does; that distinction is the whole file.
    """
    new = uuid.uuid4()
    return (
        'a new session id — `eval "$(make session)"` to adopt it in this shell',
        [f"export {SESSION_ENV}={new}", f"export {SESSION_PID_ENV}=$$"],
    )


def _emit(verdict: Verdict) -> int:
    """Print the verdict where it belongs, and return its exit code. Never a bare bool."""
    stream = sys.stdout if isinstance(verdict, Ok) else sys.stderr
    stream.write(f"\n[worktree] {render(verdict)}\n")
    stream.flush()
    return exit_code(verdict)


def main(argv: list[str] | None = None) -> int:
    """Exit code is the verdict. ``2`` = *do not proceed* — either not yours, or unknowable."""
    parser = argparse.ArgumentParser(description="Declare and check worktree ownership.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    claim_cmd = sub.add_parser("claim", help="declare this session the owner")
    claim_cmd.add_argument("--force", action="store_true", help="take a tree another session holds")
    sub.add_parser("check", help="exit 2 unless this tree is verifiably yours")
    sub.add_parser("release", help="give the tree back")
    sub.add_parser("session", help="mint a session id for this shell")

    args = parser.parse_args(argv)
    if args.cmd == "claim":
        return _emit(claim(force=args.force))
    if args.cmd == "release":
        return _emit(release())
    if args.cmd == "session":
        # The export lines go to STDOUT so `eval "$(make session)"` works; the human-facing
        # sentence goes to STDERR, where eval will not try to execute it.
        headline, exports = mint()
        sys.stderr.write(f"\n[worktree] {headline}\n")
        for export in exports:
            sys.stdout.write(export + "\n")
        return 0
    return _emit(check())


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
