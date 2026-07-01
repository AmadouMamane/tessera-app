"""Read adapters behind the spine seam (ADR 0015).

``get_reader()`` returns the process-wide :class:`SpineReader`, selected by the
``TESSERA_SPINE_SOURCE`` env (the migration flag, §Migration C): ``jsonl`` (default — the
current stores), ``spine`` (Langfuse/Prometheus/ledger composite — the flip), or ``shadow``
(serve jsonl, compare the spine, record divergence — the safety net before a flip). Swapping
the source is this factory, not a signal rewrite. Tests inject a :class:`FakeSpineReader` via
:func:`set_reader`, so the suite stays offline.
"""

from __future__ import annotations

import os

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
    "spine_source",
]

_reader: SpineReader | None = None


def spine_source() -> str:
    """The configured read source: ``jsonl`` (default) | ``spine`` | ``shadow``."""
    source = os.environ.get("TESSERA_SPINE_SOURCE", "jsonl").strip().lower()
    return source if source in {"jsonl", "spine", "shadow"} else "jsonl"


def _build_reader() -> SpineReader:
    source = spine_source()
    if source == "jsonl":
        return CurrentStoresReader()
    # Import the spine-backed adapters lazily so the default jsonl path never pulls the
    # Langfuse/Prometheus clients (and stays offline/import-light in the fast test loop).
    from tessera.observability.spine.adapters.spine import SpineStoresReader

    if source == "spine":
        return SpineStoresReader()
    from tessera.observability.spine.adapters.shadow import ShadowReader

    return ShadowReader(CurrentStoresReader(), SpineStoresReader())


def get_reader() -> SpineReader:
    """The process-wide spine reader (built from ``TESSERA_SPINE_SOURCE``, default jsonl)."""
    global _reader
    if _reader is None:
        _reader = _build_reader()
    return _reader


def set_reader(reader: SpineReader | None) -> None:
    """Override the process reader (tests inject a :class:`FakeSpineReader`).

    Passing ``None`` resets to the default on next :func:`get_reader`.
    """
    global _reader
    _reader = reader
