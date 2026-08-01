"""Read adapters behind the spine seam (ADR 0015).

``get_reader()`` returns the process-wide :class:`SpineReader`, selected by the
``TESSERA_SPINE_SOURCE`` env (the migration flag, §Migration C): ``local`` (degraded
current stores), ``spine`` (the owned stores — the flip), or ``shadow`` (serve local,
compare the spine, record divergence — the safety net before a flip). ``jsonl`` remains
accepted as a deprecated alias for ``local``. The flip is
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
    "read_scores",
    "set_reader",
    "spine_source",
]

_reader: SpineReader | None = None

_SOURCE_ALIASES = {"jsonl": "local", "local": "local", "spine": "spine", "shadow": "shadow"}
_SOURCES = set(_SOURCE_ALIASES.values())
# The per-fact flip surface (G4). bundles never flips per-fact (the spine's trace-derived
# bundles are lossy by design) and the audit ledger is the local carve-out — neither has
# an override; they follow the global source only.
_FLIPPABLE_FACTS = ("scores", "gating", "business_events")
# The default source per flippable fact when no env is set. ``scores``/``gating`` graduated to
# the owned stores at G5; ``business_events`` graduated at step 4 lot 2, once shadow parity
# baked. All three therefore READ from ClickHouse by default — the in-process store is no
# longer the default read medium for business events, only their write substrate. (The
# sentence that used to stand here said the opposite and outlived its own last clause; a
# synthetic-exclusion bug hid behind it until 2026-07-10. See ADR 0019 §4.)
_FACT_DEFAULTS = {"scores": "spine", "gating": "spine", "business_events": "spine"}


def _normalise_source(raw: str) -> str | None:
    """Canonical source value; accepts ``jsonl`` as a deprecated alias for ``local``."""
    return _SOURCE_ALIASES.get(raw.strip().lower())


def spine_source() -> str:
    """The configured global read source: ``local`` (default) | ``spine`` | ``shadow``."""
    return _normalise_source(os.environ.get("TESSERA_SPINE_SOURCE", "local")) or "local"


def fact_source(fact: str) -> str:
    """The active source for one fact: per-fact env > explicit global env > default.

    Since G5 (the local-source retirement, baked per the ADR's own gate) ``scores``/``gating``
    **default to ``spine``** — the owned stores are the system of record; ``local`` remains
    the *explicit* degraded fallback (set the global or the per-fact env). Step 4 lot 2
    flips ``business_events`` to the owned store as well. Every other fact reports the
    global source. This resolved value is what the per-signal ``source`` badge shows.
    """
    if fact in _FLIPPABLE_FACTS:
        source = _normalise_source(os.environ.get(f"TESSERA_SPINE_SOURCE_{fact.upper()}", ""))
        if source is not None:
            return source
        if _explicit_global() is not None:
            return spine_source()
        return _FACT_DEFAULTS.get(fact, "spine")
    return spine_source()


def _explicit_global() -> str | None:
    """The global source when the operator actually set it, else ``None``."""
    return _normalise_source(os.environ.get("TESSERA_SPINE_SOURCE", ""))


class FactRouter:
    """Routes each fact to its active source (the per-fact flip, G4).

    ``scores`` / ``gating`` follow :func:`fact_source`; ``bundles`` follows the global
    source; ``audit_entries`` is always the local ledger (the carve-out). ``shadow``
    for a fact serves local and records that fact's divergence, exactly like the global
    shadow mode — the bake gate is identical, just per-fact.
    """

    def __init__(self, current: SpineReader, spine: SpineReader, shadow: SpineReader) -> None:
        self._by_source: dict[str, SpineReader] = {
            "local": current,
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
        return self._by_source["local"].audit_entries(scope)


def _has_fact_overrides() -> bool:
    return any(
        _normalise_source(os.environ.get(f"TESSERA_SPINE_SOURCE_{fact.upper()}", "")) is not None
        for fact in _FLIPPABLE_FACTS
    )


def _build_reader() -> SpineReader:
    # An EXPLICIT global source with no per-fact override keeps the legacy whole-reader
    # semantics (the operator pinned one source for everything — tests and the degraded
    # fallback use this). Otherwise — including the no-env default since G5 — the
    # per-fact router serves each fact from its own active source.
    if _explicit_global() is not None and not _has_fact_overrides():
        source = spine_source()
        if source == "local":
            return CurrentStoresReader()
        # Import the spine-backed adapters lazily so the pinned-local path never pulls
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
    """The process-wide spine reader (built from ``TESSERA_SPINE_SOURCE``, default local)."""
    global _reader
    if _reader is None:
        _reader = _build_reader()
    return _reader


def read_scores(
    at: str | None = None,
    agent_id: str | None = None,
    *,
    full: bool = False,
    days: float | None = None,
) -> list[dict[str, object]]:
    """Score rows through the active reader seam — the one door every consumer uses (G5).

    Three explicit semantics, mirroring what the direct store calls used to encode:
    ``at`` set → the as-of-T view; ``at`` ``None`` with ``full=True`` → the full history
    (read as-of *now*, so the flipped sources serve it identically to the legacy
    ``persisted_scores()``); ``at`` ``None`` without ``full`` → the live ring cut
    (``recent_scores`` semantics). Routing through the seam is what lets a consumer follow
    the per-fact source flip without knowing any store exists.

    ``days`` adds the window's lower bound. It is the one door for that too — a caller
    that filtered ``scored_at`` itself would be writing the second copy of a subtraction
    that already exists on :meth:`Scope.window`.
    """
    from datetime import UTC, datetime

    from tessera.observability.spine.scope import Scope

    cutoff = at if at is not None else (datetime.now(UTC).isoformat() if full else None)
    return get_reader().scores(Scope(at=cutoff, agent_id=agent_id, period_days=days))


def set_reader(reader: SpineReader | None) -> None:
    """Override the process reader (tests inject a :class:`FakeSpineReader`).

    Passing ``None`` resets to the default on next :func:`get_reader`.
    """
    global _reader
    _reader = reader
