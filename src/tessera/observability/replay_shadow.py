"""Replay & shadow cockpit overview (page #11, ADR 0011).

Composes the "Replay & shadow" overview: the replay posture (sessions / requests
/ tokens replayed, replay cost, deviations vs baseline, shadow coverage), the
day-by-day replay traffic, the deviation breakdowns (by type, by severity), the
recent / top-deviation sessions, the baseline comparisons and per-service /
per-model distributions, plus the proofs & exports tallies and the live replay
activity feed.

The as-of-T replay engine and shadow scorer live in
:mod:`tessera.observability.replay` / :mod:`tessera.observability.shadow`; this
module is the presentation layer that assembles one self-contained payload for
the page. The dataset is a deterministic reference fixture (no live replay store
in this build); values are stable across calls so the page never "dances".
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_replay_shadow_overview"]

_SERVICE_COLOR = {
    "chat_support": "#60a5fa",
    "fraud_risk": "#f97316",
    "code_copilot": "#a78bfa",
    "data_analyst": "#34d399",
    "agent_workflow": "#fbbf24",
    "others": "#64748b",
}
_MODEL_COLOR = {
    "llama": "#60a5fa",
    "gpt4o": "#a78bfa",
    "mistral": "#f97316",
    "deepseek": "#34d399",
    "others": "#64748b",
}
_TYPE_COLOR = {
    "instruction": "#f97316",
    "hallucination": "#60a5fa",
    "toxicity": "#f472b6",
    "factual": "#a78bfa",
    "confidentiality": "#34d399",
    "others": "#64748b",
}
_SEV_COLOR = {
    "critique": "#f87171",
    "eleve": "#fb923c",
    "moyen": "#fbbf24",
    "faible": "#60a5fa",
}


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


def compute_replay_shadow_overview() -> dict[str, object]:
    """Return the full Replay & shadow overview payload.

    Returns:
        A JSON-serialisable mapping with the replay posture KPIs, traffic and
        deviation series, recent / top-deviation sessions, baseline comparisons,
        per-service and per-model distributions, replayed-eval categories,
        proofs & exports tallies and the live activity feed.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("sessions", "24 751", "+6.4%", True, [18, 19, 20, 21, 22, 23, 25]),
        _kpi("requests", "182 394", "+11.2%", True, [150, 158, 162, 168, 172, 178, 182]),
        _kpi("tokens", "412.8 M", "+9.6%", True, [360, 372, 380, 391, 398, 405, 413]),
        _kpi("cost", "€ 1 842.36", "-6.3%", False, [21, 20, 20, 19, 19, 18, 18]),
        _kpi("deviations", "132", "+23.5%", False, [95, 101, 108, 114, 120, 126, 132]),
        _kpi("evals", "451", "+12.1%", True, [390, 402, 415, 426, 435, 444, 451]),
        _kpi("proofs", "21 348", "+5.4%", True, [19, 19, 20, 20, 21, 21, 21]),
        _kpi("coverage", "61%", "+4.2 pts", True, [54, 55, 57, 58, 59, 60, 61]),
    ]

    replay_traffic = {
        "labels": ["03/05", "05/05", "07/05", "09/05", "11/05"],
        "requests": [22, 26, 24, 30, 31],
        "tokens": [40, 50, 45, 60, 62],
    }

    deviation_by_type = [
        {"key": "instruction", "count": 33, "pct": 25, "color": _TYPE_COLOR["instruction"]},
        {"key": "hallucination", "count": 25, "pct": 19, "color": _TYPE_COLOR["hallucination"]},
        {"key": "toxicity", "count": 23, "pct": 17, "color": _TYPE_COLOR["toxicity"]},
        {"key": "factual", "count": 19, "pct": 14, "color": _TYPE_COLOR["factual"]},
        {"key": "confidentiality", "count": 21, "pct": 16, "color": _TYPE_COLOR["confidentiality"]},
        {"key": "others", "count": 11, "pct": 8, "color": _TYPE_COLOR["others"]},
    ]

    deviation_severity = [
        {"key": "critique", "count": 41, "pct": 31, "color": _SEV_COLOR["critique"]},
        {"key": "eleve", "count": 35, "pct": 27, "color": _SEV_COLOR["eleve"]},
        {"key": "moyen", "count": 35, "pct": 27, "color": _SEV_COLOR["moyen"]},
        {"key": "faible", "count": 21, "pct": 15, "color": _SEV_COLOR["faible"]},
    ]

    recent_sessions = [
        {
            "id": "ses_9f71ac",
            "service": "Chat Support",
            "model": "Llama 3.2 3B",
            "status": "rejouee",
            "origin": "11/05/2025 11:54",
        },
        {
            "id": "ses_3b2d9c",
            "service": "Fraud Risk",
            "model": "Mistral 8x7B",
            "status": "rejouee",
            "origin": "11/05/2025 11:52",
        },
        {
            "id": "ses_7afe56",
            "service": "Code Copilot",
            "model": "DeepSeek-V2",
            "status": "rejouee",
            "origin": "11/05/2025 11:49",
        },
        {
            "id": "ses_1a5a44",
            "service": "Data Analyst",
            "model": "Llama 3.2 3B",
            "status": "error",
            "origin": "11/05/2025 11:47",
        },
        {
            "id": "ses_6d2a21",
            "service": "Agent Workflow",
            "model": "GPT-4o",
            "status": "encours",
            "origin": "11/05/2025 11:44",
        },
    ]

    top_deviations = [
        {
            "id": "ses_9f71ac",
            "service": "Chat Support",
            "type": "hallucination",
            "baseline": "v2.3",
            "severity": "critique",
            "delta": "-0.62",
        },
        {
            "id": "ses_3b2d9c",
            "service": "Fraud Risk",
            "type": "instruction",
            "baseline": "v2.3",
            "severity": "critique",
            "delta": "-0.71",
        },
        {
            "id": "ses_7afe56",
            "service": "Code Copilot",
            "type": "factual",
            "baseline": "v2.3",
            "severity": "critique",
            "delta": "-0.58",
        },
        {
            "id": "ses_1a5a44",
            "service": "Data Analyst",
            "type": "toxicity",
            "baseline": "v2.1",
            "severity": "eleve",
            "delta": "-0.49",
        },
        {
            "id": "ses_4b2e9f",
            "service": "Agent Workflow",
            "type": "confidentiality",
            "baseline": "v2.1",
            "severity": "moyen",
            "delta": "-0.31",
        },
        {
            "id": "ses_2c91de",
            "service": "Chat Support",
            "type": "factual",
            "baseline": "v2.2",
            "severity": "eleve",
            "delta": "-0.44",
        },
    ]

    recent_comparisons = [
        {"label": "v2.3 vs v2.1", "baseline": "v2.3", "sessions": "2 104", "deviations": 132},
        {"label": "v2.3 vs v2.2", "baseline": "v2.3", "sessions": "1 937", "deviations": 98},
        {"label": "v2.2 vs v2.1", "baseline": "v2.2", "sessions": "1 812", "deviations": 76},
        {"label": "v2.3 vs v2.0", "baseline": "v2.3", "sessions": "2 256", "deviations": 154},
    ]

    top_regressions = [
        {
            "service": "Chat Support",
            "delta": "-0.054",
            "critical": 145,
            "spark": [3, 2, 3, 2, 1, 1, 1],
        },
        {
            "service": "Fraud Risk",
            "delta": "-0.071",
            "critical": 21,
            "spark": [3, 3, 2, 2, 2, 1, 1],
        },
        {
            "service": "Code Copilot",
            "delta": "-0.056",
            "critical": 21,
            "spark": [2, 2, 2, 1, 1, 1, 1],
        },
        {
            "service": "Data Analyst",
            "delta": "-0.012",
            "critical": 21,
            "spark": [2, 2, 2, 2, 2, 1, 2],
        },
        {
            "service": "Agent Workflow",
            "delta": "-0.047",
            "critical": 9,
            "spark": [2, 2, 1, 1, 1, 1, 1],
        },
    ]

    by_service = [
        {"key": "chat_support", "count": 37845, "pct": 20, "color": _SERVICE_COLOR["chat_support"]},
        {"key": "fraud_risk", "count": 27540, "pct": 15, "color": _SERVICE_COLOR["fraud_risk"]},
        {"key": "code_copilot", "count": 24663, "pct": 13, "color": _SERVICE_COLOR["code_copilot"]},
        {"key": "data_analyst", "count": 18972, "pct": 10, "color": _SERVICE_COLOR["data_analyst"]},
        {
            "key": "agent_workflow",
            "count": 14539,
            "pct": 8,
            "color": _SERVICE_COLOR["agent_workflow"],
        },
        {"key": "others", "count": 58835, "pct": 34, "color": _SERVICE_COLOR["others"]},
    ]

    by_model = [
        {"key": "llama", "count": 76605, "pct": 42, "color": _MODEL_COLOR["llama"]},
        {"key": "gpt4o", "count": 36479, "pct": 20, "color": _MODEL_COLOR["gpt4o"]},
        {"key": "deepseek", "count": 21887, "pct": 12, "color": _MODEL_COLOR["deepseek"]},
        {"key": "mistral", "count": 16132, "pct": 9, "color": _MODEL_COLOR["mistral"]},
        {"key": "others", "count": 31291, "pct": 17, "color": _MODEL_COLOR["others"]},
    ]

    evals_by_category = [
        {"key": "hallucination", "count": 132, "pct": 29, "color": "#60a5fa"},
        {"key": "instruction", "count": 108, "pct": 24, "color": "#f97316"},
        {"key": "factual", "count": 79, "pct": 18, "color": "#a78bfa"},
        {"key": "robustness", "count": 53, "pct": 12, "color": "#34d399"},
        {"key": "confidentiality", "count": 47, "pct": 10, "color": "#f472b6"},
        {"key": "others", "count": 32, "pct": 7, "color": "#64748b"},
    ]

    activity_feed = [
        {"id": "ses_9f71ac", "time": "11:54:18", "status": "rejouee"},
        {"id": "ses_3b2d9c", "time": "11:53:58", "status": "termine"},
        {"id": "ses_0c4b48", "time": "11:53:31", "status": "rejouee"},
        {"id": "ses_8b2cc1", "time": "11:53:12", "status": "termine"},
        {"id": "ses_6c64a2", "time": "11:52:47", "status": "error"},
        {"id": "ses_d70f3c", "time": "11:52:20", "status": "rejouee"},
    ]

    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "replay_traffic": replay_traffic,
        "deviation_by_type": deviation_by_type,
        "deviation_total": 132,
        "deviation_severity": deviation_severity,
        "recent_sessions": recent_sessions,
        "top_deviations": top_deviations,
        "recent_comparisons": recent_comparisons,
        "top_regressions": top_regressions,
        "by_service": by_service,
        "by_model": by_model,
        "requests_total": "182 394",
        "evals_by_category": evals_by_category,
        "proofs_exports": {
            "generated": "21 348",
            "available": "1 162",
            "downloaded": "742",
            "total_size": "248.6 Go",
            "last_export": "11/05/2025 11:28",
        },
        "baselines": [
            {"value": "v2.3", "label": "Baseline v2.3 (référence)"},
            {"value": "v2.2", "label": "Baseline v2.2"},
            {"value": "v2.1", "label": "Baseline v2.1"},
        ],
        "services": [
            "Chat Support",
            "Fraud Risk",
            "Code Copilot",
            "Data Analyst",
            "Agent Workflow",
        ],
        "activity_feed": activity_feed,
        "footer": {
            "environment": "Production",
            "services": 24,
            "active_users": "1 245",
            "confidence": "Élevé",
            "source": "YAML · Git",
        },
    }
