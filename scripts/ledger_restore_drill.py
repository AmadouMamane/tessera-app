"""Restore-drill for the audit-ledger backup (audit P1.2).

A backup you have never restored is a hope, not a backup. This proves a ``make
ledger-backup`` dump SERVES: it restores the latest (or a named) dump into a **throwaway**
database, recreates the ledger schema there (``ensure_audit_ledger_schema`` — the structure
is code, not data), replays the data-only dump, and verifies the chain **tree-aware**
(``verify_ledger_tree``: content integrity + forks + orphans). The live ledger is never
touched, and the throwaway database is dropped at the end — even on failure.

Local-only (needs the owned Postgres container up). Not a gating test: it is a drill you
run, and whose green line is the evidence the backup is real. Exit 0 = the restored chain
verified; exit 1 = it did not (the backup does not serve — a capital finding).

Usage: ``make ledger-restore-drill`` (drills the newest backup), or
``uv run python scripts/ledger_restore_drill.py <path-to-backup.sql.gz>``.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import subprocess
import sys
from pathlib import Path

_CONTAINER = os.environ.get("LEDGER_PG_CONTAINER", "tessera-postgres")
_MAINT_DB = os.environ.get("LEDGER_DB", "tessera")
_SCHEMA = os.environ.get("LEDGER_SCHEMA", "tessera_local")
_BACKUP_DIR = Path(os.environ.get("LEDGER_BACKUP_DIR", "backups/ledger"))
_DRILL_DB = "tessera_ledger_drill"
_DRILL_DSN = f"postgresql://tessera:tessera@localhost:5432/{_DRILL_DB}"


def _docker_psql(db: str, sql: str) -> str:
    """Run one SQL statement in the ledger's Postgres container, returning trimmed stdout."""
    proc = subprocess.run(
        ["docker", "exec", "-i", _CONTAINER, "psql", "-U", "tessera", "-d", db, "-tAc", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _restore_data(db: str, sql_text: str) -> None:
    """Replay a data-only dump into ``db`` (INSERTs — the append-only trigger allows them)."""
    argv = ["docker", "exec", "-i", _CONTAINER, "psql", "-U", "tessera", "-d", db]
    subprocess.run(
        [*argv, "-v", "ON_ERROR_STOP=1"],
        input=sql_text,
        text=True,
        check=True,
    )


def _latest_backup() -> Path:
    files = sorted(_BACKUP_DIR.glob("audit_ledger-*.sql.gz"))
    if not files:
        sys.exit(f"✗ no backup in {_BACKUP_DIR} — run `make ledger-backup` first")
    return files[-1]


def _verify_sidecar(backup: Path) -> None:
    """If a ``.sha256`` sidecar exists, prove the backup was not corrupted at rest."""
    sidecar = Path(f"{backup}.sha256")
    if not sidecar.exists():
        print("  (no .sha256 sidecar — skipping at-rest integrity check)")
        return
    recorded = sidecar.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(backup.read_bytes()).hexdigest()
    if actual != recorded:
        sys.exit(f"✗ SHA-256 mismatch: recorded {recorded}, got {actual} — backup corrupt at rest")
    print(f"  at-rest SHA-256 verified: {actual}")


def main() -> int:
    """Drill the newest (or argv[1]) backup; return 0 iff the restored chain verifies."""
    backup = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_backup()
    if not backup.exists():
        sys.exit(f"✗ backup not found: {backup}")
    print(f"▶ restore drill from {backup}")
    _verify_sidecar(backup)

    # Recreate the throwaway database (never the live one).
    _docker_psql(_MAINT_DB, f"DROP DATABASE IF EXISTS {_DRILL_DB} WITH (FORCE)")
    _docker_psql(_MAINT_DB, f"CREATE DATABASE {_DRILL_DB}")
    try:
        # The ledger's structure (table + append-only trigger + fork guard + indexes) is code:
        # recreate it in the throwaway, in the same schema the dump targets. Aligning the env
        # to the schema keeps pg_schema == LEDGER_SCHEMA (see settings.pg_schema).
        os.environ["TESSERA_POSTGRES__DSN"] = _DRILL_DSN
        os.environ["TESSERA_ENVIRONMENT"] = _SCHEMA.removeprefix("tessera_")
        os.environ["TESSERA_LEDGER_DUAL_WRITE"] = "0"

        import tessera.agent.state  # noqa: F401  pre-load: breaks the guard<->agent import cycle
        from tessera.guard.ledger_store import (
            CREATE_LEDGER_TABLE,
            load_ledger_payloads_sync,
            verify_ledger_tree,
        )
        from tessera.settings import get_settings

        get_settings.cache_clear()
        # Recreate ONLY the table in the dump's schema — structure is code. NOT the fork guard:
        # its partial UNIQUE(prev_hash) would reject the ledger's grandfathered historical forks
        # (verify_ledger_tree REPORTS forks; the store's guard only constrains rows above an
        # install-time anchor). The append-only trigger is irrelevant to a restore: it
        # blocks UPDATE/DELETE only.
        ddl = (
            f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}; "
            f"SET search_path TO {_SCHEMA}, public; "
            f"{CREATE_LEDGER_TABLE}"
        )
        _docker_psql(_DRILL_DB, ddl)

        # Replay the data-only dump, then verify the restored chain tree-aware.
        _restore_data(_DRILL_DB, gzip.decompress(backup.read_bytes()).decode("utf-8"))
        count_sql = f"SELECT count(*) FROM {_SCHEMA}.audit_ledger"  # noqa: S608  fixed schema ident
        rows = int(_docker_psql(_DRILL_DB, count_sql))
        status = verify_ledger_tree(load_ledger_payloads_sync())
        print(
            f"  restored {rows} rows · content_integrity={status.content_integrity} "
            f"linear={status.linear} forks={status.fork_count} orphans={status.orphan_count} "
            f"length={status.length}"
        )
        # The backup SERVES iff every restored row hashes correctly AND the walk covered them all.
        passed = status.content_integrity and rows == status.length and rows > 0
        if passed:
            print("✓ DRILL PASSED — the backup restores to a verifying chain")
        else:
            print("✗ DRILL FAILED — the restored chain did not verify")
        return 0 if passed else 1
    finally:
        _docker_psql(_MAINT_DB, f"DROP DATABASE IF EXISTS {_DRILL_DB} WITH (FORCE)")
        print(f"  dropped throwaway database {_DRILL_DB}")


if __name__ == "__main__":
    raise SystemExit(main())
