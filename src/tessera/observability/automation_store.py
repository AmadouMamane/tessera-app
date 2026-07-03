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
    "AutomationRule",
    "available_rule_ids",
    "evaluate_rules",
    "list_rule_states",
    "load_runs",
    "set_rule_enabled",
]

_MAX_RUNS = 400
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


def _rules_path() -> Path:
    return get_settings().guard.audit_file.parent / "automation_rules.json"


def _runs_path() -> Path:
    return get_settings().guard.audit_file.parent / "automation_runs.json"


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
    return entries
