"""Shared real source for the operator work queues ("A faire" / "A traiter").

Both queue pages were deterministic fixtures. This module derives a real backlog
from artifacts that already exist:

* **failed evaluation cases** from the latest catalogue run
  (:func:`tessera.observability.eval_data.load_eval_snapshot`) - every failing
  case is a real item to review, carrying its category, language, title and the
  time it ran;
* per-item **status / assignee** is persisted to a durable JSON next to the
  guard audit log and mutated by the queue endpoints, so "Prendre en charge",
  "Marquer resolu" and assignment actually change state.

Priorities, SLA targets and the source domain are derived deterministically from
the case category. ``now``-relative SLA/age are computed on read. Free-text is
ASCII-only (accents allowed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.eval_data import CATEGORY_LABELS, load_eval_snapshot
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "OperatorItem",
    "available_item_ids",
    "load_items",
    "set_item_state",
]

# category -> priority tone (crit/high/mod/low)
_PRIORITY: dict[str, str] = {
    "prompt_injection": "crit",
    "pii_leak": "crit",
    "policy_violation": "high",
    "regulatory_misstatement": "high",
    "citation_fabrication": "high",
    "tool_misuse": "high",
    "hallucination": "mod",
    "escalation_failure": "mod",
    "overconfidence": "low",
    "language_mixing": "low",
}

# category -> source domain shown in the queue
_SOURCE: dict[str, str] = {
    "prompt_injection": "Garde-fous",
    "pii_leak": "Confidentialite",
    "policy_violation": "Garde-fous",
    "regulatory_misstatement": "Reglementaire",
    "citation_fabrication": "RAG",
    "tool_misuse": "Outils",
    "hallucination": "RAG",
    "escalation_failure": "Assistant",
    "overconfidence": "Assistant",
    "language_mixing": "Multilingue",
}

# SLA target in hours by priority.
_SLA_HOURS: dict[str, float] = {"crit": 1.0, "high": 4.0, "mod": 8.0, "low": 24.0}

_WARN_SECONDS = 2 * 3600  # under 2h remaining -> warn

_DEFAULT_STATUS = "todo"
_VALID_STATUS = {"todo", "progress", "done"}


@dataclass(frozen=True, slots=True)
class OperatorItem:
    """One real backlog item derived from a failed evaluation case."""

    item_id: str
    case_id: str
    category: str
    type_label: str
    title: str
    language: str
    source: str
    priority: str  # crit/high/mod/low
    created_at: datetime
    needs_escalation: bool
    status: str  # todo/progress/done (durable)
    assignee: str  # durable; "" when unassigned

    def age_seconds(self, now: datetime) -> float:
        """Seconds since the case ran (non-negative)."""
        return max(0.0, (now - self.created_at).total_seconds())

    def due_at(self) -> datetime:
        """SLA due time = created + the per-priority target."""
        from datetime import timedelta

        return self.created_at + timedelta(hours=_SLA_HOURS.get(self.priority, 8.0))

    def remaining_seconds(self, now: datetime) -> float:
        """Seconds left before the SLA due time (negative when overdue)."""
        return (self.due_at() - now).total_seconds()

    def overdue(self, now: datetime) -> bool:
        """True when an open item has passed its SLA due time."""
        return self.status != "done" and self.remaining_seconds(now) < 0

    def sla_tone(self, now: datetime) -> str:
        """Tone key for the SLA cell: ok / warn (<2h) / crit (overdue)."""
        if self.status == "done":
            return "ok"
        remaining = self.remaining_seconds(now)
        if remaining < 0:
            return "crit"
        if remaining < _WARN_SECONDS:
            return "warn"
        return "ok"


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "operator_items_state.json"


def _load_state() -> dict[str, dict[str, str]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, str]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


def set_item_state(item_id: str, *, status: str | None = None, assignee: str | None = None) -> None:
    """Persist a status/assignee change for one queue item."""
    state = _load_state()
    entry = state.get(item_id, {"status": _DEFAULT_STATUS, "assignee": ""})
    if status is not None and status in _VALID_STATUS:
        entry["status"] = status
    if assignee is not None:
        entry["assignee"] = assignee
    state[item_id] = entry
    _save_state(state)


def _parse_dt(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def load_items() -> list[OperatorItem]:
    """Derive the real backlog from failed eval cases, merged with durable state."""
    snap = load_eval_snapshot()
    state = _load_state()
    items: list[OperatorItem] = []
    for s in snap.sessions:
        if s.passed:
            continue
        item_id = f"{s.case_id}.{s.language}"
        st = state.get(item_id, {})
        items.append(
            OperatorItem(
                item_id=item_id,
                case_id=s.case_id,
                category=s.category,
                type_label=CATEGORY_LABELS.get(s.category, s.category),
                title=s.title,
                language=s.language,
                source=_SOURCE.get(s.category, "Assistant"),
                priority=_PRIORITY.get(s.category, "mod"),
                created_at=_parse_dt(s.started_at),
                needs_escalation=s.needs_escalation,
                status=st.get("status", _DEFAULT_STATUS),
                assignee=st.get("assignee", ""),
            )
        )
    # Most urgent first: crit < high < mod < low, then oldest first.
    order = {"crit": 0, "high": 1, "mod": 2, "low": 3}
    items.sort(key=lambda i: (order.get(i.priority, 9), i.created_at))
    return items


def available_item_ids() -> set[str]:
    """The set of known item ids (for endpoint validation)."""
    return {i.item_id for i in load_items()}
