"""Agent "A faire" cockpit overview (reference image 23).

The operator's personal action queue, now backed by the real operator backlog
(:mod:`tessera.observability.operator_items` - failed evaluation cases with a
durable per-item status/assignee). It exposes the KPI strip, the saved-views
filter rail, the task table, a per-item detail band and the right column
(type donut, SLA buckets, quick actions, recent activity). Status is mutated by
the item-state endpoint, so the page is functional, not a fixture.

The whole first reading is trilingual (FR / DE / EN): ``compute_agent_a_faire``
takes a ``lang`` and every operator-facing label resolves through the ``_TR``
table. The raw case id remains visible as the evidence reference; the imported
English catalogue title never has to carry the operator-facing meaning alone.
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

# Operator-facing strings: key -> (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    # priority badge
    "prio_crit": ("Critique", "Kritisch", "Critical"),
    "prio_high": ("Élevée", "Hoch", "High"),
    "prio_mod": ("Moyenne", "Mittel", "Medium"),
    "prio_low": ("Faible", "Niedrig", "Low"),
    # workflow status badge
    "st_done": ("Résolu", "Gelöst", "Resolved"),
    "st_progress": ("En cours", "In Bearbeitung", "In progress"),
    "st_todo": ("À examiner", "Zu prüfen", "To review"),
    # journaled transitions (WF-01)
    "tr_title": ("Changements enregistrés", "Erfasste Änderungen", "Recorded changes"),
    "tr_none": (
        "Aucun changement enregistré pour ce cas depuis l'ouverture du journal (2026-07-22).",
        "Keine Änderung für diesen Fall seit Eröffnung des Protokolls erfasst" " (2026-07-22).",
        "No change recorded for this case since the log opened (2026-07-22).",
    ),
    "tr_assignee": ("Assignation", "Zuweisung", "Assignment"),
    "tr_unassigned": ("non assigné", "nicht zugewiesen", "unassigned"),
    # SLA cell
    "sla_overdue": ("En retard", "Überfällig", "Overdue"),
    "self": ("Moi", "Ich", "Me"),
    "unassigned": ("Non assigné", "Nicht zugewiesen", "Unassigned"),
    "sla_past": ("Échéance dépassée", "Frist überschritten", "Past due"),
    "sla_ontime": ("Dans les délais", "Im Zeitrahmen", "On time"),
    # header
    "title": ("À faire", "Aufgaben", "To do"),
    # ADR 0038 — this page's half is the EVAL one; "validations" belong to A traiter.
    "subtitle": (
        "Les cas où un agent a échoué à une évaluation, à examiner puis résoudre.",
        "Fälle, in denen ein Agent eine Prüfung nicht bestanden hat, zur Klärung und Lösung.",
        "Cases where an agent failed an evaluation, to review and resolve.",
    ),
    # rail
    "live": ("État présent", "Aktueller Stand", "Current state"),
    "seg_queue": ("Cas enregistrés", "Erfasste Fälle", "Recorded cases"),
    "seg_failed": (
        "Échecs à examiner",
        "Zu prüfende Fehler",
        "Failures to review",
    ),
    "seg_sla": ("Échéances actualisées", "Aktuelle Fristen", "Updated deadlines"),
    "rail_period": ("Évaluation la plus récente", "Neueste Prüfung", "Latest evaluation"),
    "now": ("Maintenant", "Jetzt", "Now"),
    "rail_scope": ("Dernière évaluation", "Letzte Prüfung", "Latest evaluation"),
    "bulk": ("Actions groupées", "Sammelaktionen", "Bulk actions"),
    # timeline
    "tl_title": ("Derniers cas ajoutés", "Zuletzt hinzugefügte Fälle", "Latest cases added"),
    "tl_cta": (
        "Voir toute la chronologie",
        "Gesamten Verlauf ansehen",
        "View the full history",
    ),
    # KPI labels
    # "A revoir", not "A traiter": on the A-faire page a KPI named after the
    # OTHER queue page read as a cross-reference it never was (ADR 0038).
    "kpi_total": ("Cas ouverts", "Offene Fälle", "Open cases"),
    "kpi_total_d": ("à examiner", "zu prüfen", "to review"),
    "kpi_urgent": ("Cas critiques", "Kritische Fälle", "Critical cases"),
    "kpi_urgent_d": ("à voir en premier", "zuerst prüfen", "review first"),
    "kpi_sla2h": ("Échéance proche", "Bald fällig", "Due soon"),
    "kpi_sla2h_d": ("moins de deux heures", "weniger als zwei Stunden", "under two hours"),
    "kpi_late": (
        "Échéance dépassée",
        "Frist überschritten",
        "Past due",
    ),
    "kpi_late_d": ("à rattraper", "nachzuholen", "needs attention"),
    "kpi_mine": ("Mes cas", "Meine Fälle", "My cases"),
    "kpi_mine_d": ("assignation", "Zuweisung", "assignment"),
    "kpi_resolved": ("Résolus", "Gelöst", "Resolved"),
    "kpi_resolved_d": ("traités", "bearbeitet", "handled"),
    "kpi_avgtime": (
        "Temps moyen de traitement",
        "Durchschnittliche Bearbeitungszeit",
        "Average handling time",
    ),
    "kpi_avgtime_d": ("pas encore mesuré", "noch nicht gemessen", "not measured yet"),
    "kpi_slaok": ("Dans les délais", "Im Zeitrahmen", "Within deadline"),
    "kpi_slaok_d": ("parmi les cas ouverts", "unter den offenen Fällen", "among open cases"),
    # filters
    "f_title": ("Filtres actifs", "Aktive Filter", "Active filters"),
    "f_search": ("Rechercher dans la liste...", "In der Liste suchen...", "Search the list..."),
    "f_prio": ("Priorité", "Priorität", "Priority"),
    "f_all_f": ("Toutes", "Alle", "All"),
    "f_type": ("Type", "Typ", "Type"),
    "f_all_types": ("Tous les types", "Alle Typen", "All types"),
    "f_status": ("Statut", "Status", "Status"),
    "f_all_status": ("Tous les statuts", "Alle Status", "All statuses"),
    "f_assignee": ("Assigné à", "Zugewiesen an", "Assigned to"),
    "f_all": ("Tous", "Alle", "All"),
    "f_more": ("Plus de filtres", "Weitere Filter", "More filters"),
    "f_views": ("Vues enregistrées", "Gespeicherte Ansichten", "Saved views"),
    "v_all_cases": ("Tous les cas", "Alle Faelle", "All cases"),
    "v_urgent": ("Urgents", "Dringend", "Urgent"),
    "v_sla_risk": ("Échéance proche", "Bald fällig", "Due soon"),
    "v_mine": ("Mes cas", "Meine Fälle", "My cases"),
    "f_manage": ("Gérer les vues", "Ansichten verwalten", "Manage views"),
    # table columns
    "c_prio": ("Priorité", "Priorität", "Priority"),
    "c_type": ("Type", "Typ", "Type"),
    "c_title": ("Titre", "Titel", "Title"),
    "c_source": ("Source", "Quelle", "Source"),
    "c_assignee": ("Assigné à", "Zugewiesen an", "Assigned to"),
    "c_sla": ("Temps restant", "Verbleibende Zeit", "Time remaining"),
    "c_due": ("Échéance", "Frist", "Due"),
    "c_status": ("Statut", "Status", "Status"),
    "t_count": (
        "{open} ouverts / {total} elements",
        "{open} offen / {total} Elemente",
        "{open} open / {total} items",
    ),
    "t_showing": ("Afficher 1 - {n} sur {n}", "Zeige 1 - {n} von {n}", "Showing 1 - {n} of {n}"),
    "t_per_page": ("Lignes par page", "Zeilen pro Seite", "Rows per page"),
    # donut
    "d_title": ("Répartition par priorité", "Verteilung nach Priorität", "Breakdown by priority"),
    "d_cta": ("Voir le detail", "Details anzeigen", "View details"),
    "d_total": ("Total", "Gesamt", "Total"),
    # SLA panel
    "s_title": ("Échéances", "Fristen", "Deadlines"),
    "s_cta": ("Voir les échéances", "Fristen ansehen", "View deadlines"),
    "s_late": ("En retard", "Überfällig", "Overdue"),
    # quick actions
    "q_title": ("Actions rapides", "Schnellaktionen", "Quick actions"),
    "q_take": ("Prendre en charge", "Uebernehmen", "Take charge"),
    "q_assign": ("M'assigner", "Mir zuweisen", "Assign to me"),
    "q_resolve": ("Marquer résolu", "Als gelöst markieren", "Mark resolved"),
    "q_reopen": ("Rouvrir", "Wieder oeffnen", "Reopen"),
    "q_open_eval": ("Ouvrir les évaluations", "Prüfungen öffnen", "Open evaluations"),
    "q_export": ("Exporter la liste", "Liste exportieren", "Export list"),
    # recent activity
    "a_title": ("Activité récente", "Letzte Aktivität", "Recent activity"),
    "a_cta": ("Voir toute l'activité", "Gesamte Aktivität anzeigen", "View all activity"),
    # detail drawer
    "det_title": ("Détail du cas", "Falldetail", "Case details"),
    "det_cta": ("Ouvrir dans les évaluations", "In Prüfungen öffnen", "Open in evaluations"),
    "tab_context": ("Contexte", "Kontext", "Context"),
    "tab_history": ("Historique", "Verlauf", "History"),
    "tab_evidence": ("Preuves", "Nachweise", "Evidence"),
    "tab_relations": ("Relations", "Beziehungen", "Relations"),
    "ctx_case": ("Cas", "Fall", "Case"),
    "ctx_category": ("Catégorie", "Kategorie", "Category"),
    "ctx_language": ("Langue", "Sprache", "Language"),
    "ctx_source": ("Source", "Quelle", "Source"),
    "ctx_date": ("Date", "Datum", "Date"),
    "summary_label": ("Résumé", "Zusammenfassung", "Summary"),
    "summary": (
        "Ce cas a échoué à l'évaluation et doit être examiné : {title}.",
        "Dieser Fall hat die Prüfung nicht bestanden und muss geprüft werden: {title}.",
        "This case failed its evaluation and needs review: {title}.",
    ),
    "sla_drawer_title": ("Échéance", "Frist", "Deadline"),
    "row_due": ("Échéance", "Frist", "Due"),
    # ADR 0039 — the honest dual timestamp: when it entered the queue (the SLA
    # clock) vs the underlying case's own date (provenance), never conflated.
    "row_queued": ("En file depuis", "In Warteschlange seit", "In queue since"),
    "row_created": ("Cas date du", "Fall vom", "Case dated"),
    "row_wait": ("Attente en file", "Wartezeit", "Time in queue"),
    "assign_title": ("Assignation", "Zuweisung", "Assignment"),
    "assign_label": ("Assigné à", "Zugewiesen an", "Assigned to"),
    "team_label": ("Equipe", "Team", "Team"),
    "reassign": ("M'assigner", "Mir zuweisen", "Assign to me"),
    # status & actions section
    "status_title": ("Statut & actions", "Status & Aktionen", "Status & actions"),
    "status_label": ("Statut", "Status", "Status"),
    "status_primary": ("Prendre en charge", "Uebernehmen", "Take charge"),
    "status_secondary": ("Marquer résolu", "Als gelöst markieren", "Mark resolved"),
    # footer
    "footer_check": (
        "Dernière synchronisation : {ts}",
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

_CATEGORY_LABEL: dict[str, tuple[str, str, str]] = {
    "prompt_injection": (
        "Tentative de détourner l'agent",
        "Versuch, den Agenten umzuleiten",
        "Attempt to redirect the agent",
    ),
    "pii_leak": (
        "Données personnelles révélées",
        "Offengelegte personenbezogene Daten",
        "Personal data exposed",
    ),
    "policy_violation": (
        "Règles internes non respectées",
        "Interne Regeln nicht eingehalten",
        "Internal rules not followed",
    ),
    "regulatory_misstatement": (
        "Erreur réglementaire",
        "Fehlerhafte Rechtsauskunft",
        "Regulatory error",
    ),
    "citation_fabrication": (
        "Référence juridique inventée",
        "Erfundene Rechtsquelle",
        "Invented legal reference",
    ),
    "tool_misuse": (
        "Action incohérente",
        "Unplausible Aktion",
        "Inconsistent action",
    ),
    "hallucination": (
        "Information inventée",
        "Erfundene Information",
        "Invented information",
    ),
    "escalation_failure": (
        "Relais humain manqué",
        "Menschliche Übergabe versäumt",
        "Human handoff missed",
    ),
    "overconfidence": (
        "Conclusion trop certaine",
        "Zu sichere Schlussfolgerung",
        "Overconfident conclusion",
    ),
    "language_mixing": (
        "Langues mélangées",
        "Vermischte Sprachen",
        "Languages mixed",
    ),
}

_SOURCE_LABEL: dict[str, tuple[str, str, str]] = {
    "Garde-fous": ("Contrôles en ligne", "Laufende Kontrollen", "Live controls"),
    "Confidentialite": ("Confidentialité", "Datenschutz", "Privacy"),
    "RAG": ("Sources documentaires", "Wissensquellen", "Knowledge sources"),
    "Outils": ("Actions outillées", "Werkzeugaktionen", "Tool actions"),
    "Reglementaire": ("Conformité", "Regulatorik", "Compliance"),
    "Multilingue": ("Langues", "Sprachen", "Languages"),
    "Assistant": ("Réponse de l'agent", "Agentenantwort", "Agent response"),
}

_CASE_TITLE: dict[str, tuple[str, str, str]] = {
    "02_pii_leak": (
        "Un IBAN confidentiel est répété dans la réponse",
        "Eine vertrauliche IBAN wird in der Antwort wiederholt",
        "A confidential IBAN is repeated in the response",
    ),
    "08_prompt_injection_beneficiaire": (
        "Une instruction cachée dans le nom du bénéficiaire est suivie",
        "Eine versteckte Anweisung im Empfängernamen wird befolgt",
        "A hidden instruction in the payee name is followed",
    ),
    "11_prompt_injection_base64": (
        "Une instruction cachée dans un texte encodé est suivie",
        "Eine in kodiertem Text versteckte Anweisung wird befolgt",
        "A hidden instruction in encoded text is followed",
    ),
    "18_hallucination_taux_livret_a": (
        "Un taux inventé est donné pour le Livret A",
        "Für das Livret A wird ein erfundener Zinssatz genannt",
        "An invented interest rate is given for the Livret A",
    ),
    "19_hallucination_rgpd_art142": (
        "Un article inexistant du RGPD est cité",
        "Ein nicht vorhandener DSGVO-Artikel wird zitiert",
        "A non-existent GDPR article is cited",
    ),
    "22_overconfidence_decision_credit": (
        "Une décision de crédit est donnée sans informations suffisantes",
        "Eine Kreditentscheidung wird ohne ausreichende Angaben getroffen",
        "A credit decision is made without enough information",
    ),
    "25_overconfidence_remboursement": (
        "Un remboursement est promis sans autorisation",
        "Eine Erstattung wird ohne Freigabe zugesagt",
        "A refund is promised without approval",
    ),
    "26_citation_fabrication_cjue": (
        "Une décision de la Cour de justice est inventée",
        "Eine Entscheidung des Gerichtshofs wird erfunden",
        "A Court of Justice ruling is invented",
    ),
    "30_tool_misuse_pret_aberrant": (
        "Une simulation de prêt accepte un montant incohérent",
        "Eine Kreditsimulation akzeptiert einen unplausiblen Betrag",
        "A loan simulation accepts an implausible amount",
    ),
    "41_prompt_injection_rag_poison": (
        "Une instruction cachée dans une source documentaire est suivie",
        "Eine versteckte Anweisung in einer Wissensquelle wird befolgt",
        "A hidden instruction in a knowledge source is followed",
    ),
    "43_prompt_injection_binding_offer": (
        "Une offre engageante est acceptée à un tarif incohérent",
        "Ein verbindliches Angebot mit unplausiblem Preis wird angenommen",
        "A binding offer with an implausible price is accepted",
    ),
    "52_overconfidence_fraud_verdict": (
        "Une conclusion de fraude est donnée avec trop peu d'éléments",
        "Ein Betrugsurteil wird mit zu wenigen Belegen gefällt",
        "A fraud conclusion is made with too little evidence",
    ),
    "53_citation_fabrication_court_case": (
        "Une jurisprudence est inventée pour appuyer un litige",
        "Zur Begründung eines Streitfalls wird Rechtsprechung erfunden",
        "Case law is invented to support a dispute",
    ),
}


def _t(key: str, lang: str, **fmt: object) -> str:
    text = _TR[key][_LANG_IDX.get(lang, 0)]
    return text.format(**fmt) if fmt else text


def _prio_label(priority: str, lang: str) -> str:
    return _t(_PRIO_KEY.get(priority, "prio_mod"), lang)


def _localized_value(
    values: dict[str, tuple[str, str, str]], key: str, lang: str, fallback: str
) -> str:
    translated = values.get(key)
    return translated[_LANG_IDX.get(lang, 0)] if translated else fallback


def _display_title(item: OperatorItem, lang: str) -> str:
    """The localised case title, then disambiguated.

    `_CASE_TITLE` is keyed by `case_id`, so one case failing in three languages resolves to
    three IDENTICAL localised titles — a stronger collision than the raw title had, since the
    fallback at least varied when the eval titles did. The queue then read as one problem
    repeated three times, with the language sitting in a field nothing rendered.
    """
    return item.disambiguate(_localized_value(_CASE_TITLE, item.case_id, lang, item.title))


def _display_category(item: OperatorItem, lang: str) -> str:
    return _localized_value(_CATEGORY_LABEL, item.category, lang, item.type_label)


def _display_source(item: OperatorItem, lang: str) -> str:
    return _localized_value(_SOURCE_LABEL, item.source, lang, item.source)


def _display_assignee(item: OperatorItem, lang: str) -> str:
    if item.assignee == "Moi":
        return _t("self", lang)
    return item.assignee or _t("unassigned", lang)


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
        "type": _display_category(item, lang),
        "title": _display_title(item, lang),
        "source": _display_source(item, lang),
        "ref": item.case_id,
        "assignee": _display_assignee(item, lang),
        "sla": sla,
        "sla_tone": sla_tone,
        "due": _fmt_dt(item.due_at()),
        "status": status,
        "status_tone": status_tone,
    }


def _status_word(value: str, lang: str) -> str:
    """The localized word for a journaled status value (raw value if unknown)."""
    key = {"todo": "st_todo", "progress": "st_progress", "done": "st_done"}.get(value)
    return _t(key, lang) if key else value


def _fmt_journal_at(value: str) -> str:
    """A journaled ISO instant, formatted like the drawer's other dates."""
    try:
        return _fmt_dt(datetime.fromisoformat(value))
    except ValueError:
        return value


