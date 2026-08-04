"""Shared kernel for the observability route package.

Extracted verbatim from the 3 219-line ``observability.py`` god-router (audit 2026-07-10,
`god-router`). Pure helpers, request models and read-only constants — no routes, so every
surface module can import from here without a cycle.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.observability import (
    business_events as business_events_mod,
    business_scoring as business_scoring_mod,
    failure_clustering as failure_clustering_mod,
)
from tessera.observability.spine.adapters import read_scores

if TYPE_CHECKING:
    from tessera.memory import transcript
    from tessera.observability.replay import ReplayBundle

_CALIBRATION_FILE = (
    Path(__file__).resolve().parents[5] / "eval" / "calibration" / "_calibration.json"
)
_CALIBRATION_JUDGE_MODEL = "llama3.2:3b"
_CONSENSUS_PANEL: tuple[str, ...] = ("llama3.2:3b", "mistral:7b", "gemma3:27b")
_GRAMMAR_EVENT_ORDER = {
    "intent.routed": 10,
    "slots.extracted": 20,
    "business_rule.checked": 30,
    "policy.decision_made": 40,
    "artifact.created": 50,
    "artifact.status_changed": 55,
    "validation.requested": 60,
    "action.requested": 65,
    "action.prepared": 70,
    "action.blocked": 75,
    "message.generated": 80,
}
_SYNTHESE_PERIODS: dict[str, int | None] = {"h24": 1, "d7": 7, "d14": 14, "d30": 30}
_GRANTED_TOOLS = frozenset(
    {"account_balance", "card_block", "transaction_search", "loan_simulate", "ticket_escalate"}
)
_CITATION_SENTENCE = re.compile(r"[^.!?\n]*\bart(?:icle|\.)?\s*\d+[^.!?\n]*", re.IGNORECASE)


def _load_failure_items() -> list[failure_clustering_mod.FailureItem]:
    """Load the documented failures as clustering items (English prompt)."""
    import json
    from pathlib import Path

    items: list[failure_clustering_mod.FailureItem] = []
    failures_dir = Path(__file__).resolve().parents[5] / "eval" / "failures"
    for path in sorted(failures_dir.glob("[0-9]*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # best-effort: skip an unreadable/corrupt failure JSON — non-gating read (0015)
            continue
        prompts = obj.get("prompts", {})
        text = ""
        if isinstance(prompts, dict):
            for lang in ("en", "fr", "de"):
                entry = prompts.get(lang)
                if isinstance(entry, dict) and entry.get("user"):
                    text = str(entry["user"])
                    break
        text = text or str(obj.get("title", ""))
        items.append(
            failure_clustering_mod.FailureItem(
                case_id=str(obj.get("id", path.stem)),
                category=str(obj.get("category", "unknown")),
                text=text,
            )
        )
    return items


def _agent_or_none(agent: str) -> str | None:
    """Map the global ``?agent=`` filter to a backend scope.

    ``"all"`` (or empty) is the deduplicated org view → ``None`` (no filter); any
    other value is a concrete agent id. Mirrors ``lib/agent-scope`` on the front.
    """
    return None if not agent or agent == "all" else agent


def _scores_for(
    at: str | None, agent_id: str | None = None, days: float | None = None
) -> list[dict[str, object]]:
    """Scores to read: the live ring buffer, or the durable log as-of T (ADR 0011).

    Scoped to ``agent_id`` when set (per-agent SLO / trend / funnel / scores), and to the
    last ``days`` when the cockpit's period rail asks for a window.
    """
    return read_scores(at, agent_id, days=days)


def _bundles_for(
    at: str | None = None, agent_id: str | None = None, days: float | None = None
) -> list[ReplayBundle]:
    """Captured turn bundles for a scope — the bundle twin of :func:`_scores_for`.

    Exists so the window is applied by :meth:`Scope.within` here exactly as it is inside
    the batched snapshot. The alternative was each bundle-reading route filtering
    ``captured_at`` for itself, which is how a route and its snapshot slice come to
    disagree about the same week while both look right in isolation.
    """
    from tessera.observability import replay as replay_mod
    from tessera.observability.spine.scope import Scope

    if days is None:
        return replay_mod.recent_bundles(at, agent_id)
    # A period forces the DURABLE store, exactly as it does for scores. The live view is a
    # deque bounded at 100 bundles — a bound on COUNT — so filtering it by time would answer
    # "the last 30 days" with whatever those 100 turns happen to span, and would silently
    # return the same rows as "24 hours" the moment traffic is thin.
    rows = replay_mod.persisted_bundles(at, agent_id)
    scope = Scope(at=at, agent_id=agent_id, period_days=days)
    return [b for b in rows if scope.within(b.captured_at)]


def _data_availability_start(
    scores: list[dict[str, object]],
    audit_entries: list[dict[str, object]],
) -> str | None:
    """Earliest instant the cockpit holds real as-of-T data, or None if it holds none.

    The bound is the lexicographic minimum over the two durable as-of-T sources —
    eval score ``scored_at`` and guard audit ``occurred_at`` — ignoring blanks. ISO
    8601 sorts lexicographically, matching the timeline's ordering convention.
    """
    stamps = [str(s.get("scored_at", "")) for s in scores]
    stamps += [str(e.get("occurred_at", "")) for e in audit_entries]
    stamps = [s for s in stamps if s]
    return min(stamps) if stamps else None


def _payload(row: dict[str, object]) -> dict[str, object]:
    raw = row.get("payload")
    return dict(raw) if isinstance(raw, dict) else {}


def _bool_payload(row: dict[str, object], key: str) -> bool | None:
    value = _payload(row).get(key)
    return value if isinstance(value, bool) else None


def _str_payload(row: dict[str, object], key: str) -> str | None:
    value = _payload(row).get(key)
    return value if isinstance(value, str) else None


def _workflow_artifacts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    # Transitional (ADR 0017 Phase A → dissolved in Phase C): the seeded ``no_*`` flag keys
    # below are recouvrement vocabulary kept verbatim for render parity. Phase C replaces
    # this seed list with manifest-declared non-effect flags per artifact type.
    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        artifact_id = row.get("artifact_id")
        artifact_type = row.get("artifact_type")
        if not isinstance(artifact_id, str) or not artifact_id:
            payload = _payload(row)
            artifact_id = payload.get("artifact_id")
            artifact_type = payload.get("artifact_type") or artifact_type
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        payload = _payload(row)
        artifact = by_id.setdefault(
            artifact_id,
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type if isinstance(artifact_type, str) else None,
                "artifact_status": None,
                "title": None,
                "generation_mode": None,
                "template_id": None,
                "template_version": None,
                "no_message_sent": None,
                "no_payment_initiated": None,
                "no_payment_link_created": None,
                "no_payment_link_sent": None,
                "no_schedule_created": None,
                "no_external_effect": None,
            },
        )
        for source_key, target_key in (
            ("artifact_type", "artifact_type"),
            ("artifact_status", "artifact_status"),
        ):
            value = row.get(source_key)
            if isinstance(value, str) and value:
                artifact[target_key] = value
        for key in (
            "title",
            "generation_mode",
            "template_id",
            "template_version",
            "no_message_sent",
            "no_payment_initiated",
            "no_payment_link_created",
            "no_payment_link_sent",
            "no_schedule_created",
            "no_external_effect",
        ):
            if key in payload and payload[key] is not None:
                artifact[key] = payload[key]
        generation = payload.get("client_message_generation")
        if isinstance(generation, dict):
            for key in ("generation_mode", "template_id", "template_version"):
                value = generation.get(key)
                if value is not None:
                    artifact[key] = value
    return list(by_id.values())


def _workflow_decisions(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []
    for row in rows:
        decision = row.get("decision")
        reason_codes = row.get("reason_codes")
        if decision is None and not reason_codes:
            continue
        decisions.append(
            {
                "event_name": row.get("event_name"),
                "decision": decision,
                "reason_codes": reason_codes if isinstance(reason_codes, list) else [],
                "rule_id": _str_payload(row, "rule_id"),
                "action_name": _str_payload(row, "action_name"),
                "no_external_effect": _bool_payload(row, "no_external_effect"),
            }
        )
    return decisions


def _workflow_sensitive_actions(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for row in rows:
        if row.get("event_name") not in {
            "action.requested",
            "action.prepared",
            "action.blocked",
            "artifact.status_changed",
            "validation.requested",
        }:
            continue
        payload = _payload(row)
        action_name = payload.get("action_name") or payload.get("status_reason")
        if not isinstance(action_name, str) or not action_name:
            continue
        reason_codes = row.get("reason_codes")
        actions.append(
            {
                "event_name": row.get("event_name"),
                "action_name": action_name,
                "artifact_id": row.get("artifact_id") or payload.get("artifact_id"),
                "artifact_type": row.get("artifact_type") or payload.get("artifact_type"),
                "current_status": payload.get("current_status") or payload.get("previous_status"),
                "target_status": payload.get("target_status") or payload.get("new_status"),
                "no_external_effect": payload.get("no_external_effect"),
                "requires_validation": payload.get("requires_validation"),
                "reason_codes": reason_codes if isinstance(reason_codes, list) else [],
            }
        )
    return actions


def _workflow_runs_from_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        conversation_id = str(row.get("conversation_id") or "")
        turn_id = str(row.get("turn_id") or "")
        if not conversation_id or not turn_id:
            continue
        grouped.setdefault((conversation_id, turn_id), []).append(row)
    runs: list[dict[str, object]] = []
    for (conversation_id, turn_id), turn_rows in grouped.items():
        ordered_rows = sorted(
            turn_rows,
            key=lambda item: (
                _GRAMMAR_EVENT_ORDER.get(str(item.get("event_name") or ""), 100),
                str(item.get("timestamp") or ""),
            ),
        )
        scores = business_scoring_mod.score_rows(ordered_rows)
        first = ordered_rows[0]
        capability_id = next(
            (
                row.get("capability_id")
                for row in ordered_rows
                if isinstance(row.get("capability_id"), str) and row.get("capability_id")
            ),
            None,
        )
        runs.append(
            {
                "agent_id": first.get("agent_id"),
                "workflow_id": first.get("workflow_id"),
                "capability_id": capability_id,
                "surface": first.get("surface"),
                "case_id": first.get("case_id"),
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "started_at": first.get("timestamp"),
                "event_count": len(ordered_rows),
                "timeline": ordered_rows,
                "artifacts": _workflow_artifacts(ordered_rows),
                "decisions": _workflow_decisions(ordered_rows),
                "sensitive_actions": _workflow_sensitive_actions(ordered_rows),
                "scores": scores,
            }
        )
    return sorted(runs, key=lambda run: str(run.get("started_at") or ""), reverse=True)


def _business_runs_response(
    *,
    at: str | None,
    agent_id: str | None,
    workflow_id: str | None,
    conversation_id: str | None,
    turn_id: str | None,
    case_id: str | None,
    capability_id: str | None,
    limit: int,
) -> dict[str, object]:
    """Shared implementation for the generic and per-agent business-runs reads."""
    rows = business_events_mod.business_event_rows(
        at=at,
        agent_id=agent_id,
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        case_id=case_id,
        capability_id=capability_id,
    )
    runs = _workflow_runs_from_rows(rows)
    bounded_limit = max(1, min(limit, 100))
    return {
        "runs": runs[:bounded_limit],
        "events": rows,
        "scores": business_scoring_mod.score_rows(rows),
        "as_of": at,
        "agent": agent_id or "all",
        "workflow_id": workflow_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "case_id": case_id,
        "capability_id": capability_id,
    }


def _serialize_conversations(
    conversations: list[transcript.ConversationSummary],
) -> list[dict[str, object]]:
    """Public-safe JSON for a conversation list (console Récents + Historique)."""
    return [
        {
            "conversation_id": c.conversation_id,
            "title": c.title,
            "started_at": c.started_at.isoformat(),
            "last_at": c.last_at.isoformat(),
            "message_count": c.message_count,
            "turn_count": c.turn_count,
        }
        for c in conversations
    ]


def _read_audit_entries() -> list[dict[str, object]]:
    """Guard-audit entries from the ACTIVE ledger source (§Amendment 3 seam; best effort).

    The guard-audit rows are 94 % of the chain (measured), so a ``WHERE payload->>'type'`` scan
    is a full read wearing the word "filter" — and the predicate is not sargable, so it re-walked
    ~83 k rows (~1.5 s) on EVERY request. The live subset is instead derived from
    :func:`load_ledger_payloads_sync`, the incrementally-cached whole-ledger read (head-invalidated
    on ``max(seq)``): the same live payloads in the same seq order, ~24 ms steady-state, proven
    byte-identical to the old ``of_type`` result. This is a LATENCY fix, not the row-budget fix —
    it still materialises the whole chain, so ``_common.py`` stays on the frozen offender list in
    ``tests/unit/test_ledger_read_budget.py`` (the bound it owes is still a window, still OWED).
    """
    from tessera.guard.ledger_store import (
        ledger_source,
        load_ledger_payloads_sync,
        read_ledger_entries,
    )

    if ledger_source() == "postgres":
        return [p for p in load_ledger_payloads_sync() if p.get("type") == "tessera.guard.audit"]
    return [obj for obj in read_ledger_entries() if obj.get("type") == "tessera.guard.audit"]


def _corpus_sources() -> set[str]:
    """Collect the regulatory corpus source ids (e.g. 'DORA/art-5')."""
    import json
    from importlib import resources

    sources: set[str] = set()
    data_dir = Path(str(resources.files("tessera.corpus.data")))
    for path in data_dir.glob("regulations_*.json"):
        try:
            docs = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # best-effort: skip an unreadable/corrupt regulations JSON — non-gating (0015)
            continue
        if isinstance(docs, list):
            for doc in docs:
                if isinstance(doc, dict) and doc.get("source"):
                    sources.add(str(doc["source"]))
    return sources
