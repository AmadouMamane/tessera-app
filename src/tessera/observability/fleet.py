"""Fleet rollup — per-agent health/volume + conversation-level dedup (Phase 3).

The fleet view and the agent switcher read this. It combines the registry (so
all agents appear, with their names/owners, even with no traffic), the durable
transcript (volume + observable escalation rate + per-agent latency) and the S1
journal (handoffs in/out). Org totals count a conversation **once** even when it
spans two agents — never the naive per-agent sum.

Observable KPIs (volume, escalation rate, latency, handoffs) are real and differ
per agent. Judged quality (resolution/faithfulness) stays shared until per-agent
eval (Phase 4) and is intentionally absent here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID

from psycopg.rows import dict_row

from tessera.guard.audit import HANDOFF_TYPE
from tessera.guard.ledger_store import (
    handoff_conversations,
    handoff_counts,
    ledger_source,
    read_ledger_entries,
)
from tessera.observability import quality_nets, turn_evidence
from tessera.observability.agent_health import health_state
from tessera.observability.agent_release import ReleaseFacts, fleet_release_states
from tessera.observability.agent_scope import dedup_org_total
from tessera.observability.agentspec_projection import (
    declared_observability_level,
    declares_telemetry,
    is_invocable,
    observability_level,
)
from tessera.observability.business_capabilities import business_capability_aggregate
from tessera.observability.operator_items import NATURE_A_TRAITER, load_items_for
from tessera.observability.store_spans import store_read
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    from psycopg import AsyncCursor

    from tessera.agent.registry import Agent

__all__ = [
    "BusinessCardFacts",
    "FleetAgent",
    "FleetData",
    "FleetOrgTotals",
    "compute_fleet",
    "registered_agent_ids",
]


# --- The payload's shape, as a TYPE ------------------------------------------------------------
#
# This existed only as a dict literal, and the route stamped ``{"available": True, **it}`` onto a
# `response_model` that had been GENERATED from live samples. Every field those samples happened to
# show populated became non-optional — so `release`, `level` and `level_declared`, which this module
# has ALWAYS returned as ``None`` for an agent with no eval run and no manifest (the honest-empty
# the comments below insist on), were declared as required non-null.
#
# Nothing failed. `compute_fleet` did not raise, so the handler's ``except`` never saw it: FastAPI
# validated the RESPONSE, found a payload that satisfied neither arm of the union, and answered
# **500** — on a virgin install, from the component whose entire job is to observe. *A try/except
# catches an exception; a partial-but-successful return walks straight past it.*
#
# So the shape is a type now, and mypy checks it AT BUILD. It is deliberately exact about the one
# thing that broke — WHICH FIELDS MAY BE NULL — because that is the axis the generated schema got
# wrong and a sample-derived model can never get right: a sample shows what happened to be there,
# never what is allowed to be absent.
class BusinessCardFacts(TypedDict):
    """The manifest-derived business chip on a fleet card."""

    north_star: dict[str, Any] | None
    pending_business_items: int


class FleetAgent(TypedDict):
    """One fleet card. The three nullable fields are the honest-empty this module owes."""

    id: str
    name: str
    owner: str
    audience: str
    description: str
    tags: list[str]
    conversations: int
    turns: int
    messages: int
    escalation_rate: float
    latency_ms: float | None
    handoffs_in: int
    handoffs_out: int
    health: str
    #: ``None`` when NO eval has ever run for this agent. Not a failure — a fact.
    release: ReleaseFacts | None
    #: ``None`` when the agent has no AgentSpec manifest yet — honest-empty, never "L0".
    level: str | None
    level_declared: str | None
    level_evidence: str
    observable: bool
    testable: bool
    north_star: dict[str, Any] | None
    pending_business_items: int


class FleetOrgTotals(TypedDict):
    """Org totals — DISTINCT conversations, never the per-agent sum."""

    conversations: int
    turns: int


class FleetData(TypedDict):
    """Everything ``available: true`` promises. A missing key is now a mypy error, not a 500."""

    agents: list[FleetAgent]
    org: FleetOrgTotals
    naive_sum_conversations: int
    shared_conversations: int
    dedup_saved: int
    handoff_events: int
    handoff_conversations: int
    handoff_conversations_seen_shared: int


@dataclass(frozen=True, slots=True)
class HandoffRollup:
    """Completed agent transitions proven by both the ledger and transcript."""

    incoming: dict[str, int]
    outgoing: dict[str, int]
    events: int
    conversations: int


@dataclass(frozen=True, slots=True)
class HandoffClaim:
    """One raw ledger claim that an agent transition happened."""

    conversation_id: UUID
    turn_id: str
    from_agent: str
    to_agent: str
    occurred_at: datetime


_ESCALATION_ILIKE = (
    "content ILIKE '%%escalad%%' OR content ILIKE '%%conseiller%%' "
    "OR content ILIKE '%%ticket%%' OR content ILIKE '%%transf%%'"
)
# The escalation thresholds moved to `agent_health`, where the whole health rule now lives
# beside them: escalation alone never decided the dot, it only used to.


def _registry_agents() -> list[dict[str, Any]]:
    """Registry fields the fleet card needs.

    ``description`` and ``tags`` are declared in the manifest and projected verbatim: a
    visitor must be able to tell a banking agent from a platform witness (``hello-agent``,
    ``turn-agent``) from the card alone, or the fleet count overstates the demo.
    """
    try:
        from tessera.agent.registry import list_agents

        return [
            {
                "id": a.id,
                "name": a.name,
                "owner": a.owner,
                "audience": a.audience.value,
                "description": a.description,
                "tags": list(a.tags),
            }
            for a in list_agents()
        ]
    except (OSError, ValueError):
        return []


def _count_cell(value: object) -> int:
    """Convert a SQL aggregate cell to an integer without widening arbitrary objects."""
    return int(value) if isinstance(value, int | float) else 0


def registered_agent_ids() -> set[str]:
    """Return the agent identifiers currently declared by the fleet registry."""
    return {str(agent["id"]) for agent in _registry_agents()}


def _agent_records() -> dict[str, Agent]:
    """Full agent records, for manifest-derived fields (the level badge).

    Empty on a load error — the fleet then degrades to no level badge, never crashes.
    """
    try:
        from tessera.agent.registry import list_agents

        return {a.id: a for a in list_agents()}
    except (OSError, ValueError):
        return {}


def _handoff_counts(audit_path: Path) -> tuple[dict[str, int], dict[str, int], int, set[str]]:
    """S1 handoff journal, per agent and per journey: ``(incoming, outgoing, events, conv_ids)``.

    ``incoming``/``outgoing`` count events by ``to_agent``/``from_agent``. ``events`` is the
    total number of attested handoffs, and ``conv_ids`` the distinct conversation ids they
    carry — the exact journeys the journal claims crossed two agents. Those ids exist so the
    dedup can be *reconciled* against the journal instead of merely computed beside it: a
    conversation store that never shares an id reads "0 shared" forever, and only the journal
    can contradict it.

    A count is an aggregate, and an aggregate belongs in the database. In postgres mode this is
    two indexed ``GROUP BY``s; it used to read all 29 600 ledger entries into Python to find
    the few dozen that were handoffs. File mode has no index and keeps the scan — irreducible
    there, and honest about it.
    """
    if ledger_source() == "postgres":
        pg_incoming, pg_outgoing = handoff_counts()
        pg_events, pg_conv_ids = handoff_conversations()
        return pg_incoming, pg_outgoing, pg_events, pg_conv_ids
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    events = 0
    conv_ids: set[str] = set()
    for obj in read_ledger_entries(audit_path):
        if obj.get("type") != HANDOFF_TYPE:
            continue
        events += 1
        to_agent = str(obj.get("to_agent", ""))
        from_agent = str(obj.get("from_agent", ""))
        conversation_id = str(obj.get("conversation_id", ""))
        if to_agent:
            incoming[to_agent] = incoming.get(to_agent, 0) + 1
        if from_agent:
            outgoing[from_agent] = outgoing.get(from_agent, 0) + 1
        if conversation_id:
            conv_ids.add(conversation_id)
    return incoming, outgoing, events, conv_ids


def _file_handoff_claims(audit_path: Path) -> list[HandoffClaim]:
    """Read structurally complete handoff claims from the file escape ledger."""
    claims: list[HandoffClaim] = []
    for entry in read_ledger_entries(audit_path):
        if entry.get("type") != HANDOFF_TYPE:
            continue
        try:
            conversation_id = UUID(str(entry.get("conversation_id", "")))
            occurred_at = datetime.fromisoformat(str(entry.get("occurred_at", "")))
        except ValueError:
            continue
        turn_id = str(entry.get("turn_id", ""))
        from_agent = str(entry.get("from_agent", ""))
        to_agent = str(entry.get("to_agent", ""))
        if not turn_id or not from_agent or not to_agent:
            continue
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        claims.append(
            HandoffClaim(
                conversation_id=conversation_id,
                turn_id=turn_id,
                from_agent=from_agent,
                to_agent=to_agent,
                occurred_at=occurred_at,
            )
        )
    return claims


async def _verified_handoff_rollup(
    cur: AsyncCursor[dict[str, object]],
    since: datetime | None = None,
    until: datetime | None = None,
) -> HandoffRollup:
    """Count only completed transitions between two persisted agent turns.

    The historical ledger contains entries emitted when a brand-new conversation was routed
    directly to Onboarding: the supervisor used Support as a technical fallback and called the
    first orientation a handoff even though Support never handled a turn. The ledger is
    append-only, so those entries cannot be rewritten. This read therefore earns the business
    word "handoff" by requiring both witnesses:

    * a real, non-synthetic source-agent message before the ledger event;
    * a real, non-synthetic target-agent message from the exact turn named by the event.

    The database performs the reconciliation as one aggregate; no ledger or transcript history
    is materialised in Python. Invalid legacy conversation ids remain in the audit trail but
    cannot be cast to UUID and therefore cannot masquerade as completed transitions.
    """
    claim_window: list[str] = []
    params: list[object] = [HANDOFF_TYPE]
    if since is not None:
        claim_window.append("occurred_at >= %s")
        params.append(since)
    if until is not None:
        claim_window.append("occurred_at <= %s")
        params.append(until)
    claim_scope = "".join(f"\n              AND {clause}" for clause in claim_window)
    query = f"""
        WITH claims AS (
            SELECT
                occurred_at,
                payload->>'from_agent' AS from_agent,
                payload->>'to_agent' AS to_agent,
                payload->>'turn_id' AS turn_id,
                CASE
                    WHEN payload->>'conversation_id' ~*
                         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                    THEN (payload->>'conversation_id')::uuid
                    ELSE NULL
                END AS conversation_uuid
            FROM audit_ledger
            WHERE payload->>'type' = %s
            {claim_scope}
        ),
        verified AS (
            SELECT claim.*
            FROM claims claim
            WHERE claim.conversation_uuid IS NOT NULL
              AND claim.from_agent IS NOT NULL
              AND claim.to_agent IS NOT NULL
              AND claim.turn_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM conversation_messages source
                  WHERE source.conversation_id = claim.conversation_uuid
                    AND source.agent_id = claim.from_agent
                    AND source.created_at < claim.occurred_at
                    AND NOT source.synthetic
              )
              AND EXISTS (
                  SELECT 1
                  FROM conversation_messages target
                  WHERE target.conversation_id = claim.conversation_uuid
                    AND target.agent_id = claim.to_agent
                    AND target.turn_id::text = claim.turn_id
                    AND NOT target.synthetic
              )
        )
        SELECT
            claim.from_agent,
            claim.to_agent,
            count(*) AS events,
            (SELECT count(DISTINCT all_verified.conversation_uuid)
             FROM verified all_verified) AS conversations
        FROM verified claim
        GROUP BY claim.from_agent, claim.to_agent
    """  # noqa: S608  (claim_scope contains only fixed clauses above)
    await cur.execute(query, tuple(params))
    rows = await cur.fetchall()
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    events = 0
    conversations = 0
    for row in rows:
        from_agent = str(row.get("from_agent") or "")
        to_agent = str(row.get("to_agent") or "")
        count = _count_cell(row.get("events"))
        if from_agent:
            outgoing[from_agent] = outgoing.get(from_agent, 0) + count
        if to_agent:
            incoming[to_agent] = incoming.get(to_agent, 0) + count
        events += count
        conversations = max(conversations, _count_cell(row.get("conversations")))
    return HandoffRollup(
        incoming=incoming,
        outgoing=outgoing,
        events=events,
        conversations=conversations,
    )


async def _verified_file_handoff_rollup(
    cur: AsyncCursor[dict[str, object]],
    claims: list[HandoffClaim],
) -> HandoffRollup:
    """Verify file-ledger claims against the same transcript evidence as Postgres mode."""
    if not claims:
        return HandoffRollup(incoming={}, outgoing={}, events=0, conversations=0)
    conversation_ids = sorted({claim.conversation_id for claim in claims}, key=str)
    await cur.execute(
        """
        SELECT
            conversation_id::text AS conversation_id,
            turn_id::text AS turn_id,
            agent_id,
            min(created_at) AS created_at
        FROM conversation_messages
        WHERE conversation_id = ANY(%s)
          AND NOT synthetic
        GROUP BY conversation_id, turn_id, agent_id
        """,
        (conversation_ids,),
    )
    evidence = await cur.fetchall()
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    events = 0
    conversations: set[UUID] = set()
    for claim in claims:
        conversation_id = str(claim.conversation_id)
        source_seen = False
        for row in evidence:
            created_at = row.get("created_at")
            if (
                str(row.get("conversation_id") or "") == conversation_id
                and str(row.get("agent_id") or "") == claim.from_agent
                and isinstance(created_at, datetime)
                and created_at < claim.occurred_at
            ):
                source_seen = True
                break
        target_seen = any(
            str(row.get("conversation_id") or "") == conversation_id
            and str(row.get("agent_id") or "") == claim.to_agent
            and str(row.get("turn_id") or "") == claim.turn_id
            for row in evidence
        )
        if not source_seen or not target_seen:
            continue
        events += 1
        conversations.add(claim.conversation_id)
        incoming[claim.to_agent] = incoming.get(claim.to_agent, 0) + 1
        outgoing[claim.from_agent] = outgoing.get(claim.from_agent, 0) + 1
    return HandoffRollup(
        incoming=incoming,
        outgoing=outgoing,
        events=events,
        conversations=len(conversations),
    )


def _integrity_broken() -> bool:
    """Whether the audit ledger's content integrity fails to verify — fleet-wide.

    A health dot asks the weak question — "is there a PROVEN break?" — so it asks the incremental
    verdict, where a verified prefix stays verified because the append-only trigger enforces it.
    It used to ask ``active_ledger_opposability``, which computes the entire §9 opposability badge
    — a full re-hash of 29 600 rows AND a third-party seal evaluation — of which the fleet then
    used exactly one boolean. The rest was fetched and dropped.

    Unreadable ⇒ ``False``: an unreachable ledger is not a proven break, and painting every
    dot red because the cockpit could not look would be the same over-claim in reverse.
    """
    try:
        from tessera.guard.ledger_checkpoint import active_ledger_verdict

        return not active_ledger_verdict().tree.content_integrity
    except Exception:
        return False


def _canary_verdicts() -> dict[str, str]:
    """Every agent's last canary verdict, in ONE query — never one query per agent.

    The fleet asks this about all its agents at once. Asked one at a time it was six full ledger
    reads per request; asked as the question it is, it is one indexed row per agent.
    """
    try:
        return quality_nets.latest_canary_verdicts()
    except Exception:
        return {}


def _pending_items_by_agent() -> dict[str, int]:
    """Pending operator items (``status != "done"``) per agent, from ONE whole-fleet load.

    ``_business_card_facts`` counted this over ``load_items_for(NATURE_A_TRAITER, aid)``, which
    re-reads the durable queue state from disk once PER agent — for a 6-agent fleet, six loads of
    the same file, ~570 ms warm and the dominant cost of the whole rollup. The queue is one
    whole-fleet read filtered by agent (still through the ONE declared partition rule, ADR 0038 —
    ``NATURE_A_TRAITER``, never a hand-rolled ``source_kind`` filter), so loading it once and
    grouping by ``item.agent_id`` gives the identical per-agent count (verified live) at a single
    read. On a load failure the map is empty and the caller reads 0 for every agent — the same
    honest-zero the per-agent ``try/except`` gave, now shared.
    """
    try:
        items = load_items_for(NATURE_A_TRAITER, None)
    except Exception:
        return {}
    pending: dict[str, int] = {}
    for item in items:
        if item.status != "done":
            pending[item.agent_id] = pending.get(item.agent_id, 0) + 1
    return pending


def _business_card_facts(
    aid: str, record: Agent | None, pending_business_items: int
) -> BusinessCardFacts:
    """Manifest-derived business chip + pending operator items for one fleet card.

    ``pending_business_items`` is precomputed once for the whole fleet by
    :func:`_pending_items_by_agent` rather than re-loaded per card.
    """
    if record is None or record.observability is None:
        return {"north_star": None, "pending_business_items": 0}
    try:
        aggregate = business_capability_aggregate(agent_id=aid)
    except Exception:
        aggregate = {}
    raw_signals = aggregate.get("business_signals")
    signals = raw_signals if isinstance(raw_signals, list) else []
    north_star = next(
        (
            signal
            for signal in signals
            if isinstance(signal, dict) and signal.get("north_star") is True
        ),
        None,
    )
    return {"north_star": north_star, "pending_business_items": pending_business_items}


def _window_bounds(
    period_days: int | None,
    at: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Return one stable interval shared by every operational fleet query."""
    if at is None:
        until = datetime.now(UTC) if period_days is not None else None
    else:
        until = datetime.fromisoformat(at)
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
    since = until - timedelta(days=period_days) if until is not None and period_days else None
    return since, until


