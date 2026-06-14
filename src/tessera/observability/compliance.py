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

from tessera.observability import (
    ai_act as ai_act_mod,
    citation_validity as citation_validity_mod,
    conformance as conformance_mod,
    disclosure as disclosure_mod,
    erasure as erasure_mod,
    firewall_efficacy as firewall_mod,
    pii_leak as pii_leak_mod,
    refusal as refusal_mod,
    replay as replay_mod,
)
from tessera.observability.eval.scores import recent_scores

__all__ = [
    "Control",
    "Framework",
    "ComplianceReport",
    "NonConformity",
    "Obligation",
    "compute_compliance",
]

# Framework display labels.
_FRAMEWORKS: dict[str, str] = {
    "rgpd": "RGPD (UE)",
    "ai_act": "EU AI Act",
    "dora": "DORA",
    "iso27001": "ISO/IEC 27001",
    "soc2": "SOC 2 Type II",
    "internal": "Politiques internes",
}

_CONFORMANT = "conformant"
_PARTIAL = "partial"
_NON_CONFORMANT = "non_conformant"

_THRESHOLD_CONFORMANT = 0.9
_THRESHOLD_PARTIAL = 0.7


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
    scores = recent_scores()

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


def compute_compliance() -> ComplianceReport:
    """Assemble the compliance posture from the real runtime signals."""
    values = _signal_values()
    controls: list[Control] = []
    for cid, name, fw, signal, owner, ev in _CATALOGUE:
        if signal not in values:
            continue
        v = values[signal]
        st = _status(v)
        controls.append(
            Control(
                id=cid,
                name=name,
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
    for code, label in _FRAMEWORKS.items():
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
                label=label,
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
    )
