"""Shared real source for the operator work queues ("A faire" / "A traiter").

Both queue pages were deterministic fixtures. This module derives a real backlog
and partitions it by NATURE (ADR 0038) — "A faire" serves the eval/governance
half, "A traiter" the business half (``load_items_for``); ``load_items`` remains
the unfiltered union. The backlog is derived from artifacts that already exist:

* **failed evaluation cases** from the latest catalogue run
  (:func:`tessera.observability.eval_data.load_eval_snapshot`) - every failing
  case is a real item to review, carrying its category, language, title and the
  time it ran;
* **business grammar events** (``validation.requested`` and ``action.blocked``)
  from the business-events read model - every pending validation or blocked action
  becomes a real item with a deep-link back to the agent's Métier run;
* per-item **status / assignee** is persisted to a durable JSON next to the
  guard audit log and mutated by the queue endpoints, so "Prendre en charge",
  "Marquer resolu" and assignment actually change state;
* per-item **first_seen** is recorded in the same store the first time the queue
  observes the item — the honest SLA clock (ADR 0039). The SLA is anchored there,
  not on ``created_at`` (the underlying case's own time): a seeded eval run from
  days ago is not "overdue for triage" the instant the queue first shows it.

Priorities and SLA targets are derived deterministically from the case category.
The SLA clock runs from queue-entry (``queued_at``); ``created_at`` stays the
case's own timestamp, shown as provenance. ``now``-relative SLA/age are computed
on read. Free-text is ASCII-only (accents allowed).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from tessera.observability import business_events
from tessera.observability.eval_data import CATEGORY_LABELS, load_eval_snapshot
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "NATURE_A_FAIRE",
    "NATURE_A_TRAITER",
    "OperatorItem",
    "UnknownSourceKindError",
    "available_item_ids",
    "load_items",
    "load_items_for",
    "nature_of",
    "partition_items",
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

# --- The nature partition (ADR 0038) -----------------------------------------
#
# The backlog is ONE union with exactly two natures, and each queue page serves
# exactly one of them:
#
#   "a_faire"   (governance plane, routes/observability/fleet.py)    = eval_failure
#   "a_traiter" (business plane,   routes/observability/business.py) = business_event
#
# ``load_items()`` stays the unfiltered union — it is the reference the partition
# ratchet measures both halves against. Every consumer that wants one page's half
# goes through ``nature_of`` (via ``partition_items``/``load_items_for``); there
# is no second copy of the rule anywhere. A ``source_kind`` that belongs to no
# page must never vanish in silence: ``nature_of`` raises on it, the same spirit
# as an exhaustive ``Verdict`` match.

NATURE_A_FAIRE = "a_faire"
NATURE_A_TRAITER = "a_traiter"

_NATURE_KINDS: dict[str, frozenset[str]] = {
    NATURE_A_FAIRE: frozenset({"eval_failure"}),
    NATURE_A_TRAITER: frozenset({"business_event"}),
}


class UnknownSourceKindError(ValueError):
    """A ``source_kind`` no page owns — refused loudly, never dropped in silence."""


def nature_of(source_kind: str) -> str:
    """The page (``a_faire`` | ``a_traiter``) that owns this ``source_kind``.

    Raises:
        UnknownSourceKindError: The kind belongs to no declared nature.
    """
    for nature, kinds in _NATURE_KINDS.items():
        if source_kind in kinds:
            return nature
    raise UnknownSourceKindError(
        f"source_kind {source_kind!r} belongs to no queue page - declare its nature "
        f"in _NATURE_KINDS (known: {sorted(k for ks in _NATURE_KINDS.values() for k in ks)})"
    )


def partition_items(items: list[OperatorItem]) -> dict[str, list[OperatorItem]]:
    """Split a backlog into its two natures - exhaustive and loud on strangers.

    A partition by construction: every item lands in exactly one half, so
    union == input and the halves are disjoint. An unknown ``source_kind``
    raises instead of disappearing.
    """
    halves: dict[str, list[OperatorItem]] = {nature: [] for nature in _NATURE_KINDS}
    for item in items:
        halves[nature_of(item.source_kind)].append(item)
    return halves


def load_items_for(nature: str, agent_id: str | None = None) -> list[OperatorItem]:
    """One page's half of the backlog (``load_items`` stays the total union).

    Raises:
        ValueError: ``nature`` is not a declared page.
        UnknownSourceKindError: The backlog emitted a kind no page owns.
    """
    if nature not in _NATURE_KINDS:
        raise ValueError(f"unknown queue nature {nature!r} - one of {sorted(_NATURE_KINDS)}")
    return partition_items(load_items(agent_id))[nature]


@dataclass(frozen=True, slots=True)
class OperatorItem:
    """One real backlog item derived from a failed evaluation case.

    ``agent_id`` is the agent whose *own* eval run produced the failure — real per-agent
    attribution (ADR 0015 §Migration E, "ventilate the inbox"), not a fabricated split.
    """

    item_id: str
    agent_id: str
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
    source_kind: str = "eval_failure"
    detail_href: str = ""
    # When this item first entered the operator's queue — the honest SLA start
    # (ADR 0039). ``None`` on items built outside the load path; the SLA clock
    # then falls back to ``created_at`` (the pre-0039 behaviour).
    queued_at: datetime | None = None

    def sla_anchor(self) -> datetime:
        """The instant the SLA clock starts: when it entered the queue (ADR 0039).

        ``created_at`` is the underlying case's own time (an eval run days ago, a
        business event) — anchoring the SLA there made every seeded item overdue
        by construction. The clock starts when the item became *actionable* by an
        operator, i.e. when the queue first saw it. Falls back to ``created_at``
        when no queue time is known (an item built off the load path).
        """
        return self.queued_at or self.created_at

    def age_seconds(self, now: datetime) -> float:
        """Seconds since the case ran (non-negative) — the case's own age."""
        return max(0.0, (now - self.created_at).total_seconds())

    def queued_seconds(self, now: datetime) -> float:
        """Seconds this item has waited in the operator's queue (non-negative)."""
        return max(0.0, (now - self.sla_anchor()).total_seconds())

    def due_at(self) -> datetime:
        """SLA due time = queue-entry + the per-priority target (ADR 0039)."""
        from datetime import timedelta

        return self.sla_anchor() + timedelta(hours=_SLA_HOURS.get(self.priority, 8.0))

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


