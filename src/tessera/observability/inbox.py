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
from tessera.observability.operator_items import NATURE_A_TRAITER, load_items_for

if TYPE_CHECKING:
    from tessera.observability.operator_items import OperatorItem

__all__ = ["compute_inbox_overview"]

# Localized free-text (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "rail_period": ("Événements métier", "Fachliche Ereignisse", "Business events"),
    "rail_sla": ("Temps réel", "Echtzeit", "Real time"),
    "rail_compare": ("Validations & blocages", "Freigaben & Sperren", "Validations & blocks"),
    "footer_src": (
        "Validations en attente et actions bloquées (grammaire métier)",
        "Ausstehende Freigaben und blockierte Aktionen (fachliche Grammatik)",
        "Pending validations and blocked actions (business grammar)",
    ),
    "v_todo": ("a signalé", "hat gemeldet", "reported"),
    "v_progress": ("traite", "bearbeitet", "handling"),
    "v_done": ("a résolu", "hat geloest", "resolved"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


_TYPE_COLOR = {
    "conversation": "#60a5fa",
    "incident": "#f87171",
    "alert": "#fbbf24",
    "approval": "#a78bfa",
    "access": "#34d399",
    "other": "#64748b",
}

# category -> the inbox "type" bucket (keeps the existing i18n labels/colours).
_TYPE_BUCKET: dict[str, str] = {
    "prompt_injection": "incident",
    "policy_violation": "incident",
    "regulatory_misstatement": "incident",
    "pii_leak": "alert",
    "tool_misuse": "alert",
    "action_blocked": "incident",
    "hallucination": "conversation",
    "citation_fabrication": "conversation",
    "language_mixing": "conversation",
    "escalation_failure": "approval",
    "validation_requested": "approval",
    "overconfidence": "other",
}

_PRIORITY_KEY = {"crit": "urgent", "high": "high", "mod": "medium", "low": "low"}
_STATUS_KEY = {"todo": "todo", "progress": "in_progress", "done": "resolved"}

_HOUR = 3600
_WARN = 2 * _HOUR


def _fmt_remaining(item: OperatorItem, now: datetime) -> str:
    if item.status == "done":
        return "-"
    remaining = item.remaining_seconds(now)
    if remaining < 0:
        return "En retard"
    hours = int(remaining // _HOUR)
    minutes = int((remaining % _HOUR) // 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def _fmt_due(item: OperatorItem) -> str:
    return item.due_at().strftime("%d/%m %H:%M")


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

    payload_items = [
        {
            "id": i.item_id,
            "agent_id": i.agent_id,
            "agent": agent_names.get(i.agent_id, i.agent_id),
            "priority": _PRIORITY_KEY.get(i.priority, "medium"),
            "type": _TYPE_BUCKET.get(i.category, "other"),
            "title": i.title,
            "source": i.source,
            "assignee": i.assignee or "—",
            "sla": _fmt_remaining(i, now),
            "sla_tone": i.sla_tone(now),
            "due": _fmt_due(i),
            "status": _STATUS_KEY.get(i.status, "todo"),
            "href": i.detail_href,
            "source_kind": i.source_kind,
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
