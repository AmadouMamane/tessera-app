"""Durable automation rules + execution journal (create-the-source, page #13).

The Automations page needed a real rule/execution subsystem. This module IS
that source, scoped honestly to what this build can truly automate:

* the **rules** are code-defined (like the RBAC roles): each one evaluates a
  REAL condition against the owned stores — the eval release gate, the audit
  chain, the captured low-faithfulness turns, the guard deny volume and the
  curation backlog. No rule invents data; each evaluation reads the live store
  and reports the observed value.
* each rule's **enabled** flag is durable (``automation_rules.json``), mutated
  by the rule-state endpoint;
* every **evaluation actually executed** (via ``POST
  /observability/automations/evaluate``) is journalled durably
  (``automation_runs.json``) with the observed value, whether the rule fired
  and how long the check took — the page's execution figures grow only from
  real evaluations, never from invented counters.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = [
    "RULES",
    "ApprovalNotPendingError",
    "AutomationRule",
    "approvals_as_of",
    "available_rule_ids",
    "decide_approval",
    "evaluate_rules",
    "list_rule_states",
    "load_approvals",
    "load_runs",
    "pending_approvals",
    "rule_states_as_of",
    "set_rule_enabled",
]

_MAX_RUNS = 400
_MAX_APPROVALS = 200
_LOW_FAITH_THRESHOLD = 0.80
_LOW_FAITH_MIN = 3
_DENY_SPIKE_MIN = 50
_CURATION_BACKLOG_MIN = 20


@dataclass(frozen=True, slots=True)
class AutomationRule:
    """One code-defined automation rule over a real store."""

    id: str
    type: str  # qualite / securite / conformite / memoire / cout
    mode: str  # auto | approb
    role: str  # required role to act on the outcome
    severity: str  # critique / eleve / moyen when fired
    check: Callable[[], tuple[bool, str]]  # -> (fired, observed value)


def _check_gate() -> tuple[bool, str]:
    """Any agent whose LATEST eval run failed the release gate?"""
    from tessera.agent.registry import list_agents
    from tessera.observability.eval_data import load_agent_run_history

    failing: list[str] = []
    for agent in list_agents():
        history = load_agent_run_history(agent.id, limit=1)
        if history and history[0].gate_passed is False:
            failing.append(agent.id)
    return bool(failing), f"gate FAIL: {', '.join(failing) if failing else '0'}"


def _check_chain() -> tuple[bool, str]:
    """Is the tamper-evident audit chain broken?"""
    from tessera.guard.ledger_store import verify_active_ledger

    status = verify_active_ledger()
    if status.verified:
        return False, f"chain OK ({status.length})"
    return True, f"chain broken @ {status.broken_at}"


def _check_low_faith() -> tuple[bool, str]:
    """Enough low-faithfulness turns captured to warrant a review?"""
    from tessera.observability.replay import recent_bundles

    low = sum(
        1
        for b in recent_bundles()
        if getattr(b, "original_score", 1.0) is not None
        and float(getattr(b, "original_score", 1.0)) < _LOW_FAITH_THRESHOLD
    )
    return low >= _LOW_FAITH_MIN, f"{low} turns < {_LOW_FAITH_THRESHOLD}"


def _check_deny_spike() -> tuple[bool, str]:
    """Guard denies in the last 24h above the notification threshold?"""
    from tessera.guard.ledger_store import read_ledger_entries

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    denies = 0
    for entry in read_ledger_entries():
        if entry.get("type") != "tessera.guard.audit":
            continue
        decisions = entry.get("decisions")
        for dec in decisions if isinstance(decisions, list) else []:
            if not isinstance(dec, dict) or dec.get("decision") != "deny":
                continue
            raw = dec.get("occurred_at") or entry.get("occurred_at")
            try:
                when = datetime.fromisoformat(str(raw))
            except (ValueError, TypeError):
                # best-effort: skip a deny row with a bad timestamp — non-gating read (0015)
                continue
            when = when if when.tzinfo else when.replace(tzinfo=UTC)
            if when >= cutoff:
                denies += 1
    return denies >= _DENY_SPIKE_MIN, f"{denies} denies / 24h"


def _check_curation_backlog() -> tuple[bool, str]:
    """Pending curation candidates above the assignment threshold?"""
    from tessera.observability.curation_store import decision_counts

    pending = decision_counts().get("pending", 0)
    return pending >= _CURATION_BACKLOG_MIN, f"{pending} pending"


RULES: tuple[AutomationRule, ...] = (
    AutomationRule(
        id="gate_freeze",
        type="release",
        mode="auto",
        role="Operator+",
        severity="critique",
        check=_check_gate,
    ),
    AutomationRule(
        id="chain_alert",
        type="conformite",
        mode="auto",
        role="Admin+",
        severity="critique",
        check=_check_chain,
    ),
    AutomationRule(
        id="low_faith_review",
        type="qualite",
        mode="approb",
        role="Operator+",
        severity="eleve",
        check=_check_low_faith,
    ),
    AutomationRule(
        id="deny_spike",
        type="securite",
        mode="auto",
        role="Operator+",
        severity="eleve",
        check=_check_deny_spike,
    ),
    AutomationRule(
        id="curation_backlog",
        type="qualite",
        mode="approb",
        role="Compliance+",
        severity="moyen",
        check=_check_curation_backlog,
    ),
)


class ApprovalNotPendingError(KeyError):
    """Deciding an approval that is unknown or already decided — said loudly.

    Raised instead of returning a bare ``bool`` (the verdict-debt freeze): the
    refusal names the approval it is about, and a decision that changed nothing
    can never be recorded as if it had.
    """


def _rules_path() -> Path:
    return get_settings().guard.audit_file.parent / "automation_rules.json"


def _runs_path() -> Path:
    return get_settings().guard.audit_file.parent / "automation_runs.json"


def _approvals_path() -> Path:
    return get_settings().guard.audit_file.parent / "automation_approvals.json"


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_rule_states() -> dict[str, bool]:
    """The durable enabled flag per rule (default: enabled)."""
    raw = _load_json(_rules_path(), {})
    raw = raw if isinstance(raw, dict) else {}
    return {rule.id: bool(raw.get(rule.id, {}).get("enabled", True)) for rule in RULES}


def set_rule_enabled(rule_id: str, *, enabled: bool) -> None:
    """Persist a rule's enabled flag (unknown ids are ignored)."""
    if rule_id not in available_rule_ids():
        return
    raw = _load_json(_rules_path(), {})
    raw = raw if isinstance(raw, dict) else {}
    entry = raw.get(rule_id)
    entry = entry if isinstance(entry, dict) else {}
    entry["enabled"] = enabled
    raw[rule_id] = entry
    _save_json(_rules_path(), raw)


