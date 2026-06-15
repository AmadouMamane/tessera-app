"""Agent Session History ("Historique des sessions") payload (reference image 30).

The Historique page analyses conversation sessions, their quality and their
compliance: an inner tab strip (overview, sessions, messages, evaluations,
traces, users, content, errors, exports), a KPI strip (total sessions, messages
exchanged, answers generated, success rate, response time, tokens), a filterable
sessions table (user, agent, start, messages, score, status, response time,
tokens), a chart row (session trend, sessions by agent, score distribution,
success-rate gauge), two secondary panels (watchlist, quick actions) and a
per-session detail panel with a Summary / Messages / Evaluation / Activity tab
set, agent configuration, session evaluation and technical information.

This build ships without a live session store, so the payload is a deterministic
reference fixture: values are stable across calls. Colours/statuses are emitted
as keys. Free-text data is verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

__all__ = ["compute_agent_historique"]


def _kpi(
    key: str, label: str, value: str, delta: str, delta_tone: str, tone: str, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "delta_tone": delta_tone,
        "tone": tone,
        "series": series,
    }


def _row(
    sid: str,
    user: str,
    agent: str,
    start: str,
    messages: str,
    score: str,
    score_tone: str,
    status: str,
    status_tone: str,
    latency: str,
    tokens: str,
) -> dict[str, object]:
    return {
        "sid": sid,
        "user": user,
        "agent": agent,
        "start": start,
        "messages": messages,
        "score": score,
        "score_tone": score_tone,
        "status": status,
        "status_tone": status_tone,
        "latency": latency,
        "tokens": tokens,
    }


def compute_agent_historique() -> dict[str, object]:
    """Return the full Historique des sessions payload (deterministic fixture)."""
    kpis: list[dict[str, object]] = [
        _kpi(
            "sessions",
            "Sessions totales",
            "12 540",
            "-6% vs periode precedente",
            "muted",
            "violet",
            [142, 138, 150, 132, 128, 124, 118],
        ),
        _kpi(
            "messages",
            "Messages echanges",
            "98 742",
            "-5% vs periode precedente",
            "muted",
            "blue",
            [1020, 1080, 1040, 990, 970, 950, 930],
        ),
        _kpi(
            "answers",
            "Reponses generees",
            "12 502",
            "-6% vs periode precedente",
            "muted",
            "green",
            [141, 137, 149, 131, 127, 123, 117],
        ),
        _kpi(
            "success",
            "Taux de reussite",
            "93,1 %",
            "+2,4 pts vs periode precedente",
            "good",
            "green",
            [89, 90, 90, 91, 92, 92, 93],
        ),
        _kpi(
            "latency",
            "Temps de reponse (p50)",
            "2,8 s",
            "-0,4 s vs periode precedente",
            "good",
            "amber",
            [34, 33, 32, 31, 30, 29, 28],
        ),
        _kpi(
            "tokens",
            "Tokens consommes",
            "48,6M",
            "-8% vs periode precedente",
            "muted",
            "violet",
            [560, 540, 530, 510, 500, 490, 486],
        ),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une session, utilisateur, agent...",
        "selects": [
            {"label": "Agent", "value": "Tous"},
            {"label": "Utilisateur", "value": "Tous"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Score", "value": "Tous"},
        ],
        "more": "Plus de filtres",
    }

    columns = [
        "Session ID",
        "Utilisateur",
        "Agent",
        "Debut de session",
        "Messages",
        "Score",
        "Statut",
        "Temps de reponse (p50)",
        "Tokens",
    ]
    rows: list[dict[str, object]] = [
        _row(
            "sess_01J23K8Q8RZ7",
            "Sophie L.",
            "Assistant - Conformite",
            "12/06/2026 10:14",
            "18",
            "9.4",
            "good",
            "Terminee",
            "good",
            "2.2 s",
            "14 820",
        ),
        _row(
            "sess_01J23H1M4DN2",
            "Karim B.",
            "Assistant - Data",
            "12/06/2026 09:58",
            "12",
            "9.1",
            "good",
            "Terminee",
            "good",
            "2.4 s",
            "9 640",
        ),
        _row(
            "sess_01J23F6C2WK0",
            "Nadia S.",
            "Assistant - Produits",
            "12/06/2026 09:41",
            "24",
            "8.8",
            "warn",
            "Active",
            "info",
            "2.6 s",
            "18 210",
        ),
        _row(
            "sess_01J23D9P7TX5",
            "Thomas R.",
            "Assistant - Juridique",
            "12/06/2026 09:22",
            "9",
            "9.6",
            "good",
            "Terminee",
            "good",
            "1.9 s",
            "7 410",
        ),
        _row(
            "sess_01J23B4L1QV8",
            "Claire M.",
            "Assistant - Conformite",
            "12/06/2026 09:05",
            "31",
            "7.2",
            "warn",
            "Escaladee",
            "warn",
            "3.1 s",
            "22 540",
        ),
        _row(
            "sess_01J239X3HF61",
            "Hugo D.",
            "Assistant - Data",
            "12/06/2026 08:47",
            "6",
            "9.2",
            "good",
            "Terminee",
            "good",
            "2.0 s",
            "5 320",
        ),
        _row(
            "sess_01J237W8KP44",
            "Camille A.",
            "Assistant - Produits",
            "12/06/2026 08:30",
            "15",
            "8.9",
            "good",
            "Terminee",
            "good",
            "2.5 s",
            "11 980",
        ),
        _row(
            "sess_01J235T0RD29",
            "Yanis B.",
            "Assistant - DevOps",
            "12/06/2026 08:12",
            "21",
            "5.1",
            "crit",
            "Erreur",
            "crit",
            "4.2 s",
            "16 870",
        ),
        _row(
            "sess_01J233Q5MJ17",
            "Lea P.",
            "Assistant - Conformite",
            "12/06/2026 07:55",
            "11",
            "9.3",
            "good",
            "Terminee",
            "good",
            "2.1 s",
            "8 240",
        ),
        _row(
            "sess_01J231N2GC03",
            "Marc V.",
            "Assistant - Juridique",
            "12/06/2026 07:38",
            "8",
            "8.7",
            "good",
            "Terminee",
            "good",
            "2.3 s",
            "6 510",
        ),
    ]

    trend: dict[str, object] = {
        "title": "Evolution des sessions",
        "control": "Par jour",
        "series": [1180, 1320, 1240, 1410, 1280, 1500, 1360, 1440, 1380, 1420],
        "prev": [1240, 1280, 1300, 1340, 1360, 1400, 1380, 1410, 1400, 1420],
        "legend": "Sessions",
        "legend_prev": "Sessions periode precedente",
    }

    by_agent: dict[str, object] = {
        "title": "Sessions par agent (Top 5)",
        "cta": "Voir tous les agents",
        "items": [
            {"label": "Assistant - Conformite", "value": "3 240", "pct": 100, "share": "25,8%"},
            {"label": "Assistant - Juridique", "value": "2 980", "pct": 92, "share": "23,8%"},
            {"label": "Assistant - Data", "value": "2 120", "pct": 65, "share": "16,9%"},
            {"label": "Assistant - Produits", "value": "1 840", "pct": 57, "share": "14,7%"},
            {"label": "Assistant - DevOps", "value": "1 320", "pct": 41, "share": "10,5%"},
        ],
    }

    scores: dict[str, object] = {
        "title": "Repartition des scores",
        "center": "12 540",
        "center_label": "Sessions",
        "segments": [
            {
                "label": "9-10 (excellent)",
                "value": "7 540",
                "share": "60,1%",
                "pct": 60,
                "tone": "green",
            },
            {"label": "7-8 (bon)", "value": "4 110", "share": "32,8%", "pct": 33, "tone": "blue"},
            {"label": "5-6 (moyen)", "value": "740", "share": "5,9%", "pct": 6, "tone": "amber"},
            {"label": "< 5 (faible)", "value": "150", "share": "1,2%", "pct": 1, "tone": "red"},
        ],
    }

    success: dict[str, object] = {
        "title": "Taux de reussite",
        "gauge": 93,
        "value": "93,1%",
        "note": "Reussie",
        "cta": "Voir le detail",
    }

    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": "Voir toutes les alertes (3)",
        "items": [
            {
                "title": "Sessions en echec en hausse",
                "detail": "+0,4 pt sur 24h - Assistant DevOps",
                "tone": "crit",
            },
            {
                "title": "Temps de reponse en hausse",
                "detail": "+0,3 s sur 7j - Assistant Produits",
                "tone": "warn",
            },
            {
                "title": "Tokens consommes en baisse",
                "detail": "-8% sur 7j - tous agents",
                "tone": "info",
            },
        ],
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Voir les sessions en echec",
            "Analyser les scores",
            "Exporter (CSV / Parquet)",
            "Analyser une session",
        ],
    }

    detail: dict[str, object] = {
        "sid": "sess_01J23K8Q8RZ7",
        "id": "@_session_prod",
        "tabs": ["Resume", "Messages (18)", "Evaluation", "Activite"],
        "fields": [
            {"label": "Utilisateur", "value": "Sophie L."},
            {"label": "Agent", "value": "Assistant - Conformite"},
            {"label": "Duree totale", "value": "14 min 22 s"},
            {"label": "Messages", "value": "18"},
            {"label": "Score", "value": "9,4 / 10", "tone": "good"},
            {"label": "Statut", "value": "Terminee", "tone": "good"},
            {"label": "Temps de reponse (p50)", "value": "2,2 s"},
            {"label": "Tokens", "value": "14 820"},
            {"label": "Modele", "value": "gpt-4o"},
            {"label": "Cout estime", "value": "0,18 EUR"},
        ],
        "config_title": "Configuration de l'agent",
        "config_value": "Assistant - Conformite",
        "config_version": "v3.5.1",
        "eval_title": "Evaluation de la session",
        "eval_cta": "Voir tous les criteres",
        "eval": [
            {"label": "Score global", "value": "9,4", "scale": "/10", "lead": True},
            {"label": "Pertinence", "value": "9.4", "scale": "/10", "lead": False},
            {"label": "Exactitude", "value": "9.7", "scale": "/10", "lead": False},
            {"label": "Completude", "value": "9.1", "scale": "/10", "lead": False},
            {"label": "Securite", "value": "9.7", "scale": "/10", "lead": False},
        ],
        "info_title": "Informations techniques",
        "info": [
            {"label": "Session ID", "value": "sess_01J23K8Q8RZ7"},
            {"label": "IP anonymisee", "value": "10.x.x.x"},
            {"label": "IP utilisateur", "value": "10.32.45.78"},
            {"label": "Plateforme", "value": "Chrome 141.0"},
            {"label": "Region", "value": "eu-west-1"},
            {"label": "Version moteur", "value": "tessera-3.7.2"},
        ],
    }

    return {
        "title": "Historique des sessions",
        "subtitle": "Analysez les sessions de conversation, leur qualite et leur conformite.",
        "actions": {"export": "Exporter", "compare": "Comparer", "create": "Creer un rapport"},
        "subtabs": [
            "Vue d'ensemble",
            "Sessions",
            "Messages",
            "Evaluations",
            "Traces & outils",
            "Utilisateurs",
            "Contenu & sources",
            "Erreurs",
            "Exports",
        ],
        "kpis": kpis,
        "filters": filters,
        "table": {
            "columns": columns,
            "rows": rows,
            "count": "1-10 sur 12 540 sessions",
            "pages": 5,
        },
        "trend": trend,
        "by_agent": by_agent,
        "scores": scores,
        "success": success,
        "watch": watch,
        "quick": quick,
        "detail": detail,
    }
