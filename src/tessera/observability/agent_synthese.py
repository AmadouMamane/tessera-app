"""Agent overview ("Synthese de l'agent") dashboard payload (reference image 22).

The Synthese page is the operator's at-a-glance cockpit for a single agent
instance: a KPI strip (conversations, users, resolution, satisfaction, latency,
sessions, errors), the agent profile and capabilities, top conversation topics,
detailed performance metrics, the current configuration, recent conversations,
a live activity feed, active system prompts, channel usage, a change timeline,
alerts and quick configuration shortcuts.

This build ships without a live agent-analytics store, so the payload is a
deterministic reference fixture: values are stable across calls so the page never
"dances" on refetch. Colours/statuses are emitted as keys; the frontend maps each
key to its label colour. Free-text data (names, titles) is verbatim French.
"""

from __future__ import annotations

__all__ = ["compute_agent_synthese"]


def _kpi(
    key: str, label: str, value: str, delta: str, good: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "delta": delta,
        "good": good,
        "series": series,
    }


def compute_agent_synthese() -> dict[str, object]:
    """Return the full Synthese dashboard payload (deterministic fixture)."""
    kpis: list[dict[str, object]] = [
        _kpi(
            "conversations",
            "Conversations (24h)",
            "1 842",
            "+16% vs hier",
            True,
            [1180, 1240, 1320, 1410, 1500, 1660, 1842],
        ),
        _kpi(
            "users",
            "Utilisateurs actifs (24h)",
            "342",
            "+12% vs hier",
            True,
            [248, 262, 280, 295, 310, 326, 342],
        ),
        _kpi(
            "resolution",
            "Taux de resolution",
            "86.7%",
            "+2.8 pt vs hier",
            True,
            [80, 81, 82, 83, 84, 85, 87],
        ),
        _kpi(
            "satisfaction",
            "Satisfaction moyenne",
            "4.6 / 5",
            "+0.2 vs hier",
            True,
            [42, 43, 43, 44, 45, 45, 46],
        ),
        _kpi(
            "latency",
            "Temps de reponse moyen",
            "2.34 s",
            "+0.12 s vs hier",
            False,
            [200, 205, 210, 218, 222, 230, 234],
        ),
        _kpi(
            "sessions",
            "Sessions actives",
            "128",
            "+8% vs hier",
            True,
            [96, 102, 108, 114, 118, 122, 128],
        ),
        _kpi(
            "errors",
            "Erreurs / refus (24h)",
            "23",
            "+5% vs hier",
            False,
            [16, 17, 19, 18, 20, 22, 23],
        ),
    ]

    profile: dict[str, object] = {
        "name": "Tessera Assistant",
        "status": "actif",
        "fields": [
            {"label": "ID", "value": "asst_001"},
            {"label": "Version", "value": "v1.3.2"},
            {"label": "Modele principal", "value": "Llama 3.2 70B"},
            {"label": "Connecteurs actifs", "value": "8 / 12"},
            {"label": "Connaissances", "value": "158 sources"},
            {"label": "Derniere mise a jour", "value": "11/06/2026 09:45"},
        ],
        "cta": "Voir la configuration active",
    }

    capabilities: dict[str, object] = {
        "title": "Capacites principales",
        "items": [
            "Reponses basees sur l'historique",
            "Analyse & synthese de documents",
            "Recherche semantique",
            "Generation de rapports",
            "Aide a la decision",
            "Execution de taches (outils)",
        ],
        "cta": "Gerer les capacites",
    }

    topics: dict[str, object] = {
        "title": "Top sujets (24h)",
        "items": [
            {"label": "Conformite", "pct": 28, "tone": "violet"},
            {"label": "Qualite IA", "pct": 22, "tone": "blue"},
            {"label": "Incidents", "pct": 16, "tone": "amber"},
            {"label": "Securite", "pct": 12, "tone": "green"},
            {"label": "Observabilite", "pct": 9, "tone": "cyan"},
            {"label": "Autres", "pct": 13, "tone": "slate"},
        ],
        "cta": "Voir tous les sujets",
    }

    performance: dict[str, object] = {
        "title": "Performance detaillee (24h)",
        "rows": [
            {"label": "Taux de resolution", "value": "86.7%", "delta": "+2.6 pt", "good": True},
            {"label": "Taux d'escalade", "value": "13.3%", "delta": "-2.6 pt", "good": True},
            {"label": "Satisfaction", "value": "4.6 / 5", "delta": "+0.1", "good": True},
            {"label": "Reponses utiles", "value": "1 588", "delta": "+4%", "good": True},
            {"label": "Precision citations", "value": "94.2%", "delta": "+1.1 pt", "good": True},
            {"label": "Temps de reponse P50", "value": "1.71 s", "delta": "-0.05 s", "good": True},
            {"label": "Temps de reponse P95", "value": "4.89 s", "delta": "+0.20 s", "good": False},
        ],
        "cta": "Voir le detail",
    }

    config: dict[str, object] = {
        "title": "Configuration courante (a maintenant)",
        "rows": [
            {"label": "Prompt systeme", "value": "v3.2"},
            {"label": "Modele", "value": "Llama 3.2 70B"},
            {"label": "Sources connectees", "value": "158"},
            {"label": "Garde-fous actifs", "value": "7"},
        ],
        "cta": "Voir l'etat a une autre date",
    }

    conversations: dict[str, object] = {
        "title": "Conversations recentes",
        "cta": "Voir toutes les conversations",
        "rows": [
            {
                "title": "Analyse conformite ISO 27001",
                "user": "claire.martin",
                "time": "11/06/2026 10:42",
                "status": "resolu",
            },
            {
                "title": "Incidents critiques du mois",
                "user": "damien.leroy",
                "time": "11/06/2026 10:18",
                "status": "resolu",
            },
            {
                "title": "Evaluation qualite modele Llama",
                "user": "yacine.sekri",
                "time": "11/06/2026 09:55",
                "status": "escalade",
            },
            {
                "title": "Recommandations securite donnees",
                "user": "nadia.elidrissi",
                "time": "11/06/2026 09:31",
                "status": "escalade",
            },
            {
                "title": "Synthese observabilite hebdo",
                "user": "sophie.bernard",
                "time": "11/06/2026 09:02",
                "status": "resolu",
            },
        ],
    }

    activity: dict[str, object] = {
        "title": "Activite en temps reel",
        "rows": [
            {"time": "10:42", "label": "Nouvelle conversation", "kind": "info"},
            {"time": "10:42", "label": "Recherche de connaissances", "kind": "info"},
            {"time": "10:41", "label": "Nouvelle conversation", "kind": "info"},
            {"time": "10:40", "label": "Reponse generee", "kind": "ok"},
            {"time": "10:39", "label": "Reponse escaladee", "kind": "warn"},
            {"time": "10:38", "label": "Garde-fou declenche", "kind": "crit"},
        ],
    }

    prompts: dict[str, object] = {
        "title": "Prompts systeme actifs",
        "cta": "Voir tous",
        "rows": [
            {
                "name": "Prompt principal",
                "version": "v3.2",
                "status": "actif",
                "updated": "Mis a jour le 11/06/2026 09:45",
            },
            {
                "name": "Prompt securite",
                "version": "v2.1",
                "status": "actif",
                "updated": "Mis a jour le 09/06/2026 14:20",
            },
            {
                "name": "Prompt escalade",
                "version": "v1.4",
                "status": "actif",
                "updated": "Mis a jour le 06/06/2026 11:02",
            },
        ],
    }

    channels: dict[str, object] = {
        "title": "Utilisation par canal (24h)",
        "items": [
            {"label": "Application Web", "pct": 62, "tone": "blue"},
            {"label": "API", "pct": 24, "tone": "violet"},
            {"label": "Slack", "pct": 8, "tone": "green"},
            {"label": "Email", "pct": 4, "tone": "amber"},
            {"label": "Autres", "pct": 2, "tone": "slate"},
        ],
    }

    timeline: dict[str, object] = {
        "title": "Timeline de l'assistant",
        "cta": "Voir tout",
        "rows": [
            {
                "time": "09:45",
                "label": "Source ajoutee",
                "detail": "Conformite_2026.pdf",
                "kind": "ok",
            },
            {
                "time": "10:42",
                "label": "Garde-fou declenche",
                "detail": "Contenu sensible detecte",
                "kind": "crit",
            },
            {"time": "08:12", "label": "Modele change", "detail": "Llama 3.2 70B", "kind": "info"},
            {
                "time": "08:05",
                "label": "Incident conversation",
                "detail": "Escalade humaine",
                "kind": "warn",
            },
            {"time": "07:50", "label": "Retrain assistant", "detail": "v1.3.2", "kind": "ok"},
        ],
    }

    alerts: dict[str, object] = {
        "title": "Alertes & signaux (24h)",
        "cta": "Voir toutes les alertes",
        "items": [
            {"label": "Taux d'escalade en hausse", "value": "+2.6 pt vs hier", "tone": "warn"},
            {"label": "Temps de reponse P95", "value": "4.89 s", "tone": "warn"},
            {"label": "Refus de reponse", "value": "18 (-20%)", "tone": "good"},
            {"label": "Sources non synchronisees", "value": "2 connecteurs", "tone": "crit"},
        ],
    }

    quick_config: dict[str, object] = {
        "title": "Configuration rapide",
        "cta": "Voir toutes les configurations",
        "items": [
            "Inviter des sources de connaissances",
            "Configurer les garde-fous",
            "Calibrer le comportement",
            "Mettre a jour le prompt systeme",
        ],
    }

    return {
        "meta": {
            "mode": "Donnees en temps reel",
            "period": "24h",
            "updated": "11/06/2026 10:47",
            "replayAt": "Relire a T",
            "comparison": "Aucune comparaison",
        },
        "kpis": kpis,
        "profile": profile,
        "capabilities": capabilities,
        "topics": topics,
        "performance": performance,
        "config": config,
        "conversations": conversations,
        "activity": activity,
        "prompts": prompts,
        "channels": channels,
        "timeline": timeline,
        "alerts": alerts,
        "quick_config": quick_config,
    }
