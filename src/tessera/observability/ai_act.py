"""EU AI Act compliance observability (ADR 0010, idea #76).

A customer-facing banking chatbot is a *limited-risk* AI system under the EU AI
Act, which triggers transparency obligations (Art. 50 — disclose that the user is
interacting with AI) on top of the cross-cutting duties of human oversight,
logging/traceability, and risk management. Compliance is not a one-off audit; it
is a *posture* that can silently regress (a disclosure toggled off, the audit
chain broken). This module turns that posture into an observable checklist.

:func:`assess_compliance` is pure over an :class:`AIActSignals` snapshot and
returns each obligation's status with the evidence behind it, plus an overall
compliance rate. The endpoint assembles the snapshot from the disclosure config,
the audit trail (oversight / escalation events, integrity), and the consent /
erasure machinery already in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["AIActReport", "AIActSignals", "Obligation", "assess_compliance"]

_RISK_CLASS = "limited"  # customer-facing chatbot under the EU AI Act


@dataclass(frozen=True, slots=True)
class AIActSignals:
    """The compliance signal snapshot."""

    disclosure_enabled: bool = False
    n_turns: int = 0
    oversight_events: int = 0  # human escalations / overrides observed
    escalation_available: bool = True
    audit_present: bool = False
    audit_chain_verified: bool = False
    data_governance_enabled: bool = True  # consent + erasure (ADR 0007)


@dataclass(frozen=True, slots=True)
class Obligation:
    """One AI Act obligation and whether it is currently met."""

    name: str
    article: str
    satisfied: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class AIActReport:
    """The system's AI Act compliance posture."""

    risk_class: str
    n_obligations: int
    n_satisfied: int
    compliance_rate: float
    obligations: list[Obligation] = field(default_factory=list)


def assess_compliance(signals: AIActSignals) -> AIActReport:
    """Assess the AI Act compliance posture from the signal snapshot."""
    obligations = [
        Obligation(
            name="Transparency disclosure",
            article="Art. 50",
            satisfied=signals.disclosure_enabled,
            evidence=(
                "AI-interaction disclosure active"
                if signals.disclosure_enabled
                else "disclosure NOT shown to users"
            ),
        ),
        Obligation(
            name="Human oversight",
            article="Art. 14",
            satisfied=signals.escalation_available,
            evidence=(f"escalation path available; {signals.oversight_events} oversight event(s)"),
        ),
        Obligation(
            name="Logging & traceability",
            article="Art. 12",
            satisfied=signals.audit_present and signals.audit_chain_verified,
            evidence=(
                "tamper-evident audit chain verified"
                if signals.audit_present and signals.audit_chain_verified
                else "audit trail missing or chain broken"
            ),
        ),
        Obligation(
            name="Risk classification logged",
            article="Annex III",
            satisfied=True,
            evidence=f"classified as {_RISK_CLASS}-risk and logged",
        ),
        Obligation(
            name="Data governance (consent + erasure)",
            article="Art. 10 / GDPR",
            satisfied=signals.data_governance_enabled,
            evidence=(
                "per-subject consent and Art. 17 erasure enforced"
                if signals.data_governance_enabled
                else "data governance not enforced"
            ),
        ),
    ]

    n_satisfied = sum(1 for o in obligations if o.satisfied)
    return AIActReport(
        risk_class=_RISK_CLASS,
        n_obligations=len(obligations),
        n_satisfied=n_satisfied,
        compliance_rate=n_satisfied / len(obligations) if obligations else 0.0,
        obligations=obligations,
    )
