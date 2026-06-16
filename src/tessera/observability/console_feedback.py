"""Durable operator feedback for the Agent Console (Debug) chat turns.

Each thumbs up/down an operator leaves on a live assistant turn is persisted to a
JSON file next to the guard audit log (``console_feedback.json``), keyed by the
real ``conversation_id`` returned in the chat SSE envelope plus the turn index.
This makes the console's feedback control a genuine mutation (the rating
survives a reload), not a decorative toggle.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["available_ratings", "console_feedback", "record_console_feedback"]

available_ratings = frozenset({"up", "down"})


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "console_feedback.json"


def _load() -> dict[str, dict[str, str]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(conv): {str(turn): str(rating) for turn, rating in turns.items()}
        for conv, turns in data.items()
        if isinstance(turns, dict)
    }


def _save(state: dict[str, dict[str, str]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


def console_feedback(conversation_id: str) -> dict[str, str]:
    """Return the stored ``{turn: rating}`` map for a conversation."""
    return _load().get(conversation_id, {})


def record_console_feedback(conversation_id: str, turn: int, rating: str | None) -> dict[str, str]:
    """Persist (or clear) a rating for one turn and return the conversation map.

    A ``rating`` of ``None`` (or one already set) clears the entry, so clicking
    the same thumb twice toggles it off.
    """
    state = _load()
    turns = dict(state.get(conversation_id, {}))
    key = str(int(turn))
    if rating is None or turns.get(key) == rating:
        turns.pop(key, None)
    else:
        turns[key] = rating
    if turns:
        state[conversation_id] = turns
    else:
        state.pop(conversation_id, None)
    _save(state)
    return state.get(conversation_id, {})
