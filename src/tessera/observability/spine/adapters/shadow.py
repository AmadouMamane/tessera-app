"""Shadow-run reader: serve local, compare the spine, record divergence (ADR 0015 §Migration C).

Dark launch. A signal runs **both** sources, is **served from local**, and the divergence is
recorded (``tessera_spine_shadow_divergence_total``). A signal graduates local→spine only after
it holds parity over a bake period — so an autonomous flip can never regress the UI. This is the
migration safety net, not a smell: the transitional dual-run is what lets a live source migrate
without a user-visible regression, and local is retired (§Migration D) only once every signal
has flipped and held parity.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from tessera.observability.metrics import SPINE_SHADOW_DIVERGENCE
from tessera.observability.spine.adapters.base import SpineReader, SpineUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable

    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = ["ShadowReader"]


class ShadowReader:
    """Serves the ``primary`` (local) reader; reads ``shadow`` (spine) to record divergence."""

    def __init__(self, primary: SpineReader, shadow: SpineReader) -> None:
        self._primary = primary
        self._shadow = shadow

    def _compare(
        self, fact: str, primary_count: int, shadow_read: Callable[[], list[object]]
    ) -> None:
        try:
            shadow_count = len(shadow_read())
        except SpineUnavailableError:
            SPINE_SHADOW_DIVERGENCE.labels(fact=fact, result="unavailable").inc()
            return
        result = "match" if shadow_count == primary_count else "diverge"
        SPINE_SHADOW_DIVERGENCE.labels(fact=fact, result=result).inc()
        if result == "diverge":
            sys.stderr.write(
                f"tessera.spine.shadow[{fact}]: local={primary_count} spine={shadow_count} "
                "(serving local; not flipping until parity)\n"
            )

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Serve local scores; compare the spine's and record the divergence."""
        primary = self._primary.scores(scope)
        self._compare("scores", len(primary), lambda: list(self._shadow.scores(scope)))
        return primary

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Serve local bundles; compare the spine's and record the divergence."""
        primary = self._primary.bundles(scope)
        self._compare("bundles", len(primary), lambda: list(self._shadow.bundles(scope)))
        return primary

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
        """The ledger is local and canonical — served directly, no shadow (§carve-out)."""
        return self._primary.audit_entries(scope)

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Serve the file-archive gating rows; compare the owned Postgres table's."""
        primary = self._primary.gating_scores(scope)
        self._compare("gating", len(primary), lambda: list(self._shadow.gating_scores(scope)))
        return primary
