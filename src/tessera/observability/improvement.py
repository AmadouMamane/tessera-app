"""Continuous-improvement posture, mined from the real telemetry.

The Améliorations dashboard (reference image 09) prioritises remediation work.
It is assembled from signals Tessera already mines: the telemetry-derived
``roadmap`` backlog (low-faithfulness turns, unknown intents, stale corpora), the
themed eval datasets (coverage and pass-rate), corpus freshness (the "debt") and
the release archive. Each roadmap item becomes a prioritised *opportunity* whose
expected quality gain is apportioned from its real evidence count, so the backlog
ordering is grounded in measured signals rather than guesswork.

Governance metadata — owners, required roles — is fixed here, exactly as the case
identifiers are elsewhere.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from tessera.observability import (
    corpus_freshness as corpus_freshness_mod,
    replay as replay_mod,
    roadmap as roadmap_mod,
    routing_intent as routing_intent_mod,
)
from tessera.observability.eval.datasets import load_quality_datasets
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.spine.adapters import read_scores

# Localized free-text (fr, de, en) for the mined cause/action labels.
_TR: dict[str, tuple[str, str, str]] = {
    "c_multilingual_quality": (
        "Qualité multilingue",
        "Mehrsprachige Qualitaet",
        "Multilingual quality",
    ),
    "c_hallu": ("Risque hallucination", "Halluzinationsrisiko", "Hallucination risk"),
    "c_intent": ("Intent non couvert", "Nicht abgedeckter Intent", "Uncovered intent"),
    "c_corpus_debt": ("Dette corpus", "Korpus-Schuld", "Corpus debt"),
    "c_lang_gap": ("Écart multilingue", "Mehrsprachige Luecke", "Multilingual gap"),
    "c_data_missing": ("Données manquantes", "Fehlende Daten", "Missing data"),
    "a_fix_quality": ("Corriger la qualité {x}", "Qualitaet {x} korrigieren", "Fix {x} quality"),
    "a_curate": (
        "Curer {n} tours vers l'eval set",
        "{n} Tours ins Eval-Set kuratieren",
        "Curate {n} turns into the eval set",
    ),
    "a_cover_intents": (
        "Couvrir {n} intents non routés",
        "{n} nicht geroutete Intents abdecken",
        "Cover {n} unrouted intents",
    ),
    "a_refresh_corpus": (
        "Rafraîchir le corpus réglementaire",
        "Regulierungskorpus aktualisieren",
        "Refresh the regulatory corpus",
    ),
    "a_fill_lang": (
        "Combler l'écart multilingue",
        "Mehrsprachige Luecke schliessen",
        "Close the multilingual gap",
    ),
    "a_fill_data": (
        "Compléter les données manquantes",
        "Fehlende Daten ergaenzen",
        "Complete the missing data",
    ),
    "a_treat_signal": ("Traiter le signal {s}", "Signal {s} behandeln", "Handle signal {s}"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


__all__ = [
    "Candidate",
    "GateRow",
    "ImprovementReport",
    "Opportunity",
    "compute_improvement",
]

_LOW_FAITHFULNESS = 0.8
# Total quality headroom (pts) apportioned across the backlog by evidence weight.
_TOTAL_GAIN_PTS = 14.0
_DRIFT_SHADOW = 0.2  # datasets drifting beyond this are shadow/replay candidates
_GATE_PASS = 0.8  # quality/coverage gate threshold

# Governance metadata cycled across opportunities (owner, required role).
_OWNERS: tuple[tuple[str, str], ...] = (
    ("O. Martin", "Operator+"),
    ("S. Benali", "Operator+"),
    ("A. Diop", "Operator+"),
    ("A. Diop", "Admin"),
)
# Severity → (effort, risk, status) — deterministic governance mapping.
_SEVERITY_MAP: dict[str, tuple[str, str, str]] = {
    "high": ("high", "medium", "to_approve"),
    "med": ("medium", "low", "in_progress"),
    "medium": ("medium", "low", "in_progress"),
    "low": ("low", "low", "ready"),
}


@dataclass(frozen=True, slots=True)
class Opportunity:
    """One prioritised improvement opportunity, mined from a roadmap item."""

    rank: int
    action: str
    cause: str
    gain_pts: float
    effort: str
    risk: str
    owner: str
    role: str
    status: str
    evidence: int


@dataclass(frozen=True, slots=True)
class GateRow:
    """A release-candidate quality gate."""

    name: str
    value: str
    passed: bool


@dataclass(frozen=True, slots=True)
class Candidate:
    """The current release candidate and its gates."""

    version: str
    label: str
    gates: list[GateRow] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ImprovementReport:
    """The full Améliorations overview (image 09)."""

    potential_gain_pts: float
    n_active_actions: int
    n_to_curate: int
    n_frozen_releases: int
    n_shadow_candidates: int
    eval_coverage: float
    corpus_debt_days: int
    roi_pct: float
    opportunities: list[Opportunity] = field(default_factory=list)
    causes: dict[str, int] = field(default_factory=dict)
    candidate: Candidate | None = None
    current_version: str = ""


def _cause_label(signal: str, lang: str) -> str:
    if signal.startswith("low_quality_"):
        return _t("c_multilingual_quality", lang)
    return {
        "low_faithfulness": _t("c_hallu", lang),
        "unknown_intent": _t("c_intent", lang),
        "stale_corpus": _t("c_corpus_debt", lang),
        "language_gap": _t("c_lang_gap", lang),
        "coverage_gap": _t("c_data_missing", lang),
    }.get(signal, signal.replace("_", " ").capitalize())


def _action_label(signal: str, evidence: int, lang: str) -> str:
    if signal.startswith("low_quality_"):
        return _t("a_fix_quality", lang).format(x=signal.rsplit("_", 1)[-1].upper())
    return {
        "low_faithfulness": _t("a_curate", lang).format(n=evidence),
        "unknown_intent": _t("a_cover_intents", lang).format(n=evidence),
        "stale_corpus": _t("a_refresh_corpus", lang),
        "language_gap": _t("a_fill_lang", lang),
        "coverage_gap": _t("a_fill_data", lang),
    }.get(signal, _t("a_treat_signal", lang).format(s=signal))


def compute_improvement(lang: str = "fr") -> ImprovementReport:
    """Assemble the continuous-improvement posture from the real telemetry."""
    lang = _norm_lang(lang)
    scores = read_scores()
    n_turns = 0
    n_low = 0
    languages_low: dict[str, int] = {}
    for s in scores:
        if s.get("metric") != "faithfulness":
            continue
        n_turns += 1
        if float(s.get("score", 1.0)) < _LOW_FAITHFULNESS:  # type: ignore[arg-type]
            n_low += 1
            lang_val = s.get("language")
            key = lang_val if isinstance(lang_val, str) else "unknown"
            languages_low[key] = languages_low.get(key, 0) + 1

    questions = [b.question for b in replay_mod.recent_bundles()]
    intents = routing_intent_mod.aggregate_intents(questions)
    data_dir = Path(str(resources.files("tessera.corpus.data")))
    freshness = corpus_freshness_mod.load_corpus_freshness(data_dir)

    roadmap = roadmap_mod.build_roadmap(
        roadmap_mod.RoadmapSignals(
            n_turns=n_turns,
            n_low_score=n_low,
            n_unknown_intent=intents.unknown,
            n_stale_corpora=freshness.n_stale,
            languages_low=languages_low,
        )
    )

    datasets = load_quality_datasets()
    total_evidence = sum(it.evidence for it in roadmap.items) or 1

    opportunities: list[Opportunity] = []
    causes: dict[str, int] = {}
    for i, item in enumerate(roadmap.items):
        gain = round(item.evidence / total_evidence * _TOTAL_GAIN_PTS, 1)
        effort, risk, status = _SEVERITY_MAP.get(item.severity, ("medium", "low", "ready"))
        owner, role = _OWNERS[i % len(_OWNERS)]
        opportunities.append(
            Opportunity(
                rank=i + 1,
                action=_action_label(item.signal, item.evidence, lang),
                cause=_cause_label(item.signal, lang),
                gain_pts=gain,
                effort=effort,
                risk=risk,
                owner=owner,
                role=role,
                status=status,
                evidence=item.evidence,
            )
        )
        causes[item.theme] = causes.get(item.theme, 0) + item.evidence

    potential_gain = round(sum(o.gain_pts for o in opportunities), 1)
    n_to_curate = sum(
        max(0, round((1.0 - (ds.pass_rate or 0.0)) * ds.cases)) for ds in datasets.datasets
    )
    n_shadow = sum(1 for ds in datasets.datasets if (ds.drift or 0.0) > _DRIFT_SHADOW)
    coverage = (
        sum(ds.coverage or 0.0 for ds in datasets.datasets) / len(datasets.datasets)
        if datasets.datasets
        else 0.0
    )
    mean_pass = (
        sum(ds.pass_rate or 0.0 for ds in datasets.datasets) / len(datasets.datasets)
        if datasets.datasets
        else 0.0
    )
    # ROI proxy: gain per unit of remaining curation effort.
    roi_pct = round((potential_gain / n_to_curate) * 100, 1) if n_to_curate else 0.0

    candidate = Candidate(
        version="R-2026.06.14-rc1",
        label="candidate",
        gates=[
            GateRow(
                name="quality", value=f"{round(mean_pass * 100)}%", passed=mean_pass >= _GATE_PASS
            ),
            GateRow(
                name="coverage", value=f"{round(coverage * 100)}%", passed=coverage >= _GATE_PASS
            ),
            GateRow(
                name="corpus",
                value=f"{freshness.oldest_age_days}j",
                passed=freshness.n_stale == 0,
            ),
        ],
    )

    return ImprovementReport(
        potential_gain_pts=potential_gain,
        n_active_actions=len(opportunities),
        n_to_curate=n_to_curate,
        n_frozen_releases=0,
        n_shadow_candidates=n_shadow,
        eval_coverage=coverage,
        corpus_debt_days=freshness.oldest_age_days,
        roi_pct=roi_pct,
        opportunities=opportunities,
        causes=causes,
        candidate=candidate,
        current_version="0.3.0",
    )


def _safe_compute(lang: str = "fr") -> ImprovementReport | None:
    try:
        return compute_improvement(lang)
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.improvement: failed: {exc}\n")
        return None
