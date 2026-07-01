"""Read adapters behind the spine seam (ADR 0015).

``get_reader()`` returns the process-wide :class:`SpineReader`. Phase A returns a
:class:`CurrentStoresReader` (the current jsonl + ledger stores); Phase C swaps this for a
Prometheus/Langfuse-backed composite via :func:`set_reader`, without any signal rewrite.
Tests inject a :class:`FakeSpineReader` the same way, so the suite stays offline.
"""

from __future__ import annotations

from tessera.observability.spine.adapters.base import SpineReader, SpineUnavailableError
from tessera.observability.spine.adapters.current import CurrentStoresReader
from tessera.observability.spine.adapters.fake import FakeSpineReader

__all__ = [
    "CurrentStoresReader",
    "FakeSpineReader",
    "SpineReader",
    "SpineUnavailableError",
    "get_reader",
    "set_reader",
]

_reader: SpineReader | None = None


def get_reader() -> SpineReader:
    """The process-wide spine reader (defaults to the current-stores reader)."""
    global _reader
    if _reader is None:
        _reader = CurrentStoresReader()
    return _reader


def set_reader(reader: SpineReader | None) -> None:
    """Override the process reader (tests inject a :class:`FakeSpineReader`).

    Passing ``None`` resets to the default on next :func:`get_reader`.
    """
    global _reader
    _reader = reader
