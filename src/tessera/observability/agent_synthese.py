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

from tessera.observability.eval_data import load_eval_snapshot

__all__ = ["compute_agent_synthese"]


_GOOD_PCT = 70.0
_GOOD_MEAN_MS = 4000
_GOOD_P95_MS = 8000


def _secs(ms: float) -> str:
    """Milliseconds -> French seconds: 3243 -> '3,2 s'."""
    return f"{ms / 1000:.1f} s".replace(".", ",")


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
    """Return the Synthese dashboard payload.

    Quality KPIs (resolution, latency, errors), performance, topics and the
    active model are sourced from the real llama3.2:3b failure-catalogue run via
    eval_data. Volume metrics with no eval source (conversations, active users,
    satisfaction) remain illustrative demo context.
    """
    snap = load_eval_snapshot()
    total = snap.total
    passed = snap.passed
    failed = total - passed
    pass_pct = round(snap.pass_rate * 100, 1)
    escal_pct = round(100 - pass_pct, 1)
    p50 = snap.latency_percentile(50)
    p95 = snap.latency_percentile(95)
    durations = [s.duration_ms for s in snap.sessions if s.duration_ms > 0]
    mean_ms = sum(durations) / len(durations) if durations else 0.0
    chrono = sorted(snap.sessions, key=lambda s: s.started_at)
    seven = [
        chrono[round(i * len(chrono) / 7) : round((i + 1) * len(chrono) / 7)] for i in range(7)
    ]
    res_series = [round(100 * sum(1 for s in b if s.passed) / len(b)) if b else 0 for b in seven]
    lat_series = [round(sum(s.duration_ms for s in b) / len(b)) if b else 0 for b in seven]
    err_series = [sum(1 for s in b if not s.passed) for b in seven]
    top_tones = ["violet", "blue", "amber", "green", "cyan", "slate"]
    top_cats = sorted(snap.categories, key=lambda c: -c.total)[:6]

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
            f"{pass_pct:.1f}%".replace(".", ","),
            f"{passed}/{total} cas reussis",
            pass_pct >= _GOOD_PCT,
            res_series,
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
            _secs(mean_ms),
            f"p50 {_secs(p50)} - p95 {_secs(p95)}",
            mean_ms <= _GOOD_MEAN_MS,
            lat_series,
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
            "Cas en echec",
            str(failed),
            f"sur {total} cas du catalogue",
            False,
            err_series,
        ),
    ]

    profile: dict[str, object] = {
        "name": "Tessera Assistant",
        "status": "actif",
        "fields": [
            {"label": "ID", "value": "asst_001"},
            {"label": "Version", "value": "v1.3.2"},
            {"label": "Modele principal", "value": snap.model},
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
        "title": "Top categories evaluees",
        "items": [
            {"label": cat.label, "pct": round(100 * cat.total / total), "tone": tone}
            for cat, tone in zip(top_cats, top_tones, strict=False)
        ],
        "cta": "Voir toutes les categories",
    }

    performance: dict[str, object] = {
        "title": "Performance detaillee (24h)",
        "rows": [
            {
                "label": "Taux de resolution",
                "value": f"{pass_pct:.1f}%".replace(".", ","),
                "delta": f"{passed}/{total}",
                "good": pass_pct >= _GOOD_PCT,
            },
            {
                "label": "Cas en echec",
                "value": f"{escal_pct:.1f}%".replace(".", ","),
                "delta": f"{failed}/{total}",
                "good": False,
            },
            {"label": "Escalades", "value": str(snap.escalations), "delta": "cas", "good": True},
            {
                "label": "Invocations d'outils",
                "value": str(snap.tool_invocations),
                "delta": "cas",
                "good": True,
            },
            {
                "label": "Langues couvertes",
                "value": str(len(snap.languages)),
                "delta": "fr/de/en",
                "good": True,
            },
            {"label": "Temps de reponse P50", "value": _secs(p50), "delta": "median", "good": True},
            {
                "label": "Temps de reponse P95",
                "value": _secs(p95),
                "delta": "queue",
                "good": p95 <= _GOOD_P95_MS,
            },
        ],
        "cta": "Voir le detail",
    }

    config: dict[str, object] = {
        "title": "Configuration courante (a maintenant)",
        "rows": [
            {"label": "Prompt systeme", "value": snap.catalogue_version},
            {"label": "Modele", "value": snap.model},
            {"label": "Cas evalues", "value": str(total)},
            {"label": "Categories", "value": str(len(snap.categories))},
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
