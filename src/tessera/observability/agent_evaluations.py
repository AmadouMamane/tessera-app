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
from typing import TYPE_CHECKING, get_args

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.observability.eval.agent_judge import load_agent_judge
from tessera.observability.eval_data import (
    CATEGORY_LABELS,
    load_agent_or_global_snapshot,
    load_agent_run_history,
)
from tessera.observability.eval_gate_view import GateView, build_gate_view
from tessera.observability.eval_tiers import Tier, load_tier_map
from tessera.observability.eval_waivers import verify_waiver_chain

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


_TIER_TONE: dict[str, str] = {"T0": "crit", "T1": "warn", "T2": "muted"}
_LANG_LABEL: dict[str, str] = {"fr": "FR", "de": "DE", "en": "EN"}


def _critical_cases(gv: GateView, titles: dict[str, str]) -> dict[str, object]:
    """Table of the critical (T0/T1) executions that are NOT conforme.

    One row per ``(case, langue)``: tier, language, gate status and a socle
    marker. Sorted by blocking severity so the existential failures surface
    first. This is the policy's "table cas critiques".
    """
    order = {"bloquant_socle": 0, "non_execute": 1, "bloquant_t1": 2, "deroge_actif": 3}
    crit = [s for s in gv.statuses if s.is_critical and s.status_key != "conforme"]
    crit.sort(key=lambda s: (order.get(s.status_key, 9), s.case_id, s.language))
    tm = load_tier_map()
    rows = [
        {
            "case_id": s.case_id,
            "title": titles.get(s.case_id, s.case_id),
            "tier": s.tier,
            "tier_label": tm.label(s.tier),
            "tier_tone": _TIER_TONE[s.tier],
            "language": _LANG_LABEL.get(s.language, s.language.upper()),
            "status_key": s.status_key,
            "status_label": s.status_label,
            "status_tone": s.status_tone,
            "socle": s.socle,
        }
        for s in crit
    ]
    return {
        "title": "Cas critiques (grain cas x langue)",
        "columns": ["Cas", "Tier", "Langue", "Statut gate", "Socle"],
        "rows": rows,
        "total": len(rows),
    }


def _socle_by_category(gv: GateView) -> list[dict[str, object]]:
    """Per-category socle OK / ÉCHEC markers (no green score may mask a breach)."""
    cats: dict[str, list[bool]] = {}
    for s in gv.statuses:
        if s.socle and s.executed:
            cats.setdefault(s.category or "", []).append(s.passed)
    out: list[dict[str, object]] = []
    for cat, results in sorted(cats.items()):
        passed = sum(1 for r in results if r)
        out.append(
            {
                "category": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "ok": all(results),
                "passed": passed,
                "total": len(results),
            }
        )
    return out


def _venn(gv: GateView) -> dict[str, object]:
    """Structural Venn: tier membership summing to the total (≠ failure count).

    Nested: Critiques (T0/T1) contains the Socle (T0); active derogations are a
    subset of T1, never of the socle (``T0 inter derog = empty``). The disjoint regions
    Socle + T1 + Domaine sum to the total executions.
    """
    t0 = gv.tier_counts.get("T0", 0)
    t1 = gv.tier_counts.get("T1", 0)
    t2 = gv.tier_counts.get("T2", 0)
    return {
        "universe": gv.executions,
        "critiques": t0 + t1,
        "socle": t0,
        "t1": t1,
        "domaine": t2,
        "deroges": gv.waived_active,
        "reconciles": (t0 + t1 + t2) == gv.executions,
        "reconcile_total": gv.executions,
    }


def _waivers_block(gv: GateView) -> dict[str, object]:
    """The active-waiver registry, resolved against the candidate and clock."""
    tm = load_tier_map()
    items: list[dict[str, object]] = []
    for w in gv.waivers:
        e = w.event
        items.append(
            {
                "id": e.event_id,
                "case_id": e.case_id,
                "language": _LANG_LABEL.get(e.language, e.language.upper()),
                "tier": w.tier,
                "tier_label": tm.label(w.tier),
                "status": w.status,
                "status_label": w.status_label,
                "active": w.active,
                "justification": e.justification,
                "requester": e.requester,
                "requester_role": e.requester_role,
                "approver": e.approver,
                "approver_role": e.approver_role,
                "scope": e.scope,
                "controls": list(e.compensating_controls),
                "incident_ref": e.incident_ref,
                "expires_at": e.expires_at[:10],
            }
        )
    # Active first, then by status, then by id.
    items.sort(key=lambda i: (not bool(i["active"]), str(i["status"]), str(i["id"])))
    return {
        "title": "Registre des dérogations",
        "subtitle": "Objets gouvernes S1: RBAC, expiration, controles compensatoires, hash-chaine.",
        "active": gv.waived_active,
        "total": len(items),
        "chain_verified": verify_waiver_chain(),
        "items": items,
    }


