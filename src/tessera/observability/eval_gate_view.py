"""Policy-correct eval-gate view at the (case, langue) grain.

This is the computation hub behind the Evaluations page's gate section. It binds
three real sources — the agent's evaluation run (per ``(case, language)``
result), the versioned three-tier map (:mod:`eval_tiers`) and the governed waiver
store (:mod:`eval_waivers`) — and produces the verdict, breakdown, socle / hors-
socle split, the structural Venn, the critical-cases table and the active-waiver
registry, **all reconciled at one directing grain**.

The binding contract is ``docs/design/eval-gate-policy.md`` (it primes over the
normative image for verdict + numbers). Every count here is derived from the run
— nothing is fabricated. The gate is recomputed from first principles (it does
not trust the report's pre-baked two-level ``gate`` block), so the three tiers,
the per-(case, langue) grain and the waivers are all honoured.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from eval.sets import load_eval_set
from tessera.observability.eval_tiers import Tier, load_tier_map
from tessera.observability.eval_waivers import EffectiveWaiver, effective_waivers

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.eval_data import EvalSnapshot

_FAILURES_DIR = Path(__file__).resolve().parents[3] / "eval" / "failures"

__all__ = ["GateCaseStatus", "GateView", "build_gate_view", "structural_gate"]

# Per-(case, language) gate status keys, with French labels + a tone the
# frontend styles. These are the cells of the critical-cases table.
_STATUS_LABEL: dict[str, tuple[str, str]] = {
    "conforme": ("Conforme", "good"),
    "bloquant_socle": ("Bloquant · socle (T0)", "crit"),
    "bloquant_t1": ("Bloquant · critique (T1)", "crit"),
    "deroge_actif": ("Dérogé actif", "warn"),
    "echec_domaine": ("Échec · domaine (T2)", "bad"),
    "non_execute": ("Non exécuté", "crit"),
}


@dataclass(frozen=True, slots=True)
class GateCaseStatus:
    """One (case, language) execution, classified against the policy."""

    case_id: str
    language: str
    category: str
    tier: Tier
    socle: bool
    passed: bool
    executed: bool
    waiver_active: bool
    status_key: str

    @property
    def status_label(self) -> str:
        """French status label for the table cell."""
        return _STATUS_LABEL[self.status_key][0]

    @property
    def status_tone(self) -> str:
        """Tone key for the table cell."""
        return _STATUS_LABEL[self.status_key][1]

    @property
    def is_critical(self) -> bool:
        """T0 or T1 — blocking by default."""
        return self.tier in ("T0", "T1")

    @property
    def blocking(self) -> bool:
        """Whether this execution actually blocks the gate."""
        return self.status_key in ("bloquant_socle", "bloquant_t1", "non_execute")


@dataclass(slots=True)
class GateView:
    """Everything the Evaluations gate section needs, reconciled at one grain."""

    passed: bool
    verdict_label: str
    verdict_tone: str
    verdict_reason: str
    candidate_version: str
    statuses: list[GateCaseStatus]
    waivers: list[EffectiveWaiver]
    min_pass_rate: float
    # Grains (policy §4): three distinct populations, shown distinctly.
    executions: int = 0
    distinct_cases: int = 0
    socle_cases: int = 0
    # Reconciled counts (case, langue grain).
    passed_exec: int = 0
    failed_exec: int = 0
    socle_total: int = 0
    socle_passed: int = 0
    socle_ok: bool = True
    domain_total: int = 0
    domain_passed: int = 0
    domain_ok: bool = True
    # Critical breakdown (policy section 6) at case, langue grain.
    blocking_socle: int = 0
    blocking_t1: int = 0
    waived_active: int = 0
    non_executed_critical: int = 0
    # Tier partition (case, langue): sums to executions.
    tier_counts: dict[str, int] = field(default_factory=dict)

    @property
    def domain_pass_rate(self) -> float:
        """T2 pass rate (1.0 when there are no T2 executions)."""
        return self.domain_passed / self.domain_total if self.domain_total else 1.0


def _expected_universe(snap: EvalSnapshot) -> set[tuple[str, str]]:
    """The ``(case, language)`` pairs the run was supposed to cover.

    Derived from the bound eval set's effective case ids crossed with each case's
    configured prompt languages — so a *missing* result is a real "non exécuté"
    (absence of proof = blocking), not silently dropped.
    """
    try:
        eval_set = load_eval_set(snap.eval_set)
    except (KeyError, ValueError, OSError):
        return {(s.case_id, s.language) for s in snap.sessions}
    universe: set[tuple[str, str]] = set()
    for cid in eval_set.effective_case_ids:
        path = _FAILURES_DIR / f"{cid}.json"
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # best-effort: skip an unreadable/corrupt case JSON — non-gating read (0015)
            continue
        prompts = case.get("prompts") if isinstance(case, dict) else None
        if isinstance(prompts, dict):
            for lang in prompts:
                universe.add((cid, str(lang)))
    return universe or {(s.case_id, s.language) for s in snap.sessions}


def _verdict(
    *, socle_ok: bool, t1_unwaived: int, non_exec_crit: int, domain_ok: bool
) -> tuple[bool, str, str, str]:
    """Return (passed, label, tone, reason) per the policy's gate formula."""
    if not socle_ok or non_exec_crit:
        if not socle_ok:
            reason = "Un cas du socle dur (T0) a échoué ou n'a pas été exécuté."
        else:
            reason = "Un cas critique n'a pas été exécuté (absence de preuve = bloquant)."
        return False, "BLOQUÉ par le socle", "crit", reason
    if t1_unwaived:
        reason = (
            f"{t1_unwaived} cas critique(s) dérogeable(s) (T1) en échec sans dérogation " "active."
        )
        return False, "BLOQUÉ (critiques non dérogés)", "crit", reason
    if not domain_ok:
        reason = "Le taux de réussite du domaine (T2) est sous le seuil requis."
        return False, "BLOQUÉ (domaine)", "bad", reason
    return True, "PASSE", "good", "Socle intact, aucun critique non dérogé, domaine conforme."


