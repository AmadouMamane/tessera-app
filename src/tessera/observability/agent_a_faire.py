"""Agent "A faire" cockpit overview (reference image 23).

The operator's personal action queue, now backed by the real operator backlog
(:mod:`tessera.observability.operator_items` - failed evaluation cases with a
durable per-item status/assignee). It exposes the KPI strip, the saved-views
filter rail, the task table, a per-item detail band and the right column
(type donut, SLA buckets, quick actions, recent activity). Status is mutated by
the item-state endpoint, so the page is functional, not a fixture.

The whole chrome is trilingual (FR / DE / EN): ``compute_agent_a_faire`` takes a
``lang`` and every operator-facing label resolves through the ``_TR`` table.
Per-item *data* (title, category label, source domain) stays verbatim - it is
sourced from the real backlog, not localized here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.operator_items import NATURE_A_FAIRE, load_items_for

if TYPE_CHECKING:
    from tessera.observability.operator_items import OperatorItem

__all__ = ["compute_agent_a_faire"]

_HOUR = 3600
_WARN = 2 * _HOUR

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

# Operator-facing chrome strings: key -> (fr, de, en). Per-item data (item title,
# category label, source domain) is not translated here - it is real backlog data.
_TR: dict[str, tuple[str, str, str]] = {
    # priority badge
    "prio_crit": ("Critique", "Kritisch", "Critical"),
    "prio_high": ("Elevee", "Hoch", "High"),
    "prio_mod": ("Moyenne", "Mittel", "Medium"),
    "prio_low": ("Faible", "Niedrig", "Low"),
    # workflow status badge
    "st_done": ("Resolu", "Geloest", "Resolved"),
    "st_progress": ("En cours", "In Bearbeitung", "In progress"),
    "st_todo": ("A traiter", "Zu bearbeiten", "To do"),
    # SLA cell
    "sla_overdue": ("En retard", "Ueberfaellig", "Overdue"),
    "unassigned": ("Non assigne", "Nicht zugewiesen", "Unassigned"),
    "sla_past": ("Depasse", "Ueberschritten", "Overdue"),
    "sla_ontime": ("Dans les delais", "Im Zeitrahmen", "On time"),
    # header
    "title": ("A faire", "Aufgaben", "To do"),
    # ADR 0038 — this page's half is the EVAL one; "validations" belong to A traiter.
    "subtitle": (
        "Les cas d'evaluation en echec de vos agents, a revoir et resoudre.",
        "Die fehlgeschlagenen Evaluierungsfaelle Ihrer Agenten, zu pruefen und zu loesen.",
        "Your agents' failed evaluation cases, to review and resolve.",
    ),
    # rail
    "live": ("Live", "Live", "Live"),
    "seg_queue": ("File reelle", "Echte Warteschlange", "Real queue"),
    "seg_failed": (
        "Cas d'evaluation en echec",
        "Fehlgeschlagene Evaluierungsfaelle",
        "Failed evaluation cases",
    ),
    "seg_sla": ("SLA en temps reel", "SLA in Echtzeit", "Real-time SLA"),
    "rail_period": ("Run d'evaluation", "Evaluierungslauf", "Evaluation run"),
    "now": ("Maintenant", "Jetzt", "Now"),
    "rail_scope": ("Dernier run", "Letzter Lauf", "Last run"),
    "bulk": ("Actions groupees", "Sammelaktionen", "Bulk actions"),
    # timeline
    "tl_title": ("Timeline evenements (run)", "Ereignis-Timeline (Lauf)", "Event timeline (run)"),
    "tl_cta": (
        "Voir la timeline complete",
        "Vollstaendige Timeline anzeigen",
        "View full timeline",
    ),
    # KPI labels
    # "A revoir", not "A traiter": on the A-faire page a KPI named after the
    # OTHER queue page read as a cross-reference it never was (ADR 0038).
    "kpi_total": ("A revoir (total)", "Zu pruefen (gesamt)", "To review (total)"),
    "kpi_total_d": ("file reelle", "echte Warteschlange", "real queue"),
    "kpi_urgent": ("A revoir (urgents)", "Zu pruefen (dringend)", "To review (urgent)"),
    "kpi_urgent_d": ("priorite crit.", "Prio. kritisch", "crit. priority"),
    "kpi_sla2h": ("SLA < 2h", "SLA < 2h", "SLA < 2h"),
    "kpi_sla2h_d": ("echeance proche", "Frist nah", "deadline near"),
    "kpi_late": (
        "En retard (SLA depasse)",
        "Ueberfaellig (SLA ueberschritten)",
        "Overdue (SLA exceeded)",
    ),
    "kpi_late_d": ("hors delai", "ueber Frist", "past deadline"),
    "kpi_mine": ("Assignes a moi", "Mir zugewiesen", "Assigned to me"),
    "kpi_mine_d": ("assignation", "Zuweisung", "assignment"),
    "kpi_resolved": ("Resolus", "Geloest", "Resolved"),
    "kpi_resolved_d": ("traites", "bearbeitet", "handled"),
    "kpi_avgtime": (
        "Temps moyen de traitement",
        "Durchschnittliche Bearbeitungszeit",
        "Average handling time",
    ),
    "kpi_avgtime_d": ("non instrumente", "nicht instrumentiert", "not instrumented"),
    "kpi_slaok": ("SLA respectes", "SLA eingehalten", "SLA met"),
    "kpi_slaok_d": ("ouverts dans les delais", "offen im Zeitrahmen", "open on time"),
    # filters
    "f_title": ("Filtres actifs", "Aktive Filter", "Active filters"),
    "f_search": ("Rechercher dans la liste...", "In der Liste suchen...", "Search the list..."),
    "f_prio": ("Priorite", "Prioritaet", "Priority"),
    "f_all_f": ("Toutes", "Alle", "All"),
    "f_type": ("Type", "Typ", "Type"),
    "f_all_types": ("Tous les types", "Alle Typen", "All types"),
    "f_status": ("Statut", "Status", "Status"),
    "f_all_status": ("Tous les statuts", "Alle Status", "All statuses"),
    "f_assignee": ("Assigne a", "Zugewiesen an", "Assigned to"),
    "f_all": ("Tous", "Alle", "All"),
    "f_more": ("Plus de filtres", "Weitere Filter", "More filters"),
    "f_views": ("Vues enregistrees", "Gespeicherte Ansichten", "Saved views"),
    "v_all_cases": ("Tous les cas", "Alle Faelle", "All cases"),
    "v_urgent": ("Urgents", "Dringend", "Urgent"),
    "v_sla_risk": ("SLA en risque", "SLA gefaehrdet", "SLA at risk"),
    "v_mine": ("Assignes a moi", "Mir zugewiesen", "Assigned to me"),
    "f_manage": ("Gerer les vues", "Ansichten verwalten", "Manage views"),
    # table columns
    "c_prio": ("Priorite", "Prioritaet", "Priority"),
    "c_type": ("Type", "Typ", "Type"),
    "c_title": ("Titre", "Titel", "Title"),
    "c_source": ("Source", "Quelle", "Source"),
    "c_assignee": ("Assigne a", "Zugewiesen an", "Assigned to"),
    "c_sla": ("SLA", "SLA", "SLA"),
    "c_due": ("Echeance", "Frist", "Due"),
    "c_status": ("Statut", "Status", "Status"),
    "t_count": (
        "{open} ouverts / {total} elements",
        "{open} offen / {total} Elemente",
        "{open} open / {total} items",
    ),
    "t_showing": ("Afficher 1 - {n} sur {n}", "Zeige 1 - {n} von {n}", "Showing 1 - {n} of {n}"),
    "t_per_page": ("Lignes par page", "Zeilen pro Seite", "Rows per page"),
    # donut
    "d_title": ("Repartition par priorite", "Verteilung nach Prioritaet", "Breakdown by priority"),
    "d_cta": ("Voir le detail", "Details anzeigen", "View details"),
    "d_total": ("Total", "Gesamt", "Total"),
    # SLA panel
    "s_title": ("SLA & echeances", "SLA & Fristen", "SLA & deadlines"),
    "s_cta": ("Voir les SLA", "SLA anzeigen", "View SLAs"),
    "s_late": ("En retard", "Ueberfaellig", "Overdue"),
    # quick actions
    "q_title": ("Actions rapides", "Schnellaktionen", "Quick actions"),
    "q_take": ("Prendre en charge", "Uebernehmen", "Take charge"),
    "q_assign": ("M'assigner", "Mir zuweisen", "Assign to me"),
    "q_resolve": ("Marquer resolu", "Als geloest markieren", "Mark resolved"),
    "q_reopen": ("Rouvrir", "Wieder oeffnen", "Reopen"),
    "q_open_eval": ("Ouvrir les evaluations", "Evaluierungen oeffnen", "Open evaluations"),
    "q_export": ("Exporter la liste", "Liste exportieren", "Export list"),
    # recent activity
    "a_title": ("Activite recente", "Letzte Aktivitaet", "Recent activity"),
    "a_cta": ("Voir toute l'activite", "Gesamte Aktivitaet anzeigen", "View all activity"),
    # detail drawer
    "det_title": ("Detail selectionne", "Ausgewaehltes Detail", "Selected detail"),
    "det_cta": ("Ouvrir dans les evaluations", "In Evaluierungen oeffnen", "Open in evaluations"),
    "tab_context": ("Contexte", "Kontext", "Context"),
    "tab_history": ("Historique", "Verlauf", "History"),
    "tab_evidence": ("Preuves", "Nachweise", "Evidence"),
    "tab_relations": ("Relations", "Beziehungen", "Relations"),
    "ctx_case": ("Cas", "Fall", "Case"),
    "ctx_category": ("Categorie", "Kategorie", "Category"),
    "ctx_language": ("Langue", "Sprache", "Language"),
    "ctx_source": ("Source", "Quelle", "Source"),
    "ctx_date": ("Date", "Datum", "Date"),
    "summary_label": ("Resume", "Zusammenfassung", "Summary"),
    "summary": (
        "Cas d'evaluation en echec a revoir : {title}.",
        "Fehlgeschlagener Evaluierungsfall zu pruefen: {title}.",
        "Failed evaluation case to review: {title}.",
    ),
    "sla_drawer_title": ("Echeance & SLA", "Frist & SLA", "Deadline & SLA"),
    "row_due": ("Echeance", "Frist", "Due"),
    # ADR 0039 — the honest dual timestamp: when it entered the queue (the SLA
    # clock) vs the underlying case's own date (provenance), never conflated.
    "row_queued": ("En file depuis", "In Warteschlange seit", "In queue since"),
    "row_created": ("Cas date du", "Fall vom", "Case dated"),
    "row_wait": ("Attente en file", "Wartezeit", "Time in queue"),
    "assign_title": ("Assignation", "Zuweisung", "Assignment"),
    "assign_label": ("Assigne a", "Zugewiesen an", "Assigned to"),
    "team_label": ("Equipe", "Team", "Team"),
    "reassign": ("M'assigner", "Mir zuweisen", "Assign to me"),
    # status & actions section
    "status_title": ("Statut & actions", "Status & Aktionen", "Status & actions"),
    "status_label": ("Statut", "Status", "Status"),
    "status_primary": ("Prendre en charge", "Uebernehmen", "Take charge"),
    "status_secondary": ("Marquer resolu", "Als geloest markieren", "Mark resolved"),
    # footer
    "footer_check": (
        "Derniere synchronisation : {ts}",
        "Letzte Synchronisierung: {ts}",
        "Last sync: {ts}",
    ),
    "footer_ok": ("OK", "OK", "OK"),
}

_PRIO_KEY = {"crit": "prio_crit", "high": "prio_high", "mod": "prio_mod", "low": "prio_low"}
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


def _t(key: str, lang: str, **fmt: object) -> str:
    text = _TR[key][_LANG_IDX.get(lang, 0)]
    return text.format(**fmt) if fmt else text


def _prio_label(priority: str, lang: str) -> str:
    return _t(_PRIO_KEY.get(priority, "prio_mod"), lang)


def _fmt_remaining(item: OperatorItem, now: datetime, lang: str) -> tuple[str, str]:
    """(label, tone) for the SLA cell."""
    if item.status == "done":
        return _t("st_done", lang), "ok"
    remaining = item.remaining_seconds(now)
    if remaining < 0:
        return _t("sla_overdue", lang), "crit"
    hours = int(remaining // _HOUR)
    minutes = int((remaining % _HOUR) // 60)
    label = f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"
    return label, ("warn" if remaining < _WARN else "ok")


def _status_label(item: OperatorItem, lang: str) -> tuple[str, str]:
    """(label, tone) for the workflow status badge.

    Reflects the durable workflow state only; SLA breach is shown separately in
    the SLA cell, so taking charge of an overdue item is visibly reflected here.
    """
    if item.status == "done":
        return _t("st_done", lang), "done"
    if item.status == "progress":
        return _t("st_progress", lang), "progress"
    return _t("st_todo", lang), "todo"


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


def _task(item: OperatorItem, now: datetime, lang: str) -> dict[str, object]:
    sla, sla_tone = _fmt_remaining(item, now, lang)
    status, status_tone = _status_label(item, lang)
    return {
        "key": item.item_id,
        "priority": _prio_label(item.priority, lang),
        "prio_tone": item.priority,
        "type": item.type_label,
        "title": item.title,
        "source": item.source,
        "ref": item.case_id,
        "assignee": item.assignee or _t("unassigned", lang),
        "sla": sla,
        "sla_tone": sla_tone,
        "due": _fmt_dt(item.due_at()),
        "status": status,
        "status_tone": status_tone,
    }


def _detail(item: OperatorItem, now: datetime, lang: str) -> dict[str, object]:
    sla, _ = _fmt_remaining(item, now, lang)
    status, status_tone = _status_label(item, lang)
    remaining = item.remaining_seconds(now)
    sla_value = ("-" if remaining < 0 else "") + _fmt_age(abs(remaining))
    sla_note = _t("sla_past", lang) if remaining < 0 else _t("sla_ontime", lang)
    return {
        "key": item.item_id,
        "title": _t("det_title", lang),
        "selected": {
            "key": item.item_id,
            "id": item.item_id,
            "priority": _prio_label(item.priority, lang),
            "prio_tone": item.priority,
            "title": item.title,
            "subtitle": f"{item.type_label} - {item.source}",
            "cta": _t("det_cta", lang),
        },
        "tabs": [
            _t("tab_context", lang),
            _t("tab_history", lang),
            _t("tab_evidence", lang),
            _t("tab_relations", lang),
        ],
        "context": [
            {"label": _t("ctx_case", lang), "value": item.case_id},
            {"label": _t("ctx_category", lang), "value": item.type_label},
            {"label": _t("ctx_language", lang), "value": item.language.upper()},
            {"label": _t("ctx_source", lang), "value": item.source},
            {"label": _t("ctx_date", lang), "value": _fmt_dt(item.created_at)},
        ],
        "summary_label": _t("summary_label", lang),
        "summary": _t("summary", lang, title=item.title),
        "sla_title": _t("sla_drawer_title", lang),
        "sla_value": sla_value,
        "sla_note": sla_note,
        "sla_tone": item.sla_tone(now),
        "sla_rows": [
            {"label": _t("row_due", lang), "value": _fmt_dt(item.due_at())},
            {"label": _t("row_queued", lang), "value": _fmt_dt(item.sla_anchor())},
            {"label": _t("row_wait", lang), "value": _fmt_age(item.queued_seconds(now))},
            {"label": _t("row_created", lang), "value": _fmt_dt(item.created_at)},
        ],
        "assign_title": _t("assign_title", lang),
        "assign_label": _t("assign_label", lang),
        "assignee": item.assignee or _t("unassigned", lang),
        "team_label": _t("team_label", lang),
        "team": _TEAM.get(item.source, "Support"),
        "reassign": _t("reassign", lang),
        "current_status": status,
        "current_status_tone": status_tone,
        "sla_cell": sla,
    }


def compute_agent_a_faire(lang: str = "fr", now: datetime | None = None) -> dict[str, object]:
    """Return the full "A faire" overview payload from the real backlog.

    ``lang`` selects the locale (fr / de / en) for every operator-facing label.
    ``now`` is the reference instant for all SLA/age computations; it defaults
    to the current time and is injectable so tests are deterministic.
    """
    now = now or datetime.now(UTC)
    # ADR 0038 — this page serves the eval/governance half of the backlog, and
    # only it; the business half belongs to "A traiter" (compute_inbox_overview).
    items = load_items_for(NATURE_A_FAIRE)
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
            _t("kpi_total", lang),
            str(len(open_items)),
            _t("kpi_total_d", lang),
            False,
            "red",
            prio_series,
        ),
        _kpi(
            "urgent",
            _t("kpi_urgent", lang),
            str(urgent),
            _t("kpi_urgent_d", lang),
            False,
            "red",
            prio_series,
        ),
        _kpi(
            "sla2h",
            _t("kpi_sla2h", lang),
            str(sla2h),
            _t("kpi_sla2h_d", lang),
            False,
            "amber",
            prio_series,
        ),
        _kpi(
            "late",
            _t("kpi_late", lang),
            str(late),
            _t("kpi_late_d", lang),
            False,
            "red",
            prio_series,
        ),
        _kpi(
            "mine",
            _t("kpi_mine", lang),
            str(mine),
            _t("kpi_mine_d", lang),
            True,
            "teal",
            prio_series,
        ),
        _kpi(
            "resolved",
            _t("kpi_resolved", lang),
            str(resolved),
            _t("kpi_resolved_d", lang),
            True,
            "teal",
            prio_series,
        ),
        _kpi(
            "avgtime",
            _t("kpi_avgtime", lang),
            "-",
            _t("kpi_avgtime_d", lang),
            True,
            "amber",
            prio_series,
        ),
        _kpi(
            "slaok",
            _t("kpi_slaok", lang),
            f"{sla_ok}%",
            _t("kpi_slaok_d", lang),
            True,
            "teal",
            prio_series,
        ),
    ]

    tasks = [_task(i, now, lang) for i in items]
    details = [_detail(i, now, lang) for i in items]

    return {
        "title": _t("title", lang),
        "subtitle": _t("subtitle", lang),
        "rail": {
            "live": _t("live", lang),
            "segments": [_t("seg_queue", lang), _t("seg_failed", lang), _t("seg_sla", lang)],
            "period": _t("rail_period", lang),
            "updated": now.strftime("%d/%m/%Y %H:%M:%S"),
            "now": _t("now", lang),
            "scope": _t("rail_scope", lang),
            "bulk": _t("bulk", lang),
        },
        "timeline": _timeline(items, lang),
        "kpis": kpis,
        "filters": _filters(lang),
        "table": {
            "columns": [
                _t("c_prio", lang),
                _t("c_type", lang),
                _t("c_title", lang),
                _t("c_source", lang),
                _t("c_assignee", lang),
                _t("c_sla", lang),
                _t("c_due", lang),
                _t("c_status", lang),
            ],
            "tasks": tasks,
            "count": _t("t_count", lang, open=len(open_items), total=len(items)),
            "showing": _t("t_showing", lang, n=len(tasks)),
            "pages": [1],
            "per_page_label": _t("t_per_page", lang),
            "per_page": str(len(tasks)),
        },
        "detail": details[0] if details else None,
        "details": details,
        "donut": _donut(items, lang),
        "sla": _sla(open_items, now, lang),
        "quick": {
            "title": _t("q_title", lang),
            "items": [
                _t("q_take", lang),
                _t("q_assign", lang),
                _t("q_resolve", lang),
                _t("q_reopen", lang),
                _t("q_open_eval", lang),
                _t("q_export", lang),
            ],
        },
        "activity": _activity(items, lang),
        "status": {
            "title": _t("status_title", lang),
            "label": _t("status_label", lang),
            "value": details[0]["current_status"] if details else _t("st_todo", lang),
            "primary": _t("status_primary", lang),
            "secondary": _t("status_secondary", lang),
        },
        "footer": {
            "check": _t("footer_check", lang, ts=now.strftime("%d/%m/%Y %H:%M:%S")),
            "status": _t("footer_ok", lang),
        },
    }


def _filters(lang: str) -> dict[str, object]:
    return {
        "title": _t("f_title", lang),
        "search": _t("f_search", lang),
        "selects": [
            {"label": _t("f_prio", lang), "value": _t("f_all_f", lang)},
            {"label": _t("f_type", lang), "value": _t("f_all_types", lang)},
            {"label": _t("f_status", lang), "value": _t("f_all_status", lang)},
            {"label": _t("f_assignee", lang), "value": _t("f_all", lang)},
        ],
        "more": _t("f_more", lang),
        "views_title": _t("f_views", lang),
        "views": [
            _t("v_all_cases", lang),
            _t("v_urgent", lang),
            _t("v_sla_risk", lang),
            _t("v_mine", lang),
        ],
        "views_cta": _t("f_manage", lang),
    }


def _timeline(items: list[OperatorItem], lang: str) -> dict[str, object]:
    recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:6]
    tone = {"crit": "crit", "high": "warn", "mod": "warn", "low": "ok"}
    return {
        "title": _t("tl_title", lang),
        "cta": _t("tl_cta", lang),
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


def _donut(items: list[OperatorItem], lang: str) -> dict[str, object]:
    counts: dict[str, int] = {}
    for i in items:
        counts[i.priority] = counts.get(i.priority, 0) + 1
    total = len(items) or 1
    segments = [
        {
            "label": _prio_label(p, lang),
            "count": counts[p],
            "share": f"{round(100 * counts[p] / total)}%",
            "color": _TYPE_COLOR[p],
        }
        for p in ("crit", "high", "mod", "low")
        if counts.get(p)
    ]
    return {
        "title": _t("d_title", lang),
        "cta": _t("d_cta", lang),
        "center": str(len(items)),
        "center_label": _t("d_total", lang),
        "segments": segments,
    }


def _sla(open_items: list[OperatorItem], now: datetime, lang: str) -> dict[str, object]:
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
        "title": _t("s_title", lang),
        "cta": _t("s_cta", lang),
        "buckets": [
            {"label": _t("s_late", lang), "count": counts["late"], "color": "#f87171"},
            {"label": "< 2h", "count": counts["lt2h"], "color": "#e0763a"},
            {"label": "2h - 8h", "count": counts["h2_8"], "color": "#e0a23a"},
            {"label": "> 8h", "count": counts["gt8h"], "color": "#34d399"},
        ],
    }


def _activity(items: list[OperatorItem], lang: str) -> dict[str, object]:
    recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:4]
    return {
        "title": _t("a_title", lang),
        "cta": _t("a_cta", lang),
        "items": [
            {"actor": i.source, "action": i.title, "time": i.created_at.strftime("%H:%M")}
            for i in recent
        ],
    }