def available_rule_ids() -> set[str]:
    """The known rule ids (endpoint validation)."""
    return {rule.id for rule in RULES}


def load_runs() -> list[dict[str, object]]:
    """The journalled evaluations, oldest first (best-effort read)."""
    raw = _load_json(_runs_path(), [])
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def load_approvals() -> list[dict[str, object]]:
    """Every approval request, oldest first (pending and decided alike)."""
    raw = _load_json(_approvals_path(), [])
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def rule_states_as_of(at: str) -> dict[str, bool]:
    """Fold the S1 governance journal to every rule's enabled flag at instant T.

    C1 as-of projection (registre §3): start from the code default (enabled) and
    replay, chronologically, every journalled ``automation.rule_state`` /
    ``automation.rules_state`` mutation at or before T. Only journalled acts are
    visible — which is the point: since ADR 0024 every toggle IS journalled, so
    the fold reconstructs what an operator would have seen at T, provably.
    """
    from tessera.guard.ledger_store import read_ledger_entries
    from tessera.observability._asof import occurred_before

    states = {rule.id: True for rule in RULES}
    events: list[tuple[str, str, dict[str, object]]] = []
    for obj in read_ledger_entries():
        if str(obj.get("type", "")) != "tessera.guard.audit":
            continue
        target = str(obj.get("target", ""))
        if target not in {"automation.rule_state", "automation.rules_state"}:
            continue
        occurred = str(obj.get("occurred_at", ""))
        if not occurred or not occurred_before(occurred, at):
            continue
        args = obj.get("arguments")
        events.append((occurred, target, args if isinstance(args, dict) else {}))
    events.sort(key=lambda e: e[0])
    for _, target, args in events:
        enabled = bool(args.get("enabled", True))
        if target == "automation.rule_state":
            rid = str(args.get("rule", ""))
            if rid in states:
                states[rid] = enabled
        else:
            rules = args.get("rules")
            for rid in rules if isinstance(rules, list) else []:
                if str(rid) in states:
                    states[str(rid)] = enabled
    return states