def _transcript_scope(
    since: datetime | None,
    until: datetime | None,
) -> tuple[str, tuple[datetime, ...]]:
    """SQL WHERE clause for real transcript traffic in the selected fleet window."""
    clauses = ["NOT synthetic"]
    params: list[datetime] = []
    if since is not None:
        clauses.append("created_at >= %s")
        params.append(since)
    if until is not None:
        clauses.append("created_at <= %s")
        params.append(until)
    return " AND ".join(clauses), tuple(params)


async def compute_fleet(
    lang: str = "fr",
    period_days: int | None = None,
    at: str | None = None,
) -> FleetData:
    """Return the fleet payload: per-agent observable KPIs + deduplicated org totals.

    ``lang`` localizes the per-agent release ``verdict_label``; all other fields
    are language-independent. ``period_days`` bounds every transcript-derived
    figure to one trailing interval ending at ``at`` (or now).
    """
    since, until = _window_bounds(period_days, at)
    transcript_where, transcript_params = _transcript_scope(since, until)
    file_handoff_claims = (
        await asyncio.to_thread(_file_handoff_claims, get_settings().guard.audit_file)
        if ledger_source() == "file"
        else None
    )
    if file_handoff_claims is not None:
        file_handoff_claims = [
            claim
            for claim in file_handoff_claims
            if (since is None or claim.occurred_at >= since)
            and (until is None or claim.occurred_at <= until)
        ]
    with store_read(
        "postgres", "conversation_messages.fleet_rollup", target="conversation_messages"
    ) as read:
        async with _connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT agent_id, "  # noqa: S608  (escalation clause is a constant)
                "count(DISTINCT conversation_id) AS convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "count(*) AS msgs, "
                f"count(*) FILTER (WHERE role = 'assistant' AND ({_ESCALATION_ILIKE})) "
                "AS escal, "
                "count(*) FILTER (WHERE role = 'assistant') AS answers, "
                "avg(latency_ms) FILTER (WHERE latency_ms IS NOT NULL) AS lat "
                # ADR 0040: real traffic only — operator TEST turns (synthetic) never
                # inflate the Flotte, matching the business-event surfaces and the Synthèse.
                f"FROM conversation_messages WHERE {transcript_where} GROUP BY agent_id",
                transcript_params,
            )
            by_agent = {str(r["agent_id"]): r for r in await cur.fetchall()}

            await cur.execute(
                "SELECT count(*) FILTER (WHERE role = 'user') AS turns "  # noqa: S608
                # `transcript_where` is assembled from fixed clauses in `_transcript_scope`;
                # all timestamps remain bound values.
                f"FROM conversation_messages WHERE {transcript_where}",
                transcript_params,
            )
            org_turns = int((await cur.fetchone() or {}).get("turns") or 0)

            # Deduplicated conversation rollup via the shared helper — a handoff
            # conversation counts ONCE for the org, never the per-agent sum.
            rollup = await dedup_org_total(
                cur,
                table="conversation_messages",
                entity_col="conversation_id",
                synthetic_col="synthetic",
                time_col="created_at",
                since=since,
                until=until,
            )
            if ledger_source() == "postgres":
                handoffs = await _verified_handoff_rollup(cur, since, until)
            else:
                # File is the explicit operator escape hatch. Its scan is irreducible, but the
                # resulting claims still earn "handoff" through the same transcript evidence.
                handoffs = await _verified_file_handoff_rollup(
                    cur,
                    file_handoff_claims or [],
                )
        read.rows_read(len(by_agent))

    # Every read below is SYNCHRONOUS — Postgres, Prometheus, the ledger, the eval snapshots.
    # Called inline they ran on the event loop, and the whole server froze for as long as the
    # slowest one took: a `/healthz` costing 2 ms at rest was measured at 3 639 ms while ONE
    # fleet request was in flight. The cost and the blocking are two different bugs, and making
    # the reads cheap fixes only the first. They go to threads, and — being independent — they
    # go there together.
    #
    #   * releases — the eval/gating facts;
    #   * records  — the manifests (the registry seam);
    #   * observed — ONE Prometheus read for the whole fleet: which agents the cockpit has
    #     OBSERVED emitting turns (ADR 0017 §F). ``None`` = evidence disabled/unreachable, which
    #     proves nothing — the computed level falls back and the badge says the rung is declared;
    #   * integrity — ONE ledger verdict for the whole fleet: a broken chain indicts every agent
    #     it records, so it is a fleet-wide fact, not a per-card one;
    #   * canaries — ONE query for every agent's last verdict, not one query per agent.
    (
        releases,
        records,
        observed_turns,
        integrity_broken,
        canary_verdicts,
    ) = await asyncio.gather(
        asyncio.to_thread(fleet_release_states, lang),
        asyncio.to_thread(_agent_records),
        asyncio.to_thread(turn_evidence.agents_with_turn_evidence),
        asyncio.to_thread(_integrity_broken),
        asyncio.to_thread(_canary_verdicts),
    )

    registry = _registry_agents()
    # The per-card business facts are per-agent reads (ClickHouse + the operator queue) and were
    # also inline. Same rule: off the loop, and concurrently with each other. The operator-queue
    # pending count is one whole-fleet read filtered by agent, so it is loaded ONCE here and grouped
    # (byte-identical to the per-card load, but ~6x fewer disk reads) instead of reloaded per card.
    pending_items = await asyncio.to_thread(_pending_items_by_agent)
    business_by_agent = dict(
        zip(
            [reg["id"] for reg in registry],
            await asyncio.gather(
                *(
                    asyncio.to_thread(
                        _business_card_facts,
                        reg["id"],
                        records.get(reg["id"]),
                        pending_items.get(reg["id"], 0),
                    )
                    for reg in registry
                )
            ),
            strict=True,
        )
    )

    # Registry first (every agent appears), enriched with its real slice.
    agents: list[FleetAgent] = []
    for reg in registry:
        aid = reg["id"]
        row = by_agent.get(aid, {})
        answers = int(row.get("answers") or 0)
        escal = int(row.get("escal") or 0)
        escalation_rate = round(100 * escal / answers, 1) if answers else 0.0
        lat = row.get("lat")
        rel = releases.get(aid)
        record = records.get(aid)
        # L2 (Governed) requires the eval/guard facts to be VISIBLE — a real gating socle
        # actually ran (ADR 0017 §4). The level is computed from this fact, never asserted.
        governed = rel is not None and rel.available and rel.socle_total > 0
        # Two rungs, never one: `level` rests on observed turns alone, `level_declared` on the
        # manifest. When they differ the badge says so — a declared rung must never be dressed
        # up as a computed one (the over-claim `turn-agent` made visible).
        evidence = turn_evidence.turn_evidence_state(aid, observed_turns)
        level = (
            observability_level(record, governed=governed, has_turn_evidence=evidence == "observed")
            if record is not None
            else None
        )
        level_declared = (
            declared_observability_level(record, governed=governed) if record is not None else None
        )
        business_facts = business_by_agent[aid]
        agents.append(
            {
                "id": aid,
                "name": reg["name"],
                "owner": reg["owner"],
                "audience": reg.get("audience", "operator"),
                "description": reg.get("description", ""),
                "tags": reg.get("tags", []),
                "conversations": int(row.get("convs") or 0),
                "turns": int(row.get("turns") or 0),
                "messages": int(row.get("msgs") or 0),
                "escalation_rate": escalation_rate,
                "latency_ms": round(float(lat), 1) if lat is not None else None,
                "handoffs_in": int(handoffs.incoming.get(aid, 0)),
                "handoffs_out": int(handoffs.outgoing.get(aid, 0)),
                # Three facts, one rule, stated in `agent_health`. Green is a claim about
                # observed evidence, never merely the absence of bad news.
                "health": health_state(
                    escalation_rate=escalation_rate,
                    canary_red=canary_verdicts.get(aid) == "red",
                    integrity_broken=integrity_broken,
                    turn_evidence=evidence,
                ),
                # `None` when NO eval has ever run — a fact about the agent, not a failure of
                # this read. The response model used to forbid it and answered 500 instead.
                "release": rel.as_dict() if rel else None,
                # ADR 0017 §4 — observability level (L0-L2 in Phase B; None when the agent
                # has no AgentSpec manifest yet → honest-empty, not "L0").
                "level": level,
                "level_declared": level_declared,
                "level_evidence": evidence,
                # The two structural contracts the card states, both derived from the manifest
                # (ADR 0017 §3 / ADR 0019 §1) and never from an agent id. `False` for an
                # un-manifested agent — the chip is then absent, not falsely negative.
                "observable": record is not None and declares_telemetry(record),
                "testable": record is not None and is_invocable(record),
                # Spread out by hand, not `**business_facts`: a `**` of an untyped dict is a hole
                # mypy cannot see through, and this whole change exists because a shape nobody
                # checked reached the wire.
                "north_star": business_facts["north_star"],
                "pending_business_items": business_facts["pending_business_items"],
            }
        )

    return {
        "agents": agents,
        "org": {"conversations": rollup.org, "turns": org_turns},
        "naive_sum_conversations": rollup.naive_sum,
        "shared_conversations": rollup.shared,
        "dedup_saved": rollup.dedup_saved,
        # A fleet handoff is a completed transition, not any raw entry carrying the legacy
        # event type. The ledger entry, prior source turn and persisted target turn all agree.
        "handoff_events": handoffs.events,
        "handoff_conversations": handoffs.conversations,
        "handoff_conversations_seen_shared": handoffs.conversations,
    }