def structural_gate(
    results: Sequence[tuple[str, str, bool]], *, min_pass_rate: float
) -> dict[str, object]:
    """The tier-aware **structural** gate, at the (case, langue) grain — no waivers.

    This is the policy-shaped gate the *run itself* can carry (stamped into the
    report by the eval runner), so the report is authoritative for the structural
    verdict instead of the cruder two-level block. It deliberately excludes
    waivers and expiry: those are **dynamic** (clock-dependent) and resolved at
    render by :func:`build_gate_view`, which layers the active-waiver delta on top
    of this same tier classification. ``results`` are ``(case_id, language,
    passed)`` triples for the reference run.
    """
    tiers = load_tier_map()
    counts = {"T0": 0, "T1": 0, "T2": 0}
    socle_total = socle_passed = 0
    domain_total = domain_passed = 0
    blocking_socle = blocking_t1 = 0
    for case_id, _lang, passed in results:
        tier = tiers.tier_of(case_id)
        counts[tier] += 1
        if tier == "T0":
            socle_total += 1
            socle_passed += int(passed)
            blocking_socle += int(not passed)
        elif tier == "T1":
            blocking_t1 += int(not passed)
        else:
            domain_total += 1
            domain_passed += int(passed)
    socle_ok = socle_total > 0 and socle_passed == socle_total
    domain_rate = domain_passed / domain_total if domain_total else 1.0
    domain_ok = domain_rate >= min_pass_rate
    passed, label, tone, reason = _verdict(
        socle_ok=socle_ok, t1_unwaived=blocking_t1, non_exec_crit=0, domain_ok=domain_ok
    )
    return {
        "grain": "case_language",
        "passed": passed,
        "label": label,
        "tone": tone,
        "reason": reason,
        "min_pass_rate": min_pass_rate,
        "tier_counts": counts,
        "executions": sum(counts.values()),
        "socle": {"ok": socle_ok, "passed": socle_passed, "total": socle_total},
        "domain": {
            "ok": domain_ok,
            "passed": domain_passed,
            "total": domain_total,
            "rate": round(domain_rate, 4),
        },
        "breakdown": {"blocking_socle": blocking_socle, "blocking_t1": blocking_t1},
        "note": "Gate structurel (sans dérogations) ; les dérogations sont résolues au rendu.",
    }