def approvals_as_of(at: str) -> list[dict[str, object]]:
    """Every approval request as it stood at T (status folded from timestamps).

    A request exists at T once ``requested_at`` ≤ T; its status at T is the
    stored decision only if ``decided_at`` ≤ T — otherwise it was still pending
    at T, whatever happened later.
    """
    from tessera.observability._asof import occurred_before

    out: list[dict[str, object]] = []
    for req in load_approvals():
        if not occurred_before(str(req.get("requested_at", "")), at):
            continue
        entry = dict(req)
        decided_at = req.get("decided_at")
        if not (isinstance(decided_at, str) and occurred_before(decided_at, at)):
            entry["status"] = "pending"
            entry["decided_at"] = None
            entry["decided_by"] = None
        out.append(entry)
    return out


def pending_approvals() -> list[dict[str, object]]:
    """The approval requests still awaiting an operator decision."""
    return [a for a in load_approvals() if a.get("status") == "pending"]


def _record_approval_requests(entries: list[dict[str, object]]) -> None:
    """Open one pending approval per fired ``approb`` rule (idempotent).

    A rule in ``approb`` mode does not act on its own: firing means it
    RECOMMENDS an action and asks an operator. That request is durable — one
    open request per rule at a time, so re-evaluating an unresolved condition
    refreshes nothing and invents nothing.
    """
    approb_rules = {rule.id for rule in RULES if rule.mode == "approb"}
    fired = [e for e in entries if e.get("fired") and str(e.get("rule_id", "")) in approb_rules]
    if not fired:
        return
    approvals = load_approvals()
    open_rules = {str(a.get("rule_id", "")) for a in approvals if a.get("status") == "pending"}
    added = False
    for entry in fired:
        rule_id = str(entry.get("rule_id", ""))
        if rule_id in open_rules:
            continue
        approvals.append(
            {
                "id": f"{rule_id}@{entry.get('at', '')}",
                "rule_id": rule_id,
                "observed": str(entry.get("observed", "")),
                "requested_at": str(entry.get("at", "")),
                "status": "pending",
                "decided_at": None,
                "decided_by": None,
            }
        )
        open_rules.add(rule_id)
        added = True
    if added:
        _save_json(_approvals_path(), approvals[-_MAX_APPROVALS:])


def decide_approval(approval_id: str, *, approved: bool, decided_by: str) -> dict[str, object]:
    """Decide one PENDING approval request, attributed (ADR 0024).

    Args:
        approval_id: The request id, as listed by :func:`pending_approvals`.
        approved: ``True`` approves the recommended action; ``False`` rejects it.
        decided_by: The verified operator principal — no default, ever.

    Returns:
        The decided entry, as stored.

    Raises:
        ApprovalNotPendingError: Unknown id, or a request already decided —
            a second decision must never silently overwrite the first author.
    """
    approvals = load_approvals()
    for entry in approvals:
        if str(entry.get("id")) == approval_id and entry.get("status") == "pending":
            entry["status"] = "approved" if approved else "rejected"
            entry["decided_at"] = datetime.now(UTC).isoformat()
            entry["decided_by"] = decided_by
            _save_json(_approvals_path(), approvals)
            return entry
    raise ApprovalNotPendingError(approval_id)


def evaluate_rules() -> list[dict[str, object]]:
    """Evaluate every ENABLED rule against its real store and journal the runs.

    Returns:
        The journal entries appended by this evaluation (one per enabled rule):
        rule id, whether it fired, the observed real value, and the check
        duration in milliseconds. A rule whose store read fails journals an
        ``error`` result rather than a fabricated outcome.
    """
    states = list_rule_states()
    entries: list[dict[str, object]] = []
    for rule in RULES:
        if not states.get(rule.id, True):
            continue
        started = time.perf_counter()
        try:
            fired, observed = rule.check()
            result = "fired" if fired else "ok"
        except Exception as exc:  # a broken store read is an error, not a guess
            fired, observed, result = False, f"error: {exc}", "error"
        entries.append(
            {
                "rule_id": rule.id,
                "fired": fired,
                "observed": observed,
                "result": result,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "at": datetime.now(UTC).isoformat(),
            }
        )
    runs = load_runs()
    runs.extend(entries)
    _save_json(_runs_path(), runs[-_MAX_RUNS:])
    # A fired approb-mode rule asks a human: open its durable approval request.
    _record_approval_requests(entries)
    return entries
