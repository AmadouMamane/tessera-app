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

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, get_args

from eval.sets import list_eval_sets
from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.observability.eval.agent_judge import load_agent_judge
from tessera.observability.eval_data import (
    CATEGORY_LABELS,
    load_agent_or_global_snapshot,
    load_agent_run_history,
)
from tessera.observability.eval_floor import grade_against_own_floor
from tessera.observability.eval_gate_view import GateView, build_gate_view
from tessera.observability.eval_tiers import Tier, load_tier_map
from tessera.observability.eval_waivers import verify_waiver_chain

if TYPE_CHECKING:
    from tessera.observability.eval_data import CategoryStat, EvalSnapshot

__all__ = ["compute_agent_evaluations"]

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


# Presentation-layer translation of the FR labels emitted by the (shared,
# FR-authored) eval-gate subsystem (gate view / tiers / waivers). Translating
# here keeps the gate view's other callers (release_control, agent_release)
# untouched. Unmapped strings fall through verbatim.
_GATE_TR: dict[str, tuple[str, str]] = {
    # gate-status labels (eval_gate_view._STATUS_LABEL)
    "Conforme": ("Konform", "Compliant"),
    "Bloquant · socle (T0)": ("Blockierend · Sockel (T0)", "Blocking · core (T0)"),
    "Bloquant · critique (T1)": ("Blockierend · kritisch (T1)", "Blocking · critical (T1)"),
    "Dérogé actif": ("Aktive Ausnahme", "Active waiver"),
    "Échec · domaine (T2, non bloquant)": (
        "Fehler · Domaene (T2, nicht blockierend)",
        "Failure · domain (T2, non-blocking)",
    ),
    "Non exécuté": ("Nicht ausgefuehrt", "Not executed"),
    # tier labels (eval_tiers._TIER_LABEL)
    "Cœur non-dérogeable": ("Nicht ausnehmbarer Kern", "Non-waivable core"),
    "Critique dérogeable": ("Ausnehmbar kritisch", "Waivable critical"),
    "Domaine gradé": ("Gradierte Domaene", "Graded domain"),
    # verdict labels (eval_gate_view._verdict). "BLOQUÉ (domaine)" is gone with the bar
    # that produced it (ADR 0021): no domain rate can block a release any more.
    "BLOQUÉ par le socle": ("DURCH SOCKEL BLOCKIERT", "BLOCKED by core"),
    "BLOQUÉ (critiques non dérogés)": (
        "BLOCKIERT (kritische ohne Ausnahme)",
        "BLOCKED (unwaived critical)",
    ),
    "PASSE": ("BESTANDEN", "PASS"),
    # verdict reasons (static variants)
    "Un cas du socle dur (T0) a échoué ou n'a pas été exécuté.": (
        "Ein Fall des harten Sockels (T0) ist fehlgeschlagen oder wurde nicht ausgefuehrt.",
        "A hard-core (T0) case failed or was not executed.",
    ),
    "Un cas critique n'a pas été exécuté (absence de preuve = bloquant).": (
        "Ein kritischer Fall wurde nicht ausgefuehrt (kein Nachweis = blockierend).",
        "A critical case was not executed (no evidence = blocking).",
    ),
    "Socle intact, aucun critique non dérogé, aucun critique non exécuté.": (
        "Sockel intakt, kein kritischer ohne Ausnahme, kein kritischer nicht ausgefuehrt.",
        "Core intact, no unwaived critical, no critical left unexecuted.",
    ),
    # waiver status labels (eval_waivers._STATUS_LABEL)
    "Dérogation active": ("Aktive Ausnahme", "Active waiver"),
    "Expirée — re-blocage auto": ("Abgelaufen — Auto-Wiedersperrung", "Expired — auto re-block"),
    "Révoquée": ("Widerrufen", "Revoked"),
    "Sans effet (cœur non-dérogeable)": (
        "Wirkungslos (nicht ausnehmbarer Kern)",
        "No effect (non-waivable core)",
    ),
    "Liée à un autre candidat": ("An anderen Kandidaten gebunden", "Linked to another candidate"),
}


def _gate(label: str, lang: str) -> str:
    """Translate an eval-gate subsystem FR label for display (de/en)."""
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return label
    pair = _GATE_TR.get(label)
    return pair[idx - 1] if pair else label


def _gate_reason(reason: str, lang: str) -> str:
    """Translate a gate verdict reason, including the interpolated T1 variant."""
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return reason
    marker = "cas critique(s) dérogeable(s) (T1) en échec sans dérogation active."
    if marker in reason:
        n = reason.split(" ", 1)[0]
        de = (
            f"{n} ausnehmbare(r) kritische(r) Fall/Faelle (T1) "
            "ohne aktive Ausnahme fehlgeschlagen."
        )
        en = f"{n} waivable critical (T1) case(s) failed without an active waiver."
        return _loc(lang, reason, de, en)
    return _gate(reason, lang)


# Map each failure-catalogue category to a display "type" + tone key used by the
# evaluations table. Tone keys (sys/tpl/agt) are the ones the frontend styles.
# The display label is localized via ``_group_label`` (the tone key is stable).
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

# Localized display labels for the _GROUP type names (the FR value is the key).
_GROUP_TR: dict[str, tuple[str, str]] = {
    "Sécurité": ("Sicherheit", "Security"),
    "Confidentialité": ("Vertraulichkeit", "Privacy"),
    "Politiques": ("Richtlinien", "Policies"),
    "Conformité": ("Konformitaet", "Compliance"),
    "Factualité": ("Faktentreue", "Factuality"),
    "Multilingue": ("Mehrsprachig", "Multilingual"),
    "Agent": ("Agent", "Agent"),
    "Autre": ("Andere", "Other"),
}


def _group_label(category: str, lang: str) -> tuple[str, str]:
    """Return (localized type label, stable tone key) for a category."""
    label, tone = _GROUP.get(category, ("Autre", "sys"))
    idx = _LANG_IDX.get(lang, 0)
    if idx > 0:
        pair = _GROUP_TR.get(label)
        if pair:
            label = pair[idx - 1]
    return label, tone


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


