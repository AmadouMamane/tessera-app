"""Filesystem helpers shared across the file-backed local stores.

The observability cockpit keeps a family of small JSON documents on the durable state
volume — incidents, agent configs, automations, curation, evidence packs, as-of snapshots,
replay bundles, … — each rewritten in full on every operator mutation. A plain
``Path.write_text`` truncates the file and then writes, so it has a window in which the file
on disk is empty or half-written. With one process that window is only ever observed by the
same request that opened it; with N worker processes (ADR 0044) a *concurrent* cockpit read
on another worker can land inside it and read a truncated document — a transient 500 that
looks like data loss and is not.

:func:`atomic_write_text` closes that window: it writes to a sibling temp file, fsyncs, and
``os.replace``s it over the target. ``os.replace`` is atomic on POSIX and Windows when the
temp file is on the same filesystem (hence a sibling in the target's own directory), so a
reader always sees either the whole old document or the whole new one — never a torn write.
It is a drop-in for the ``path.write_text(text, encoding="utf-8")`` calls it replaces.
"""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["atomic_write_text"]


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically (temp file + fsync + ``os.replace``).

    Creates ``path``'s parent directory if missing. A reader on another process never observes
    a partial file: it sees the previous contents until the instant the fully-written temp
    file is renamed over the target. A crash mid-write leaves the old file intact and, at
    worst, a ``.<name>.*.tmp`` sibling to be cleaned up on the next successful write.

    Args:
        path: Destination file.
        text: Full new contents.
        encoding: Text encoding (default UTF-8).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            from pathlib import Path as _Path

            temporary = _Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)  # atomic same-filesystem rename — the single publish step
        temporary = None  # ownership passed to `path`; nothing left to clean up
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
