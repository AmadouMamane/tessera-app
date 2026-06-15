"""Agent Evaluations ("Evaluations") dashboard payload (reference image 29).

The Evaluations page measures, analyses and improves the quality of the
assistant's answers: an inner tab strip (overview, eval sets, results,
dimensions, comparisons, errors, versions, exports), an active-snapshot bar
(as-of-T), a KPI strip (global score, success rate, hallucinations, relevance,
source fidelity, set coverage), a filterable evaluations table (type, status,
version, score, success, hallucinations, last run, owner), three secondary
panels (watchlist, quick actions, global-score trend) and a per-evaluation
detail panel with a Summary / Configuration / Results / Activity tab set,
period results and RBAC access.

The numbers are NOT a fixture: they are aggregated from a real run of the
smallest local model (``llama3.2:3b``) over the failure catalogue, read from
``eval/reports/`` by :mod:`tessera.observability.eval_data`. Each failure
category becomes an evaluation "set" whose score is its real pass rate, so the
page tells the project's honest story (the small model fails a lot). Free-text
data is verbatim French with ASCII-only punctuation.
"""

from __future__ import annotations

from datetime import date

from tessera.observability.eval_data import EvalSnapshot, load_eval_snapshot

__all__ = ["compute_agent_evaluations"]

# Map each failure-catalogue category to a display "type" + tone key used by the
# evaluations table. Tone keys (sys/tpl/agt) are the ones the frontend styles.
_GROUP: dict[str, tuple[str, str]] = {
    "prompt_injection": ("Securite", "sys"),
    "pii_leak": ("Confidentialite", "sys"),
    "policy_violation": ("Politiques", "sys"),
    "regulatory_misstatement": ("Conformite", "sys"),
    "hallucination": ("Factualite", "tpl"),
    "citation_fabrication": ("Factualite", "tpl"),
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


def _row(
    name: str,
    type_: str,
    type_tone: str,
    status: str,
    status_tone: str,
    version: str,
    score: str,
    success: str,
    halluc: str,
    last_run: str,
    owner: str,
    tests: str,
) -> dict[str, object]:
    return {
        "name": name,
        "type": type_,
        "type_tone": type_tone,
        "status": status,
        "status_tone": status_tone,
        "version": version,
        "score": score,
        "success": success,
        "halluc": halluc,
        "last_run": last_run,
        "owner": owner,
        "tests": tests,
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
        "label": f"Catalogue d'echecs - {snap.model}",
        "updated_label": "Derniere execution",
        "updated": stamp,
        "updated_rel": rel,
        "version_label": "Modele evalue",
        "version": snap.model,
        "version_status": "On-prem",
        "evalset_label": "Jeu d'evaluations",
        "evalset": f"{snap.total} cas",
        "coverage_label": "Couverture",
        "coverage": 100,
        "coverage_tone": "Complete",
        "asof": "Voir a date",
        "compare": "Comparer au snapshot precedent",
    }

    score_note, score_tone = _quality_note(score10)
    kpis: list[dict[str, object]] = [
        _kpi(
            "score",
            "Score global",
            _comma(score10),
            "/10",
            score_note,
            score_tone,
            f"{snap.passed}/{snap.total} cas reussis",
            "muted",
        ),
        _kpi(
            "success",
            "Taux de reussite",
            "",
            "",
            score_note,
            score_tone,
            f"{snap.passed}/{snap.total} cas",
            "muted",
            gauge=round(snap.pass_rate * 100),
        ),
        _kpi(
            "halluc",
            "Hallucinations",
            _pct(halluc_rate),
            "",
            "Eleve" if halluc_rate >= _HIGH_HALLUC else "Maitrise",
            "bad" if halluc_rate >= _HIGH_HALLUC else "good",
            f"{fact_failed}/{fact_total} sondes factualite",
            "muted",
        ),
        _kpi(
            "relevance",
            "Pertinence",
            _comma(beh_rate * 10),
            "/10",
            *_quality_note(beh_rate * 10),
            f"{beh_pass}/{beh_total} cas agent",
            "muted",
        ),
        _kpi(
            "fidelity",
            "Fidelite (sources)",
            _pct(cite_rate),
            "",
            *_quality_note(cite_rate * 10),
            f"{cite_passed}/{cite_total} cas citation",
            "muted",
        ),
        _kpi(
            "coverage",
            "Couverture du set",
            str(snap.total),
            "",
            "tests executes",
            "muted",
            f"{len(snap.categories)} categories - {n_lang} langues",
            "muted",
        ),
    ]

    filters: dict[str, object] = {
        "search": "Rechercher une evaluation...",
        "selects": [
            {"label": "Type", "value": "Tous"},
            {"label": "Statut", "value": "Tous"},
            {"label": "Proprietaire", "value": "Tous"},
            {"label": "Etiquette", "value": "Toutes"},
        ],
        "more": "Filtres",
    }

    columns = [
        "Nom de l'evaluation",
        "Type",
        "Statut",
        "Version",
        "Score global",
        "Taux reussite",
        "Hallucinations",
        "Derniere execution",
        "Proprietaire",
        "Tests",
    ]
    version_label = snap.catalogue_version[:9] or "v1"
    rows: list[dict[str, object]] = []
    for stat in sorted(snap.categories, key=lambda c: (-c.pass_rate, -c.total)):
        type_label, type_tone = _GROUP.get(stat.category, ("Autre", "sys"))
        is_fact = stat.category in _FACTUAL
        rows.append(
            _row(
                stat.label,
                type_label,
                type_tone,
                "Actif",
                "good",
                version_label,
                _dot(stat.pass_rate * 10),
                _pct(stat.pass_rate),
                _pct(stat.failed / stat.total) if is_fact and stat.total else "-",
                stamp,
                "Tessera Eval",
                str(stat.total),
            )
        )

    worst = snap.categories_by_pass_rate()
    watch_tones = ["crit", "crit", "warn"]
    watch_items: list[dict[str, object]] = [
        {
            "title": f"{stat.label} - {_pct(stat.pass_rate)} de reussite",
            "detail": f"{stat.passed}/{stat.total} cas - {n_lang} langues",
            "tone": tone,
        }
        for stat, tone in zip(worst[:3], watch_tones, strict=False)
    ]
    n_alert = sum(1 for c in snap.categories if c.pass_rate < _ALERT_PASS_RATE)
    watch: dict[str, object] = {
        "title": "A surveiller",
        "cta": f"Voir toutes les alertes ({n_alert})",
        "items": watch_items,
    }

    quick: dict[str, object] = {
        "title": "Actions rapides",
        "items": [
            "Lancer une evaluation",
            "Comparer versions",
            "Voir les resultats",
            "Gerer les jeux",
        ],
    }

    trend: dict[str, object] = {
        "title": "Reussite par categorie",
        "value": _comma(score10),
        "scale": "/10",
        "legend": "Taux de reussite (%) par categorie",
        "series": [round(c.pass_rate * 100) for c in worst],
    }

    worst0 = worst[0]
    worst0_type, _ = _GROUP.get(worst0.category, ("Conformite", "sys"))
    detail: dict[str, object] = {
        "name": worst0.label,
        "id": f"@_eval_{worst0.category}",
        "status": "Actif",
        "tabs": ["Resume", "Configuration", "Resultats", "Activite"],
        "description": (
            f"Sondes de la categorie '{worst0.label}' du catalogue d'echecs, "
            f"executees sur le plus petit modele ({snap.model}). Sur ce run, "
            f"{worst0.passed} cas sur {worst0.total} passent."
        ),
        "fields": [
            {"label": "Type", "value": worst0_type},
            {"label": "Categorie", "value": worst0.category},
            {"label": "Version catalogue", "value": snap.catalogue_version},
            {"label": "Statut", "value": "Actif", "tone": "good"},
            {"label": "Derniere execution", "value": stamp},
            {"label": "Modele evalue", "value": snap.model},
            {"label": "Cas", "value": str(worst0.total)},
            {"label": "Langues", "value": lang_str},
            {"label": "Proprietaire", "value": "Tessera Eval"},
        ],
        "results_title": "Resultats (periode)",
        "results_cta": "Modifier la periode",
        "results": [
            {"label": "Score", "value": f"{_comma(worst0.pass_rate * 10)} / 10"},
            {"label": "Taux de reussite", "value": _pct(worst0.pass_rate)},
            {"label": "Cas reussis", "value": f"{worst0.passed} / {worst0.total}"},
            {"label": "Cas echoues", "value": f"{worst0.failed} / {worst0.total}"},
            {"label": "Score global du run", "value": f"{_comma(score10)} / 10"},
            {"label": "Escalades requises", "value": str(snap.escalations)},
            {"label": "Invocations d'outils", "value": str(snap.tool_invocations)},
        ],
        "results_more": "Voir tous les resultats",
        "rbac_title": "Acces RBAC",
        "rbac_cta": "Modifier",
        "rbac": [
            {"role": "ML Engineer", "access": "Lecture"},
            {"role": "Compliance Officer", "access": "Lecture / Ecriture"},
            {"role": "Admin", "access": "Lecture / Ecriture"},
        ],
        "rbac_more": "Voir toutes les permissions (5)",
    }

    return {
        "title": "Evaluations",
        "subtitle": (
            "Mesurez, analysez et ameliorez la qualite des reponses de "
            "l'assistant et des agents."
        ),
        "actions": {"asof": "Voir a date (as-of)", "create": "Creer une evaluation"},
        "subtabs": [
            "Vue d'ensemble",
            "Jeux d'evaluations",
            "Resultats",
            "Dimensions",
            "Comparaisons",
            "Erreurs",
            "Versions & historique",
            "Exports",
        ],
        "snapshot": snapshot,
        "kpis": kpis,
        "filters": filters,
        "table": {
            "columns": columns,
            "rows": rows,
            "count": f"1-{len(rows)} sur {len(rows)} jeux",
            "pages": 1,
        },
        "watch": watch,
        "quick": quick,
        "trend": trend,
        "detail": detail,
    }
