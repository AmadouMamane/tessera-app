#!/usr/bin/env python
"""Back up the audit ledger — and **prove** that a backup was actually taken.

The recipe this replaces was three laundered exit codes stacked on a single ``make`` line, and it
was measured, on 2026-07-13, against a container that does not exist::

    Error response from daemon: No such container: tessera-does-not-exist
    Error response from daemon: No such container: tessera-does-not-exist
    ✓ backups/ledger/audit_ledger-…-20260713T120216Z.sql.gz (4.0K,  rows) sha256=1ff72a3b…
    $? = 0

It printed a tick. It exited **0**. It wrote a 20-byte archive that decompresses to **zero bytes**,
and it wrote a ``.sha256`` sidecar **authenticating the empty archive** — so the file was not merely
useless, it was *notarised* useless. Three mechanisms, each sufficient on its own:

1. ``pg_dump … | gzip -9 > $out`` — a pipeline's exit code is the **last** command's, and the
   Makefile declares no shell, so recipes run under ``/bin/sh`` with no ``pipefail``. ``gzip``
   compresses a failed dump's empty output with complete success. *This is the origin instance of
   [ADR 0026](../docs/decisions/0026-a-witness-interrogates-the-thing.md), verbatim.*
2. The recipe was one backslash-continued ``;``-chain with **no ``set -e``**, so every command after
   the failure ran anyway — including the sidecar write.
3. Its **last command was ``echo "✓ …"``**, and a recipe line's exit code is its last command's. The
   target was structurally incapable of returning anything but zero.

So it is not shell any more, and — the part that actually matters — **it interrogates the
artefact**. "``pg_dump`` exited 0" and "the ledger is backed up" are two different facts, and only
the second one is the one you want at 3am. This script therefore reopens the file it just wrote,
decompresses it, and requires the table's own ``COPY`` header to be in there. An empty ledger is
fine and passes (a fresh install has no rows, and ``pg_dump`` still emits the header); a *failed*
dump is not, and cannot pretend to be.

A failed run leaves **no file behind** — deliberately. ``ledger_restore_drill.py`` drills the
*newest* backup, and a 0-byte archive that survived a crash would become that newest backup: the
drill would then correctly fail, but only after retention had had a chance to rotate the good ones
away. A backup that does not exist is an honest absence. A backup that exists and is empty is a lie
with a checksum.

Exit code: ``0`` iff a verified dump is on disk. ``2`` = do not proceed (:mod:`tessera.verdict`).

Usage: ``make ledger-backup`` (env: ``LEDGER_PG_CONTAINER``, ``LEDGER_DB``, ``LEDGER_SCHEMA``,
``LEDGER_BACKUP_DIR``).
"""

from __future__ import annotations

import gzip
import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from tessera.verdict import CannotSay, NotOk, Ok, Verdict, exit_code, render

_CONTAINER: Final = os.environ.get("LEDGER_PG_CONTAINER", "tessera-postgres")
_DB: Final = os.environ.get("LEDGER_DB", "tessera")
_SCHEMA: Final = os.environ.get("LEDGER_SCHEMA", "tessera_local")
_BACKUP_DIR: Final = Path(os.environ.get("LEDGER_BACKUP_DIR", "backups/ledger"))

#: The table pg_dump is asked for. Its `COPY` header is what proves the dump is a dump.
_TABLE: Final = "audit_ledger"


def dump_rows(dump: bytes) -> int | None:
    """How many ledger rows are in this dump? ``None`` when **it is not a dump of the ledger**.

    This is the whole witness, and it asks the artefact rather than the process that made it.

    ``pg_dump --data-only -t <schema>.audit_ledger`` always emits a ``COPY <schema>.audit_ledger
    (…) FROM stdin;`` header, terminated by a lone ``\\.`` — *even for an empty table*. So the
    header's presence separates the two cases a bare exit code cannot:

    * **no header** → ``pg_dump`` did not produce a dump (dead container, missing table, wrong
      credentials, a truncated pipe). ``None`` — a blind spot, never a zero.
    * **header, zero rows** → the ledger is genuinely empty. ``0``, and that is a pass: a fresh
      install has nothing to back up, and refusing it would be a false red.

    Args:
        dump: The decompressed SQL text of the dump, as bytes.

    Returns:
        The number of data rows, or ``None`` if this is not a dump of the ledger table at all.
    """
    header = f"COPY {_SCHEMA}.{_TABLE} ".encode()
    rows: int | None = None
    for line in dump.splitlines():
        if rows is None:
            if line.startswith(header):
                rows = 0
            continue
        if line.startswith(b"\\."):
            break
        rows += 1
    return rows


def _pg_dump() -> tuple[bytes | None, str]:
    """The ledger's data-only dump, or ``(None, reason)``.

    ``capture_output`` on **both** streams and ``check=False``: the exit code is read from the
    process, and stderr is kept, because a failure whose reason has been thrown away is a failure
    the operator gets to debug twice.
    """
    proc = subprocess.run(
        [
            "docker",
            "exec",
            _CONTAINER,
            "pg_dump",
            "-U",
            "tessera",
            "-d",
            _DB,
            "--data-only",
            "--no-owner",
            "--no-privileges",
            "-t",
            f"{_SCHEMA}.{_TABLE}",
        ],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        reason = proc.stderr.decode("utf-8", "replace").strip() or "(no message on stderr)"
        return None, f"pg_dump exited {proc.returncode}: {reason}"
    return proc.stdout, ""


def backup() -> Verdict:
    """Take a backup, verify it, notarise it — in that order, and only in that order."""
    try:
        dumped, failure = _pg_dump()
    except OSError as exc:  # docker itself is not installed / not on PATH
        return CannotSay(f"could not run `docker exec {_CONTAINER} pg_dump`: {exc}")

    if dumped is None:
        return NotOk(f"no backup was taken — {failure}")

    rows = dump_rows(dumped)
    if rows is None:
        return NotOk(
            f"the dump contains no `COPY {_SCHEMA}.{_TABLE}` header, so it is not a dump of the "
            f"ledger — {len(dumped)} bytes of something else. NOTHING WAS WRITTEN.\n"
            "  (This is the case the old recipe notarised with a SHA-256 and called ✓.)"
        )

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = _BACKUP_DIR / f"{_TABLE}-{_SCHEMA}-{stamp}.sql.gz"

    payload = gzip.compress(dumped, compresslevel=9)
    out.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    # The sidecar is written LAST and only here: it is a claim that this archive is the one that
    # verified, and a claim made before the verification is exactly the artefact we found.
    Path(f"{out}.sha256").write_text(f"{sha}  {out.name}\n", encoding="utf-8")

    return Ok(f"{out} ({len(payload)} bytes, {rows} rows) sha256={sha}")


def main() -> int:
    """Exit code is the verdict. ``0`` iff a *verified* dump is on disk."""
    verdict = backup()
    stream = sys.stdout if isinstance(verdict, Ok) else sys.stderr
    stream.write(f"\n[ledger-backup] {render(verdict)}\n")
    stream.flush()
    return exit_code(verdict)


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
