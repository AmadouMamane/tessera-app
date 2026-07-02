"""Governed-activity feed for the SURVEILLER Vue d'ensemble (normatives 02/03).

A feed of real **governance** actions — distinct from the guard-decision firehose
and from the signal rail. Two real, append-only, as-of-T sources:

* the **S1 hash-chained journal** (``settings.guard.audit_file``) — agent routing,
  hand-overs, proposals and release decisions (``tessera.agent.*``);
* the **replay bundle lineage** — model / prompt / guard-policy **version changes**
  read off ``captured_at`` (a config deploy is a governed event).

Honesty (Tessera positioning): only events that ACTUALLY happened are returned —
no fixtures. Sparse categories (proposals / releases are 0 until an operator
promotes an agent) simply do not appear; the panel shows an honest empty state.
Every event keeps its instant, so the feed is reproducible and filters as-of-T
(``occurred_before``), staying consistent with the rail's provenance contract.

The backend returns STRUCTURED events (``kind`` + fields); the frontend localises
the labels — so no presentation French is hard-coded here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from tessera.guard.ledger_store import read_ledger_entries
from tessera.observability import replay as replay_mod
from tessera.observability._asof import occurred_before

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["GovernanceEvent", "GovernanceFeed", "compute_governance_feed"]

# S1 journal event types that are GOVERNANCE actions (not guard denials).
_GOVERNANCE_TYPES: dict[str, str] = {
    "tessera.agent.routing": "routing",
    "tessera.agent.handoff": "handoff",
    "tessera.agent.proposed": "proposed",
    "tessera.agent.released": "released",
    "tessera.agent.release_blocked": "blocked",
}


@dataclass(frozen=True)
class GovernanceEvent:
    """One governed action, language-neutral (the frontend renders the label)."""

    occurred_at: str
    kind: str
    actor: str
    agent_id: str | None = None
    from_agent: str | None = None
    to_agent: str | None = None
    detail: str = ""
    count: int = 1
    evidence: str | None = None


@dataclass(frozen=True)
class GovernanceFeed:
    """The feed payload: newest-first events + a real by-kind census."""

    events: list[dict[str, object]]
    total: int
    by_kind: dict[str, int]
    as_of: str | None


def _audit_path() -> Path:
    """The S1 hash-chained journal path (seam for tests, mirrors scores._scores_path)."""
    from tessera.settings import get_settings

    return get_settings().guard.audit_file


def _read_audit_governance(at: str | None, agent: str | None) -> list[GovernanceEvent]:
    """Parse the S1 journal for agent-governance events ≤ T (newest-first, raw)."""
    events: list[GovernanceEvent] = []
    for obj in read_ledger_entries(_audit_path()):
        kind = _GOVERNANCE_TYPES.get(str(obj.get("type", "")))
        if kind is None:
            continue
        occurred = str(obj.get("occurred_at", ""))
        if not occurred or not occurred_before(occurred, at):
            continue
        agent_id = obj.get("agent_id")
        agent_id = str(agent_id) if isinstance(agent_id, str) else None
        if agent and agent not in ("all", agent_id):
            continue
        hash_ref = obj.get("hash")
        events.append(
            GovernanceEvent(
                occurred_at=occurred,
                kind=kind,
                actor=str(obj.get("actor", "system")),
                agent_id=agent_id,
                from_agent=(
                    str(obj.get("from_agent")) if isinstance(obj.get("from_agent"), str) else None
                ),
                to_agent=(
                    str(obj.get("to_agent")) if isinstance(obj.get("to_agent"), str) else None
                ),
                detail=str(obj.get("reason", "") or obj.get("name", "")),
                evidence=str(hash_ref)[:12] if isinstance(hash_ref, str) else None,
            )
        )
    return events


def _collapse_routings(events: list[GovernanceEvent]) -> list[GovernanceEvent]:
    """Collapse consecutive identical routings (same agent + reason) into one row.

    The supervisor records EVERY turn's routing; a long run of identical
    "stay→support-client" decisions is one governed fact with a count, not N rows.
    Events must already be newest-first; non-routing events pass through untouched.
    """
    out: list[GovernanceEvent] = []
    for ev in events:
        if (
            ev.kind == "routing"
            and out
            and out[-1].kind == "routing"
            and out[-1].agent_id == ev.agent_id
            and out[-1].detail == ev.detail
        ):
            prev = out[-1]
            out[-1] = GovernanceEvent(
                occurred_at=prev.occurred_at,  # keep the latest (newest-first)
                kind="routing",
                actor=prev.actor,
                agent_id=prev.agent_id,
                detail=prev.detail,
                count=prev.count + 1,
                evidence=prev.evidence,
            )
        else:
            out.append(ev)
    return out


def _lineage_deploys(at: str | None, agent: str | None) -> list[GovernanceEvent]:
    """Detect model / prompt / guard-policy version changes from bundle lineage.

    A change between consecutive (oldest→newest) captured bundles is a config
    deploy — a real governed event, attributed to the system and stamped at the
    bundle's ``captured_at``. As-of-T honoured via ``persisted_bundles(at)``.
    """
    if agent and agent != "all":
        # Bundles are not agent-attributed in this build; skip rather than fake it.
        return []
    bundles = [b for b in replay_mod.persisted_bundles(at) if b.lineage is not None]
    bundles.sort(key=lambda b: b.captured_at)
    deploys: list[GovernanceEvent] = []
    seen: dict[str, str] = {}
    fields = (
        ("deploy_model", "model"),
        ("deploy_prompt", "prompt_version"),
        ("deploy_policy", "guard_policy_version"),
    )
    for bundle in bundles:
        lineage = bundle.lineage
        for kind, attr in fields:
            value = getattr(lineage, attr, None)
            if not isinstance(value, str) or not value:
                continue
            if seen.get(attr) is None:
                seen[attr] = value  # baseline; not a "change" event
                continue
            if seen[attr] != value:
                seen[attr] = value
                deploys.append(
                    GovernanceEvent(
                        occurred_at=bundle.captured_at,
                        kind=kind,
                        actor="system",
                        detail=value,
                        evidence=value[:12],
                    )
                )
    return deploys


def compute_governance_feed(
    at: str | None = None, limit: int = 8, agent: str | None = None
) -> GovernanceFeed:
    """Assemble the governed-activity feed from the real S1 journal + lineage.

    Args:
        at: Optional ISO instant T; only events at or before T are returned.
        limit: Maximum number of events to return (newest-first).
        agent: Optional agent scope (``all`` or an agent id) for the S1 events.

    Returns:
        A :class:`GovernanceFeed` with the newest-first events (capped at ``limit``)
        and a by-kind census over ALL matching events (not just the page).
    """
    audit_events = _collapse_routings(_read_audit_governance(at, agent))
    merged = audit_events + _lineage_deploys(at, agent)
    merged.sort(key=lambda e: e.occurred_at, reverse=True)

    by_kind: dict[str, int] = {}
    for ev in merged:
        by_kind[ev.kind] = by_kind.get(ev.kind, 0) + 1

    return GovernanceFeed(
        events=[asdict(e) for e in merged[: max(1, limit)]],
        total=len(merged),
        by_kind=by_kind,
        as_of=at,
    )
