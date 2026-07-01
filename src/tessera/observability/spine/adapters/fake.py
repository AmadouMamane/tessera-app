"""In-memory ``SpineReader`` for offline, deterministic tests (ADR 0015 §Testing 1).

Seeded with canned facts, it applies the *same* as-of-T + agent filtering the real stores
do, so a signal read over the fake matches its shape over jsonl. This is what keeps the
existing unit suite offline and green through the migration: tests inject the fake instead
of standing up Langfuse / Prometheus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability._asof import occurred_before

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = ["FakeSpineReader"]


class FakeSpineReader:
    """A seeded, in-memory reader mirroring the real stores' filtering semantics."""

    def __init__(
        self,
        *,
        scores: list[dict[str, object]] | None = None,
        bundles: list[ReplayBundle] | None = None,
        audit_entries: list[dict[str, object]] | None = None,
    ) -> None:
        self._scores = list(scores or [])
        self._bundles = list(bundles or [])
        self._audit = list(audit_entries or [])

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Seeded score rows, filtered by the scope's as-of-T + agent, like the real store."""
        rows = [r for r in self._scores if occurred_before(r.get("scored_at"), scope.at)]
        if scope.agent_id is not None:
            rows = [r for r in rows if r.get("agent_id") == scope.agent_id]
        return rows

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Seeded bundles, filtered by the scope's as-of-T + agent, like the real store."""
        items = [b for b in self._bundles if occurred_before(b.captured_at, scope.at)]
        if scope.agent_id is not None:
            items = [b for b in items if b.agent_id == scope.agent_id]
        return items

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:  # noqa: ARG002
        """The seeded ledger entries whole (scope filter applied downstream)."""
        return list(self._audit)
