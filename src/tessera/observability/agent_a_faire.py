"""Agent "A faire" cockpit overview (reference image 23).

The "A faire" page is the operator's personal action queue: a temporal rail and
a 24h event timeline, a KPI strip (to-do total/urgent, SLA under 2h, overdue,
assigned to me, resolved today, mean handling time, SLA met), a saved-views
filter rail, the task table (priority, type, title, source, assignee, SLA, due,
status) and a right column with a type-breakdown donut, SLA buckets, quick
actions, recent activity and a status/action footer.

This is the sibling of the "A traiter" inbox (page 24). It ships without a live
task store, so the payload is a deterministic reference fixture: values are
stable across calls. Colours/priorities/statuses are emitted as keys; the
frontend maps each key to its label colour. Free-text data is verbatim French
with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_a_faire"]


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


def _task(
    priority: str,
    prio_tone: str,
    type_: str,
    title: str,
    source: str,
    ref: str,
    assignee: str,
    sla: str,
    sla_tone: str,
    due: str,
    status: str,
    status_tone: str,
) -> dict[str, object]:
    return {
        "priority": priority,
        "prio_tone": prio_tone,
        "type": type_,
        "title": title,
        "source": source,
        "ref": ref,
        "assignee": assignee,
        "sla": sla,
        "sla_tone": sla_tone,
        "due": due,
        "status": status,
        "status_tone": status_tone,
    }


def compute_agent_a_faire() -> dict[str, object]:
    """Return the full "A faire" overview payload (deterministic fixture)."""
    rail: dict[str, object] = {
        "live": "Live",
        "segments": ["File actuelle", "Donnees en temps reel", "SLA en temps reel"],
        "period": "24h",
        "updated": "11/06/2026 10:42:15",
        "now": "Maintenant",
        "scope": "Ce matin (08:00)",
        "bulk": "Actions groupees",
    }

    timeline: dict[str, object] = {
        "title": "Timeline evenements (24h)",
        "cta": "Voir la timeline complete",
        "events": [
            {"time": "09:12", "label": "Ticket cree", "ref": "BC-8318", "tone": "ok"},
            {"time": "09:45", "label": "Assignation", "ref": "BC-8316", "tone": "warn"},
            {"time": "10:05", "label": "SLA risque", "ref": "BC-8309", "tone": "warn"},
            {"time": "10:18", "label": "Escalade", "ref": "BC-8305", "tone": "crit"},
            {"time": "10:25", "label": "Ticket resolu", "ref": "BC-8302", "tone": "ok"},
            {"time": "10:38", "label": "Reouverture", "ref": "BC-8301", "tone": "crit"},
        ],
    }

    kpis: list[dict[str, object]] = [
        _kpi(
            "total",
            "A traiter (total)",
            "23",
            "+18% vs ce matin",
            False,
            "red",
            [14, 16, 15, 18, 19, 21, 23],
        ),
        _kpi("urgent", "A traiter (urgents)", "6", "+33%", False, "red", [3, 3, 4, 4, 5, 5, 6]),
        _kpi("sla2h", "SLA < 2h", "4", "+100%", False, "red", [1, 1, 2, 2, 3, 3, 4]),
        _kpi("late", "En retard (SLA depasse)", "3", "+50%", False, "red", [1, 1, 2, 2, 2, 3, 3]),
        _kpi("mine", "Assignes a moi", "9", "+11%", True, "teal", [6, 7, 7, 8, 8, 9, 9]),
        _kpi(
            "resolved",
            "Resolus aujourd'hui",
            "18",
            "+22%",
            True,
            "teal",
            [10, 12, 13, 14, 16, 17, 18],
        ),
        _kpi(
            "avgtime",
            "Temps moyen de traitement",
            "1h 42m",
            "-12%",
            True,
            "amber",
            [128, 122, 118, 112, 108, 104, 102],
        ),
        _kpi("slaok", "SLA respectes", "92%", "+5 pts", True, "teal", [85, 86, 88, 89, 90, 91, 92]),
    ]

    filters: dict[str, object] = {
        "title": "Filtres actifs",
        "search": "Rechercher dans la liste...",
        "selects": [
            {"label": "Priorite", "value": "Toutes"},
            {"label": "Type", "value": "Tous les types"},
            {"label": "Statut", "value": "Tous les statuts"},
            {"label": "Assigne a", "value": "Moi"},
            {"label": "Echeance", "value": "Toutes"},
            {"label": "SLA", "value": "Toutes"},
        ],
        "more": "Plus de filtres",
        "views_title": "Vues enregistrees",
        "views": ["Ma vue par defaut", "Urgents", "SLA en risque", "Incidents critiques"],
        "views_cta": "Gerer les vues",
    }

    columns = [
        "Priorite",
        "Type",
        "Titre",
        "Source",
        "Assigne a",
        "SLA",
        "Echeance",
        "Statut",
    ]
    tasks: list[dict[str, object]] = [
        _task(
            "Critique",
            "crit",
            "Incident",
            "Reponse inappropriee detectee",
            "Assistant",
            "#C-8921",
            "Alice Martin",
            "En retard",
            "crit",
            "11/06/2026 10:30",
            "En retard",
            "crit",
        ),
        _task(
            "Elevee",
            "high",
            "Incident",
            "Fuite de donnees suspectee",
            "Assistant",
            "#C-8916",
            "Bob Levy",
            "1h 20m",
            "warn",
            "11/06/2026 12:00",
            "A traiter",
            "todo",
        ),
        _task(
            "Elevee",
            "high",
            "Demande acces",
            "Demande d'acces a des sources sensibles",
            "RAG",
            "#A-4442",
            "Vous",
            "1h 35m",
            "warn",
            "11/06/2026 12:15",
            "A traiter",
            "todo",
        ),
        _task(
            "Moyenne",
            "mod",
            "Habilitation",
            "Habilitation a revoir",
            "RAG",
            "#A-4419",
            "Vous",
            "2h 20m",
            "ok",
            "11/06/2026 13:00",
            "En cours",
            "progress",
        ),
        _task(
            "Critique",
            "crit",
            "Garde-fou",
            "Contournement de garde-fou",
            "Garde-fous",
            "#GF-2231",
            "Clara Dubois",
            "0h 45m",
            "crit",
            "11/06/2026 11:25",
            "En retard",
            "crit",
        ),
        _task(
            "Moyenne",
            "mod",
            "Anomalie",
            "Anomalie d'utilisation detectee",
            "Connecteur",
            "#CON-774",
            "Vous",
            "3h 10m",
            "ok",
            "11/06/2026 13:50",
            "A traiter",
            "todo",
        ),
        _task(
            "Faible",
            "low",
            "Acces",
            "Acces a l'environnement systeme",
            "Connecteur",
            "#CON-768",
            "Hugo D.",
            "5h 40m",
            "ok",
            "11/06/2026 16:20",
            "A traiter",
            "todo",
        ),
        _task(
            "Moyenne",
            "mod",
            "Qualite",
            "Score qualite en baisse",
            "Evaluations",
            "#EV-5531",
            "Alice Martin",
            "4h 05m",
            "ok",
            "11/06/2026 14:45",
            "En cours",
            "progress",
        ),
    ]

    donut: dict[str, object] = {
        "title": "Repartition par type",
        "cta": "Voir le detail",
        "center": "23",
        "center_label": "Total",
        "segments": [
            {"label": "Conversations IA", "count": 9, "share": "39%", "color": "#4c8bf5"},
            {"label": "Incidents", "count": 6, "share": "26%", "color": "#8b7cf0"},
            {"label": "Alertes", "count": 4, "share": "17%", "color": "#e0a23a"},
            {"label": "Approbations", "count": 2, "share": "9%", "color": "#e0763a"},
            {"label": "Demandes d'acces", "count": 1, "share": "4%", "color": "#34d399"},
            {"label": "Autres", "count": 1, "share": "4%", "color": "#64748b"},
        ],
    }

    sla: dict[str, object] = {
        "title": "SLA & echeances",
        "cta": "Voir les SLA",
        "buckets": [
            {"label": "En retard", "count": 3, "color": "#f87171"},
            {"label": "< 2h", "count": 4, "color": "#e0763a"},
            {"label": "2h - 8h", "count": 9, "color": "#e0a23a"},
            {"label": "> 8h", "count": 7, "color": "#34d399"},
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Escalader",
            "Assigner",
            "Ajouter une note",
            "Marquer resolu",
            "Creer une vue",
            "Demander une revue",
        ],
    }

    activity: dict[str, object] = {
        "title": "Activite recente",
        "cta": "Voir toute l'activite (24)",
        "items": [
            {"actor": "incident risque", "action": "Fuite de donnees suspectee", "time": "08:42"},
            {
                "actor": "approbation accordee",
                "action": "Acces a des donnees sensibles",
                "time": "08:30",
            },
            {"actor": "alerte creee", "action": "Anomalie d'utilisation detectee", "time": "08:18"},
            {
                "actor": "conversation analysee",
                "action": "Contexte potentiellement dangereux",
                "time": "08:05",
            },
        ],
    }

    status: dict[str, object] = {
        "title": "Statut & actions",
        "label": "Statut",
        "value": "A traiter",
        "primary": "Prendre en charge",
        "secondary": "Escalader",
    }

    footer: dict[str, object] = {
        "check": "Derniere verification d'integrite : 11/06/2026 10:42:15",
        "status": "OK",
    }

    return {
        "title": "A faire",
        "subtitle": "Vos taches, revues et validations en attente de traitement.",
        "rail": rail,
        "timeline": timeline,
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "tasks": tasks, "count": "23 elements"},
        "donut": donut,
        "sla": sla,
        "quick": quick,
        "activity": activity,
        "status": status,
        "footer": footer,
    }