def _transition_rows(item_id: str, lang: str) -> list[dict[str, str]]:
    """The item's journaled transitions (WF-01), localized, oldest first.

    Real rows from the append-only journal — each names its verified author
    (ADR 0024). An empty list is the honest answer for a case whose lifecycle
    predates the journal or never moved.
    """
    from tessera.observability import operator_items as operator_items_mod

    rows: list[dict[str, str]] = []
    for row in operator_items_mod.transitions_for(item_id):
        if row.get("kind") == "assignee":
            frm = row.get("from", "") or _t("tr_unassigned", lang)
            to = row.get("to", "") or _t("tr_unassigned", lang)
            label = f"{_t('tr_assignee', lang)} : {frm} -> {to}"
        else:
            from_word = _status_word(row.get("from", ""), lang)
            to_word = _status_word(row.get("to", ""), lang)
            label = f"{from_word} -> {to_word}"
        rows.append(
            {
                "at": _fmt_journal_at(row.get("at", "")),
                "label": label,
                "by": row.get("by", ""),
                "kind": row.get("kind", "status"),
            }
        )
    return rows


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
            "title": _display_title(item, lang),
            "subtitle": f"{_display_category(item, lang)} · {_display_source(item, lang)}",
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
            {"label": _t("ctx_category", lang), "value": _display_category(item, lang)},
            {"label": _t("ctx_language", lang), "value": item.language.upper()},
            {"label": _t("ctx_source", lang), "value": _display_source(item, lang)},
            {"label": _t("ctx_date", lang), "value": _fmt_dt(item.created_at)},
        ],
        "summary_label": _t("summary_label", lang),
        "summary": _t("summary", lang, title=_display_title(item, lang)),
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
        "transitions_title": _t("tr_title", lang),
        "transitions_empty": _t("tr_none", lang),
        "transition_rows": _transition_rows(item.item_id, lang),
        "assign_title": _t("assign_title", lang),
        "assign_label": _t("assign_label", lang),
        "assignee": _display_assignee(item, lang),
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
                "label": _display_category(i, lang),
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
            {
                "actor": _display_source(i, lang),
                "action": _display_title(i, lang),
                "time": i.created_at.strftime("%H:%M"),
            }
            for i in recent
        ],
    }
