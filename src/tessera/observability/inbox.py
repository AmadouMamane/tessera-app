"""Inbox / "A traiter" cockpit overview (page #24).

Composes the "A traiter" overview from the BUSINESS half of the real operator
backlog (:mod:`tessera.observability.operator_items`, ADR 0038 - pending
validations and blocked actions from the business grammar, with a durable
per-item status/assignee): the queue posture KPIs (open, urgent, SLA-at-risk,
overdue, assigned-to-me, resolved, resolution rate), the task queue, the
by-type distribution, the SLA buckets and the recent activity. Status is
mutated by the item-state endpoint, so the page is functional, not a fixture.
The eval/governance half belongs to "A faire" (:mod:`agent_a_faire`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.operator_items import (
    NATURE_A_TRAITER,
    load_items_for,
    transitions_by_item,
)

if TYPE_CHECKING:
    from tessera.observability.operator_items import OperatorItem

__all__ = ["compute_inbox_overview"]

# Localized free-text (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "rail_period": ("Décisions métier", "Fachliche Entscheidungen", "Business decisions"),
    "rail_sla": ("État présent", "Aktueller Stand", "Current state"),
    "rail_compare": (
        "Validations et actions arrêtées",
        "Freigaben und gestoppte Aktionen",
        "Approvals and stopped actions",
    ),
    "footer_src": (
        "Journal des validations et des actions arrêtées",
        "Protokoll der Freigaben und gestoppten Aktionen",
        "Approval and stopped-action log",
    ),
    "v_todo": ("a signalé", "hat gemeldet", "reported"),
    "v_progress": ("traite", "bearbeitet", "handling"),
    "v_done": ("a résolu", "hat geloest", "resolved"),
    "overdue": ("En retard", "Überfällig", "Overdue"),
    "validation_title": (
        "Validation à donner — {case_id}",
        "Freigabe erforderlich — {case_id}",
        "Approval needed — {case_id}",
    ),
    "blocked_title": (
        "Action arrêtée — {case_id}",
        "Aktion gestoppt — {case_id}",
        "Action stopped — {case_id}",
    ),
    # journaled transitions (WF-01)
    "tr_st_todo": ("À traiter", "Zu bearbeiten", "To do"),
    "tr_st_progress": ("En cours", "In Bearbeitung", "In progress"),
    "tr_st_done": ("Résolu", "Gelöst", "Resolved"),
    "tr_assignee": ("Assignation", "Zuweisung", "Assignment"),
    "tr_unassigned": ("non assigné", "nicht zugewiesen", "unassigned"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _transition_rows_for(
    journal: dict[str, list[dict[str, str]]], item_id: str, lang: str
) -> list[dict[str, str]]:
    """Journaled transitions of one case (WF-01), localized, oldest first.

    Real rows from the append-only journal, each naming its verified author
    (ADR 0024). An empty list is the honest answer for a case that never moved
    since the journal opened.
    """

    def word(value: str) -> str:
        key = {"todo": "tr_st_todo", "progress": "tr_st_progress", "done": "tr_st_done"}.get(value)
        return _t(key, lang) if key else value

    def fmt_at(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value

    rows: list[dict[str, str]] = []
    for row in journal.get(item_id, []):
        if row.get("kind") == "assignee":
            frm = row.get("from", "") or _t("tr_unassigned", lang)
            to = row.get("to", "") or _t("tr_unassigned", lang)
            label = f"{_t('tr_assignee', lang)} : {frm} → {to}"
        else:
            label = f"{word(row.get('from', ''))} → {word(row.get('to', ''))}"
        rows.append({"at": fmt_at(row.get("at", "")), "label": label, "by": row.get("by", "")})
    return rows


_TYPE_COLOR = {
    "conversation": "#60a5fa",
    "incident": "#f87171",
    "alert": "#fbbf24",
    "approval": "#a78bfa",
    "access": "#34d399",
    "other": "#64748b",
}

# category -> the inbox "type" bucket. Only the BUSINESS categories remain:
# since ADR 0038 this page serves the business half only, and the eval-category
# entries that used to live here were dead the moment the partition landed —
# a map that still claimed them would read as "this page can show them".
# Anything unknown falls back to "other" explicitly.
_TYPE_BUCKET: dict[str, str] = {
    "action_blocked": "incident",
    "validation_requested": "approval",
}

_PRIORITY_KEY = {"crit": "urgent", "high": "high", "mod": "medium", "low": "low"}
_STATUS_KEY = {"todo": "todo", "progress": "in_progress", "done": "resolved"}

_HOUR = 3600
_WARN = 2 * _HOUR


def _fmt_remaining(item: OperatorItem, now: datetime, lang: str) -> str:
    if item.status == "done":
        return "-"
    remaining = item.remaining_seconds(now)
    if remaining < 0:
        return _t("overdue", lang)
    hours = int(remaining // _HOUR)
    minutes = int((remaining % _HOUR) // 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def _fmt_due(item: OperatorItem) -> str:
    return item.due_at().strftime("%d/%m %H:%M")


def _display_title(item: OperatorItem, lang: str) -> str:
    """Human title for the queue; the raw event remains unchanged in the ledger."""
    key = {
        "validation_requested": "validation_title",
        "action_blocked": "blocked_title",
    }.get(item.category)
    return _t(key, lang).format(case_id=item.case_id) if key else item.title


def _kpi(
    key: str, value: str, delta_label: str, good_is_up: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "delta_label": delta_label,
        "good_is_up": good_is_up,
        "series": series,
    }


def _agent_names() -> dict[str, str]:
    """`{agent_id: display name}` from the registry, for labelling ventilated items."""
    try:
        from tessera.agent.registry import list_agents

        return {a.id: a.name for a in list_agents()}
    except Exception:  # never break the queue over a label lookup
        return {}


def compute_inbox_overview(
    now: datetime | None = None, lang: str = "fr", agent_id: str | None = None
) -> dict[str, object]:
    """Return the full Inbox / A traiter overview payload from real items.

    ``now`` is the reference instant for all SLA/age computations; it defaults
    to the current time and is injectable so tests are deterministic. ``agent_id``
    ventilates the shared queue to one agent's own failed cases (ADR 0015 §Migration E);
    ``None`` aggregates the whole fleet, each item still carrying its source agent.
    """
    lang = _norm_lang(lang)
    now = now or datetime.now(UTC)
    # ADR 0038 — this page serves the business half of the backlog, and only
    # it; the eval/governance half belongs to "A faire" (compute_agent_a_faire).
    items = load_items_for(NATURE_A_TRAITER, agent_id)
    agent_names = _agent_names()
    open_items = [i for i in items if i.status != "done"]
    done_items = [i for i in items if i.status == "done"]

    urgent = sum(1 for i in open_items if i.priority == "crit")
    sla_2h = sum(1 for i in open_items if 0 <= i.remaining_seconds(now) < _WARN)
    overdue = sum(1 for i in open_items if i.remaining_seconds(now) < 0)
    assigned = sum(1 for i in open_items if i.assignee == "Moi")
    total = len(open_items)
    resolved = len(done_items)
    resolution_rate = round(100 * resolved / len(items)) if items else 0

    # Real distribution series (per-bucket counts) - not a fabricated time-series.
    bucket_counts: dict[str, int] = {}
    for i in open_items:
        bucket = _TYPE_BUCKET.get(i.category, "other")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    series = [bucket_counts.get(k, 0) for k in _TYPE_COLOR]

    kpis = [
        _kpi("total", str(total), "-", False, series),
        _kpi("urgent", str(urgent), "-", False, series),
        _kpi("sla_2h", str(sla_2h), "-", False, series),
        _kpi("overdue", str(overdue), "-", False, series),
        _kpi("assigned", str(assigned), "-", True, series),
        _kpi("resolved", str(resolved), "-", True, series),
        _kpi("avg_time", "-", "-", False, series),
        _kpi("resolution_rate", f"{resolution_rate}%", "-", True, series),
    ]

    rail = {
        "period": _t("rail_period", lang),
        "sla": _t("rail_sla", lang),
        "updated": now.strftime("%d/%m/%Y %H:%M:%S"),
        "compare": _t("rail_compare", lang),
    }

    # WF-01 — one journal scan decorates the whole backlog with its real,
    # attributed transition rows (never one file scan per case).
    journal = transitions_by_item()
    payload_items = [
        {
            "id": i.item_id,
            "agent_id": i.agent_id,
            "agent": agent_names.get(i.agent_id, i.agent_id),
            "priority": _PRIORITY_KEY.get(i.priority, "medium"),
            "type": _TYPE_BUCKET.get(i.category, "other"),
            "title": _display_title(i, lang),
            "source": i.source,
            "assignee": i.assignee or "—",
            "sla": _fmt_remaining(i, now, lang),
            "sla_tone": i.sla_tone(now),
            "due": _fmt_due(i),
            "status": _STATUS_KEY.get(i.status, "todo"),
            "href": i.detail_href,
            "source_kind": i.source_kind,
            "transitions": _transition_rows_for(journal, i.item_id, lang),
        }
        for i in items
    ]

    by_type_total = len(items) or 1
    type_counts: dict[str, int] = {}
    for i in items:
        bucket = _TYPE_BUCKET.get(i.category, "other")
        type_counts[bucket] = type_counts.get(bucket, 0) + 1
    by_type = [
        {
            "key": key,
            "count": type_counts.get(key, 0),
            "pct": round(100 * type_counts.get(key, 0) / by_type_total),
            "color": color,
        }
        for key, color in _TYPE_COLOR.items()
        if type_counts.get(key, 0) > 0
    ]

    sla_buckets = _sla_buckets(open_items, now)
    recent_activity = _recent_activity(items, lang)

    return {
        "generated_at": now.isoformat(),
        "rail": rail,
        "kpis": kpis,
        "items": payload_items,
        "total_items": len(items),
        "by_type": by_type,
        "by_type_total": len(items),
        "sla_buckets": sla_buckets,
        "recent_activity": recent_activity,
        "footer": {"total": len(items), "source": _t("footer_src", lang)},
    }


def _sla_buckets(open_items: list[OperatorItem], now: datetime) -> list[dict[str, object]]:
    counts = {"overdue": 0, "lt2h": 0, "h2_8": 0, "gt8h": 0}
    for i in open_items:
        remaining = i.remaining_seconds(now)
        if remaining < 0:
            counts["overdue"] += 1
        elif remaining < _WARN:
            counts["lt2h"] += 1
        elif remaining < 8 * _HOUR:
            counts["h2_8"] += 1
        else:
            counts["gt8h"] += 1
    colors = {"overdue": "#f87171", "lt2h": "#fbbf24", "h2_8": "#fbbf24", "gt8h": "#34d399"}
    return [{"key": k, "count": counts[k], "color": colors[k]} for k in counts]


def _recent_activity(items: list[OperatorItem], lang: str) -> list[dict[str, object]]:
    recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:5]
    out: list[dict[str, object]] = []
    for i in recent:
        verb = {
            "todo": _t("v_todo", lang),
            "progress": _t("v_progress", lang),
            "done": _t("v_done", lang),
        }.get(i.status, _t("v_todo", lang))
        out.append(
            {
                "time": i.created_at.strftime("%H:%M"),
                "actor": i.source,
                "action": f"{verb} {i.case_id}",
            }
        )
    return out
