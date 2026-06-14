"""Signal catalogue cockpit overview (page #16).

Composes the "Signal catalogue" overview: the catalogue posture (total / active /
in-evaluation / deprecated / disabled signals and the severity split), the
filterable signal table, and the detail panel for the selected signal (its
definition, thresholds, 30-day distribution and trend, and usage).

The dataset is a deterministic reference fixture (the catalogue ships as a
governance artifact in this build); values are stable across calls so the page
never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_signal_catalogue"]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def compute_signal_catalogue() -> dict[str, object]:
    """Return the full Signal catalogue overview payload.

    Returns:
        A JSON-serialisable mapping with the catalogue posture KPIs, the signal
        table and the selected-signal detail (definition, thresholds, 30-day
        distribution and trend, usage).
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("total", "312", "+12 ce mois", [288, 292, 297, 301, 305, 309, 312]),
        _kpi("active", "278", "89% du total", [250, 256, 261, 266, 270, 274, 278]),
        _kpi("evaluation", "14", "4% du total", [10, 11, 12, 12, 13, 13, 14]),
        _kpi("deprecated", "10", "3% du total", [12, 12, 11, 11, 10, 10, 10]),
        _kpi("disabled", "10", "3% du total", [8, 8, 9, 9, 10, 10, 10]),
        _kpi("critical", "38", "12% du total", [32, 33, 34, 35, 36, 37, 38]),
        _kpi("high", "86", "28% du total", [78, 80, 81, 83, 84, 85, 86]),
        _kpi("medium", "124", "40% du total", [116, 118, 120, 121, 122, 123, 124]),
        _kpi("low", "64", "20% du total", [60, 61, 61, 62, 63, 63, 64]),
    ]

    signals = [
        {
            "id": "SIG-001",
            "name": "hallucination_rate",
            "category": "qualite",
            "description": "Taux d'hallucination détecté sur les réponses RAG",
            "source": "Observabilité",
            "severity": "critical",
            "status": "active",
            "quality": 92,
            "last_activity": "il y a 4 min",
            "owner": "AI Quality Team",
            "modified": "11/06/2026",
        },
        {
            "id": "SIG-014",
            "name": "pii_leak_rate",
            "category": "securite",
            "description": "Fuite de PII dans les sorties du modèle",
            "source": "Guard",
            "severity": "critical",
            "status": "active",
            "quality": 99,
            "last_activity": "il y a 2 min",
            "owner": "Privacy Team",
            "modified": "11/06/2026",
        },
        {
            "id": "SIG-022",
            "name": "prompt_injection_bypass",
            "category": "securite",
            "description": "Contournement du firewall par injection de prompt",
            "source": "Guard",
            "severity": "high",
            "status": "active",
            "quality": 88,
            "last_activity": "il y a 11 min",
            "owner": "Security Team",
            "modified": "10/06/2026",
        },
        {
            "id": "SIG-031",
            "name": "grounding_score",
            "category": "qualite",
            "description": "Ancrage des réponses dans le corpus récupéré",
            "source": "Eval",
            "severity": "high",
            "status": "active",
            "quality": 90,
            "last_activity": "il y a 6 min",
            "owner": "AI Quality Team",
            "modified": "10/06/2026",
        },
        {
            "id": "SIG-045",
            "name": "toxicity_rate",
            "category": "securite",
            "description": "Toxicité détectée dans les réponses",
            "source": "Guard",
            "severity": "medium",
            "status": "active",
            "quality": 97,
            "last_activity": "il y a 18 min",
            "owner": "Safety Team",
            "modified": "09/06/2026",
        },
        {
            "id": "SIG-058",
            "name": "disclosure_art50",
            "category": "conformite",
            "description": "Présence de la divulgation IA (Art. 50)",
            "source": "Eval",
            "severity": "medium",
            "status": "active",
            "quality": 95,
            "last_activity": "il y a 22 min",
            "owner": "Compliance",
            "modified": "08/06/2026",
        },
        {
            "id": "SIG-067",
            "name": "token_cost_per_turn",
            "category": "cout",
            "description": "Coût en tokens par tour de conversation",
            "source": "Observabilité",
            "severity": "low",
            "status": "active",
            "quality": 99,
            "last_activity": "il y a 1 min",
            "owner": "FinOps",
            "modified": "08/06/2026",
        },
        {
            "id": "SIG-079",
            "name": "memory_ttl_breach",
            "category": "memoire",
            "description": "Dépassement du TTL de la mémoire conversationnelle",
            "source": "Observabilité",
            "severity": "medium",
            "status": "evaluation",
            "quality": 84,
            "last_activity": "il y a 33 min",
            "owner": "Privacy Team",
            "modified": "07/06/2026",
        },
        {
            "id": "SIG-088",
            "name": "language_routing_error",
            "category": "qualite",
            "description": "Erreur de routage de la langue de réponse",
            "source": "Eval",
            "severity": "medium",
            "status": "active",
            "quality": 91,
            "last_activity": "il y a 9 min",
            "owner": "AI Quality Team",
            "modified": "07/06/2026",
        },
        {
            "id": "SIG-093",
            "name": "cross_tenant_leak",
            "category": "securite",
            "description": "Fuite de données entre tenants",
            "source": "Guard",
            "severity": "critical",
            "status": "active",
            "quality": 100,
            "last_activity": "il y a 14 min",
            "owner": "Security Team",
            "modified": "06/06/2026",
        },
    ]

    selected = {
        "id": "SIG-001",
        "name": "hallucination_rate",
        "category": "qualite",
        "status": "active",
        "description": (
            "Taux d'hallucination détecté sur les réponses RAG, comparé aux sources de vérité."
        ),
        "source": "Observabilité",
        "type": "Score",
        "unit": "%",
        "direction": "Plus bas est mieux",
        "frequency": "24h / temps réel",
        "environment": "Tous",
        "tags": ["tous les modèles", "qualité", "hallucination", "llm"],
        "created": "01/04/2026",
        "modified": "11/06/2026 08:12",
        "severity": "critical",
        "threshold_critical": "> 5%",
        "threshold_alert": "> 3%",
        "model": "Llama 3.2 3B",
        "last_activity": "AG-501",
        "quality": 92,
        "distribution": [
            {"label": "0-1%", "count": 62, "color": "#34d399"},
            {"label": "1-3%", "count": 48, "color": "#34d399"},
            {"label": "3-5%", "count": 26, "color": "#fbbf24"},
            {"label": "5-8%", "count": 14, "color": "#fbbf24"},
            {"label": ">8%", "count": 6, "color": "#f87171"},
        ],
        "trend": [4.8, 4.5, 4.2, 4.4, 3.9, 3.6, 3.4],
        "usage": {"logged_by": "12 playbooks", "monitors": "8 datasets"},
    }

    return {
        "generated_at": now.isoformat(),
        "total_signals": 312,
        "page_size": 10,
        "kpis": kpis,
        "signals": signals,
        "selected": selected,
        "categories": ["qualite", "securite", "conformite", "observabilite", "cout", "memoire"],
        "footer": {"total": 312, "source": "YAML · Git"},
    }
