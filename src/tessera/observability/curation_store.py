"""Real source for the eval-set curation decision core (page #12).

The Curation page was a full fixture. This module makes its **decision core** real,
mirroring :mod:`tessera.observability.operator_items` exactly:

* **candidates** are the real failed evaluation cases from each agent's latest
  catalogue run (:func:`tessera.observability.eval_data.load_eval_snapshot`) - a
  failing case is a genuine candidate to curate into the eval set, carrying its
  category, language, title and the time it ran;
* per-candidate **decision** (pending / promote / review / reject) is persisted to
  a durable JSON next to the guard audit log and mutated by the curation endpoint,
  so "Promouvoir", "Revoir" and "Rejeter" actually change state and survive a
  restart.

The curation category and risk tier are derived deterministically from the real
case category (never a fabricated per-case ML score). ``now``-relative fields are
computed on read. Free-text is ASCII-only (accents allowed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability.eval_data import load_eval_snapshot
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CurationCandidate",
    "DECISIONS",
    "available_candidate_ids",
    "decision_counts",
    "load_candidates",
    "set_decision",
]

DECISIONS = ("pending", "promote", "review", "reject")
_DEFAULT_DECISION = "pending"

# case category -> the curation dimension shown on the page (stable enum keys the
# frontend maps to localized labels + colours).
_CURATION_CATEGORY: dict[str, str] = {
    "hallucination": "hallucination",
    "citation_fabrication": "grounding",
    "regulatory_misstatement": "conformite",
    "policy_violation": "conformite",
    "pii_leak": "pii_securite",
    "prompt_injection": "pii_securite",
    "tool_misuse": "outils",
    "language_mixing": "multilingue",
    "escalation_failure": "autres",
    "overconfidence": "autres",
}

# case category -> curation risk tier (crit/high/mod/low), same tiers as the triage
# queue so the two views agree on what is urgent.
_PRIORITY: dict[str, str] = {
    "prompt_injection": "crit",
    "pii_leak": "crit",
    "policy_violation": "high",
    "regulatory_misstatement": "high",
    "citation_fabrication": "high",
    "tool_misuse": "high",
    "hallucination": "mod",
    "escalation_failure": "mod",
    "overconfidence": "low",
    "language_mixing": "low",
}

# risk tier -> a representative 0-100 curation-priority indicator. This is a
# deterministic mapping from the real category, NOT a fabricated per-case score.
_TIER_SCORE: dict[str, int] = {"crit": 92, "high": 82, "mod": 72, "low": 62}
_TIER_RISK: dict[str, str] = {"crit": "eleve", "high": "eleve", "mod": "moyen", "low": "bas"}


@dataclass(frozen=True, slots=True)
class CurationCandidate:
    """One real curation candidate derived from a failed evaluation case.

    ``agent_id`` is the agent whose *own* eval run produced the failure - real
    per-agent attribution, not a fabricated split. ``decision`` and ``decided_by``
    are the durable state mutated by the curation endpoint.
    """

    candidate_id: str
    agent_id: str
    case_id: str
    category: str  # real eval category
    curation_category: str  # curation dimension (mapped)
    title: str
    language: str
    priority: str  # crit/high/mod/low
    score: int  # 0-100 tier indicator (derived from category, not fabricated)
    risk: str  # eleve/moyen/bas
    created_at: datetime
    needs_escalation: bool
    decision: str  # pending/promote/review/reject (durable)
    decided_by: str  # durable; "" when undecided


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "curation_decisions.json"


def _load_state() -> dict[str, dict[str, str]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, str]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


def set_decision(candidate_id: str, *, decision: str, decided_by: str = "") -> None:
    """Persist a curation decision for one candidate (idempotent per candidate).

    Args:
        candidate_id: The candidate whose decision to set.
        decision: One of :data:`DECISIONS` (invalid values are ignored).
        decided_by: The actor recording the decision (durable; "" to leave as-is).
    """
    if decision not in DECISIONS:
        return
    state = _load_state()
    entry = state.get(candidate_id, {"decision": _DEFAULT_DECISION, "decided_by": ""})
    entry["decision"] = decision
    if decided_by:
        entry["decided_by"] = decided_by
    state[candidate_id] = entry
    _save_state(state)


def _parse_dt(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _agent_targets(agent_id: str | None) -> list[str]:
    """Which agents to source candidates from: one, or the whole registered fleet."""
    from tessera.agent.registry import list_agents

    if agent_id:
        return [agent_id]
    return [a.id for a in list_agents()]


def load_candidates(agent_id: str | None = None) -> list[CurationCandidate]:
    """Derive real curation candidates from failed eval cases, per-agent attributed.

    Each candidate is a case that *this agent's own eval run* failed - real
    attribution, so the curation backlog can be ventilated by agent. With
    ``agent_id`` set, only that agent's candidates are returned; ``None``
    aggregates the whole fleet. An agent with no eval run contributes nothing.
    """
    state = _load_state()
    out: list[CurationCandidate] = []
    for aid in _agent_targets(agent_id):
        try:
            snap = load_eval_snapshot(aid)
        except FileNotFoundError:
            continue  # no run for this agent -> no candidates (never fabricate)
        if snap.agent_id != aid:
            continue
        for s in snap.sessions:
            if s.passed:
                continue
            candidate_id = f"{aid}.{s.case_id}.{s.language}"
            st = state.get(candidate_id, {})
            tier = _PRIORITY.get(s.category, "mod")
            out.append(
                CurationCandidate(
                    candidate_id=candidate_id,
                    agent_id=aid,
                    case_id=s.case_id,
                    category=s.category,
                    curation_category=_CURATION_CATEGORY.get(s.category, "autres"),
                    title=s.title,
                    language=s.language,
                    priority=tier,
                    score=_TIER_SCORE.get(tier, 72),
                    risk=_TIER_RISK.get(tier, "moyen"),
                    created_at=_parse_dt(s.started_at),
                    needs_escalation=s.needs_escalation,
                    decision=st.get("decision", _DEFAULT_DECISION),
                    decided_by=st.get("decided_by", ""),
                )
            )
    # Most urgent first: crit < high < mod < low, then highest score, then oldest.
    order = {"crit": 0, "high": 1, "mod": 2, "low": 3}
    out.sort(key=lambda c: (order.get(c.priority, 9), -c.score, c.created_at))
    return out


def decision_counts(agent_id: str | None = None) -> dict[str, int]:
    """Return the real tally per decision (pending/promote/review/reject) + total."""
    counts = {d: 0 for d in DECISIONS}
    candidates = load_candidates(agent_id)
    for c in candidates:
        counts[c.decision] = counts.get(c.decision, 0) + 1
    counts["total"] = len(candidates)
    return counts


def available_candidate_ids() -> set[str]:
    """The set of known candidate ids across the whole fleet (endpoint validation)."""
    return {c.candidate_id for c in load_candidates()}
