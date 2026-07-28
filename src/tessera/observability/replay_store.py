"""Durable journal of REAL replay executions (create-the-source, page #11).

Every replay actually executed through ``POST /observability/replay`` is
recorded here — bundle id, candidate model, the measured ``score_delta`` and
``similarity``, and when it ran. The Replay & shadow page reads this journal:
its "requêtes rejouées" and deviation figures grow only when a replay is truly
run, never from invented counters. Mirrors the ``operator_items`` /
``curation_store`` durable-JSON pattern (a sibling of the audit log, so the
file lives outside the repo and survives restarts).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["load_replay_runs", "record_replay_run"]

_MAX_RUNS = 500  # keep the journal bounded; oldest entries roll off


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "replay_runs.json"


def load_replay_runs() -> list[dict[str, object]]:
    """Return the recorded replay executions, oldest first (best-effort read)."""
    path = _state_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def record_replay_run(
    bundle_id: str,
    *,
    agent_id: str,
    model: str,
    score_delta: float | None,
    similarity: float | None,
) -> None:
    """Append one real replay execution to the durable journal.

    Args:
        bundle_id: The captured turn that was replayed.
        agent_id: The agent that owns the original turn.
        model: The candidate model the turn was replayed against.
        score_delta: Measured candidate-minus-original score, if scored.
        similarity: Measured answer similarity, if computed.
    """
    runs = load_replay_runs()
    runs.append(
        {
            "bundle_id": bundle_id,
            "agent_id": agent_id,
            "model": model,
            "score_delta": score_delta,
            "similarity": similarity,
            "at": datetime.now(UTC).isoformat(),
        }
    )
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(runs[-_MAX_RUNS:], indent=2, ensure_ascii=False))
