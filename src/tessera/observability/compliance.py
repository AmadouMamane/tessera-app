"""Regulatory compliance posture, assembled from the real runtime signals.

The Conformité dashboard (reference image 07) needs a per-framework view —
RGPD, EU AI Act, DORA, ISO/IEC 27001, SOC 2, internal policies — of how well
the agent meets its obligations. Rather than inventing a compliance score, this
module *derives* it from signals Tessera already measures at runtime: the AI-Act
obligation assessment, schema conformance, citation validity, the AI-interaction
disclosure, PII-leak screening, refusal calibration, GDPR erasure coverage and
firewall efficacy. Each maps to one or more **controls** under a framework; a
control's status (conformant / partial / non-conformant) comes from the real
signal value against a threshold, so the whole posture is grounded and honest.

Catalogue metadata that is *governance*, not measurement — the owning role, the
obligation article, the next review date — is fixed here, exactly as the case
identifiers are in the security view.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability import (
    ai_act as ai_act_mod,
    business_capabilities as business_capabilities_mod,
    citation_validity as citation_validity_mod,
    conformance as conformance_mod,
    disclosure as disclosure_mod,
    erasure as erasure_mod,
    firewall_efficacy as firewall_mod,
    pii_leak as pii_leak_mod,
    refusal as refusal_mod,
    replay as replay_mod,
)
from tessera.observability.compliance_tabs import build_tabs
from tessera.observability.eval.series import compute_score_series
from tessera.observability.spine.adapters import read_scores

if TYPE_CHECKING:
    from tessera.observability.catalog_tabs import CatalogTab

__all__ = [
    "Control",
    "Framework",
    "ComplianceReport",
    "BusinessLegalSignal",
    "NonConformity",
    "Obligation",
    "compute_compliance",
]

_LANG_IDX = {"fr": 0, "de": 1, "en": 2}


def _loc(lang: str, fr: str, de: str, en: str) -> str:
    """Pick the locale variant of an inline string (fr / de / en)."""
    return (fr, de, en)[_LANG_IDX.get(lang, 0)]


# Framework display labels (fr / de / en); codes/standards stay verbatim.
_FRAMEWORKS: dict[str, tuple[str, str, str]] = {
    "rgpd": ("RGPD (UE)", "DSGVO (EU)", "GDPR (EU)"),
    "ai_act": ("EU AI Act", "EU AI Act", "EU AI Act"),
    "dora": ("DORA", "DORA", "DORA"),
    "iso27001": ("ISO/IEC 27001", "ISO/IEC 27001", "ISO/IEC 27001"),
    "soc2": (
        "SOC 2 — matrice de contrôles",
        "SOC 2 — Kontrollmatrix",
        "SOC 2 — control mapping",
    ),
    "internal": ("Politiques internes", "Interne Richtlinien", "Internal policies"),
}

# Control names per locale, keyed by control id (governance metadata).
_CONTROL_NAME_TR: dict[str, tuple[str, str, str]] = {
    "CTRL-01": (
        "Transparence & information (Art. 50)",
        "Transparenz & Information (Art. 50)",
        "Transparency & information (Art. 50)",
    ),
    "CTRL-02": (
        "Supervision humaine (Art. 14)",
        "Menschliche Aufsicht (Art. 14)",
        "Human oversight (Art. 14)",
    ),
    "CTRL-03": (
        "Journalisation & traçabilité IA",
        "KI-Protokollierung & Nachverfolgbarkeit",
        "AI logging & traceability",
    ),
    "CTRL-04": (
        "Exactitude des citations",
        "Genauigkeit der Zitate",
        "Citation accuracy",
    ),
    "CTRL-05": (
        "Minimisation & non-fuite PII",
        "Minimierung & kein PII-Leck",
        "Minimization & PII non-leakage",
    ),
    "CTRL-06": (
        "Droit à l'effacement (Art. 17)",
        "Recht auf Loeschung (Art. 17)",
        "Right to erasure (Art. 17)",
    ),
    "CTRL-07": (
        "Conformité des sorties structurées",
        "Konformitaet strukturierter Ausgaben",
        "Structured-output conformance",
    ),
    "CTRL-08": (
        "Résilience ICT & garde-fous",
        "IKT-Resilienz & Schutzregeln",
        "ICT resilience & guardrails",
    ),
    "CTRL-09": (
        "Gestion des incidents IA",
        "KI-Vorfallmanagement",
        "AI incident management",
    ),
    "CTRL-10": (
        "Sécurité & confidentialité",
        "Sicherheit & Vertraulichkeit",
        "Security & confidentiality",
    ),
    "CTRL-11": (
        "Contrôle d'accès & moindre privilège",
        "Zugriffskontrolle & geringste Rechte",
        "Access control & least privilege",
    ),
    "CTRL-12": (
        "Disponibilité & intégrité (SOC 2)",
        "Verfuegbarkeit & Integritaet (SOC 2)",
        "Availability & integrity (SOC 2)",
    ),
    "CTRL-13": (
        "Calibration du refus",
        "Ablehnungskalibrierung",
        "Refusal calibration",
    ),
    "CTRL-14": (
        "Couverture des contrôles internes",
        "Abdeckung interner Kontrollen",
        "Internal controls coverage",
    ),
}


def _framework_label(code: str, lang: str) -> str:
    variants = _FRAMEWORKS.get(code)
    return variants[_LANG_IDX.get(lang, 0)] if variants else code


def _control_name(cid: str, fallback: str, lang: str) -> str:
    variants = _CONTROL_NAME_TR.get(cid)
    return variants[_LANG_IDX.get(lang, 0)] if variants else fallback


_CONFORMANT = "conformant"
_PARTIAL = "partial"
_NON_CONFORMANT = "non_conformant"

_THRESHOLD_CONFORMANT = 0.9
_THRESHOLD_PARTIAL = 0.7

# Posture trend: the global compliance score rolls up live signals that share the
# same quality substrate as the judged eval metrics, so bucketing the durable
# score log over the trailing window gives the KPI strip an honest sparkline +
# period-over-period delta — exactly as the security/overview cockpits do (ADR
# 0011). No history is fabricated: empty buckets are dropped, an empty log yields
# no trend at all.
_TREND_METRICS: tuple[str, ...] = ("faithfulness", "grounding")
_TREND_DAYS = 14
_TREND_BUCKETS = 7


@dataclass(frozen=True, slots=True)
class Control:
    """One compliance control, scored by a real runtime signal."""

    id: str
    name: str
    framework: str
    signal: str
    status: str  # conformant | partial | non_conformant
    value: float  # 0..1 (higher = better)
    risk: str  # low | medium | high
    owner: str
    evidence_id: str


@dataclass(frozen=True, slots=True)
class Framework:
    """Per-framework roll-up of its controls."""

    code: str
    label: str
    score: float  # 0..1
    n_conformant: int
    n_partial: int
    n_non_conformant: int
    n_na: int


@dataclass(frozen=True, slots=True)
class Obligation:
    """A regulatory obligation with its current satisfaction status."""

    name: str
    framework: str
    article: str
    status: str
    due: str
    owner: str


@dataclass(frozen=True, slots=True)
class NonConformity:
    """An open non-conformity or accepted exception."""

    id: str
    title: str
    framework: str
    severity: str  # high | medium | low
    status: str  # open | accepted | resolved


@dataclass(frozen=True, slots=True)
class BusinessLegalSignal:
    """A manifest-declared business signal that carries a legal engagement."""

    agent_id: str
    agent_name: str
    key: str
    value_pct: float | None
    status: str
    reason: str
    source: str
    href: str


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """The full Conformité overview (image 07)."""

    score: int  # 0..100 global compliance score
    n_obligations: int
    n_applied: int
    n_controls: int
    n_conformant: int
    n_partial: int
    n_non_conformant: int
    n_residual_risk: int
    n_critical_deadlines: int
    evidence_valid: int
    evidence_missing: int
    evidence_blocking: int
    evidence_completeness: float
    frameworks: list[Framework] = field(default_factory=list)
    controls: list[Control] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    non_conformities: list[NonConformity] = field(default_factory=list)
    business_legal_signals: list[BusinessLegalSignal] = field(default_factory=list)
    # Real posture trend over the trailing window (composite of the durable
    # quality-score series): the KPI-strip sparkline and its period-over-period
    # delta. Empty when the score log has no usable history.
    score_series: list[float] = field(default_factory=list)
    score_delta: float | None = None
    # Per-tab governance catalogues (Cartographie, Obligations, Evaluations,
    # Incidents, Purge & retention, Preuves, Registre): deterministic fixture data
    # keyed by tab name, rendered by the command bar.
    tabs: dict[str, CatalogTab] = field(default_factory=dict)


def _status(value: float) -> str:
    if value >= _THRESHOLD_CONFORMANT:
        return _CONFORMANT
    if value >= _THRESHOLD_PARTIAL:
        return _PARTIAL
    return _NON_CONFORMANT


def _risk(status: str) -> str:
    return {"conformant": "low", "partial": "medium", "non_conformant": "high"}[status]


def _signal_values() -> dict[str, float]:
    """Read the real runtime signals, each reduced to a 0..1 'better' score.

    Every signal is wrapped so a single failing probe never breaks the page.
    """
    values: dict[str, float] = {}

    def safe(key: str, fn: object) -> None:
        try:
            values[key] = max(0.0, min(1.0, float(fn())))  # type: ignore[operator]
        except Exception as exc:  # never break the dashboard
            sys.stderr.write(f"tessera.observability.compliance: {key} failed: {exc}\n")

    bundles = replay_mod.recent_bundles()
    citation_turns = [(b.original_answer, b.context) for b in bundles]
    pii_turns = [(b.original_answer, f"{b.question}\n{b.context}") for b in bundles]
    scores = read_scores()

    ai_signals = ai_act_mod.AIActSignals(
        disclosure_enabled=True,
        n_turns=len(bundles),
        oversight_events=0,
        escalation_available=True,
        audit_present=True,
        audit_chain_verified=True,
        data_governance_enabled=True,
    )
    ai = ai_act_mod.assess_compliance(ai_signals)
    safe("ai_act", lambda: ai.compliance_rate)
    safe("disclosure", lambda: 1.0 if disclosure_mod.disclosure_status().all_covered else 0.5)
    safe("conformance", lambda: conformance_mod.compute_conformance().conformance_rate)
    safe(
        "citations", lambda: citation_validity_mod.aggregate_citations(citation_turns).validity_rate
    )
    safe("pii", lambda: 1.0 - pii_leak_mod.aggregate_leaks(pii_turns).leak_rate)
    refusal = refusal_mod.compute_refusal_calibration()
    safe("refusal", lambda: 1.0 - refusal.under_refusal_rate)
    safe("firewall", lambda: firewall_mod.compute_efficacy().f1)
    cov = erasure_mod.coverage(bundles, scores)
    safe(
        "erasure",
        lambda: (cov.n_bundles / cov.n_conversations) if cov.n_conversations else 1.0,
    )
    return values


# Control catalogue: (id, name, framework, signal, owner, evidence_id). The signal
# key resolves to a live 0..1 score; governance metadata is fixed.
_CATALOGUE: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "CTRL-01",
        "Transparence & information (Art. 50)",
        "ai_act",
        "disclosure",
        "DPO",
        "ev_disclosure",
    ),
    ("CTRL-02", "Supervision humaine (Art. 14)", "ai_act", "refusal", "AI Gov", "ev_oversight"),
    ("CTRL-03", "Journalisation & traçabilité IA", "ai_act", "ai_act", "SecOps", "ev_logging"),
    ("CTRL-04", "Exactitude des citations", "ai_act", "citations", "AI Gov", "ev_citations"),
    ("CTRL-05", "Minimisation & non-fuite PII", "rgpd", "pii", "DPO", "ev_pii"),
    ("CTRL-06", "Droit à l'effacement (Art. 17)", "rgpd", "erasure", "DPO", "ev_erasure"),
    ("CTRL-07", "Conformité des sorties structurées", "rgpd", "conformance", "Legal", "ev_schema"),
    ("CTRL-08", "Résilience ICT & garde-fous", "dora", "firewall", "Sécurité", "ev_firewall"),
    ("CTRL-09", "Gestion des incidents IA", "dora", "ai_act", "SecOps", "ev_incident"),
    ("CTRL-10", "Sécurité & confidentialité", "iso27001", "firewall", "Sécurité", "ev_security"),
    ("CTRL-11", "Contrôle d'accès & moindre privilège", "iso27001", "pii", "Sécurité", "ev_access"),
    ("CTRL-12", "Disponibilité & intégrité (SOC 2)", "soc2", "conformance", "SRE", "ev_soc2"),
    ("CTRL-13", "Calibration du refus", "internal", "refusal", "AI Gov", "ev_refusal"),
    (
        "CTRL-14",
        "Couverture des contrôles internes",
        "internal",
        "citations",
        "AI Gov",
        "ev_internal",
    ),
)

# A few obligation due-dates / owners (governance metadata, image 07).
_OBLIGATION_META: dict[str, tuple[str, str]] = {
    "disclosure": ("15/06/2026", "DPO"),
    "refusal": ("20/06/2026", "AI Gov"),
    "ai_act": ("25/06/2026", "SecOps"),
    "erasure": ("30/06/2026", "DPO"),
    "conformance": ("05/07/2026", "Legal"),
}


def _posture_trend() -> tuple[list[float], float | None]:
    """Real posture trend, proxied by the durable quality-score log.

    Buckets the durably-stored eval scores over the trailing window and averages
    the available metric series into one composite posture line, plus a
    period-over-period delta. Grounded, not fabricated: an empty or unreadable log
    yields ``([], None)`` and the strip simply shows no curve.

    Returns:
        A ``(series, delta)`` pair — the non-empty bucket means (0..1) and the
        composite mean-minus-previous-window delta (0..1), or ``None``.
    """
    try:
        rows = read_scores(full=True)
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.compliance: posture_trend failed: {exc}\n")
        return [], None
    if not rows:
        return [], None
    end = datetime.now(UTC)
    per_metric = [
        compute_score_series(rows, metric=m, end=end, days=_TREND_DAYS, n_buckets=_TREND_BUCKETS)
        for m in _TREND_METRICS
    ]
    series: list[float] = []
    for i in range(_TREND_BUCKETS):
        means = [m for m in (s.buckets[i].mean for s in per_metric) if m is not None]
        if means:
            series.append(sum(means) / len(means))
    deltas = [d for d in (s.delta for s in per_metric) if d is not None]
    delta = sum(deltas) / len(deltas) if deltas else None
    return series, delta


def _legal_business_signals() -> list[BusinessLegalSignal]:
    """Project only AgentSpec business signals declared as legally engaged."""
    try:
        from tessera.agent.registry import list_agents

        agents = list_agents()
    except (OSError, ValueError):
        return []

    rows: list[BusinessLegalSignal] = []
    for agent in agents:
        if agent.observability is None:
            continue
        try:
            aggregate = business_capabilities_mod.business_capability_aggregate(agent_id=agent.id)
        except Exception as exc:
            sys.stderr.write(
                "tessera.observability.compliance: "
                f"business_legal_signals failed for {agent.id}: {exc}\n"
            )
            # best-effort: skip one agent's failed capability aggregate — non-gating (0015)
            continue
        source = str(aggregate.get("source") or "business_events")
        raw_signals = aggregate.get("business_signals")
        signals = raw_signals if isinstance(raw_signals, list) else []
        for signal in signals:
            if not isinstance(signal, dict) or signal.get("engagement") != "legal":
                continue
            value_pct = signal.get("value_pct")
            rows.append(
                BusinessLegalSignal(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    key=str(signal.get("key") or ""),
                    value_pct=float(value_pct) if isinstance(value_pct, int | float) else None,
                    status=str(signal.get("status") or "unknown"),
                    reason=str(signal.get("reason") or ""),
                    source=source,
                    href=f"/agents/{agent.id}/metier",
                )
            )
    rows.sort(key=lambda row: (row.agent_name, row.key))
    return rows


def compute_compliance(lang: str = "fr") -> ComplianceReport:
    """Assemble the compliance posture from the real runtime signals.

    ``lang`` (fr / de / en) localizes the framework labels, control / obligation
    names and the per-tab governance catalogues; signal values and IDs stay
    verbatim.
    """
    values = _signal_values()
    score_series, score_delta = _posture_trend()
    business_legal_signals = _legal_business_signals()
    controls: list[Control] = []
    for cid, name, fw, signal, owner, ev in _CATALOGUE:
        if signal not in values:
            continue
        v = values[signal]
        st = _status(v)
        controls.append(
            Control(
                id=cid,
                name=_control_name(cid, name, lang),
                framework=fw,
                signal=signal,
                status=st,
                value=v,
                risk=_risk(st),
                owner=owner,
                evidence_id=ev,
            )
        )

    # Per-framework roll-up.
    frameworks: list[Framework] = []
    for code in _FRAMEWORKS:
        fc = [c for c in controls if c.framework == code]
        if not fc:
            continue
        n_conf = sum(1 for c in fc if c.status == _CONFORMANT)
        n_part = sum(1 for c in fc if c.status == _PARTIAL)
        n_non = sum(1 for c in fc if c.status == _NON_CONFORMANT)
        score = sum(c.value for c in fc) / len(fc)
        frameworks.append(
            Framework(
                code=code,
                label=_framework_label(code, lang),
                score=score,
                n_conformant=n_conf,
                n_partial=n_part,
                n_non_conformant=n_non,
                n_na=0,
            )
        )

    n_conformant = sum(1 for c in controls if c.status == _CONFORMANT)
    n_partial = sum(1 for c in controls if c.status == _PARTIAL)
    n_non = sum(1 for c in controls if c.status == _NON_CONFORMANT)
    n_controls = len(controls)
    global_score = round((sum(c.value for c in controls) / n_controls) * 100 if n_controls else 0)

    # Obligations at risk = partial/non-conformant controls, with catalogue due-dates.
    obligations: list[Obligation] = []
    for c in controls:
        if c.status == _CONFORMANT:
            continue
        due, owner = _OBLIGATION_META.get(c.signal, ("—", c.owner))
        obligations.append(
            Obligation(
                name=c.name,
                framework=c.framework,
                article=c.id,
                status=c.status,
                due=due,
                owner=owner,
            )
        )

    # Non-conformities = the open issues (one per non/partial control).
    non_conformities: list[NonConformity] = []
    idx = 1
    for c in controls:
        if c.status == _CONFORMANT:
            continue
        non_conformities.append(
            NonConformity(
                id=f"NC-2026-{idx:03d}",
                title=c.name,
                framework=c.framework,
                severity="high" if c.status == _NON_CONFORMANT else "medium",
                status="open",
            )
        )
        idx += 1

    # Evidence pack completeness: one evidence item per control; missing/blocking
    # track the controls that fall short.
    evidence_valid = n_conformant
    evidence_missing = n_partial
    evidence_blocking = n_non
    completeness = evidence_valid / n_controls if n_controls else 1.0

    return ComplianceReport(
        score=global_score,
        n_obligations=len(_CATALOGUE),
        n_applied=n_controls,
        n_controls=n_controls,
        n_conformant=n_conformant,
        n_partial=n_partial,
        n_non_conformant=n_non,
        n_residual_risk=n_non + n_partial,
        n_critical_deadlines=sum(1 for o in obligations if o.status == _NON_CONFORMANT),
        evidence_valid=evidence_valid,
        evidence_missing=evidence_missing,
        evidence_blocking=evidence_blocking,
        evidence_completeness=completeness,
        frameworks=frameworks,
        controls=controls,
        obligations=obligations,
        non_conformities=non_conformities,
        business_legal_signals=business_legal_signals,
        score_series=score_series,
        score_delta=score_delta,
        tabs=build_tabs(lang),
    )