def _now() -> datetime:
    """Current instant (UTC). Indirected so tests can freeze first-seen stamping."""
    return datetime.now(UTC)


def _resolve_queued_at(
    state: dict[str, dict[str, str]],
    item_id: str,
    now: datetime,
    new_stamps: dict[str, str],
) -> datetime:
    """When this item entered the queue: the durable ``first_seen``, or ``now``.

    First observation wins and is recorded once (ADR 0039). A stamp already in
    ``state`` is authoritative; a brand-new item is stamped ``now`` and queued
    into ``new_stamps`` for the caller to persist in one write.
    """
    stamped = state.get(item_id, {}).get("first_seen")
    if isinstance(stamped, str) and stamped:
        return _parse_dt(stamped)
    new_stamps[item_id] = now.isoformat()
    return now


def _persist_first_seen(new_stamps: dict[str, str]) -> None:
    """Durably record first-seen stamps, best-effort (never breaks a read).

    Re-reads the store so a concurrent status/assignee write is not clobbered,
    and ``setdefault`` so a racing observer that stamped first keeps its instant.
    """
    if not new_stamps:
        return
    try:
        fresh = _load_state()
        for item_id, ts in new_stamps.items():
            entry = fresh.get(item_id)
            if not isinstance(entry, dict):
                entry = {}
            entry.setdefault("first_seen", ts)
            fresh[item_id] = entry
        _save_state(fresh)
    except Exception as exc:  # a read must never fail because an observation could not be saved
        sys.stderr.write(
            f"tessera.observability.operator_items: first_seen persist failed: {exc}\n"
        )


def _agent_targets(agent_id: str | None) -> list[str]:
    """Which agents to source the backlog from: one, or the whole registered fleet."""
    from tessera.agent.registry import list_agents

    if agent_id:
        return [agent_id]
    return [a.id for a in list_agents()]


def _payload(row: dict[str, object]) -> dict[str, object]:
    raw = row.get("payload")
    return raw if isinstance(raw, dict) else {}


def _business_event_title(row: dict[str, object]) -> tuple[str, str, str, bool]:
    """Return (category, title, priority, needs_escalation) for one operator event."""
    event_name = str(row.get("event_name") or "")
    case_id = str(row.get("case_id") or "dossier")
    if event_name == business_events.BusinessEventName.VALIDATION_REQUESTED.value:
        artifact = str(row.get("artifact_type") or row.get("artifact_id") or "artefact")
        return (
            "validation_requested",
            f"Validation requise - {case_id} ({artifact})",
            "high",
            False,
        )
    action_name = str(_payload(row).get("action_name") or "action")
    return (
        "action_blocked",
        f"Action bloquée - {case_id} ({action_name})",
        "crit",
        True,
    )


def _business_event_href(row: dict[str, object]) -> str:
    agent_id = str(row.get("agent_id") or "")
    if not agent_id:
        return ""
    params = {
        "conversation_id": str(row.get("conversation_id") or ""),
        "turn_id": str(row.get("turn_id") or ""),
    }
    capability_id = row.get("capability_id")
    if isinstance(capability_id, str) and capability_id:
        params["capability_id"] = capability_id
    query = urlencode({k: v for k, v in params.items() if v})
    return f"/agents/{agent_id}/metier{f'?{query}' if query else ''}"


