"""Agent Evaluations ("Évaluations") dashboard payload (reference image 29).

The Evaluations page measures, analyses and improves the quality of the
assistant's answers: an inner tab strip, an active-snapshot bar (as-of-T), a KPI
strip (global score, success rate, hallucinations, relevance, source fidelity,
set coverage), a filterable + sortable + paginated evaluations table (one row
per failure-catalogue category), three secondary panels (watchlist, quick
actions, per-category success trend) and a per-row detail panel (Summary /
Configuration / Results / Activity) driven by the selected evaluation set.

The numbers are NOT a fixture: they are aggregated from a real run of the
smallest local model (``llama3.2:3b``) over the failure catalogue, read from
``eval/reports/`` by :mod:`tessera.observability.eval_data`. Each failure
category becomes an evaluation "set" whose score is its real pass rate, so the
page tells the project's honest story (the small model fails a lot).

The page is read-only on the eval run (an immutable artifact): the functional
axis is the wired filters / sort / pagination / row-selection and the real
cross-page navigation, verified end to end. Free-text data is verbatim French
(accented).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from tessera.observability.eval_data import load_eval_snapshot

if TYPE_CHECKING:
    from tessera.observability.eval_data import CategoryStat, EvalSnapshot

__all__ = ["compute_agent_evaluations"]

# Map each failure-catalogue category to a display "type" + tone key used by the
# evaluations table. Tone keys (sys/tpl/agt) are the ones the frontend styles.
_GROUP: dict[str, tuple[str, str]] = {
    "prompt_injection": ("Sécurité", "sys"),
    "pii_leak": ("Confidentialité", "sys"),
    "policy_violation": ("Politiques", "sys"),
    "regulatory_misstatement": ("Conformité", "sys"),
    "hallucination": ("Factualité", "tpl"),
    "citation_fabrication": ("Factualité", "tpl"),
    "language_mixing": ("Multilingue", "tpl"),
    "overconfidence": ("Agent", "agt"),
    "tool_misuse": ("Agent", "agt"),
    "escalation_failure": ("Agent", "agt"),
}

_FACTUAL = {"hallucination", "citation_fabrication"}

# Quality thresholds (on a 0-10 score) and rate thresholds (0-1).
_GOOD_SCORE = 7.0
_OK_SCORE = 5.0
_HIGH_HALLUC = 0.3
_ALERT_PASS_RATE = 0.7


def _comma(value: float) -> str:
    """French decimal: 4.2 -> '4,2'."""
    return f"{value:.1f}".replace(".", ",")


def _dot(value: float) -> str:
    """Dot decimal for the table score column: 7.9 -> '7.9'."""
    return f"{value:.1f}"


def _pct(value: float) -> str:
    return f"{round(value * 100)}%"


def _quality_note(score10: float) -> tuple[str, str]:
    if score10 >= _GOOD_SCORE:
        return "Bon", "good"
    if score10 >= _OK_SCORE:
        return "Moyen", "warn"
    return "Faible", "bad"


def _kpi(
    key: str,
    label: str,
    value: str,
    scale: str,
    note: str,
    note_tone: str,
    delta: str,
    delta_tone: str,
    gauge: int | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "scale": scale,
        "note": note,
        "note_tone": note_tone,
        "delta": delta,
        "delta_tone": delta_tone,
        "gauge": gauge,
    }


def _row(stat: CategoryStat, version_label: str, stamp: str) -> dict[str, object]:
    """A self-describing evaluation-set row (display cells + raw keys for the detail)."""
    type_label, type_tone = _GROUP.get(stat.category, ("Autre", "sys"))
    is_fact = stat.category in _FACTUAL
    quality, quality_tone = _quality_note(stat.pass_rate * 10)
    return {
        "name": stat.label,
        "type": type_label,
        "type_tone": type_tone,
        "status": "Actif",
        "status_tone": "good",
        "version": version_label,
        "score": _dot(stat.pass_rate * 10),
        "score_num": round(stat.pass_rate * 10, 1),
        "success": _pct(stat.pass_rate),
        "halluc": _pct(stat.failed / stat.total) if is_fact and stat.total else "-",
        "last_run": stamp,
        "owner": "Tessera Eval",
        "tests": str(stat.total),
        # raw fields for filtering + the detail panel
        "category_key": stat.category,
        "quality_key": quality_tone,
        "quality_label": quality,
        "is_fact": is_fact,
        "passed": stat.passed,
        "total": stat.total,
        "failed": stat.failed,
        "pass_rate": round(stat.pass_rate, 4),
    }


def _run_labels(snap: EvalSnapshot) -> tuple[str, str]:
    """Return (formatted timestamp, relative age) for the run."""
    moment = snap.run_datetime()
    if moment is None:
        return snap.run_at, ""
    stamp = moment.strftime("%d/%m/%Y %H:%M")
    days = (date.today() - moment.date()).days
    if days <= 0:
        rel = "aujourd'hui"
    elif days == 1:
        rel = "hier"
    else:
        rel = f"il y a {days} j"
    return stamp, rel


def compute_agent_evaluations() -> dict[str, object]:
    """Return the Evaluations dashboard payload from a real llama3.2:3b run."""
    snap = load_eval_snapshot()
    stamp, rel = _run_labels(snap)
    n_lang = len(snap.languages)
    lang_str = ", ".join(code for code, _ in snap.languages)
    score10 = snap.pass_rate * 10

    factual = [c for c in snap.categories if c.category in _FACTUAL]
    fact_total = sum(c.total for c in factual)
    fact_failed = sum(c.failed for c in factual)
    halluc_rate = fact_failed / fact_total if fact_total else 0.0
    cite = snap.category("citation_fabrication")
    cite_rate = cite.pass_rate if cite else 0.0
    cite_passed = cite.passed if cite else 0
    cite_total = cite.total if cite else 0

    behaviour = [c for c in snap.categories if _GROUP.get(c.category, ("", ""))[1] == "agt"]
    beh_total = sum(c.total for c in behaviour)
    beh_pass = sum(c.passed for c in behaviour)
    beh_rate = beh_pass / beh_total if beh_total else 0.0

    snapshot: dict[str, object] = {
        "tag": "SNAPSHOT ACTIF",
        "label": f"Catalogue d'échecs - {snap.model}",
        "updated_label": "Dernière exécution",
        "updated": stamp,
        "updated_rel": rel,
        "version_label": "Modèle évalué",
        "version": snap.model,
        "version_status": "On-prem",
        "evalset_label": "Jeu d'évaluations",
        "evalset": f"{snap.total} cas",
        "coverage_label": "Couverture",
        "coverage": 100,
        "coverage_tone": "Complète",
        "asof": "Voir à date",
        "compare": "Comparer au snapshot précédent",
    }

    score_note, score_tone = _quality_note(score10)
    kpis: list[dict[str, object]] = [
        _kpi("score", "Score global", _comma(score10), "/10", score_note, score_tone,
             f"{snap.passed}/{snap.total} cas réussis", "muted"),
        _kpi("success", "Taux de réussite", "", "", score_note, score_tone,
             f"{snap.passed}/{snap.total} cas", "muted", gauge=round(snap.pass_rate * 100)),
        _kpi("halluc", "Hallucinations", _pct(halluc_rate), "",
             "Élevé" if halluc_rate >= _HIGH_HALLUC else "Maîtrisé",
             "bad" if halluc_rate >= _HIGH_HALLUC else "good",
             f"{fact_failed}/{fact_total} sondes factualité", "muted"),
        _kpi("relevance", "Pertinence", _comma(beh_rate * 10), "/10", *_quality_note(beh_rate * 10),
             f"{beh_pass}/{beh_total} cas agent", "muted"),
        _kpi("fidelity", "Fidélité (sources)", _pct(cite_rate), "", *_quality_note(cite_rate * 10),
             f"{cite_passed}/{cite_total} cas citation", "muted"),
        _kpi("coverage", "Couverture du set", str(snap.total), "", "tests exécutés", "muted",
             f"{len(snap.categories)} catégories - {n_lang} langues", "muted"),
    ]

    # Filter options that genuinely partition the rows (type / quality band /
    # hallucinations), keyed on stable values - the normative's uniform
    # Statut/Proprietaire would never change the row count, so they are dropped.
    seen_types: dict[str, str] = {}
    for stat in snap.categories:
        label, _tone = _GROUP.get(stat.category, ("Autre", "sys"))
        seen_types.setdefault(label, label)
    filters: dict[str, object] = {
        "search": "Rechercher une évaluation...",
        "options": {
            "type": [{"key": lbl, "label": lbl} for lbl in sorted(seen_types)],
            "quality": [
                {"key": "good", "label": "Bon"},
                {"key": "warn", "label": "Moyen"},
                {"key": "bad", "label": "Faible"},
            ],
            "halluc": [
                {"key": "with", "label": "Avec hallucinations"},
                {"key": "without", "label": "Sans"},
            ],
        },
    }

    columns = [
        "Nom de l'évaluation", "Type", "Statut", "Version", "Score global",
        "Taux réussite", "Hallucinations", "Dernière exécution", "Propriétaire", "Tests",
    ]
    version_label = snap.catalogue_version[:9] or "v1"
    rows = [
        _row(stat, version_label, stamp)
        for stat in sorted(snap.categories, key=lambda c: (-c.pass_rate, -c.total))
    ]

    worst = snap.categories_by_pass_rate()
    watch_tones = ["crit", "crit", "warn"]
    watch_items = [
        {"title": f"{stat.label} - {_pct(stat.pass_rate)} de réussite",
         "detail": f"{stat.passed}/{stat.total} cas - {n_lang} langues", "tone": tone}
        for stat, tone in zip(worst[:3], watch_tones, strict=False)
    ]
    n_alert = sum(1 for c in snap.categories if c.pass_rate < _ALERT_PASS_RATE)
    watch: dict[str, object] = {
        "title": "À surveiller",
        "cta": f"Voir toutes les alertes ({n_alert})",
        "cta_href": "/agent/a-traiter",
        "items": watch_items,
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            {"key": "run", "label": "Lancer une évaluation"},
            {"key": "compare", "label": "Comparer versions"},
            {"key": "results", "label": "Voir les résultats"},
            {"key": "sets", "label": "Gérer les jeux"},
        ],
    }

    trend: dict[str, object] = {
        "title": "Réussite par catégorie",
        "value": _comma(score10),
        "scale": "/10",
        "legend": "Taux de réussite (%) par catégorie",
        "series": [round(c.pass_rate * 100) for c in worst],
    }

    return {
        "title": "Évaluations",
        "subtitle": (
            "Mesurez, analysez et améliorez la qualité des réponses de "
            "l'assistant et des agents."
        ),
        "actions": {"asof": "Voir à date (as-of)", "create": "Créer une évaluation"},
        "subtabs": [
            "Vue d'ensemble", "Jeux d'évaluations", "Résultats", "Dimensions",
            "Comparaisons", "Erreurs", "Versions & historique", "Exports",
        ],
        "meta": {
            "model": snap.model,
            "catalogue_version": snap.catalogue_version,
            "languages": lang_str,
            "score10": _comma(score10),
            "escalations": snap.escalations,
            "tool_invocations": snap.tool_invocations,
            "rbac": [
                {"role": "ML Engineer", "access": "Lecture"},
                {"role": "Compliance Officer", "access": "Lecture / Écriture"},
                {"role": "Admin", "access": "Lecture / Écriture"},
            ],
        },
        "detail_labels": {
            "eyebrow": "Détails de l'évaluation",
            "tabs": ["Résumé", "Configuration", "Résultats", "Activité"],
            "results_title": "Résultats (run)",
            "results_cta": "Voir tous les résultats",
            "rbac_title": "Accès RBAC",
            "config_title": "Configuration du jeu",
            "info_title": "Informations techniques",
            "activity_title": "Journal d'activité",
        },
        "snapshot": snapshot,
        "kpis": kpis,
        "filters": filters,
        "table": {"columns": columns, "rows": rows, "total": len(rows)},
        "watch": watch,
        "quick": quick,
        "trend": trend,
    }