def _gate_block(snap: EvalSnapshot) -> dict[str, object]:
    """The release gate verdict + full policy breakdown, at the (case, langue) grain.

    The binding ``eval-gate-policy.md`` primes over the image: the verdict (not
    the aggregate score) is the headline, every critical failure is blocking
    unless lifted by an *active governed waiver*, and Tier 0 (the socle) can
    never be waived. Every count is recomputed from the real run + the versioned
    tiers + the hash-chained waiver store, and all counters reconcile.
    """
    gv = build_gate_view(snap)
    titles = {s.case_id: s.title for s in snap.sessions}
    return {
        # ── compat fields kept for the existing banner ──────────────────────
        "passed": gv.passed,
        "failed_critical": sorted(
            {s.case_id for s in gv.statuses if s.status_key == "bloquant_socle"}
        ),
        "min_pass_rate": gv.min_pass_rate,
        "standard_passed": gv.domain_passed,
        "standard_total": gv.domain_total,
        "label": gv.verdict_label,
        "breakdown": {
            "critical_blocking": gv.blocking_socle + gv.blocking_t1,
            "tier0_non_derogeable": gv.blocking_socle,
            "waived": gv.waived_active,
        },
        # ── policy-correct enrichments ──────────────────────────────────────
        "tone": gv.verdict_tone,
        "reason": gv.verdict_reason,
        "candidate": gv.candidate_version,
        "grains": {
            "executions": gv.executions,
            "distinct_cases": gv.distinct_cases,
            "socle_cases": gv.socle_cases,
        },
        "counts": {"passed": gv.passed_exec, "failed": gv.failed_exec},
        "socle": {"ok": gv.socle_ok, "passed": gv.socle_passed, "total": gv.socle_total},
        "domain": {
            "ok": gv.domain_ok,
            "passed": gv.domain_passed,
            "total": gv.domain_total,
            "rate": round(gv.domain_pass_rate, 4),
            "min": gv.min_pass_rate,
        },
        "breakdown_grain": {
            "blocking_socle": gv.blocking_socle,
            "blocking_t1": gv.blocking_t1,
            "waived_active": gv.waived_active,
            "non_executed_critical": gv.non_executed_critical,
        },
        "tiers": [
            {
                "tier": t,
                "label": load_tier_map().label(t),
                "count": gv.tier_counts.get(t, 0),
                "tone": _TIER_TONE[t],
                "waivable": load_tier_map().waivable(t),
            }
            for t in get_args(Tier)
        ],
        "venn": _venn(gv),
        "socle_by_category": _socle_by_category(gv),
        "critical_cases": _critical_cases(gv, titles),
        "waivers": _waivers_block(gv),
    }


def _judge_block(agent_id: str) -> dict[str, object]:
    """Real per-agent judged metrics (faithfulness/grounding/hallucination)."""
    report = load_agent_judge()
    scores = report.for_agent(agent_id)
    if scores is None:
        return {"available": False}
    return {
        "available": True,
        "judge_model": report.judge_model,
        "context_basis": report.context_basis,
        "faithfulness": scores.faithfulness,
        "grounding": scores.grounding,
        "hallucination": scores.hallucination,
        "n": scores.n,
    }


def _runs_rail(agent_id: str) -> dict[str, object]:
    """ER-01 rail: the agent's run history (which run/scores were current when)."""
    history = load_agent_run_history(agent_id)
    items: list[dict[str, object]] = []
    for entry in history:
        moment = entry.run_datetime()
        items.append(
            {
                "run_at": entry.run_at,
                "label": moment.strftime("%d/%m %H:%M") if moment else entry.run_at,
                "pass_rate": round(entry.pass_rate, 4),
                "score": _dot(entry.pass_rate * 10),
                "gate_passed": entry.gate_passed,
                "eval_set": entry.eval_set,
            }
        )
    return {
        "title": "Historique des runs",
        "subtitle": "Reconstruit quel run et quels scores étaient courants à chaque date.",
        "items": items,
        "count": len(items),
    }


def compute_agent_evaluations(agent_id: str = DEFAULT_AGENT_ID) -> dict[str, object]:
    """Return the Evaluations dashboard payload from this agent's real run.

    Args:
        agent_id: the agent whose own run (over its own curated set) to read; the
            quality figures, judged metrics and run history are all scoped to it.
    """
    snap = load_agent_or_global_snapshot(agent_id)
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
        _kpi(
            "score",
            "Score global",
            _comma(score10),
            "/10",
            score_note,
            score_tone,
            f"{snap.passed}/{snap.total} cas réussis",
            "muted",
        ),
        _kpi(
            "success",
            "Taux de réussite",
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
            "Élevé" if halluc_rate >= _HIGH_HALLUC else "Maîtrisé",
            "bad" if halluc_rate >= _HIGH_HALLUC else "good",
            f"{fact_failed}/{fact_total} sondes factualité",
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
            "Fidélité (sources)",
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
            "tests exécutés",
            "muted",
            f"{len(snap.categories)} catégories - {n_lang} langues",
            "muted",
        ),
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
        "Nom de l'évaluation",
        "Type",
        "Statut",
        "Version",
        "Score global",
        "Taux réussite",
        "Hallucinations",
        "Dernière exécution",
        "Propriétaire",
        "Tests",
    ]
    version_label = snap.catalogue_version[:9] or "v1"
    rows = [
        _row(stat, version_label, stamp)
        for stat in sorted(snap.categories, key=lambda c: (-c.pass_rate, -c.total))
    ]

    worst = snap.categories_by_pass_rate()
    watch_tones = ["crit", "crit", "warn"]
    watch_items = [
        {
            "title": f"{stat.label} - {_pct(stat.pass_rate)} de réussite",
            "detail": f"{stat.passed}/{stat.total} cas - {n_lang} langues",
            "tone": tone,
        }
        for stat, tone in zip(worst[:3], watch_tones, strict=False)
    ]
    n_alert = sum(1 for c in snap.categories if c.pass_rate < _ALERT_PASS_RATE)
    watch: dict[str, object] = {
        "title": "À surveiller",
        "cta": f"Voir toutes les alertes ({n_alert})",
        "cta_href": "/a-traiter",
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
            "Vue d'ensemble",
            "Jeux d'évaluations",
            "Résultats",
            "Dimensions",
            "Comparaisons",
            "Erreurs",
            "Versions & historique",
            "Exports",
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
        "agent_id": snap.agent_id or agent_id,
        "scoped": bool(snap.agent_id),
        "gate": _gate_block(snap),
        "judge": _judge_block(snap.agent_id or agent_id),
        "runs": _runs_rail(snap.agent_id or agent_id),
    }
