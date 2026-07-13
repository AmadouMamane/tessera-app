"""What code is THIS PROCESS running? Asked of the process — never of its directory.

`make dev-status` claimed to report the code a server was serving. What it actually did was
``lsof`` the process's **working directory**, then ask **git** about that **directory**:

    pid=$(lsof …)  ·  cwd=$(lsof -d cwd $pid)  ·  head=$(git -C "$cwd" rev-parse HEAD)

Three hops, and not one of them ever addresses the process. Move the checkout under a live
server — a merge, a branch switch, another agent's `git checkout` — and the witness keeps
reporting, with total composure, the sha of code the process has never loaded. On 2026-07-13 it
did exactly that: the operator's backend had booted at 23:56, before the ledger fix landed, and
`dev-status` cheerfully printed the sha of the fix. His browser was paying 1 087 ms for a badge
that costs 20 ms, and every witness on the machine agreed everything was fine.

**A witness interrogates the thing, never its neighbourhood** (ADR 0026). So the process states
its own identity, and it states it as a fact about itself:

* **``digest``** — a content hash of the ``.py`` files **the interpreter is actually loading this
  package from** (``Path(__file__).parent``, wherever that is: a src-layout checkout, a
  site-packages install, a container image). This is the thing itself. It needs no git, no
  repository, and no cooperation from the filesystem's history.
* **``sha`` / ``dirty``** — the human-readable *name* for that content, when one can be had. The
  name is a convenience; the digest is the evidence.
* **``sha_source``** — where the name came from: ``env`` (a build stamped it), ``git`` (a source
  tree), or ``unknown``. **"Unknown" is a fact, not a placeholder.** A process that cannot know
  which commit it is must say so, and must never be given a default that reads like knowledge —
  the same rule the ledger's actor field earned (ADR 0024).

Everything above is captured **at import, once**, and frozen. That is the whole design, and it is
the only line in this module that matters: a value recomputed per request would answer *"what is
on disk NOW"* — which is precisely the question `dev-status` was already asking, and getting
wrong. The point is not to compute the sha in a new place. **The point is to compute it at the
one moment when it is a fact about the process: when the process loaded the code.**

**A corollary worth its own paragraph.** This codebase imports lazily on purpose (dozens of
function-local imports, to break cycles and keep boot cheap). So a checkout that moves under a
live server does not merely make it *stale* — it makes it **incoherent**: the modules already in
``sys.modules`` are the old code, and the next lazy import reads the new file off disk. The
process ends up running two commits at once, and nothing anywhere says so. That is why the STALE
verdict in `dev-status` is loud, and why it says *restart*, not *note*.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

__all__ = ["CodeIdentity", "identity", "source_digest"]

#: Where the name of the loaded code came from. ``unknown`` is an answer, not a gap to be filled.
ShaSource = Literal["env", "git", "unknown"]

#: A build stamps this into the image (see `infra/docker/`): a container has no git, and asking
#: it for one would produce exactly the fabricated confidence this module exists to refuse.
BUILD_SHA_ENV: Final = "TESSERA_BUILD_SHA"

_GIT_TIMEOUT_S: Final = 2.0


@dataclass(frozen=True, slots=True)
class CodeIdentity:
    """What a process loaded. A statement about the process — not about a directory."""

    #: The evidence: a content hash of the package's ``.py`` files, as the interpreter sees them.
    digest: str
    #: The name, when one can be had. ``None`` when the process genuinely cannot know.
    sha: str | None
    #: Where the name came from. ``unknown`` ⇒ ``sha is None``, always.
    sha_source: ShaSource
    #: Uncommitted edits at load time. ``None`` = unknowable (no git), never a comfortable False.
    dirty: bool | None
    #: The directory the interpreter is loading this package from.
    package_path: str

    @property
    def short(self) -> str:
        """A short human line: the name if there is one, else the digest — never nothing."""
        if self.sha is None:
            return f"digest:{self.digest[:12]}"
        return f"{self.sha[:12]}{'+dirty' if self.dirty else ''}"


def source_digest(package_dir: Path) -> str:
    """Content hash of every ``.py`` under ``package_dir`` — the path AND the bytes.

    The path is hashed too, not just the contents: a file *moved* is a different program, and a
    digest that only summed contents would call a rename identical.

    Deliberately independent of git. It is what makes this witness work in a container, where
    there is no repository at all — and it is what makes it *stronger* than a sha even where there
    is one: a sha names a commit, while this names the bytes. A dirty tree has a sha too, and the
    sha lies about it.
    """
    digest = hashlib.sha256()
    for path in sorted(package_dir.rglob("*.py")):
        digest.update(str(path.relative_to(package_dir)).encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _git(package_dir: Path, *args: str) -> str | None:
    """Run git in the package's own directory. ``None`` on any failure — including "no git"."""
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell, no user input
            ["git", *args],  # noqa: S607 — resolved from PATH by design (dev machines vary)
            cwd=package_dir,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # no git binary, not a repository, a timeout — all mean "cannot know"
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _capture(package_dir: Path) -> CodeIdentity:
    """Take the identity of the code being loaded, right now, once."""
    digest = source_digest(package_dir)

    stamped = os.environ.get(BUILD_SHA_ENV, "").strip()
    if stamped:
        # A build stamped it. There is no working tree to be dirty about, and inventing one would
        # be the fabrication this module refuses: `dirty` stays None — unknowable, and said so.
        return CodeIdentity(
            digest=digest,
            sha=stamped,
            sha_source="env",
            dirty=None,
            package_path=str(package_dir),
        )

    head = _git(package_dir, "rev-parse", "HEAD")
    if head:
        porcelain = _git(package_dir, "status", "--porcelain")
        return CodeIdentity(
            digest=digest,
            sha=head,
            sha_source="git",
            # `porcelain is None` means the *second* git call failed while the first succeeded:
            # we know the commit and do NOT know whether the tree was clean. That is `None`, not
            # False. "No news" and "good news" are different facts.
            dirty=None if porcelain is None else bool(porcelain),
            package_path=str(package_dir),
        )

    return CodeIdentity(
        digest=digest,
        sha=None,
        sha_source="unknown",
        dirty=None,
        package_path=str(package_dir),
    )


#: The directory the interpreter loaded THIS module from — hence the package it is running.
#: Not a configured path, not a guess: the one the import system actually used.
_PACKAGE_DIR: Final = Path(__file__).resolve().parent

#: Captured at import. **Frozen.** A checkout that moves under this process cannot change it —
#: which is the entire point, and the reason it is a module constant rather than a function.
_IDENTITY: Final = _capture(_PACKAGE_DIR)


def identity() -> CodeIdentity:
    """The identity captured when this module was imported. Never recomputed.

    If you are tempted to refresh it, read the module docstring: a refreshed value describes the
    **disk**, and the disk is not the process. That confusion is the bug this module exists to
    make structurally impossible.
    """
    return _IDENTITY


if __name__ == "__main__":  # pragma: no cover — the seam `make dev-status` calls
    # ONE implementation of the digest, called from both sides of the comparison. A second copy
    # in shell would be a second thing to be wrong, and the two would drift the first time either
    # was touched — the failure mode the SQL-identifier lot already paid for once.
    import sys

    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else _PACKAGE_DIR
    print(source_digest(target))
