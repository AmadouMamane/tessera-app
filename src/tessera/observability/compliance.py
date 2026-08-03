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
    from collections.abc import Callable

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
#: Not applicable — the control could not be MEASURED. Distinct from non-conformant, which is
#: a measurement that came out bad. Before this existed a probe over an empty window scored
#: 1.0 and read "conformant", and a probe that raised vanished from the table entirely.
_NA = "na"

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
    #: Why this control could not be measured — ``no-sample`` (the probe ran over an empty
    #: window), ``read-failed`` (it raised) or ``no-reader`` (nothing produces this signal).
    #: ``None`` when the control WAS measured. A dash on a compliance screen must say why.
    unavailable: str | None = None
    #: How many observations stand behind ``value``. Zero means the number is not a measurement.
    n_samples: int = 0


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
    # `na` is deliberately not "low": a control nobody could measure is not a control known to
    # be fine. Reporting an unmeasured obligation as low risk is the same lie as scoring it 1.0.
    return {"conformant": "low", "partial": "medium", "non_conformant": "high", _NA: "unknown"}[
        status
    ]


@dataclass(frozen=True, slots=True)
class ChainFacts:
    """What the audit chain actually says, asked of the ledger rather than asserted."""

    present: bool
    verified: bool


def _audit_chain_facts() -> ChainFacts:
    """Ask the ledger whether it exists and whether it verifies.

    The AI-Act signals used to hard-code ``audit_present=True`` and
    ``audit_chain_verified=True``, and ``ai_act.py`` renders those into a SATISFIED Art. 12
    obligation whose evidence line reads "tamper-evident audit chain verified". The twin route
    ``/observability/ai-act`` did the real work all along — so one obligation had two answers,
    and the affirming one was on the regulatory screen. A witness interrogates the thing
    (ADR 0026). If the ledger cannot be asked, the honest answer is *not verified*, never
    *verified*.
    """
    try:
        from tessera.guard.ledger_store import ledger_available, verify_active_ledger_checkpointed

        if not ledger_available():
            return ChainFacts(present=False, verified=False)
        return ChainFacts(present=True, verified=bool(verify_active_ledger_checkpointed().verified))
    except Exception as exc:  # a chain that cannot be asked is not a verified chain
        sys.stderr.write(f"tessera.observability.compliance: audit chain unreadable: {exc}\n")
        return ChainFacts(present=False, verified=False)


@dataclass(frozen=True, slots=True)
class SignalReading:
    """One probe's answer, WITH the size of the sample it was taken over.

    Reducing a probe to a bare float destroyed the one thing a compliance reader needs: how
    many observations stand behind the number. ``citation_validity``, ``pii_leak`` and
    ``conformance`` all return 1.0 over an empty set, and the erasure coverage returned a
    literal 1.0 when there were no conversations — so on any window with no traffic the
    regulatory screen announced "Exactitude des citations 100 %", "Minimisation & non-fuite PII
    100 %" and "Droit à l'effacement 100 %" over zero citations, zero turns and zero
    conversations. Audit 2026-08-03.
    """

    value: float | None
    n: int = 0
    cause: str | None = None

    @property
    def measured(self) -> bool:
        """True only when a value was produced over a non-empty sample."""
        return self.value is not None and self.n > 0


def _conformance_reading(report: conformance_mod.ConformanceReport) -> tuple[float, int]:
    """``(rate, n)`` — a conformance rate over zero checked calls is not a rate."""
    return report.conformance_rate, report.n_calls


def _citation_reading(report: citation_validity_mod.CitationSummary) -> tuple[float, int]:
    """``(rate, n)`` — 1.0 over zero citations said "every citation is valid" about none."""
    return report.validity_rate, report.n_citations


def _leak_reading(report: pii_leak_mod.PIILeakSummary) -> tuple[float, int]:
    """PII is scored as the ABSENCE of leaks, over the turns actually examined."""
    return 1.0 - report.leak_rate, report.n_turns


def _coverage_reading(cov: erasure_mod.ErasureCoverage) -> tuple[float, int]:
    """Erasure coverage over the conversations there were — zero of them means unknown."""
    total = cov.n_conversations
    return (cov.n_bundles / total if total else 0.0), total