def build_gate_view(snap: EvalSnapshot, *, now: datetime | None = None) -> GateView:
    """Compute the full policy-correct gate view from a real run + tiers + waivers."""
    clock = now or datetime.now(UTC)
    tiers = load_tier_map()
    candidate = snap.run_at
    waivers = effective_waivers(candidate, now=clock)
    active_waiver_keys = {
        (w.event.case_id, w.event.language, w.event.candidate_version) for w in waivers if w.active
    }

    def waiver_active(case_id: str, language: str) -> bool:
        return (case_id, language, candidate) in active_waiver_keys or (
            case_id,
            "*",
            candidate,
        ) in active_waiver_keys

    present = {(s.case_id, s.language) for s in snap.sessions}
    expected = _expected_universe(snap)
    statuses: list[GateCaseStatus] = []

    for s in snap.sessions:
        tier = tiers.tier_of(s.case_id)
        socle = tier == "T0"
        w_active = tier == "T1" and waiver_active(s.case_id, s.language)
        if s.passed:
            key = "conforme"
        elif tier == "T0":
            key = "bloquant_socle"
        elif tier == "T1":
            key = "deroge_actif" if w_active else "bloquant_t1"
        else:
            key = "echec_domaine"
        statuses.append(
            GateCaseStatus(
                case_id=s.case_id,
                language=s.language,
                category=s.category,
                tier=tier,
                socle=socle,
                passed=s.passed,
                executed=True,
                waiver_active=w_active,
                status_key=key,
            )
        )

    # Non exécuté (expected but absent) — absence of proof is blocking if critical.
    for cid, lang in sorted(expected - present):
        tier = tiers.tier_of(cid)
        statuses.append(
            GateCaseStatus(
                case_id=cid,
                language=lang,
                category="",
                tier=tier,
                socle=tier == "T0",
                passed=False,
                executed=False,
                waiver_active=False,
                status_key="non_execute",
            )
        )

    # -- Reconciled aggregates (case, langue grain) ──────────────────────────
    executions = len(statuses)
    distinct_cases = len({s.case_id for s in statuses})
    socle_cases = len({s.case_id for s in statuses if s.socle})
    passed_exec = sum(1 for s in statuses if s.passed)
    failed_exec = executions - passed_exec

    socle_st = [s for s in statuses if s.socle]
    socle_total = len(socle_st)
    socle_passed = sum(1 for s in socle_st if s.passed)
    socle_ok = all(s.passed and s.executed for s in socle_st)

    domain_st = [s for s in statuses if s.tier == "T2"]
    domain_total = len(domain_st)
    domain_passed = sum(1 for s in domain_st if s.passed)
    domain_rate = domain_passed / domain_total if domain_total else 1.0
    min_rate_or_none = snap.gate_min_pass_rate
    domain_ok = min_rate_or_none is None or domain_rate >= min_rate_or_none

    blocking_socle = sum(1 for s in statuses if s.status_key == "bloquant_socle")
    blocking_t1 = sum(1 for s in statuses if s.status_key == "bloquant_t1")
    waived_active = sum(1 for s in statuses if s.status_key == "deroge_actif")
    non_executed_critical = sum(
        1 for s in statuses if s.status_key == "non_execute" and s.is_critical
    )

    tier_counts = {
        "T0": sum(1 for s in statuses if s.tier == "T0"),
        "T1": sum(1 for s in statuses if s.tier == "T1"),
        "T2": sum(1 for s in statuses if s.tier == "T2"),
    }

    min_rate = snap.gate_min_pass_rate if snap.gate_min_pass_rate is not None else 0.0
    passed, label, tone, reason = _verdict(
        socle_ok=socle_ok,
        t1_unwaived=blocking_t1,
        non_exec_crit=non_executed_critical,
        domain_ok=domain_ok,
    )

    return GateView(
        passed=passed,
        verdict_label=label,
        verdict_tone=tone,
        verdict_reason=reason,
        candidate_version=candidate,
        statuses=statuses,
        waivers=waivers,
        min_pass_rate=min_rate,
        executions=executions,
        distinct_cases=distinct_cases,
        socle_cases=socle_cases,
        passed_exec=passed_exec,
        failed_exec=failed_exec,
        socle_total=socle_total,
        socle_passed=socle_passed,
        socle_ok=socle_ok,
        domain_total=domain_total,
        domain_passed=domain_passed,
        domain_ok=domain_ok,
        blocking_socle=blocking_socle,
        blocking_t1=blocking_t1,
        waived_active=waived_active,
        non_executed_critical=non_executed_critical,
        tier_counts=tier_counts,
    )
