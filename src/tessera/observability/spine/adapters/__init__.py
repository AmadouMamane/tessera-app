"""Read adapters behind the spine seam (ADR 0015).

``get_reader()`` returns the process-wide :class:`SpineReader`, selected by the
``TESSERA_SPINE_SOURCE`` env (the migration flag, §Migration C): ``jsonl`` (default — the
current stores), ``spine`` (the owned stores — the flip), or ``shadow`` (serve jsonl,
compare the spine, record divergence — the safety net before a flip). The flip is
**per-fact** (G4): ``TESSERA_SPINE_SOURCE_SCORES`` / ``TESSERA_SPINE_SOURCE_GATING``
override the global for the two flippable facts, so scores can graduate to the owned
ClickHouse table while bundles (lossy-by-design in the spine) and the audit ledger (the
local carve-out) stay on their canonical reads. Swapping a source is this factory, not a
signal rewrite. Tests inject a :class:`FakeSpineReader` via :func:`set_reader`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tessera.observability.spine.adapters.base import SpineReader, SpineUnavailableError
from tessera.observability.spine.adapters.current import CurrentStoresReader
from tessera.observability.spine.adapters.fake import FakeSpineReader

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = [
    "CurrentStoresReader",
    "FactRouter",
    "FakeSpineReader",
    "SpineReader",
    "SpineUnavailableError",
    "fact_source",
    "get_reader",
    "set_reader",
    "spine_source",
]

_reader: SpineReader | None = None

_SOURCES = {"jsonl", "spine", "shadow"}
# The per-fact flip surface (G4). bundles never flips per-fact (the spine's trace-derived
# bundles are lossy by design) and the audit ledger is the local carve-out — neither has
# an override; they follow the global source only.
_FLIPPABLE_FACTS = ("scores", "gating")


def spine_source() -> str:
    """The configured global read source: ``jsonl`` (default) | ``spine`` | ``shadow``."""
    source = os.environ.get("TESSERA_SPINE_SOURCE", "jsonl").strip().lower()
    return source if source in _SOURCES else "jsonl"


def fact_source(fact: str) -> str:
    """The active source for one fact: its per-fact override, else the global source.

    Only the flippable facts (``scores``, ``gating``) honour an override; every other
    fact reports the global source. This is what the per-signal ``source`` badge shows,
    so a flipped signal is visibly flipped — never silently.
    """
    if fact in _FLIPPABLE_FACTS:
        raw = os.environ.get(f"TESSERA_SPINE_SOURCE_{fact.upper()}", "").strip().lower()
        if raw in _SOURCES:
            return raw
    return spine_source()


class FactRouter:
    """Routes each fact to its active source (the per-fact flip, G4).

    ``scores`` / ``gating`` follow :func:`fact_source`; ``bundles`` follows the global
    source; ``audit_entries`` is always the local ledger (the carve-out). ``shadow``
    for a fact serves jsonl and records that fact's divergence, exactly like the global
    shadow mode — the bake gate is identical, just per-fact.
    """

    def __init__(self, current: SpineReader, spine: SpineReader, shadow: SpineReader) -> None:
        self._by_source: dict[str, SpineReader] = {
            "jsonl": current,
            "spine": spine,
            "shadow": shadow,
        }

    def _pick(self, source: str) -> SpineReader:
        return self._by_source[source]

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Online score rows from the fact's active source."""
        return self._pick(fact_source("scores")).scores(scope)

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Release-gating rows from the fact's active source."""
        return self._pick(fact_source("gating")).gating_scores(scope)

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Captured-turn bundles from the GLOBAL source (bundles never flips per-fact)."""
        return self._pick(spine_source()).bundles(scope)

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
        """The tamper-evident ledger — always local and canonical, never routed elsewhere."""
        return self._by_source["jsonl"].audit_entries(scope)


def _has_fact_overrides() -> bool:
    return any(
        os.environ.get(f"TESSERA_SPINE_SOURCE_{fact.upper()}", "").strip().lower() in _SOURCES
        for fact in _FLIPPABLE_FACTS
    )


def _build_reader() -> SpineReader:
    source = spine_source()
    if not _has_fact_overrides():
        if source == "jsonl":
            return CurrentStoresReader()
        # Import the spine-backed adapters lazily so the default jsonl path never pulls
        # the owned-store clients (and stays offline/import-light in the fast test loop).
        from tessera.observability.spine.adapters.spine import SpineStoresReader

        if source == "spine":
            return SpineStoresReader()
        from tessera.observability.spine.adapters.shadow import ShadowReader

        return ShadowReader(CurrentStoresReader(), SpineStoresReader())
    from tessera.observability.spine.adapters.shadow import ShadowReader
    from tessera.observability.spine.adapters.spine import SpineStoresReader

    current = CurrentStoresReader()
    spine = SpineStoresReader()
    return FactRouter(current, spine, ShadowReader(current, spine))


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
