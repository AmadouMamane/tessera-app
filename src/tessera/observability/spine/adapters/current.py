"""Phase A spine reader over the current stores (ADR 0015 §Migration A).

This is the transitional ``jsonl`` source: it reads the existing ``scores.jsonl`` /
``bundles.jsonl`` convenience stores and the tamper-evident guard ledger through the
existing store functions *unchanged*, so a snapshot signal is byte-parity with its route.
ADR 0015 §Migration D keeps a thin, clearly-labelled local reader like this for a
degraded-offline mode after the spine becomes the system of record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import replay as replay_mod
from tessera.observability.eval.scores import persisted_scores, recent_scores

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = ["CurrentStoresReader"]


class CurrentStoresReader:
    """Reads the current convenience stores + the tamper-evident audit ledger.

    Mirrors the route helpers exactly: ``persisted_scores`` when an as-of-T instant is
    set, the live ring otherwise; ``recent_bundles`` (which itself falls back to the
    durable store under ``at``); and the guard audit log filtered to guard entries.
    """

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Eval score rows for the scope (durable log as-of-T, else the live ring).

        ``agent`` + as-of-T are pushed into the store read; ``language`` / ``model`` are
        applied here (the rows carry both), so the same store read serves every language
        slice of the agent x time x language cube (ADR 0015 §Migration F).
        """
        rows = (
            persisted_scores(scope.at, scope.agent_id)
            if scope.at
            else recent_scores(scope.agent_id)
        )
        if scope.language is not None:
            rows = [r for r in rows if r.get("language") == scope.language]
        if scope.model is not None:
            rows = [r for r in rows if r.get("model") == scope.model]
        return rows

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Captured turn bundles for the scope (as-of-T + agent, then language / model)."""
        rows = replay_mod.recent_bundles(scope.at, scope.agent_id)
        if scope.language is not None:
            rows = [b for b in rows if b.language == scope.language]
        if scope.model is not None:
            rows = [b for b in rows if b.original_model == scope.model]
        return rows

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:  # noqa: ARG002
        """The whole guard audit ledger (scope filter is applied downstream by signals)."""
        return _read_audit_ledger()


def _read_audit_ledger() -> list[dict[str, object]]:
    """Parse the guard audit log (``type == tessera.guard.audit``), best effort.

    Mirrors the routes' ``_read_audit_entries`` so the ledger read matches today's exactly.
    The full ledger is returned unfiltered; downstream signals apply the scope filter
    (agent / as-of-T) via :mod:`tessera.observability.spine.adapters.ledger`.
    """
    import json

    from tessera.settings import get_settings

    path = get_settings().guard.audit_file
    entries: list[dict[str, object]] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "tessera.guard.audit":
                entries.append(obj)
    return entries
