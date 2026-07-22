"""Curation eval-set cockpit overview (page #12).

Composes the "Curation eval set" overview. The page has a REAL decision core and
a demonstration subsystem:

* **REAL (from :mod:`tessera.observability.curation_store`):** the backlog posture
  KPIs (candidates / promotable / manual-review / rejected / pending / …), the
  priority curation lots and the candidate distribution are derived from the real
  failed evaluation cases and their durable curation decisions (promote / review /
  reject), mutated by the curation endpoint and surviving restarts.
* **DEMONSTRATION:** the why-this-turn rationale, the collect→…→promote workflow
  stages, the eval-set coverage heatmap, the candidate-quality signals, the linked
  datasets, the governance owners/actions and the trend charts describe a fuller
  curation subsystem this build does not implement. They stay a deterministic
  fixture; the frontend marks their zones with the ``curation`` synthetic notice.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability.curation_store import (
    candidates_as_of,
    decision_counts,
    load_candidates,
)
from tessera.observability.knowledge import _LANG_IDX, _norm_lang

__all__ = ["compute_curation_overview"]

# Localized free-text (fr, de, en). IDs/names/dates/enum keys stay verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "why1": (
        "Trop peu de cas sur le crédit immobilier",
        "Zu wenige Fälle zu Immobilienkrediten",
        "Too few mortgage cases",
    ),
    "why2": (
        "Trop peu de cas en allemand",
        "Zu wenige Fälle auf Deutsch",
        "Too few cases in German",
    ),
    "why3": (
        "Plusieurs refus dans une même situation",
        "Mehrere Ablehnungen in derselben Situation",
        "Several refusals in the same situation",
    ),
    "why4": (
        "Cas à vérifier au regard de l'article 50",
        "Fall im Hinblick auf Artikel 50 prüfen",
        "Case to review against Article 50",
    ),
    "wf_collect": ("Collecte", "Erfassung", "Collection"),
    "wf_norm": ("Mise au même format", "Einheitliches Format", "Use a common format"),
    "wf_dedup": ("Retrait des doublons", "Duplikate entfernen", "Remove duplicates"),
    "wf_pii": (
        "Masquage des données personnelles",
        "Personenbezogene Daten maskieren",
        "Mask personal data",
    ),
    "wf_label": ("Classement des cas", "Fälle einordnen", "Classify cases"),
    "wf_dual": (
        "Double validation",
        "Bestätigung durch zwei Personen",
        "Two-person approval",
    ),
    "wf_promo": (
        "Ajout au jeu d'évaluation",
        "Zum Prüfsatz hinzufügen",
        "Add to the evaluation set",
    ),
    "dt_today": ("aujourd'hui {t}", "heute {t}", "today {t}"),
    "dt_yesterday": ("hier {t}", "gestern {t}", "yesterday {t}"),
    "dt_mon": ("lun. {t}", "Mo. {t}", "Mon {t}"),
    "act1": (
        "Sélection ajoutée au jeu — CUR-018",
        "Auswahl zum Prüfsatz hinzugefügt — CUR-018",
        "Selection added to the set — CUR-018",
    ),
    "act2": (
        "Vérification attribuée — CUR-042",
        "Prüfung zugewiesen — CUR-042",
        "Review assigned — CUR-042",
    ),
    "act3": (
        "Données personnelles masquées",
        "Personenbezogene Daten maskiert",
        "Personal data masked",
    ),
    "act4": (
        "Sélection créée — CUR-042",
        "Auswahl erstellt — CUR-042",
        "Selection created — CUR-042",
    ),
    "act5": (
        "Cas rejoués pour vérification",
        "Fälle zur Prüfung erneut abgespielt",
        "Cases replayed for review",
    ),
    "actor_system": ("Système", "System", "System"),
    "rel_ready": ("Prêt pour la mise en ligne", "Bereit zur Freigabe", "Ready to launch"),
    "owner_analyst": ("Analyse", "Analyse", "Analysis"),
    "owner_engineering": ("Ingénierie des modèles", "Modellentwicklung", "Model engineering"),
    "owner_compliance": ("Conformité", "Regelkonformität", "Compliance"),
    "owner_admin": ("Administration", "Administration", "Administration"),
    "sync_2min": ("il y a 2 min", "vor 2 Min", "2 min ago"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


_DIST_COLOR = {
    "hallucination": "#60a5fa",
    "grounding": "#34d399",
    "conformite": "#a78bfa",
    "pii_securite": "#f472b6",
    "outils": "#22d3ee",
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


def compute_curation_overview(lang: str = "fr", at: str | None = None) -> dict[str, object]:
    """Return the full Curation eval-set overview payload.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.
        at: Optional ISO instant T (registre §6): candidates and their decisions
            fold to what an operator saw at T; mutations stay live-only.

    Returns:
        A JSON-serialisable mapping with the backlog posture KPIs, the priority
        curation lots and their rationale, the curation workflow, the coverage
        heatmap, the candidate distribution and quality signals, the linked
        datasets, the governance actions and the backlog / balance / pass-rate
        trends.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)

    # ── REAL decision core (curation_store over failed eval cases) ──────────
    candidates = candidates_as_of(at) if at else load_candidates()
    if at:
        counts = {d: 0 for d in ("pending", "promote", "review", "reject")}
        for cand in candidates:
            counts[cand.decision] = counts.get(cand.decision, 0) + 1
        counts["total"] = len(candidates)
    else:
        counts = decision_counts()
    n_escalations = sum(1 for c in candidates if c.needs_escalation)
    n_critical = sum(1 for c in candidates if c.priority == "crit")
    n_decided = counts["promote"] + counts["review"] + counts["reject"]

    def _flat(v: int) -> list[int]:
        # Honest: the current real count, no fabricated trend line.
        return [v] * 7

    kpis = [
        _kpi("candidates", str(counts["total"]), "0", True, _flat(counts["total"])),
        _kpi("promotable", str(counts["promote"]), "0", True, _flat(counts["promote"])),
        _kpi("manual_review", str(counts["review"]), "0", False, _flat(counts["review"])),
        _kpi("rejected", str(counts["reject"]), "0", False, _flat(counts["reject"])),
        _kpi("pending", str(counts["pending"]), "0", False, _flat(counts["pending"])),
        _kpi("escalations", str(n_escalations), "0", False, _flat(n_escalations)),
        _kpi("critical", str(n_critical), "0", False, _flat(n_critical)),
        _kpi("decided", str(n_decided), "0", True, _flat(n_decided)),
    ]

    # Real: the highest-priority candidates (store sort = crit-first, top score,
    # oldest). Each row carries its durable decision + the unique candidate_id the
    # decision endpoint mutates. ``source`` is "replay": candidates come from the
    # eval harness replaying the catalogue cases.
    priority_lots = [
        {
            "id": f"{c.case_id} · {c.language.upper()}",
            "candidate_id": c.candidate_id,
            "source": "replay",
            "category": c.curation_category,
            "score": c.score,
            "risk": c.risk,
            "owner": c.decided_by or "—",
            "decision": c.decision,
        }
        for c in candidates[:6]
    ]

    # Real: the FULL candidate queue (the curate/promotions/rejections/history tabs
    # work over every real candidate, not just the top-6 overview slice).
    candidate_lots = [
        {
            "id": f"{c.case_id} · {c.language.upper()}",
            "candidate_id": c.candidate_id,
            "agent_id": c.agent_id,
            "title": c.title,
            "source": "replay",
            "category": c.curation_category,
            "language": c.language,
            "priority": c.priority,
            "score": c.score,
            "risk": c.risk,
            "owner": c.decided_by or "—",
            "decision": c.decision,
            "decided_at": c.decided_at,
        }
        for c in candidates
    ]

    why_tours = [
        {"reason": _t("why1", lang), "value": 92, "cost": "1 h 00"},
        {"reason": _t("why2", lang), "value": 78, "cost": "0 h 45"},
        {"reason": _t("why3", lang), "value": 73, "cost": "0 h 35"},
        {"reason": _t("why4", lang), "value": 62, "cost": "0 h 50"},
    ]

    workflow = [
        {"step": _t("wf_collect", lang), "qty": 148, "status": "termine"},
        {"step": _t("wf_norm", lang), "qty": 148, "status": "termine"},
        {"step": _t("wf_dedup", lang), "qty": 126, "status": "encours"},
        {"step": _t("wf_pii", lang), "qty": 98, "status": "encours"},
        {"step": _t("wf_label", lang), "qty": 98, "status": "attente"},
        {"step": _t("wf_dual", lang), "qty": 36, "status": "attente"},
        {"step": _t("wf_promo", lang), "qty": 36, "status": "attente"},
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

    # Real: candidate counts per curation dimension (only dimensions with real
    # candidates appear; nothing is fabricated to fill the donut).
    _dist_counts: dict[str, int] = {}
    for c in candidates:
        _dist_counts[c.curation_category] = _dist_counts.get(c.curation_category, 0) + 1
    _dist_total = len(candidates) or 1
    candidates_distribution = [
        {
            "key": key,
            "count": n,
            "pct": round(n / _dist_total * 100),
            "color": _DIST_COLOR.get(key, _DIST_COLOR["autres"]),
        }
        for key, n in sorted(_dist_counts.items(), key=lambda kv: kv[1], reverse=True)
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
            "updated": _t("dt_today", lang).format(t="11:42"),
        },
        {
            "name": "safety-fr-v2",
            "size": "9 763 tours",
            "status": "actif",
            "updated": _t("dt_yesterday", lang).format(t="18:09"),
        },
        {
            "name": "multilingual-edge-v1",
            "size": "8 125 tours",
            "status": "actif",
            "updated": _t("dt_yesterday", lang).format(t="18:09"),
        },
        {
            "name": "compliance-eu-v3",
            "size": "4 631 tours",
            "status": "actif",
            "updated": _t("dt_mon", lang).format(t="16:07"),
        },
    ]

    owners = [
        {"role": _t("owner_analyst", lang), "required": 1, "assigned": 1, "status": "ok"},
        {
            "role": _t("owner_engineering", lang),
            "required": 2,
            "assigned": 2,
            "status": "ok",
        },
        {
            "role": _t("owner_compliance", lang),
            "required": 1,
            "assigned": 0,
            "status": "pending",
        },
        {"role": _t("owner_admin", lang), "required": 1, "assigned": 1, "status": "ok"},
    ]

    actions = [
        {"key": "promote", "role": "", "requirement": "dual"},
        {"key": "assign_review", "role": "Compliance+", "requirement": ""},
        {"key": "freeze", "role": "", "requirement": "signature"},
        {"key": "create_replay", "role": "Operator+", "requirement": ""},
        {"key": "export", "role": "Admin+", "requirement": "signature"},
    ]

    recent_activity = [
        {"time": "11:48:24", "action": _t("act1", lang), "actor": "A. Compliance"},
        {"time": "11:42:18", "action": _t("act2", lang), "actor": "M. Engineer"},
        {"time": "11:31:05", "action": _t("act3", lang), "actor": _t("actor_system", lang)},
        {"time": "11:20:41", "action": _t("act4", lang), "actor": "S. Sysadmin"},
        {"time": "11:05:37", "action": _t("act5", lang), "actor": "D. DevRel"},
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
        "as_of": at,
        "period_days": 7,
        "updated_at": "11:54:01",
        "kpis": kpis,
        "priority_lots": priority_lots,
        "candidate_lots": candidate_lots,
        "why_tours": why_tours,
        "workflow": workflow,
        "release": {"id": "R-2024-11-07-1", "status": _t("rel_ready", lang), "readiness": 87},
        "cohort": "cohorte-2024-11-07",
        "coverage": coverage,
        "candidates_distribution": candidates_distribution,
        "distribution_total": len(candidates),
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
            "sync": _t("sync_2min", lang),
        },
    }
