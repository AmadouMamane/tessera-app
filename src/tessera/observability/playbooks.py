"""AI-specific incident playbooks (ADR 0010, idea #115).

Generic SRE runbooks do not cover the failure modes unique to an LLM agent: a
hallucination spike, a jailbreak getting through, a PII leak, a token-cost
runaway. This module encodes those as *playbooks* and, crucially, wires them to
the live signals the rest of the observability layer already computes — so the
dashboard does not just say "quality is down", it surfaces the matching incident
with concrete remediation steps and a severity.

:func:`trigger_playbooks` is a pure function over a :class:`PlaybookSignals`
snapshot; the endpoint assembles that snapshot from the score buffer, the
red-team snapshots, the PII-leak scan and the cost-anomaly detector. Only
playbooks whose trigger condition is met are returned, most severe first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Playbook", "PlaybookReport", "PlaybookSignals", "trigger_playbooks"]

_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1}


@dataclass(frozen=True, slots=True)
class PlaybookSignals:
    """The live signal snapshot the playbooks fire on, and how much each one saw.

    **Every rate needs its sample size, and only one had it.** `low_score_rate` was guarded by
    `n_scores > 0`; the other three were not, so with no data at all they read 0.0, 0.0 and 0,
    nothing fired, and the page said "0 incidents". That is not a false alarm — it is the
    opposite, and worse: a clean bill issued over an empty window, indistinguishable on screen
    from a genuinely quiet fleet.

    The demo made it concrete. The last conversation is 2026-07-24 and the page reads a 7-day
    window, so on 2026-08-01 every bundle-derived signal saw zero turns and the incident panel
    reported peace. ADR 0026: a witness that cannot see reports a blind spot; it may not report
    "ok". So each family now carries what it looked at, and the report says how many families
    could not look.
    """

    low_score_rate: float = 0.0  # share of recent turns below the faithfulness bar
    n_scores: int = 0
    jailbreak_success_rate: float = 0.0  # latest red-team attack-success rate
    #: Red-team snapshots available. The rate is the LATEST one, so zero snapshots is not a
    #: zero rate — it is no rate at all, and the guard below refuses to read it as safety.
    n_snapshots: int = 0
    pii_leak_rate: float = 0.0
    cost_anomalies: int = 0
    #: Captured turns behind `pii_leak_rate` and `cost_anomalies`. Both derive from the same
    #: bundle set, so one count serves both.
    n_turns: int = 0


@dataclass(frozen=True, slots=True)
class Playbook:
    """A triggered incident playbook."""

    incident: str
    severity: str
    trigger: str
    steps: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PlaybookReport:
    """The incident playbooks currently triggered, and what could not be examined.

    ``n_unmeasured`` is the load-bearing field. `n_triggered: 0` means "no incident fired";
    combined with `n_unmeasured: 3` it means "no incident fired, and three of the four families
    had nothing to fire on" — the same digit, opposite meanings, and the surface could not tell
    them apart until this existed.
    """

    n_triggered: int
    playbooks: list[Playbook] = field(default_factory=list)
    #: Signal families with an empty sample. They cannot trigger, and their silence is not news.
    unmeasured: list[str] = field(default_factory=list)
    n_unmeasured: int = 0


# Thresholds at which each incident fires.
_HALLUCINATION_RATE = 0.30
_JAILBREAK_RATE = 0.20
_PII_RATE = 0.0  # any output PII leak is an incident


def _severity(value: float, *, high: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= high:
        return "high"
    return "medium"


def trigger_playbooks(signals: PlaybookSignals) -> PlaybookReport:
    """Return the incident playbooks triggered by the current signals.

    Each family is gated on its own sample size. A family with no sample is reported as
    unmeasured rather than silently contributing a zero to the "no incident" verdict.
    """
    playbooks: list[Playbook] = []
    unmeasured: list[str] = []
    if signals.n_scores <= 0:
        unmeasured.append("hallucination")
    if signals.n_snapshots <= 0:
        unmeasured.append("jailbreak")
    if signals.n_turns <= 0:
        unmeasured += ["pii_leak", "cost"]

    if signals.n_scores > 0 and signals.low_score_rate > _HALLUCINATION_RATE:
        playbooks.append(
            Playbook(
                incident="Hallucination / quality spike",
                severity=_severity(signals.low_score_rate, high=0.30, critical=0.50),
                trigger=f"{round(signals.low_score_rate * 100)}% of turns below the SLO",
                steps=[
                    "Check recent model / prompt / policy changes (lineage, what-changed #17).",
                    "Inspect low-scoring traces in Phoenix and the replay panel.",
                    "Freeze deploys until the error budget recovers (SLO #15).",
                    "Curate the worst turns into eval/failures (#123).",
                ],
            )
        )

    if signals.n_snapshots > 0 and signals.jailbreak_success_rate > _JAILBREAK_RATE:
        playbooks.append(
            Playbook(
                incident="Jailbreak / guard bypass",
                severity=_severity(signals.jailbreak_success_rate, high=0.20, critical=0.40),
                trigger=f"attack-success rate {round(signals.jailbreak_success_rate * 100)}%",
                steps=[
                    "Review bypassed adversarial samples (red-team #24).",
                    "Tighten the guard deny patterns / add the bypass to the policy.",
                    "Re-run the adversarial corpus to confirm the gap is closed.",
                    "Escalate to the security on-call if account-action tools were reached.",
                ],
            )
        )

    if signals.n_turns > 0 and signals.pii_leak_rate > _PII_RATE:
        playbooks.append(
            Playbook(
                incident="PII leak in output",
                severity="critical",
                trigger=f"output PII-leak rate {round(signals.pii_leak_rate * 100)}%",
                steps=[
                    "Identify the leaked entities and the source turns (PII-leak #38).",
                    "Verify the output guard / redaction is active on the affected path.",
                    "Notify the DPO; assess GDPR breach-notification obligations.",
                    "Purge the affected telemetry (erasure #180) once captured.",
                ],
            )
        )

    if signals.n_turns > 0 and signals.cost_anomalies > 0:
        playbooks.append(
            Playbook(
                incident="Token-cost runaway",
                severity="high" if signals.cost_anomalies > 1 else "medium",
                trigger=f"{signals.cost_anomalies} token-burn anomaly turn(s)",
                steps=[
                    "Inspect the outlier turns (cost anomaly #33).",
                    "Check for an injection loop re-feeding context or a runaway generation.",
                    "Confirm per-turn token budgets / max-output caps are enforced.",
                ],
            )
        )

    playbooks.sort(key=lambda p: _SEVERITY_RANK.get(p.severity, 0), reverse=True)
    return PlaybookReport(
        n_triggered=len(playbooks),
        playbooks=playbooks,
        unmeasured=unmeasured,
        n_unmeasured=len(unmeasured),
    )