def _quality_note(score10: float, lang: str = "fr") -> tuple[str, str]:
    if score10 >= _GOOD_SCORE:
        return _loc(lang, "Bon", "Gut", "Good"), "good"
    if score10 >= _OK_SCORE:
        return _loc(lang, "Moyen", "Mittel", "Medium"), "warn"
    return _loc(lang, "Faible", "Schwach", "Weak"), "bad"


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


def _row(stat: CategoryStat, version_label: str, stamp: str, lang: str) -> dict[str, object]:
    """A self-describing evaluation-set row (display cells + raw keys for the detail)."""
    type_label, type_tone = _group_label(stat.category, lang)
    is_fact = stat.category in _FACTUAL
    quality, quality_tone = _quality_note(stat.pass_rate * 10, lang)
    return {
        "name": stat.label,
        "type": type_label,
        "type_tone": type_tone,
        "status": _loc(lang, "Actif", "Aktiv", "Active"),
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


def _run_labels(snap: EvalSnapshot, lang: str = "fr") -> tuple[str, str]:
    """Return (formatted timestamp, relative age) for the run."""
    moment = snap.run_datetime()
    if moment is None:
        return snap.run_at, ""
    stamp = moment.strftime("%d/%m/%Y %H:%M")
    days = (date.today() - moment.date()).days
    if days <= 0:
        rel = _loc(lang, "aujourd'hui", "heute", "today")
    elif days == 1:
        rel = _loc(lang, "hier", "gestern", "yesterday")
    else:
        rel = _loc(lang, f"il y a {days} j", f"vor {days} T", f"{days}d ago")
    return stamp, rel


_TIER_TONE: dict[str, str] = {"T0": "crit", "T1": "warn", "T2": "muted"}
_LANG_LABEL: dict[str, str] = {"fr": "FR", "de": "DE", "en": "EN"}


def _critical_cases(gv: GateView, titles: dict[str, str], lang: str) -> dict[str, object]:
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
            "tier_label": _gate(tm.label(s.tier), lang),
            "tier_tone": _TIER_TONE[s.tier],
            "language": _LANG_LABEL.get(s.language, s.language.upper()),
            "status_key": s.status_key,
            "status_label": _gate(s.status_label, lang),
            "status_tone": s.status_tone,
            "socle": s.socle,
        }
        for s in crit
    ]
    return {
        "title": _loc(
            lang,
            "Cas critiques (grain cas x langue)",
            "Kritische Faelle (Grain Fall x Sprache)",
            "Critical cases (case x language grain)",
        ),
        "columns": [
            _loc(lang, "Cas", "Fall", "Case"),
            _loc(lang, "Tier", "Tier", "Tier"),
            _loc(lang, "Langue", "Sprache", "Language"),
            _loc(lang, "Statut gate", "Gate-Status", "Gate status"),
            _loc(lang, "Socle", "Sockel", "Core"),
        ],
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


def _waivers_block(gv: GateView, lang: str) -> dict[str, object]:
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
                "tier_label": _gate(tm.label(w.tier), lang),
                "status": w.status,
                "status_label": _gate(w.status_label, lang),
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
        "title": _loc(lang, "Registre des dérogations", "Ausnahmenregister", "Waiver registry"),
        "subtitle": _loc(
            lang,
            "Objets gouvernes S1: RBAC, expiration, controles compensatoires, hash-chaine.",
            "S1-gesteuerte Objekte: RBAC, Ablauf, kompensierende Kontrollen, Hash-Kette.",
            "S1-governed objects: RBAC, expiry, compensating controls, hash-chain.",
        ),
        "active": gv.waived_active,
        "total": len(items),
        "chain_verified": verify_waiver_chain(),
        "items": items,
    }


def _gate_block(snap: EvalSnapshot, lang: str) -> dict[str, object]:
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
        "standard_passed": gv.domain_passed,
        "standard_total": gv.domain_total,
        "label": _gate(gv.verdict_label, lang),
        "breakdown": {
            "critical_blocking": gv.blocking_socle + gv.blocking_t1,
            "tier0_non_derogeable": gv.blocking_socle,
            "waived": gv.waived_active,
        },
        # ── policy-correct enrichments ──────────────────────────────────────
        "tone": gv.verdict_tone,
        "reason": _gate_reason(gv.verdict_reason, lang),
        "candidate": gv.candidate_version,
        "grains": {
            "executions": gv.executions,
            "distinct_cases": gv.distinct_cases,
            "socle_cases": gv.socle_cases,
        },
        "counts": {"passed": gv.passed_exec, "failed": gv.failed_exec},
        "socle": {"ok": gv.socle_ok, "passed": gv.socle_passed, "total": gv.socle_total},
        # T2: a measurement. No `ok`, no `min` — there is no bar (ADR 0021), and the page
        # must not print one. `gating: False` says so on the wire rather than by omission.
        "domain": {
            "passed": gv.domain_passed,
            "total": gv.domain_total,
            "rate": round(gv.domain_pass_rate, 4),
            "gating": False,
        },
        "contribution": _contribution_block(snap, lang),
        "breakdown_grain": {
            "blocking_socle": gv.blocking_socle,
            "blocking_t1": gv.blocking_t1,
            "waived_active": gv.waived_active,
            "non_executed_critical": gv.non_executed_critical,
        },
        "tiers": [
            {
                "tier": t,
                "label": _gate(load_tier_map().label(t), lang),
                "count": gv.tier_counts.get(t, 0),
                "tone": _TIER_TONE[t],
                "waivable": load_tier_map().waivable(t),
            }
            for t in get_args(Tier)
        ],
        "venn": _venn(gv),
        "socle_by_category": _socle_by_category(gv),
        "critical_cases": _critical_cases(gv, titles, lang),
        "waivers": _waivers_block(gv, lang),
    }


