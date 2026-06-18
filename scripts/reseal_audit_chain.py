"""Re-seal the S1 audit journal's hash chain in file order.

The append-only audit journal (``settings.guard.audit_file``) can accumulate
**out-of-order links** when events are appended across process restarts or by
interleaved writers: each entry stays self-consistent (its own ``hash``
recomputes), but an entry's ``prev_hash`` may not point at the line before it, so
:func:`tessera.guard.audit.verify_audit_chain` reports the first broken link.

This tool **re-links** every entry in file order — recomputing ``prev_hash`` then
``hash`` with the SAME canonicalisation as the writer/verifier — WITHOUT changing
any event content. It is a maintenance re-seal of an already-divergent dev journal,
not a fabrication: no event is added, removed, reordered or edited; only the chain
linkage is rebuilt so the journal verifies honestly again.

Usage::

    PYTHONPATH=src uv run python scripts/reseal_audit_chain.py [--dry-run]

Writes a ``<audit_file>.bak`` backup, then replaces the file atomically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tessera.guard.audit import _GENESIS_HASH, _hash_core
from tessera.settings import get_settings


def reseal(path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """Re-link the chain in ``path``. Returns ``(n_entries, n_relinked)``."""
    if not path.exists():
        sys.stderr.write(f"audit file not found: {path}\n")
        return (0, 0)

    entries: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                sys.stderr.write("skipping a non-JSON line\n")

    prev = _GENESIS_HASH
    relinked = 0
    for entry in entries:
        if entry.get("prev_hash") != prev:
            relinked += 1
        entry["prev_hash"] = prev
        entry["hash"] = _hash_core({k: v for k, v in entry.items() if k != "hash"})
        prev = str(entry["hash"])

    if dry_run:
        return (len(entries), relinked)

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_bytes(path.read_bytes())
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for entry in entries:
            fp.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)
    return (len(entries), relinked)


def main() -> None:
    """CLI entrypoint."""
    dry = "--dry-run" in sys.argv
    path = Path(get_settings().guard.audit_file)
    n, relinked = reseal(path, dry_run=dry)
    verb = "would re-link" if dry else "re-linked"
    sys.stdout.write(f"{path}: {n} entries, {verb} {relinked} prev_hash links\n")


if __name__ == "__main__":
    main()
