"""Curation eval-set cockpit overview (page #12).

Composes the "Curation eval set" overview: the current backlog posture
(candidate turns, promotable / to-review / rejected, intent & language coverage,
duplicates, blocked failures), the priority curation lots with why-this-turn
rationale, the curation workflow stages, the eval-set coverage heatmap, the
candidate-quality signals, the linked datasets, the governance actions and the
backlog / promote-reject-review / pass-rate-impact trends.

The dataset is a deterministic reference fixture (no live curation store in this
build); values are stable across calls so the page never "dances" on refetch.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["compute_curation_overview"]

_DIST_COLOR = {
    "hallucination": "#60a5fa",
    "grounding": "#34d399",
    "conformite": "#a78bfa",
    "pii_securite": "#f472b6",
    "multilingue": "#fbbf24",
    "autres": "#64748b",
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


def compute_curation_overview() -> dict[str, object]:
    """Return the full Curation eval-set overview payload.

    Returns:
        A JSON-serialisable mapping with the backlog posture KPIs, the priority
        curation lots and their rationale, the curation workflow, the coverage
        heatmap, the candidate distribution and quality signals, the linked
        datasets, the governance actions and the backlog / balance / pass-rate
        trends.
    """
    now = datetime.now(UTC)

    kpis = [
        _kpi("candidates", "148", "+15", True, [120, 126, 130, 135, 140, 144, 148]),
        _kpi("promotable", "36", "+6", True, [28, 30, 31, 33, 34, 35, 36]),
        _kpi("manual_review", "21", "+3", False, [16, 17, 18, 19, 20, 20, 21]),
        _kpi("rejected", "17", "+2", False, [13, 14, 14, 15, 16, 16, 17]),
        _kpi("intent_coverage", "82%", "+4 pts", True, [74, 76, 77, 79, 80, 81, 82]),
        _kpi("lang_coverage", "94%", "+1 pt", True, [90, 91, 92, 92, 93, 93, 94]),
        _kpi("duplicates", "12", "-2", False, [16, 15, 15, 14, 13, 13, 12]),
        _kpi("failures", "3", "-1", False, [5, 5, 4, 4, 4, 3, 3]),
    ]

    priority_lots = [
        {
            "id": "CUR-042",
            "source": "live",
            "category": "hallucination",
            "score": 92,
            "risk": "eleve",
            "owner": "S. Sysadmin",
        },
        {
            "id": "CUR-037",
            "source": "replay",
            "category": "pii",
            "score": 88,
            "risk": "bas",
            "owner": "A. Compliance",
        },
        {
            "id": "CUR-018",
            "source": "live",
            "category": "conformite",
            "score": 81,
            "risk": "bas",
            "owner": "A. Compliance",
        },
        {
            "id": "CUR-009",
            "source": "shadow",
            "category": "outils",
            "score": 78,
            "risk": "bas",
            "owner": "D. DevRel",
        },
        {
            "id": "CUR-031",
            "source": "live",
            "category": "grounding",
            "score": 72,
            "risk": "moyen",
            "owner": "M. Engineer",
        },
    ]

    why_tours = [
        {"reason": "Faible couverture intent crédit immobilier", "value": 92, "cost": "1 h 00"},
        {"reason": "Faible couverture langue DE", "value": 78, "cost": "0 h 45"},
        {"reason": "Cluster de refus sous-segment", "value": 73, "cost": "0 h 35"},
        {"reason": "Cas limite compliance Art. 50", "value": 62, "cost": "0 h 50"},
    ]

    workflow = [
        {"step": "Collecte", "qty": 148, "status": "termine"},
        {"step": "Normalisation", "qty": 148, "status": "termine"},
        {"step": "Déduplication", "qty": 126, "status": "encours"},
        {"step": "Masquage PII", "qty": 98, "status": "encours"},
        {"step": "Labellisation", "qty": 98, "status": "attente"},
        {"step": "Validation dual-control", "qty": 36, "status": "attente"},
        {"step": "Promotion dataset", "qty": 36, "status": "attente"},
    ]

    # Eval-set coverage heatmap: 7 segments x 5 dimensions, level in ok/warn/bad/none.
    cov_rows = ["virements", "carte", "credit", "frais", "kyc", "securite", "support"]
    cov_cols = ["intent", "langue", "canal", "politique", "type_echec"]
    cov_levels = [
        ["ok", "ok", "ok", "warn", "ok"],
        ["ok", "warn", "ok", "ok", "warn"],
        ["warn", "bad", "ok", "warn", "ok"],
        ["ok", "ok", "warn", "ok", "ok"],
        ["bad", "warn", "ok", "warn", "bad"],
        ["ok", "ok", "ok", "ok", "warn"],
        ["warn", "ok", "warn", "ok", "ok"],
    ]
    coverage = {
        "rows": cov_rows,
        "cols": cov_cols,
        "cells": cov_levels,
    }

    candidates_distribution = [
        {"key": "hallucination", "count": 47, "pct": 32, "color": _DIST_COLOR["hallucination"]},
        {"key": "grounding", "count": 34, "pct": 23, "color": _DIST_COLOR["grounding"]},
        {"key": "conformite", "count": 22, "pct": 15, "color": _DIST_COLOR["conformite"]},
        {"key": "pii_securite", "count": 16, "pct": 11, "color": _DIST_COLOR["pii_securite"]},
        {"key": "multilingue", "count": 14, "pct": 9, "color": _DIST_COLOR["multilingue"]},
        {"key": "autres", "count": 15, "pct": 10, "color": _DIST_COLOR["autres"]},
    ]

    quality_signals = [
        {"key": "dedup", "pct": 98, "level": "bon"},
        {"key": "anchoring", "pct": 88, "level": "bon"},
        {"key": "labels", "pct": 74, "level": "moyen"},
        {"key": "pii_sensitivity", "pct": 91, "level": "bon"},
        {"key": "cross_tenant", "pct": 0, "level": "bon"},
        {"key": "release_coverage", "pct": 65, "level": "moyen"},
    ]

    linked_datasets = [
        {
            "name": "regression-fr-v4",
            "size": "12 842 tours",
            "status": "actif",
            "updated": "aujourd'hui 11:42",
        },
        {"name": "safety-fr-v2", "size": "9 763 tours", "status": "actif", "updated": "hier 18:09"},
        {
            "name": "multilingual-edge-v1",
            "size": "8 125 tours",
            "status": "actif",
            "updated": "hier 18:09",
        },
        {
            "name": "compliance-eu-v3",
            "size": "4 631 tours",
            "status": "actif",
            "updated": "lun. 16:07",
        },
    ]

    owners = [
        {"role": "Analyst", "required": 1, "assigned": 1, "status": "ok"},
        {"role": "M. Engineer", "required": 2, "assigned": 2, "status": "ok"},
        {"role": "Compliance", "required": 1, "assigned": 0, "status": "pending"},
        {"role": "Admin", "required": 1, "assigned": 1, "status": "ok"},
    ]

    actions = [
        {"key": "promote", "role": "", "requirement": "dual"},
        {"key": "assign_review", "role": "Compliance+", "requirement": ""},
        {"key": "freeze", "role": "", "requirement": "signature"},
        {"key": "create_replay", "role": "Operator+", "requirement": ""},
        {"key": "export", "role": "Admin+", "requirement": "signature"},
    ]

    recent_activity = [
        {"time": "11:48:24", "action": "Promotion lot — CUR-018", "actor": "A. Compliance"},
        {"time": "11:42:18", "action": "Revue assignée — CUR-042", "actor": "M. Engineer"},
        {"time": "11:31:05", "action": "Masquage PII — lot", "actor": "Système"},
        {"time": "11:20:41", "action": "Lot créé — CUR-042", "actor": "S. Sysadmin"},
        {"time": "11:05:37", "action": "Replay de validation", "actor": "D. DevRel"},
    ]

    backlog_trend = {
        "labels": ["05/05", "06/05", "07/05", "08/05", "09/05", "10/05", "11/05"],
        "total": [120, 126, 130, 135, 140, 144, 148],
        "to_curate": [78, 80, 82, 84, 86, 88, 91],
        "promotable": [28, 30, 31, 33, 34, 35, 36],
        "rejected": [13, 14, 14, 15, 16, 16, 17],
    }

    balance = {
        "labels": ["05/05", "06/05", "07/05", "08/05", "09/05", "10/05", "11/05"],
        "promote": [40, 42, 45, 44, 46, 48, 50],
        "review": [38, 36, 34, 35, 33, 31, 29],
        "reject": [22, 22, 21, 21, 21, 21, 21],
    }

    impact = {
        "current": "78.2%",
        "projected": "82.8%",
        "delta": "+4.6 pp",
        "current_val": 78.2,
        "projected_val": 82.8,
    }

    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "priority_lots": priority_lots,
        "why_tours": why_tours,
        "workflow": workflow,
        "release": {"id": "R-2024-11-07-1", "status": "Prêt à publier", "readiness": 87},
        "cohort": "cohorte-2024-11-07",
        "coverage": coverage,
        "candidates_distribution": candidates_distribution,
        "distribution_total": 148,
        "quality_signals": quality_signals,
        "linked_datasets": linked_datasets,
        "owners": owners,
        "actions": actions,
        "recent_activity": recent_activity,
        "backlog_trend": backlog_trend,
        "balance": balance,
        "impact": impact,
        "footer": {
            "release": "R-2024.11.07-1",
            "source": "YAML · Git",
            "sync": "il y a 2 min",
        },
    }