def _contribution_block(snap: EvalSnapshot, lang: str) -> dict[str, object]:
    """What the model EARNED over this set's own null floor — the bar's replacement.

    ADR 0021 removed the absolute domain bar and put nothing decorative in its place.
    What the page prints instead is measured end to end: the set's floor is the committed
    null control (``eval/baselines/null-control.json``) restricted to the set's own cases,
    and the two numbers shown are the model's delta over it — the runs it BREAKS that the
    agent passes with no model at all (rule 1), and the runs it CLOSES that the floor
    fails (rule 2). No threshold appears, because none exists.

    Three honesty guards, all load-bearing:

    * **A modelless run is not a good one.** The report's ``model`` field is written even
      when every backend was unreachable, so it proves nothing; generated tokens do. A run
      with zero output tokens contributed nothing and broke nothing, and reporting "0
      regressions" for it would read as a clean bill of health. It degrades instead.
    * **The cockpit cannot reproduce a break.** Sampling is stochastic, and ADR 0021 only
      counts a regression once replayed — which needs the model. So a break is surfaced
      here as a *candidate*, with the command that settles it, and never as a confirmed
      regression the page has no standing to declare.
    * **A floor that does not apply grades nothing.** Every figure below is a count against
      a population read off the committed null control, so if this set's cases have moved
      since it was captured, the counts are of runs that no longer exist. The gate refuses
      (``verdict.refusal``) and the tile degrades — because a refusal rendered as
      "contribution 0/0" would read as a measured zero, which is the one thing worse than
      showing nothing.
    """
    # ONE grader, shared with `agent_lifecycle.release_decision` — this tile and the Release
    # button that sits beside it in the same component must read the same floor. They did
    # not: the tile computed the contribution and the button ignored it entirely, so an
    # agent could be SHOWN breaking a case the guard closes unaided and be released anyway.
    # Two implementations of "the floor" is how they drifted; there is now only one.
    grade = grade_against_own_floor(snap)
    if not grade.graded:
        # Honest-empty (0015): no floor applies to this run — no eval set, no model that
        # spoke, or a floor whose cases have moved. A refusal must never render as a grade
        # of zero, because "contribution 0/0" reads as a measured, clean tile. Degrade, and
        # say why. (The release decision blocks on this same fact — an ungraded model is not
        # a cleared one.)
        return {"available": False, "refusal": grade.obstacle}
    verdict = grade.verdict
    assert verdict is not None

    return {
        "available": True,
        "title": _loc(
            lang,
            "Contribution du modèle (au-dessus du plancher du set)",
            "Modellbeitrag (ueber dem Sockelwert des Sets)",
            "Model contribution (over the set's own floor)",
        ),
        "model": snap.model,
        # The set's own measured floor — the bar, and it was never chosen.
        "floor_passed": grade.floor_passed,
        "floor_total": grade.floor_total,
        # Rule 1: runs the floor passes and this run breaks. CANDIDATES — see the docstring.
        "regression_candidates": list(verdict.confirmed_breaks),
        # Rule 2: of the runs the floor fails, how many the model closes. Measured, ungated.
        "contribution": verdict.contribution,
        "contribution_population": verdict.contribution_population,
        "gated": False,
        "note": _loc(
            lang,
            "Aucun seuil : la barre est le plancher mesuré de ce set (null control), "
            "jamais un nombre choisi. Une régression n'est acquise qu'une fois REJOUÉE — "
            "le cockpit ne peut pas rejouer : scripts/check_contribution.py tranche.",
            "Keine Schwelle: die Messlatte ist der gemessene Sockelwert dieses Sets "
            "(Null-Kontrolle), nie eine gewaehlte Zahl. Eine Regression zaehlt erst nach "
            "WIEDERHOLUNG — das Cockpit kann nicht wiederholen: "
            "scripts/check_contribution.py entscheidet.",
            "No threshold: the bar is this set's measured floor (the null control), never "
            "a chosen number. A regression only counts once REPLAYED — the cockpit cannot "
            "replay: scripts/check_contribution.py settles it.",
        ),
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


_INTENT_BENCH_DIR = Path(__file__).resolve().parents[3] / "eval" / "reports" / "intent_bench"


def _latest_intent_bench(agent_id: str) -> dict[str, object] | None:
    """The agent's most recent published intent-bench report, by its own run stamp."""
    try:
        candidates = sorted(_INTENT_BENCH_DIR.glob("*.json"))
    except OSError:
        return None
    latest: dict[str, object] | None = None
    latest_run = ""
    for path in candidates:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(report, dict) or report.get("agent_id") != agent_id:
            continue
        run_at = str(report.get("run_at") or "")
        if run_at >= latest_run:
            latest, latest_run = report, run_at
    return latest


def _understanding_bench_block(agent_id: str, lang: str) -> dict[str, object] | None:
    """The reading layer's EVALUATION plane (ADR 0053 §7): the latest published intent bench.

    Distinct on purpose from the continuous counts the quality band and the Métier card
    carry (suivi continu vs évaluation — operator rule, 2026-08-24): the bench is measured
    against the labeled referent (human ground truth), so this is where a rate is honest —
    its denominator is the referent's own case count, stamped with the run instant, the
    referent's sha and the measured model. ``None`` when no full report (regex + llm
    columns) was published for the agent: publication is a deliberate act (the bench's
    ``--report`` flag), so the section does not exist rather than showing an invented zero.
    """
    latest = _latest_intent_bench(agent_id)
    if latest is None:
        return None
    columns = latest.get("columns")
    if not isinstance(columns, dict):
        return None
    regex_column = columns.get("regex")
    llm_column = columns.get("llm")
    if not isinstance(regex_column, dict) or not isinstance(llm_column, dict):
        return None

    def pct(value: float) -> str:
        text = f"{value * 100:.1f}"
        return (text if lang == "en" else text.replace(".", ",")) + " %"

    def seconds(ms: float) -> str:
        return _dot(ms / 1000) if lang == "en" else _comma(ms / 1000)

    def score(block: object) -> tuple[str, float] | None:
        if not isinstance(block, dict):
            return None
        correct, n = int(block.get("correct", 0)), int(block.get("n", 0))
        return f"{correct}/{n}", float(block.get("accuracy", 0.0))

    regex_overall = score(regex_column.get("overall"))
    llm_overall = score(llm_column.get("overall"))
    composite = score(llm_column.get("with_regex_fallback"))
    if regex_overall is None or llm_overall is None or composite is None:
        return None
    models = llm_column.get("models")
    model = str(models[0]) if isinstance(models, list) and models else ""
    run_at = str(latest.get("run_at") or "")
    try:
        run_dt = datetime.fromisoformat(run_at)
        stamp = run_dt.strftime("%Y-%m-%d %H:%M" if lang == "en" else "%d/%m/%Y %H:%M")
    except ValueError:
        stamp = run_at
    sha = str(latest.get("set_sha256") or "")[:8]
    set_version = str(latest.get("set_version") or "")
    referent = f"{set_version} — " + str(regex_column.get("overall", {}).get("n", ""))
    rows = [
        {
            "label": _loc(
                lang,
                "Détection par mots-clés (repli)",
                "Stichworterkennung (Rückfall)",
                "Keyword detection (fallback)",
            ),
            "value": f"{regex_overall[0]} — {pct(regex_overall[1])}",
            # Explicit None, not an absent key: the response model serialises the field,
            # and the byte-parity witness compares what is SERVED, key for key.
            "tone": None,
        },
        {
            "label": _loc(lang, "Modèle seul", "Modell allein", "Model alone"),
            "value": f"{llm_overall[0]} — {pct(llm_overall[1])}",
            "tone": None,
        },
        {
            "label": _loc(
                lang,
                "Servi — modèle avec repli",
                "Serviert — Modell mit Rückfall",
                "Served — model with fallback",
            ),
            "value": f"{composite[0]} — {pct(composite[1])}",
            "tone": "served",
        },
    ]
    per_language: list[str] = []
    by_language = llm_column.get("by_language")
    if isinstance(by_language, dict):
        for code in ("fr", "en", "de"):
            cell = score(by_language.get(code))
            if cell is not None:
                per_language.append(f"{code.upper()} {cell[0]}")
    languages = _loc(
        lang,
        f"par langue (modèle seul) : {' · '.join(per_language)}",
        f"nach Sprache (Modell allein): {' · '.join(per_language)}",
        f"by language (model alone): {' · '.join(per_language)}",
    )
    latency_block = llm_column.get("latency_ms")
    latency = ""
    if isinstance(latency_block, dict) and latency_block.get("p50") is not None:
        p50 = seconds(float(latency_block["p50"]))
        peak = seconds(float(latency_block.get("max", 0.0)))
        latency = _loc(
            lang,
            f"lecture du texte au banc : {p50} s en médiane · max {peak} s",
            f"Lesen des Textes im Prüfstand: {p50} s im Median · max {peak} s",
            f"text reading on the bench: median {p50} s · max {peak} s",
        )
    return {
        "title": _loc(
            lang,
            "Banc d'essai — lecture des demandes",
            "Prüfstand — Lesen der Anfragen",
            "Test bench — request reading",
        ),
        "note": _loc(
            lang,
            "Chaque lecture est comparée à une étiquette posée par un humain ; "
            "le chiffre servi est celui du modèle avec repli mots-clés.",
            "Jede Lesart wird mit einem menschlich gesetzten Etikett verglichen; "
            "die servierte Zahl ist das Modell mit Stichwort-Rückfall.",
            "Each reading is compared to a human-set label; "
            "the served figure is the model with keyword fallback.",
        ),
        "meta": _loc(
            lang,
            f"Exécuté le {stamp} · référent {referent} cas (sha {sha}) · {model}",
            f"Ausgeführt am {stamp} · Referent {referent} Fälle (sha {sha}) · {model}",
            f"Run {stamp} · referent {referent} cases (sha {sha}) · {model}",
        ),
        "rows": rows,
        "languages": languages,
        "latency": latency,
    }


def _runs_rail(agent_id: str, lang: str) -> dict[str, object]:
    """ER-01 rail payload: the agent's eval-run journal (S3), one point per run.

    Each item carries its own stored provenance — run date + catalogue version +
    model (eval-gate-policy § provenance: never a single "dernière éval" that
    masks the staggering between agents) — and the gate verdict *recorded at run
    time* (``None`` = not recorded, said as such, never recomputed against
    today's waivers). ``delta_pass_rate`` is the one derived figure: pass-rate
    delta vs the previous run, present only when a previous run exists AND was
    scored against the same catalogue version — a cross-catalogue delta would
    compare two different exams.
    """
    history = load_agent_run_history(agent_id)
    items: list[dict[str, object]] = []
    for idx, entry in enumerate(history):
        moment = entry.run_datetime()
        previous = history[idx + 1] if idx + 1 < len(history) else None
        delta: float | None = None
        if (
            previous is not None
            and previous.total > 0
            and entry.total > 0
            and previous.catalogue_version == entry.catalogue_version
        ):
            delta = round(entry.pass_rate - previous.pass_rate, 4)
        items.append(
            {
                "run_at": entry.run_at,
                "label": moment.strftime("%d/%m %H:%M") if moment else entry.run_at,
                "date_label": moment.strftime("%d/%m") if moment else entry.run_at,
                "pass_rate": round(entry.pass_rate, 4),
                "score": _dot(entry.pass_rate * 10),
                "passed": entry.passed,
                "total": entry.total,
                "gate_passed": entry.gate_passed,
                "eval_set": entry.eval_set,
                "catalogue_version": entry.catalogue_version,
                "model": entry.model,
                "delta_pass_rate": delta,
            }
        )
    return {
        "title": _loc(
            lang,
            "Historique des runs d'évaluation",
            "Verlauf der Evaluierungslaeufe",
            "Evaluation run history",
        ),
        "subtitle": _loc(
            lang,
            "Chaque point est un run : date, version de catalogue, taux, verdict gate.",
            "Jeder Punkt ist ein Lauf: Datum, Katalogversion, Rate, Gate-Urteil.",
            "Each point is a run: date, catalogue version, rate, gate verdict.",
        ),
        "empty_label": _loc(
            lang,
            "Éval non exécutée — aucun run d'évaluation enregistré pour cet agent.",
            "Evaluierung nicht ausgefuehrt — kein Evaluierungslauf fuer diesen Agenten "
            "aufgezeichnet.",
            "Eval not executed — no evaluation run recorded for this agent.",
        ),
        "items": items,
        "count": len(items),
    }


_FAILURES_DIR = Path(__file__).resolve().parents[3] / "eval" / "failures"
_RESPONSE_SNIPPET = 320
_MS_PER_S = 1000


@lru_cache(maxsize=1)
def _catalogue_cases() -> dict[str, dict[str, object]]:
    """Failure-case metadata keyed by id, read once from ``eval/failures/``.

    The run reports carry no user prompt, so the question text for the Results /
    Errors views is joined from here (``prompts.<lang>.user``). Titles, severity,
    categories, tags and the source citation are the case's own reference data.
    """
    cases: dict[str, dict[str, object]] = {}
    for path in sorted(_FAILURES_DIR.glob("[0-9][0-9]*_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        raw_prompts = payload.get("prompts")
        prompts = raw_prompts if isinstance(raw_prompts, dict) else {}
        questions = {
            str(code): str(bundle.get("user", ""))
            for code, bundle in prompts.items()
            if isinstance(bundle, dict)
        }
        ref = payload.get("source_reference")
        citation = str(ref.get("citation", "")) if isinstance(ref, dict) else ""
        cases[path.stem] = {
            "id": path.stem,
            "title": str(payload.get("title", path.stem)),
            "category": str(payload.get("category", "")),
            "severity": str(payload.get("severity", "standard")),
            "languages": [x for x in payload.get("languages", []) if isinstance(x, str)],
            "tags": [x for x in payload.get("tags", []) if isinstance(x, str)],
            "expected_behavior": str(payload.get("expected_behavior", "")),
            "citation": citation,
            "questions": questions,
        }
    return cases


def _severity_label(severity: str, lang: str) -> tuple[str, str]:
    """(localized label, stable tone key) for a case severity."""
    if severity == "critical":
        return _loc(lang, "Critique", "Kritisch", "Critical"), "crit"
    return _loc(lang, "Standard", "Standard", "Standard"), "muted"


def _snippet(text: str, limit: int) -> str:
    """Collapse whitespace and cap to ``limit`` chars with an ellipsis."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "…"


def _oneline(text: str) -> str:
    """Collapse whitespace; never truncate.

    The question is a short identifier shown clipped with a hover reveal, so it
    must carry its FULL text — a baked cut would make the reveal show the same
    clipped string. The response body keeps :func:`_snippet` (preview + detail).
    """
    return " ".join(text.split())


def _duration_label(ms: float, lang: str) -> str:
    """Human latency: '12 ms' / '1,2 s' / '-' when untimed."""
    del lang  # numeric format is locale-neutral here (comma decimal for seconds)
    if ms <= 0:
        return "-"
    if ms >= _MS_PER_S:
        return f"{_comma(ms / _MS_PER_S)} s"
    return f"{round(ms)} ms"


def _sets_block(snap: EvalSnapshot, lang: str) -> dict[str, object]:
    """'Jeux d'évaluations': every curated eval set + the case catalogue.

    Real source: ``eval/sets/*.json`` (the curated manifests an agent binds)
    joined with ``eval/failures/*.json`` (case metadata). Set names/descriptions
    are the manifests' own authored text; the chrome is localized. The active set
    is the one THIS agent's run was scored on (``snap.eval_set``).
    """
    cases = _catalogue_cases()
    active_slug = snap.eval_set
    rows: list[dict[str, object]] = []
    for eval_set in list_eval_sets():
        effective = eval_set.effective_case_ids
        known = [cases[c] for c in effective if c in cases]
        cats = {str(m["category"]) for m in known}
        crit = sum(1 for m in known if m["severity"] == "critical")
        lang_codes: set[str] = set()
        for meta in known:
            questions = meta["questions"]
            if isinstance(questions, dict):
                lang_codes.update(str(code) for code in questions)
        rows.append(
            {
                "slug": eval_set.slug,
                "name": eval_set.name,
                "description": eval_set.description,
                "agent_id": eval_set.agent_id,
                "bound": bool(eval_set.agent_id),
                "active": bool(active_slug) and eval_set.slug == active_slug,
                "case_count": len(effective),
                "declared_count": len(eval_set.case_ids),
                "floor_count": len(effective) - len(eval_set.case_ids),
                "critical_count": crit,
                "standard_count": len(known) - crit,
                "category_count": len(cats),
                "languages": sorted(lang_codes),
                "gate_rationale": eval_set.gate.rationale,
                "case_ids": list(effective),
            }
        )
    case_rows: list[dict[str, object]] = []
    for cid, meta in cases.items():
        sev_label, sev_tone = _severity_label(str(meta["severity"]), lang)
        cat_label, cat_tone = _group_label(str(meta["category"]), lang)
        case_rows.append(
            {
                "id": cid,
                "title": meta["title"],
                "category": meta["category"],
                "category_label": cat_label,
                "category_tone": cat_tone,
                "severity": meta["severity"],
                "severity_label": sev_label,
                "severity_tone": sev_tone,
                "languages": meta["languages"],
                "tags": meta["tags"],
                "citation": meta["citation"],
            }
        )
    return {
        "title": _loc(lang, "Jeux d'évaluations", "Evaluierungssets", "Evaluation sets"),
        "subtitle": _loc(
            lang,
            "Les jeux curés que les agents bindent - sous-ensembles du catalogue d'échecs.",
            "Die kuratierten Sets, die Agenten binden - Teilmengen des Fehlerkatalogs.",
            "The curated sets agents bind - subsets of the failure catalogue.",
        ),
        "columns": [
            _loc(lang, "Jeu", "Set", "Set"),
            _loc(lang, "Portée", "Geltungsbereich", "Scope"),
            _loc(lang, "Cas", "Faelle", "Cases"),
            _loc(lang, "Critiques", "Kritische", "Critical"),
            _loc(lang, "Catégories", "Kategorien", "Categories"),
            _loc(lang, "Langues", "Sprachen", "Languages"),
        ],
        "case_columns": [
            _loc(lang, "Cas", "Fall", "Case"),
            _loc(lang, "Type", "Typ", "Type"),
            _loc(lang, "Sévérité", "Schweregrad", "Severity"),
            _loc(lang, "Langues", "Sprachen", "Languages"),
        ],
        "rows": rows,
        "cases": case_rows,
        "total": len(rows),
        "active_slug": active_slug,
        "empty_label": _loc(
            lang,
            "Aucun jeu d'évaluations défini.",
            "Kein Evaluierungsset definiert.",
            "No evaluation set defined.",
        ),
        "cases_label": _loc(lang, "Cas du jeu", "Faelle des Sets", "Set cases"),
        "bound_label": _loc(lang, "Lié à un agent", "An Agent gebunden", "Agent-bound"),
        "shared_label": _loc(lang, "Partagé / global", "Geteilt / global", "Shared / global"),
        "active_label": _loc(
            lang, "Jeu actif (run courant)", "Aktives Set (akt. Lauf)", "Active set (current run)"
        ),
        "rationale_label": _loc(lang, "Barre de gate", "Gate-Schwelle", "Gate bar"),
        "floor_note": _loc(
            lang,
            "dont socle de sécurité injecté",
            "davon injizierter Sicherheitssockel",
            "incl. injected security floor",
        ),
    }


def _results_block(snap: EvalSnapshot, lang: str) -> dict[str, object]:
    """'Résultats' / 'Erreurs': the run's per-case outcomes (``snap.sessions``).

    Each session is one case x language execution. The user prompt is joined from
    the case catalogue (the reports store only the answer); the grader's
    ``reasons`` explain a pass/fail verbatim. Responses/questions are snippeted.
    """
    cases = _catalogue_cases()
    rows: list[dict[str, object]] = []
    for session in snap.sessions:
        meta = cases.get(session.case_id)
        question = ""
        title = session.title or session.case_id
        if meta is not None:
            questions = meta.get("questions")
            if isinstance(questions, dict):
                question = str(questions.get(session.language, ""))
            if not session.title:
                title = str(meta.get("title", "")) or session.case_id
        cat_label, cat_tone = _group_label(session.category, lang)
        rows.append(
            {
                "case_id": session.case_id,
                "title": title,
                "language": session.language,
                "category": session.category,
                "category_label": cat_label,
                "category_tone": cat_tone,
                "passed": session.passed,
                "status_label": _loc(lang, "Réussi", "Bestanden", "Passed")
                if session.passed
                else _loc(lang, "Échoué", "Fehlgeschlagen", "Failed"),
                "status_tone": "good" if session.passed else "bad",
                "escalated": session.needs_escalation,
                "tools": list(session.tools),
                "tool_count": len(session.tools),
                "duration_ms": round(session.duration_ms, 3),
                "duration_label": _duration_label(session.duration_ms, lang),
                "input_tokens": session.input_tokens,
                "output_tokens": session.output_tokens,
                "total_tokens": session.total_tokens,
                "question": _oneline(question),
                "response": _snippet(session.response, _RESPONSE_SNIPPET),
                "reasons": list(session.reasons),
                "started_at": session.started_at,
            }
        )
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    escalated = sum(1 for r in rows if r["escalated"])
    return {
        "title": _loc(lang, "Résultats du run", "Ergebnisse des Laufs", "Run results"),
        "subtitle": _loc(
            lang,
            "Un résultat par cas x langue exécuté sur ce run.",
            "Ein Ergebnis pro Fall x Sprache in diesem Lauf.",
            "One result per case x language executed in this run.",
        ),
        "columns": [
            _loc(lang, "Cas", "Fall", "Case"),
            _loc(lang, "Type", "Typ", "Type"),
            _loc(lang, "Langue", "Sprache", "Language"),
            _loc(lang, "Statut", "Status", "Status"),
            _loc(lang, "Latence", "Latenz", "Latency"),
            _loc(lang, "Outils", "Tools", "Tools"),
        ],
        "rows": rows,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "escalated": escalated,
        "errors_title": _loc(lang, "Cas en échec", "Fehlgeschlagene Faelle", "Failed cases"),
        "errors_subtitle": _loc(
            lang,
            "Chaque échec porte le diagnostic du juge - pourquoi il a échoué.",
            "Jeder Fehler traegt die Diagnose des Richters - warum er fehlschlug.",
            "Each failure carries the judge's diagnostic - why it failed.",
        ),
        "empty_results": _loc(
            lang,
            "Aucun résultat - éval non exécutée pour cet agent.",
            "Keine Ergebnisse - Evaluierung nicht ausgefuehrt.",
            "No results - eval not executed for this agent.",
        ),
        "empty_errors": _loc(
            lang,
            "Aucun cas en échec sur ce run.",
            "Keine fehlgeschlagenen Faelle in diesem Lauf.",
            "No failed cases in this run.",
        ),
        "labels": {
            "question": _loc(lang, "Requête de test", "Testanfrage", "Test query"),
            "response": _loc(lang, "Réponse du modèle", "Modellantwort", "Model response"),
            "diagnostic": _loc(
                lang, "Diagnostic du juge", "Diagnose des Richters", "Judge diagnostic"
            ),
            "tools": _loc(lang, "Outils invoqués", "Aufgerufene Tools", "Invoked tools"),
            "no_tools": _loc(lang, "Aucun outil invoqué", "Keine Tools aufgerufen", "No tools"),
            "escalated": _loc(
                lang, "Escalade requise", "Eskalation erforderlich", "Escalation required"
            ),
            "tokens": _loc(
                lang, "Jetons (entrée / sortie)", "Tokens (Ein / Aus)", "Tokens (in / out)"
            ),
            "started": _loc(lang, "Exécuté", "Ausgefuehrt", "Executed"),
            "no_question": _loc(
                lang, "Requête indisponible", "Anfrage nicht verfuegbar", "Query unavailable"
            ),
        },
    }


def compute_agent_evaluations(
    agent_id: str = DEFAULT_AGENT_ID, lang: str = "fr"
) -> dict[str, object]:
    """Return the Evaluations dashboard payload from this agent's real run.

    Args:
        agent_id: the agent whose own run (over its own curated set) to read; the
            quality figures, judged metrics and run history are all scoped to it.
        lang: locale (fr / de / en) for the chrome and the eval-gate labels;
            category names and the real Q/A data stay verbatim.
    """
    snap = load_agent_or_global_snapshot(agent_id)
    stamp, rel = _run_labels(snap, lang)
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
        "tag": _loc(lang, "SNAPSHOT ACTIF", "AKTIVER SNAPSHOT", "ACTIVE SNAPSHOT"),
        "label": _loc(
            lang,
            f"Catalogue d'échecs - {snap.model}",
            f"Fehlerkatalog - {snap.model}",
            f"Failure catalogue - {snap.model}",
        ),
        "updated_label": _loc(lang, "Dernière exécution", "Letzte Ausfuehrung", "Last run"),
        "updated": stamp,
        "updated_rel": rel,
        "version_label": _loc(lang, "Modèle évalué", "Evaluiertes Modell", "Evaluated model"),
        "version": snap.model,
        "version_status": "On-prem",
        "evalset_label": _loc(lang, "Jeu d'évaluations", "Evaluierungsset", "Evaluation set"),
        "evalset": _loc(lang, f"{snap.total} cas", f"{snap.total} Faelle", f"{snap.total} cases"),
        "coverage_label": _loc(lang, "Couverture", "Abdeckung", "Coverage"),
        "coverage": 100,
        "coverage_tone": _loc(lang, "Complète", "Vollstaendig", "Complete"),
        "asof": _loc(lang, "Voir à date", "Stand anzeigen", "View as-of"),
        "compare": _loc(
            lang,
            "Comparer au snapshot précédent",
            "Mit vorherigem Snapshot vergleichen",
            "Compare to previous snapshot",
        ),
    }

    score_note, score_tone = _quality_note(score10, lang)
    kpis: list[dict[str, object]] = [
        _kpi(
            "score",
            _loc(lang, "Score global", "Gesamtscore", "Global score"),
            _comma(score10),
            "/10",
            score_note,
            score_tone,
            _loc(
                lang,
                f"{snap.passed}/{snap.total} cas réussis",
                f"{snap.passed}/{snap.total} bestandene Faelle",
                f"{snap.passed}/{snap.total} cases passed",
            ),
            "muted",
        ),
        _kpi(
            "success",
            _loc(lang, "Taux de réussite", "Erfolgsrate", "Pass rate"),
            "",
            "",
            score_note,
            score_tone,
            _loc(
                lang,
                f"{snap.passed}/{snap.total} cas",
                f"{snap.passed}/{snap.total} Faelle",
                f"{snap.passed}/{snap.total} cases",
            ),
            "muted",
            gauge=round(snap.pass_rate * 100),
        ),
        _kpi(
            "halluc",
            _loc(lang, "Hallucinations", "Halluzinationen", "Hallucinations"),
            _pct(halluc_rate),
            "",
            _loc(lang, "Élevé", "Hoch", "High")
            if halluc_rate >= _HIGH_HALLUC
            else _loc(lang, "Maîtrisé", "Beherrscht", "Controlled"),
            "bad" if halluc_rate >= _HIGH_HALLUC else "good",
            _loc(
                lang,
                f"{fact_failed}/{fact_total} sondes factualité",
                f"{fact_failed}/{fact_total} Faktentreue-Sonden",
                f"{fact_failed}/{fact_total} factuality probes",
            ),
            "muted",
        ),
        _kpi(
            "relevance",
            _loc(lang, "Pertinence", "Relevanz", "Relevance"),
            _comma(beh_rate * 10),
            "/10",
            *_quality_note(beh_rate * 10, lang),
            _loc(
                lang,
                f"{beh_pass}/{beh_total} cas agent",
                f"{beh_pass}/{beh_total} Agent-Faelle",
                f"{beh_pass}/{beh_total} agent cases",
            ),
            "muted",
        ),
        _kpi(
            "fidelity",
            _loc(lang, "Fidélité (sources)", "Treue (Quellen)", "Fidelity (sources)"),
            _pct(cite_rate),
            "",
            *_quality_note(cite_rate * 10, lang),
            _loc(
                lang,
                f"{cite_passed}/{cite_total} cas citation",
                f"{cite_passed}/{cite_total} Zitat-Faelle",
                f"{cite_passed}/{cite_total} citation cases",
            ),
            "muted",
        ),
        _kpi(
            "coverage",
            _loc(lang, "Couverture du set", "Set-Abdeckung", "Set coverage"),
            str(snap.total),
            "",
            _loc(lang, "tests exécutés", "ausgefuehrte Tests", "tests run"),
            "muted",
            _loc(
                lang,
                f"{len(snap.categories)} catégories - {n_lang} langues",
                f"{len(snap.categories)} Kategorien - {n_lang} Sprachen",
                f"{len(snap.categories)} categories - {n_lang} languages",
            ),
            "muted",
        ),
    ]

    # Filter options that genuinely partition the rows (type / quality band /
    # hallucinations), keyed on stable values - the normative's uniform
    # Statut/Proprietaire would never change the row count, so they are dropped.
    seen_types: dict[str, str] = {}
    for stat in snap.categories:
        label, _tone = _group_label(stat.category, lang)
        seen_types.setdefault(label, label)
    filters: dict[str, object] = {
        "search": _loc(
            lang,
            "Rechercher une évaluation...",
            "Eine Evaluierung suchen...",
            "Search an evaluation...",
        ),
        "options": {
            "type": [{"key": lbl, "label": lbl} for lbl in sorted(seen_types)],
            "quality": [
                {"key": "good", "label": _loc(lang, "Bon", "Gut", "Good")},
                {"key": "warn", "label": _loc(lang, "Moyen", "Mittel", "Medium")},
                {"key": "bad", "label": _loc(lang, "Faible", "Schwach", "Weak")},
            ],
            "halluc": [
                {
                    "key": "with",
                    "label": _loc(
                        lang, "Avec hallucinations", "Mit Halluzinationen", "With hallucinations"
                    ),
                },
                {"key": "without", "label": _loc(lang, "Sans", "Ohne", "Without")},
            ],
        },
    }

    columns = [
        _loc(lang, "Nom de l'évaluation", "Name der Evaluierung", "Evaluation name"),
        _loc(lang, "Type", "Typ", "Type"),
        _loc(lang, "Statut", "Status", "Status"),
        _loc(lang, "Version", "Version", "Version"),
        _loc(lang, "Score global", "Gesamtscore", "Global score"),
        _loc(lang, "Taux réussite", "Erfolgsrate", "Pass rate"),
        _loc(lang, "Hallucinations", "Halluzinationen", "Hallucinations"),
        _loc(lang, "Dernière exécution", "Letzte Ausfuehrung", "Last run"),
        _loc(lang, "Propriétaire", "Eigentuemer", "Owner"),
        _loc(lang, "Tests", "Tests", "Tests"),
    ]
    version_label = snap.catalogue_version[:9] or "v1"
    rows = [
        _row(stat, version_label, stamp, lang)
        for stat in sorted(snap.categories, key=lambda c: (-c.pass_rate, -c.total))
    ]

    worst = snap.categories_by_pass_rate()
    watch_tones = ["crit", "crit", "warn"]
    watch_items = [
        {
            "title": _loc(
                lang,
                f"{stat.label} - {_pct(stat.pass_rate)} de réussite",
                f"{stat.label} - {_pct(stat.pass_rate)} Erfolg",
                f"{stat.label} - {_pct(stat.pass_rate)} pass",
            ),
            "detail": _loc(
                lang,
                f"{stat.passed}/{stat.total} cas - {n_lang} langues",
                f"{stat.passed}/{stat.total} Faelle - {n_lang} Sprachen",
                f"{stat.passed}/{stat.total} cases - {n_lang} languages",
            ),
            "tone": tone,
        }
        for stat, tone in zip(worst[:3], watch_tones, strict=False)
    ]
    n_alert = sum(1 for c in snap.categories if c.pass_rate < _ALERT_PASS_RATE)
    watch: dict[str, object] = {
        "title": _loc(lang, "À surveiller", "Zu beobachten", "To watch"),
        "cta": _loc(
            lang,
            f"Voir toutes les alertes ({n_alert})",
            f"Alle Warnungen anzeigen ({n_alert})",
            f"View all alerts ({n_alert})",
        ),
        "cta_href": "/a-traiter",
        "items": watch_items,
    }

    quick: dict[str, object] = {
        "title": _loc(lang, "Actions rapides", "Schnellaktionen", "Quick actions"),
        "items": [
            {
                "key": "run",
                "label": _loc(
                    lang, "Lancer une évaluation", "Evaluierung starten", "Run an evaluation"
                ),
            },
            {
                "key": "compare",
                "label": _loc(
                    lang, "Comparer versions", "Versionen vergleichen", "Compare versions"
                ),
            },
            {
                "key": "results",
                "label": _loc(lang, "Voir les résultats", "Ergebnisse anzeigen", "View results"),
            },
            {"key": "sets", "label": _loc(lang, "Gérer les jeux", "Sets verwalten", "Manage sets")},
        ],
    }

    trend: dict[str, object] = {
        "title": _loc(
            lang, "Réussite par catégorie", "Erfolg nach Kategorie", "Pass rate by category"
        ),
        "value": _comma(score10),
        "scale": "/10",
        "legend": _loc(
            lang,
            "Taux de réussite (%) par catégorie",
            "Erfolgsrate (%) nach Kategorie",
            "Pass rate (%) by category",
        ),
        "series": [round(c.pass_rate * 100) for c in worst],
    }

    read = _loc(lang, "Lecture", "Lesen", "Read")
    read_write = _loc(lang, "Lecture / Écriture", "Lesen / Schreiben", "Read / Write")
    return {
        "title": _loc(lang, "Évaluations", "Evaluierungen", "Evaluations"),
        "subtitle": _loc(
            lang,
            "Mesurez, analysez et améliorez la qualité des réponses de "
            "l'assistant et des agents.",
            "Messen, analysieren und verbessern Sie die Qualitaet der Antworten "
            "des Assistenten und der Agenten.",
            "Measure, analyze and improve the quality of the assistant's and " "agents' answers.",
        ),
        "actions": {
            "asof": _loc(lang, "Voir à date (as-of)", "Stand anzeigen (as-of)", "View as-of"),
            "create": _loc(
                lang, "Créer une évaluation", "Evaluierung erstellen", "Create an evaluation"
            ),
        },
        "subtabs": [
            _loc(lang, "Vue d'ensemble", "Uebersicht", "Overview"),
            _loc(lang, "Jeux d'évaluations", "Evaluierungssets", "Evaluation sets"),
            _loc(lang, "Résultats", "Ergebnisse", "Results"),
            _loc(lang, "Dimensions", "Dimensionen", "Dimensions"),
            _loc(lang, "Comparaisons", "Vergleiche", "Comparisons"),
            _loc(lang, "Erreurs", "Fehler", "Errors"),
            _loc(lang, "Versions & historique", "Versionen & Verlauf", "Versions & history"),
            _loc(lang, "Exports", "Exporte", "Exports"),
        ],
        "meta": {
            "model": snap.model,
            "catalogue_version": snap.catalogue_version,
            "languages": lang_str,
            "score10": _comma(score10),
            "escalations": snap.escalations,
            "tool_invocations": snap.tool_invocations,
            "rbac": [
                {"role": "ML Engineer", "access": read},
                {"role": "Compliance Officer", "access": read_write},
                {"role": "Admin", "access": read_write},
            ],
        },
        "detail_labels": {
            "eyebrow": _loc(
                lang, "Détails de l'évaluation", "Evaluierungsdetails", "Evaluation details"
            ),
            "tabs": [
                _loc(lang, "Résumé", "Zusammenfassung", "Summary"),
                _loc(lang, "Configuration", "Konfiguration", "Configuration"),
                _loc(lang, "Résultats", "Ergebnisse", "Results"),
                _loc(lang, "Activité", "Aktivitaet", "Activity"),
            ],
            "results_title": _loc(lang, "Résultats (run)", "Ergebnisse (Lauf)", "Results (run)"),
            "results_cta": _loc(
                lang, "Voir tous les résultats", "Alle Ergebnisse anzeigen", "View all results"
            ),
            "rbac_title": _loc(lang, "Accès RBAC", "RBAC-Zugriff", "RBAC access"),
            "config_title": _loc(
                lang, "Configuration du jeu", "Set-Konfiguration", "Set configuration"
            ),
            "info_title": _loc(
                lang, "Informations techniques", "Technische Informationen", "Technical information"
            ),
            "activity_title": _loc(
                lang, "Journal d'activité", "Aktivitaetsprotokoll", "Activity log"
            ),
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
        "gate": _gate_block(snap, lang),
        "judge": _judge_block(snap.agent_id or agent_id),
        "understanding_bench": _understanding_bench_block(snap.agent_id or agent_id, lang),
        "runs": _runs_rail(snap.agent_id or agent_id, lang),
        "sets": _sets_block(snap, lang),
        "results": _results_block(snap, lang),
    }
