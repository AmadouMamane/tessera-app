#!/usr/bin/env python
"""Reset the LOCAL demo audit ledger: verified backup FIRST, then TRUNCATE, then restart the agent.

Wiping the opposable ledger is the most destructive thing this repo can do to its own memory, so
this recipe is built to REFUSE before it is built to run, and every step interrogates its own
artefact (ADR 0026) instead of trusting the step before it:

1. It refuses any schema that is not a ``_local`` one — a production ledger can never reach the
   TRUNCATE, whatever the operator types.
2. It requires an explicit confirmation that NAMES the schema being wiped (``CONFIRM=<schema>``), so
   a reset cannot be fat-fingered off shell history.
3. It takes a backup through the PROVEN, artefact-interrogating :mod:`scripts.ledger_backup` and
   requires that backup's OWN verdict (its exit code) to be ``0`` — a reset never wipes an
   un-backed-up ledger. "pg_dump ran" and "a verified backup is on disk" are different facts; only
   the second gates the truncate.
4. Only then does it ``TRUNCATE audit_ledger, audit_ledger_checkpoint RESTART IDENTITY`` (the
   append-only trigger fires only ``BEFORE DELETE OR UPDATE``, so TRUNCATE is permitted), and it
   RE-READS the row counts to PROVE the tables are empty — never trusts psql's exit code.
5. It restarts the agent so its head-keyed read caches re-derive from the now-empty ledger.

Exit code is the verdict (:mod:`tessera.verdict`): ``0`` iff a verified backup was taken AND the
ledger is now empty. ``2`` = refused / could not proceed.

Usage: ``make ledger-reset CONFIRM=tessera_local``.
Env: ``LEDGER_PG_CONTAINER``, ``LEDGER_DB``, ``LEDGER_SCHEMA``, ``LEDGER_BACKUP_DIR`` (as
``ledger-backup``), ``AGENT_CONTAINER`` (default ``tessera-local-agent``), ``LEDGER_RESET_CONFIRM``
(the ``CONFIRM`` token).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

from tessera.verdict import CannotSay, NotOk, Ok, Verdict, exit_code, render

_CONTAINER: Final = os.environ.get("LEDGER_PG_CONTAINER", "tessera-postgres")
_DB: Final = os.environ.get("LEDGER_DB", "tessera")
_SCHEMA: Final = os.environ.get("LEDGER_SCHEMA", "tessera_local")
_AGENT: Final = os.environ.get("AGENT_CONTAINER", "tessera-local-agent")
_CONFIRM: Final = os.environ.get("LEDGER_RESET_CONFIRM")

#: The ledger tables truncated together. The backup captures ``audit_ledger`` (the irreplaceable
#: chain); the checkpoint is derived and the agent rebuilds it on boot, so it is wiped, not backed.
_TABLES: Final = ("audit_ledger", "audit_ledger_checkpoint")


def guard(schema: str, confirm: str | None) -> Verdict | None:
    """Refuse a non-local schema or a missing/mismatched confirmation; ``None`` ⇒ proceed.

    Two independent locks: a STRUCTURAL one no production schema can pass (``endswith('_local')``),
    and a TYPED one that makes the operator name the exact schema being wiped.
    """
    if not schema.endswith("_local"):
        return NotOk(
            f"refusing to reset schema {schema!r}: only a `_local` demo ledger may be truncated — "
            "a production ledger is never wiped by this tool."
        )
    if confirm != schema:
        return CannotSay(
            "reset needs an explicit confirmation that names the schema. Re-run with "
            f"`make ledger-reset CONFIRM={schema}` (got CONFIRM={confirm!r})."
        )
    return None


def remaining_rows(stdout: str) -> int | None:
    """Parse the summed post-truncate row count from psql's output, or ``None`` if unparseable."""
    try:
        return int(stdout.strip())
    except (ValueError, AttributeError):
        return None


def _run_backup() -> Verdict | None:
    """Run the proven ledger-backup; ``None`` ⇒ a verified backup is on disk, else a refusal."""
    try:
        proc = subprocess.run(
            [sys.executable, str(Path("scripts") / "ledger_backup.py")],
            check=False,
        )
    except OSError as exc:
        return CannotSay(f"could not launch ledger_backup.py: {exc}")
    if proc.returncode != 0:
        return NotOk(
            f"backup did not verify (ledger_backup.py exited {proc.returncode}); "
            "the ledger was NOT truncated."
        )
    return None


def _psql(sql: str) -> subprocess.CompletedProcess[bytes]:
    """Run one SQL statement in the ledger's Postgres container (unaligned, tuples-only)."""
    return subprocess.run(
        ["docker", "exec", _CONTAINER, "psql", "-U", "tessera", "-d", _DB, "-qAt", "-c", sql],
        check=False,
        capture_output=True,
    )


def _count_remaining(schema: str) -> int | None:
    """Total rows across the ledger tables, or ``None`` when the count could not be read.

    The schema is env-supplied and already passed ``guard`` (``endswith('_local')``), and the table
    names are a module constant — no user input reaches the SQL, and SQL identifiers cannot be bound
    parameters anyway, so the f-string interpolation (S608) is the only way and is safe here.
    """
    cols = " union all ".join(f"select count(*) from {schema}.{t}" for t in _TABLES)  # noqa: S608
    proc = _psql(f"select coalesce(sum(c), 0) from ({cols}) s(c);")  # noqa: S608
    if proc.returncode != 0:
        return None
    return remaining_rows(proc.stdout.decode("utf-8", "replace"))


def reset() -> Verdict:
    """Back up, refuse-or-truncate, prove-empty, restart — in that order, and only in that order."""
    refusal = guard(_SCHEMA, _CONFIRM)
    if refusal is not None:
        return refusal

    backup_refusal = _run_backup()
    if backup_refusal is not None:
        return backup_refusal

    targets = ", ".join(f"{_SCHEMA}.{t}" for t in _TABLES)
    trunc = _psql(f"TRUNCATE {targets} RESTART IDENTITY;")
    if trunc.returncode != 0:
        reason = trunc.stderr.decode("utf-8", "replace").strip() or "(no message)"
        return NotOk(f"TRUNCATE failed: {reason}")

    remaining = _count_remaining(_SCHEMA)
    if remaining is None:
        return CannotSay("truncate ran but the post-truncate row count could not be read")
    if remaining != 0:
        return NotOk(f"truncate ran but {remaining} row(s) remain — the ledger is NOT empty")

    # The wipe succeeded and is verified; the restart is a follow-up so the agent's head-keyed
    # caches re-derive from the empty ledger. A failed restart is reported loudly, never fatal — the
    # database is already in the intended state.
    restart = subprocess.run(["docker", "restart", _AGENT], check=False, capture_output=True)
    if restart.returncode == 0:
        note = f"agent {_AGENT} restarted"
    else:
        why = restart.stderr.decode("utf-8", "replace").strip() or f"exit {restart.returncode}"
        note = f"ledger emptied but `docker restart {_AGENT}` failed ({why}) — restart it manually"

    tables = ", ".join(_TABLES)
    return Ok(f"{_SCHEMA} ledger backed up then truncated ({tables} now empty); {note}")


def main() -> int:
    """Exit code is the verdict: ``0`` iff a verified backup was taken AND the ledger is empty."""
    verdict = reset()
    stream = sys.stdout if isinstance(verdict, Ok) else sys.stderr
    stream.write(f"\n[ledger-reset] {render(verdict)}\n")
    stream.flush()
    return exit_code(verdict)


if __name__ == "__main__":  # pragma: no cover  thin CLI shim
    raise SystemExit(main())