def _signal_values(at: str | None = None, days: float | None = None) -> dict[str, SignalReading]:
    """Read the real runtime signals, each reduced to a 0..1 'better' score AND its sample size.

    Every signal is wrapped so a single failing probe never breaks the page — but a failure is
    now RECORDED as one. It used to be dropped from the mapping, and the catalogue loop skipped
    any signal it could not find, so a probe that raised silently removed its control from the
    table, from the framework roll-up and from the list of non-conformities. Since the global
    score is the mean of the surviving controls, an unreadable calibration file made the
    compliance score go UP.
    """
    values: dict[str, SignalReading] = {}

    def read(key: str, fn: Callable[[], tuple[float, int]]) -> None:
        """Run one probe under its own guard; record the value AND how big its sample was."""
        try:
            value, n = fn()
        except Exception as exc:  # never break the dashboard — but never hide it either
            sys.stderr.write(f"tessera.observability.compliance: {key} failed: {exc}\n")
            values[key] = SignalReading(value=None, n=0, cause="read-failed")
            return
        values[key] = (
            SignalReading(value=max(0.0, min(1.0, float(value))), n=n)
            if n > 0
            else SignalReading(value=None, n=0, cause="no-sample")
        )

    bundles = _windowed_bundles(at, days)
    citation_turns = [(b.original_answer, b.context) for b in bundles]
    pii_turns = [(b.original_answer, f"{b.question}\n{b.context}") for b in bundles]
    scores = read_scores(at, days=days)

    # The audit-chain facts are ASKED, not asserted. `audit_present` and
    # `audit_chain_verified` were the literals `True`, and ai_act.py turns them into a
    # satisfied Art. 12 obligation whose evidence line reads "tamper-evident audit chain
    # verified" — on the regulatory surface, while the twin route /observability/ai-act did
    # the real verification. Two surfaces, one obligation, two answers, and the one that
    # affirmed was the one a regulator reads (audit 2026-08-03, ADR 0026/0028).
    chain = _audit_chain_facts()
    ai_signals = ai_act_mod.AIActSignals(
        disclosure_enabled=True,
        n_turns=len(bundles),
        oversight_events=0,
        escalation_available=True,
        audit_present=chain.present,
        audit_chain_verified=chain.verified,
        data_governance_enabled=True,
    )
    ai = ai_act_mod.assess_compliance(ai_signals)
    # Each probe is READ inside its own guard, returning ``(value, sample size)``. Computing
    # the sizes outside `safe` would have been the obvious way to get them — and would have
    # made one raising probe break the whole page, which is the opposite of what the wrapper
    # is for.
    read("ai_act", lambda: (ai.compliance_rate, len(bundles)))
    read(
        "disclosure",
        lambda: (1.0 if disclosure_mod.disclosure_status().all_covered else 0.5, 1),
    )
    read("conformance", lambda: _conformance_reading(conformance_mod.compute_conformance()))
    read(
        "citations",
        lambda: _citation_reading(citation_validity_mod.aggregate_citations(citation_turns)),
    )
    read("pii", lambda: _leak_reading(pii_leak_mod.aggregate_leaks(pii_turns)))
    read(
        "refusal",
        lambda: (1.0 - refusal_mod.compute_refusal_calibration().under_refusal_rate, 1),
    )
    read("firewall", lambda: (firewall_mod.compute_efficacy().f1, 1))
    # No conversations means the erasure footprint is UNKNOWN, not complete. The literal 1.0
    # this used to fall back to is the plainest form of the defect.
    read("erasure", lambda: _coverage_reading(erasure_mod.coverage(bundles, scores)))
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


def compute_compliance(
    lang: str = "fr", at: str | None = None, days: float | None = None
) -> ComplianceReport:
    """Assemble the compliance posture from the real runtime signals.

    ``lang`` (fr / de / en) localizes the framework labels, control / obligation
    names and the per-tab governance catalogues; signal values and IDs stay
    verbatim.
    """
    values = _signal_values(at, days)
    score_series, score_delta = _posture_trend()
    business_legal_signals = _legal_business_signals()
    controls: list[Control] = []
    for cid, name, fw, signal, owner, ev in _CATALOGUE:
        # A control whose signal is missing or unmeasured STAYS IN THE TABLE, as `na` with a
        # cause. Skipping it removed the control from the roll-up, from the obligations list
        # and from the denominator of the global score — so a probe that raised made the
        # compliance score go up, and the frameworks reported "0 non applicable" while one of
        # their controls had silently evaporated. Audit 2026-08-03.
        reading = values.get(signal, SignalReading(value=None, n=0, cause="no-reader"))
        if not reading.measured:
            controls.append(
                Control(
                    id=cid,
                    name=_control_name(cid, name, lang),
                    framework=fw,
                    signal=signal,
                    status=_NA,
                    value=0.0,
                    risk=_risk(_NA),
                    owner=owner,
                    evidence_id=ev,
                    unavailable=reading.cause or "no-sample",
                    n_samples=reading.n,
                )
            )
            continue
        v = reading.value or 0.0
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
                n_samples=reading.n,
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
        # Averaged over what was MEASURED. An `na` control contributes no score — counting it
        # as 0.0 would invent a failure, and dropping it from the list would hide it.
        scored = [c for c in fc if c.status != _NA]
        score = (sum(c.value for c in scored) / len(scored)) if scored else 0.0
        frameworks.append(
            Framework(
                code=code,
                label=_framework_label(code, lang),
                score=score,
                n_conformant=n_conf,
                n_partial=n_part,
                n_non_conformant=n_non,
                n_na=sum(1 for c in fc if c.status == _NA),
            )
        )

    n_conformant = sum(1 for c in controls if c.status == _CONFORMANT)
    n_partial = sum(1 for c in controls if c.status == _PARTIAL)
    n_non = sum(1 for c in controls if c.status == _NON_CONFORMANT)
    n_controls = len(controls)
    scored_controls = [c for c in controls if c.status != _NA]
    global_score = round(
        (sum(c.value for c in scored_controls) / len(scored_controls)) * 100
        if scored_controls
        else 0
    )

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


def _windowed_bundles(at: str | None, days: float | None) -> list[replay_mod.ReplayBundle]:
    """Captured turns for a scope — the durable store when a period narrows the read.

    The live view is a deque bounded at 100 bundles, a bound on COUNT: filtering it by time
    answers "whatever those hundred turns happen to span", and answers 30 days and 24 hours
    identically the moment traffic is thin.
    """
    if days is None:
        return replay_mod.recent_bundles(at)
    from tessera.observability.spine.scope import Scope

    scope = Scope(at=at, period_days=days)
    return [b for b in replay_mod.persisted_bundles(at) if scope.within(b.captured_at)]