def _business_event_items(
    *,
    state: dict[str, dict[str, str]],
    now: datetime,
    new_stamps: dict[str, str],
    agent_id: str | None = None,
) -> list[OperatorItem]:
    """Derive real operator items from pending/blocked business grammar events."""
    rows: list[dict[str, object]] = []
    for event_name in (
        business_events.BusinessEventName.VALIDATION_REQUESTED.value,
        business_events.BusinessEventName.ACTION_BLOCKED.value,
    ):
        try:
            rows.extend(
                business_events.business_event_rows(agent_id=agent_id, event_name=event_name)
            )
        except Exception as exc:
            sys.stderr.write(
                "tessera.observability.operator_items: "
                f"business_event_items failed for {event_name}: {exc}\n"
            )
            # best-effort: skip one failed business-event source — non-gating (0015)
            continue

    items: list[OperatorItem] = []
    for row in rows:
        aid = str(row.get("agent_id") or "")
        if not aid:
            continue
        event_name = str(row.get("event_name") or "")
        conversation_id = str(row.get("conversation_id") or "")
        turn_id = str(row.get("turn_id") or "")
        artifact_key = str(row.get("artifact_id") or row.get("case_id") or "none")
        item_id = f"{aid}.{event_name}.{conversation_id}.{turn_id}.{artifact_key}"
        st = state.get(item_id, {})
        category, title, priority, needs_escalation = _business_event_title(row)
        items.append(
            OperatorItem(
                item_id=item_id,
                agent_id=aid,
                case_id=str(row.get("case_id") or turn_id or conversation_id),
                category=category,
                type_label=category,
                title=title,
                language=str(row.get("language") or ""),
                source="Métier",
                priority=priority,
                created_at=_parse_dt(str(row.get("timestamp") or row.get("occurred_at") or "")),
                needs_escalation=needs_escalation,
                status=st.get("status", _DEFAULT_STATUS),
                assignee=st.get("assignee", ""),
                source_kind="business_event",
                detail_href=_business_event_href(row),
                queued_at=_resolve_queued_at(state, item_id, now, new_stamps),
            )
        )
    return items


def _dedupe_items(items: list[OperatorItem]) -> list[OperatorItem]:
    """Collapse duplicate natural backlog ids emitted by overlapping read paths."""
    seen: set[str] = set()
    unique: list[OperatorItem] = []
    for item in items:
        if item.item_id in seen:
            continue
        seen.add(item.item_id)
        unique.append(item)
    return unique


def load_items(agent_id: str | None = None) -> list[OperatorItem]:
    """Derive the real backlog from failed eval cases, **per-agent attributed**.

    Each item is a case that *this agent's own eval run* failed — real attribution, so the
    shared triage queue can be ventilated by agent (ADR 0015 §Migration E). With ``agent_id``
    set, only that agent's items are returned; ``None`` aggregates the whole fleet. An agent
    with no eval run of its own contributes nothing (honest — never a fabricated split).
    """
    from tessera.observability.store_spans import store_read

    with store_read("file", "operator_items.load", target="eval/reports") as read:
        items = _load_items_uninstrumented(agent_id)
        read.rows_read(len(items))
    return items


def _load_items_uninstrumented(agent_id: str | None = None) -> list[OperatorItem]:
    """The real work of :func:`load_items` — the eval snapshots, read from disk."""
    state = _load_state()
    now = _now()
    new_stamps: dict[str, str] = {}
    items: list[OperatorItem] = []
    for aid in _agent_targets(agent_id):
        try:
            snap = load_eval_snapshot(aid)
        except FileNotFoundError:
            continue  # no run for this agent → no items (never fabricate an attribution)
        # load_eval_snapshot(aid) matches only aid's own report (it raises otherwise), so
        # every case here is genuinely this agent's failure — assert the invariant cheaply.
        if snap.agent_id != aid:
            continue
        for s in snap.sessions:
            if s.passed:
                continue
            item_id = f"{aid}.{s.case_id}.{s.language}"
            st = state.get(item_id, {})
            items.append(
                OperatorItem(
                    item_id=item_id,
                    agent_id=aid,
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
                    queued_at=_resolve_queued_at(state, item_id, now, new_stamps),
                )
            )
    items.extend(
        _business_event_items(state=state, now=now, new_stamps=new_stamps, agent_id=agent_id)
    )
    items = _dedupe_items(items)
    # First observation is recorded once, in a single best-effort write per pass.
    _persist_first_seen(new_stamps)
    # Most urgent first: crit < high < mod < low, then oldest first.
    order = {"crit": 0, "high": 1, "mod": 2, "low": 3}
    items.sort(key=lambda i: (order.get(i.priority, 9), i.created_at))
    return items


def available_item_ids(nature: str | None = None) -> set[str]:
    """Known item ids for endpoint validation - the whole union, or one page's half.

    The item-state endpoints are per-page, so each validates against its own
    nature (ADR 0038): a mutation arriving from "A traiter" for an item that
    page cannot show is refused, not honoured across the partition.
    """
    items = load_items() if nature is None else load_items_for(nature)
    return {i.item_id for i in items}
