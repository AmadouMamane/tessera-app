"""Agent "A faire" cockpit overview (reference image 23).

The operator's personal action queue, now backed by the real operator backlog
(:mod:`tessera.observability.operator_items` - failed evaluation cases with a
durable per-item status/assignee). It exposes the KPI strip, the saved-views
filter rail, the task table, a per-item detail band and the right column
(type donut, SLA buckets, quick actions, recent activity). Status is mutated by
the item-state endpoint, so the page is functional, not a fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.operator_items import load_items

if TYPE_CHECKING:
    from tessera.observability.operator_items import OperatorItem

__all__ = ["compute_agent_a_faire"]

_HOUR = 3600
_WARN = 2 * _HOUR

_PRIO_LABEL = {"crit": "Critique", "high": "Elevee", "mod": "Moyenne", "low": "Faible"}
_TYPE_COLOR = {
    "crit": "#f87171",
    "high": "#e0763a",
    "mod": "#e0a23a",
    "low": "#34d399",
}
_TEAM = {
    "Garde-fous": "AI Safety",
    "Confidentialite": "Privacy",
    "RAG": "Knowledge",
    "Outils": "Platform",
    "Reglementaire": "Compliance",
    "Multilingue": "Localization",
    "Assistant": "Support",
}


def _fmt_remaining(item: OperatorItem, now: datetime) -> tuple[str, str]:
    """(label, tone) for the SLA cell."""
    if item.status == "done":
        return "Resolu", "ok"
    remaining = item.remaining_seconds(now)
    if remaining < 0:
        return "En retard", "crit"
    hours = int(remaining // _HOUR)
    minutes = int((remaining % _HOUR) // 60)
    label = f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"
    return label, ("warn" if remaining < _WARN else "ok")


def _status_label(item: OperatorItem) -> tuple[str, str]:
    """(label, tone) for the workflow status badge.

    Reflects the durable workflow state only; SLA breach is shown separately in
    the SLA cell, so taking charge of an overdue item is visibly reflected here.
    """
    if item.status == "done":
        return "Resolu", "done"
    if item.status == "progress":
        return "En cours", "progress"
    return "A traiter", "todo"


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


def _fmt_age(seconds: float) -> str:
    hours = int(seconds // _HOUR)
    minutes = int((seconds % _HOUR) // 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def _kpi(
    key: str, label: str, value: str, delta: str, good: bool, tone: str, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "tone": tone,
        "series": series,
    }


def _task(item: OperatorItem, now: datetime) -> dict[str, object]:
    sla, sla_tone = _fmt_remaining(item, now)
    status, status_tone = _status_label(item)
    return {
        "key": item.item_id,
        "priority": _PRIO_LABEL.get(item.priority, "Moyenne"),
        "prio_tone": item.priority,
        "type": item.type_label,
        "title": item.title,
        "source": item.source,
        "ref": item.case_id,
        "assignee": item.assignee or "Non assigne",
        "sla": sla,
        "sla_tone": sla_tone,
        "due": _fmt_dt(item.due_at()),
        "status": status,
        "status_tone": status_tone,
    }


def _detail(item: OperatorItem, now: datetime) -> dict[str, object]:
    sla, _ = _fmt_remaining(item, now)
    status, status_tone = _status_label(item)
    remaining = item.remaining_seconds(now)
    sla_value = ("-" if remaining < 0 else "") + _fmt_age(abs(remaining))
    sla_note = "Depasse" if remaining < 0 else "Dans les delais"
    return {
        "key": item.item_id,
        "title": "Detail selectionne",
        "selected": {
            "key": item.item_id,
            "id": item.item_id,
            "priority": _PRIO_LABEL.get(item.priority, "Moyenne"),
            "prio_tone": item.priority,
            "title": item.title,
            "subtitle": f"{item.type_label} - {item.source}",
            "cta": "Ouvrir dans les evaluations",
        },
        "tabs": ["Contexte", "Historique", "Preuves", "Relations"],
        "context": [
            {"label": "Cas", "value": item.case_id},
            {"label": "Categorie", "value": item.type_label},
            {"label": "Langue", "value": item.language.upper()},
            {"label": "Source", "value": item.source},
            {"label": "Date", "value": _fmt_dt(item.created_at)},
        ],
        "summary_label": "Resume",
        "summary": f"Cas d'evaluation en echec a revoir : {item.title}.",
        "sla_title": "Echeance & SLA",
        "sla_value": sla_value,
        "sla_note": sla_note,
        "sla_rows": [
            {"label": "Echeance", "value": _fmt_dt(item.due_at())},
            {"label": "Cree le", "value": _fmt_dt(item.created_at)},
            {"label": "Age", "value": _fmt_age(item.age_seconds(now))},
        ],
        "assign_title": "Assignation",
        "assign_label": "Assigne a",
        "assignee": item.assignee or "Non assigne",
        "team_label": "Equipe",
        "team": _TEAM.get(item.source, "Support"),
        "reassign": "M'assigner",
        "current_status": status,
        "current_status_tone": status_tone,
        "sla_cell": sla,
    }


def compute_agent_a_faire(now: datetime | None = None) -> dict[str, object]:
    """Return the full "A faire" overview payload from the real backlog.

    ``now`` is the reference instant for all SLA/age computations; it defaults
    to the current time and is injectable so tests are deterministic.
    """
    now = now or datetime.now(UTC)
    items = load_items()
    open_items = [i for i in items if i.status != "done"]

    urgent = sum(1 for i in open_items if i.priority == "crit")
    sla2h = sum(1 for i in open_items if 0 <= i.remaining_seconds(now) < _WARN)
    late = sum(1 for i in open_items if i.remaining_seconds(now) < 0)
    mine = sum(1 for i in open_items if i.assignee == "Moi")
    resolved = sum(1 for i in items if i.status == "done")
    on_time = len(open_items) - late
    sla_ok = round(100 * on_time / len(open_items)) if open_items else 100

    prio_series = [
        sum(1 for i in open_items if i.priority == p) for p in ("crit", "high", "mod", "low")
    ]

    kpis = [
        _kpi(
            "total",
            "A traiter (total)",
            str(len(open_items)),
            "file reelle",
            False,
            "red",
            prio_series,
        ),
        _kpi(
            "urgent",
            "A traiter (urgents)",
            str(urgent),
            "priorite crit.",
            False,
            "red",
            prio_series,
        ),
        _kpi("sla2h", "SLA < 2h", str(sla2h), "echeance proche", False, "amber", prio_series),
        _kpi("late", "En retard (SLA depasse)", str(late), "hors delai", False, "red", prio_series),
        _kpi("mine", "Assignes a moi", str(mine), "assignation", True, "teal", prio_series),
        _kpi("resolved", "Resolus", str(resolved), "traites", True, "teal", prio_series),
        _kpi(
            "avgtime",
            "Temps moyen de traitement",
            "-",
            "non instrumente",
            True,
            "amber",
            prio_series,
        ),
        _kpi(
            "slaok",
            "SLA respectes",
            f"{sla_ok}%",
            "ouverts dans les delais",
            True,
            "teal",
            prio_series,
        ),
    ]

    tasks = [_task(i, now) for i in items]
    details = [_detail(i, now) for i in items]

    return {
        "title": "A faire",
        "subtitle": "Vos taches, revues et validations en attente de traitement.",
        "rail": {
            "live": "Live",
            "segments": ["File reelle", "Cas d'evaluation en echec", "SLA en temps reel"],
            "period": "Run d'evaluation",
            "updated": now.strftime("%d/%m/%Y %H:%M:%S"),
            "now": "Maintenant",
            "scope": "Dernier run",
            "bulk": "Actions groupees",
        },
        "timeline": _timeline(items),
        "kpis": kpis,
        "filters": _filters(),
        "table": {
            "columns": [
                "Priorite",
                "Type",
                "Titre",
                "Source",
                "Assigne a",
                "SLA",
                "Echeance",
                "Statut",
            ],
            "tasks": tasks,
            "count": f"{len(open_items)} ouverts / {len(items)} elements",
            "showing": f"Afficher 1 - {len(tasks)} sur {len(tasks)}",
            "pages": [1],
            "per_page_label": "Lignes par page",
            "per_page": str(len(tasks)),
        },
        "detail": details[0] if details else None,
        "details": details,
        "donut": _donut(items),
        "sla": _sla(open_items, now),
        "quick": {
            "title": "Actions rapides",
            "items": [
                "Prendre en charge",
                "M'assigner",
                "Marquer resolu",
                "Rouvrir",
                "Ouvrir les evaluations",
                "Exporter la liste",
            ],
        },
        "activity": _activity(items),
        "status": {
            "title": "Statut & actions",
            "label": "Statut",
            "value": details[0]["current_status"] if details else "A traiter",
            "primary": "Prendre en charge",
            "secondary": "Marquer resolu",
        },
        "footer": {
            "check": f"Derniere synchronisation : {now.strftime('%d/%m/%Y %H:%M:%S')}",
            "status": "OK",
        },
    }


def _filters() -> dict[str, object]:
    return {
        "title": "Filtres actifs",
        "search": "Rechercher dans la liste...",
        "selects": [
            {"label": "Priorite", "value": "Toutes"},
            {"label": "Type", "value": "Tous les types"},
            {"label": "Statut", "value": "Tous les statuts"},
            {"label": "Assigne a", "value": "Tous"},
        ],
        "more": "Plus de filtres",
        "views_title": "Vues enregistrees",
        "views": ["Tous les cas", "Urgents", "SLA en risque", "Assignes a moi"],
        "views_cta": "Gerer les vues",
    }


def _timeline(items: list[OperatorItem]) -> dict[str, object]:
    recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:6]
    tone = {"crit": "crit", "high": "warn", "mod": "warn", "low": "ok"}
    return {
        "title": "Timeline evenements (run)",
        "cta": "Voir la timeline complete",
        "events": [
            {
                "time": i.created_at.strftime("%H:%M"),
                "label": i.type_label,
                "ref": i.case_id,
                "tone": tone.get(i.priority, "ok"),
            }
            for i in recent
        ],
    }


def _donut(items: list[OperatorItem]) -> dict[str, object]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for i in items:
        counts[i.priority] = counts.get(i.priority, 0) + 1
        labels[i.priority] = _PRIO_LABEL.get(i.priority, i.priority)
    total = len(items) or 1
    segments = [
        {
            "label": labels[p],
            "count": counts[p],
            "share": f"{round(100 * counts[p] / total)}%",
            "color": _TYPE_COLOR[p],
        }
        for p in ("crit", "high", "mod", "low")
        if counts.get(p)
    ]
    return {
        "title": "Repartition par priorite",
        "cta": "Voir le detail",
        "center": str(len(items)),
        "center_label": "Total",
        "segments": segments,
    }


def _sla(open_items: list[OperatorItem], now: datetime) -> dict[str, object]:
    counts = {"late": 0, "lt2h": 0, "h2_8": 0, "gt8h": 0}
    for i in open_items:
        remaining = i.remaining_seconds(now)
        if remaining < 0:
            counts["late"] += 1
        elif remaining < _WARN:
            counts["lt2h"] += 1
        elif remaining < 8 * _HOUR:
            counts["h2_8"] += 1
        else:
            counts["gt8h"] += 1
    return {
        "title": "SLA & echeances",
        "cta": "Voir les SLA",
        "buckets": [
            {"label": "En retard", "count": counts["late"], "color": "#f87171"},
            {"label": "< 2h", "count": counts["lt2h"], "color": "#e0763a"},
            {"label": "2h - 8h", "count": counts["h2_8"], "color": "#e0a23a"},
            {"label": "> 8h", "count": counts["gt8h"], "color": "#34d399"},
        ],
    }


def _activity(items: list[OperatorItem]) -> dict[str, object]:
    recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:4]
    return {
        "title": "Activite recente",
        "cta": "Voir toute l'activite",
        "items": [
            {"actor": i.source, "action": i.title, "time": i.created_at.strftime("%H:%M")}
            for i in recent
        ],
    }
