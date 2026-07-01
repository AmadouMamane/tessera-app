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
    "Échec · domaine (T2)": ("Fehler · Domaene (T2)", "Failure · domain (T2)"),
    "Non exécuté": ("Nicht ausgefuehrt", "Not executed"),
    # tier labels (eval_tiers._TIER_LABEL)
    "Cœur non-dérogeable": ("Nicht ausnehmbarer Kern", "Non-waivable core"),
    "Critique dérogeable": ("Ausnehmbar kritisch", "Waivable critical"),
    "Domaine gradé": ("Gradierte Domaene", "Graded domain"),
    # verdict labels (eval_gate_view._verdict)
    "BLOQUÉ par le socle": ("DURCH SOCKEL BLOCKIERT", "BLOCKED by core"),
    "BLOQUÉ (critiques non dérogés)": (
        "BLOCKIERT (kritische ohne Ausnahme)",
        "BLOCKED (unwaived critical)",
    ),
    "BLOQUÉ (domaine)": ("BLOCKIERT (Domaene)", "BLOCKED (domain)"),
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
    "Le taux de réussite du domaine (T2) est sous le seuil requis.": (
        "Die Erfolgsrate der Domaene (T2) liegt unter dem erforderlichen Schwellenwert.",
        "The domain (T2) pass rate is below the required threshold.",
    ),
    "Socle intact, aucun critique non dérogé, domaine conforme.": (
        "Sockel intakt, kein kritischer ohne Ausnahme, Domaene konform.",
        "Core intact, no unwaived critical, domain compliant.",
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
        "min_pass_rate": gv.min_pass_rate,
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


def _runs_rail(agent_id: str, lang: str) -> dict[str, object]:
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
        "title": _loc(lang, "Historique des runs", "Lauf-Verlauf", "Run history"),
        "subtitle": _loc(
            lang,
            "Reconstruit quel run et quels scores étaient courants à chaque date.",
            "Rekonstruiert, welcher Lauf und welche Scores zu jedem Datum aktuell waren.",
            "Reconstructs which run and which scores were current at each date.",
        ),
        "items": items,
        "count": len(items),
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
        "runs": _runs_rail(snap.agent_id or agent_id, lang),
    }
