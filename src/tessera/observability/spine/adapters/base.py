"""The ``SpineReader`` protocol — the read seam every signal goes through (ADR 0015 §Testing 1).

Every signal reads dimensioned facts through a :class:`SpineReader`, so tests inject an
in-memory fake and stay offline / deterministic, while production reads the current stores
(Phase A) or the live spine (Phase C) behind the **same** interface. Swapping the source
is a factory change, not a signal rewrite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = ["SpineReader", "SpineUnavailableError"]


class SpineUnavailableError(RuntimeError):
    """A spine backend was unreachable — the caller returns an honest-empty state.

    Raised by a reader when its backend (Langfuse / Prometheus) cannot be reached, so the
    registry marks the signal ``unavailable`` and the UI shows "spine indisponible" rather
    than a fabricated zero (ADR 0015 §Honest degradation).
    """


class SpineReader(Protocol):
    """Reads dimensioned facts for a ``Scope``.

    Phase A implementations read the current stores; Phase C implementations read the live
    spine. The three methods are the shared reads a snapshot fans out over — a snapshot
    calls each at most once (memoised by the snapshot context).
    """

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Eval score rows for the scope (as-of-T + agent filtered), oldest→newest."""
        ...

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Captured turn bundles for the scope (as-of-T + agent filtered)."""
        ...

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
        """Guard audit ledger entries (tamper-evident; stays local, unfiltered at read)."""
        ...
