"""Observability routes — the SUBJECT-SCOPED read surface. Personal data, one guard.

Audit 2026-07-12, **P1 F-4**. The cockpit's reads were public by declaration (ADR 0009: the
aggregate surface is the shop window, and it stays open — scores, rates, levels, badges,
signals carry no subject). But *these* reads are not aggregates. They return what a person
said, what an agent answered them, what the system remembers about them, and how much of it
would be erased on request. That is personal data under the GDPR, and it was served to
anyone who asked: the observability router was mounted with no route-level auth
(``api/main.py``, under a comment reading "public surface"), and the front's BFF listed
``observability`` in ``ALWAYS_PUBLIC``, attaching the service bearer on an anonymous
visitor's behalf.

The exploit needed two of these routes and no credentials at all:

1. ``GET /observability/conversations`` — a directory. Each row carries the
   ``conversation_id`` **and** the ``title``, which ``memory/transcript.py`` defines as
   *"the conversation's opening user message"*.
2. ``GET /observability/conversation-messages?conversation_id=…`` — the full transcript of
   that id.

List, then read. The unguessable uuid4 that the product widget's own comment called *"a
capability the customer's browser already holds"* was published, next to the first thing the
customer typed. A directory defeats a secret url.

**The dividing line is the PAYLOAD, not the route, and not read-vs-write.** The question is
only ever *"can this response identify someone?"*, and reading the code is not a reliable way
to answer it. Four of the routes below do not look like they carry personal data, and do:
``trace-snapshot`` reads as a node-shape diff and carries ``drifts[].question`` verbatim;
``handoffs`` and ``context-overflow`` hand each turn's question to an analyzer that echoes it
back as a row label; ``agent-historique`` is a synthetic dashboard with one real block
(``live_conversations``) bolted on, whose ``title`` is each customer's opening message. The
last three were found by the ratchet, not by review — which is the argument for having it.

Touching subject records is NOT disclosing them, and that distinction is the whole design:
``tail-sampling``, ``erasure-coverage``, ``replay-shadow``, ``pii-leak``, ``citations`` and a
dozen others read the same captured turns and emit only counts. They stay public. The ratchet
(``tests/unit/test_subject_reads_carry_auth.py``) settles it by execution rather than by
opinion: it seeds a canary into every store that holds a person's words, sweeps every GET as
an anonymous caller, and fails if the canary comes back — and fails, symmetrically, if an
aggregate ever grows a guard it does not need.

Every route here carries :func:`~tessera.api.security.require_subject_reader` — declared on
the router, never at the mount site, so a route added to this module cannot forget it (the
``mutations.py`` model; F-1's structural lesson was that guarding routers one by one closes
findings, not classes). It admits **every operator role**: the ``auditor`` above all, because
reading is its trade, and ``collections``, because the recouvrement console's "Récents" list
and conversation resume ARE two of these endpoints.

The customer's own transcript resume does NOT come through here — it cannot, since the
customer plane has no operator assertion. It moved to ``GET /session/transcript``, behind a
signed capability minted at ``turn.start`` (:func:`~tessera.api.session.issue_resume_token`).
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.api.routes.observability._common import _serialize_conversations
from tessera.api.security import require_subject_reader
from tessera.memory import transcript
from tessera.observability import (
    agent_historique as agent_historique_mod,
    console_feedback as console_feedback_mod,
    context_overflow as context_overflow_mod,
    erasure as erasure_mod,
    handoffs as handoffs_mod,
    memory_inventory as memory_inventory_mod,
    provenance as provenance_mod,
    replay as replay_mod,
    retrieval_quality as retrieval_quality_mod,
    session_detail as session_detail_mod,
    trace_snapshot as trace_snapshot_mod,
    trajectory as trajectory_mod,
)
from tessera.observability.spine.adapters import read_scores
from tessera.observability.spine.capabilities import capability_for

#: Personal data. A verified operator — of any role — or nobody.
router = APIRouter(dependencies=[Depends(require_subject_reader)])


@router.get("/observability/recouvrement-queue")
async def observability_recouvrement_queue() -> dict[str, object]:
    """The REAL collection-case queue + per-status counters (RC product, lot 9).

    Subject-scoped by nature: a dossier names a client and a debt. The router's
    ``require_subject_reader`` guards it (``collections`` is in the read roles —
    ADR 0025); the seeded demo book carries ``seed: true`` on every case so no
    surface can present it as production data.
    """
    from tessera.observability import recouvrement_case_store as case_store

    return {
        "available": True,
        "counters": case_store.queue_counters(),
        "cases": case_store.load_cases(),
    }


@router.get("/observability/recouvrement-case/{case_id}")
async def observability_recouvrement_case(case_id: str) -> dict[str, object]:
    """One collection dossier by id — 404 loudly on an id nobody holds."""
    from fastapi import HTTPException

    from tessera.observability import recouvrement_case_store as case_store

    try:
        return {"available": True, "case": case_store.get_case(case_id)}
    except case_store.CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown case {case_id!r}") from exc


@router.get("/observability/conversations")
async def observability_conversations(
    agent_id: str = DEFAULT_AGENT_ID,
    limit: int = 30,
) -> dict[str, object]:
    """Recent conversations handled by ``agent_id`` (most-recently-active first).

    Powers the business console's "Récents" list. Degrades to an empty list rather than
    breaking the console.

    Subject-scoped: ``title`` is the conversation's opening user message (``transcript.py``),
    so this is not a list of ids — it is a list of the first thing each customer typed. It
    was the directory half of F-4's exploit chain.
    """
    try:
        bounded = max(1, min(limit, 100))
        return {
            "available": True,
            "conversations": _serialize_conversations(
                await transcript.list_conversations(agent_id, limit=bounded)
            ),
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.conversations: failed: {exc}\n")
        return {"available": False, "conversations": []}


@router.get("/observability/conversation-messages")
async def observability_conversation_messages(conversation_id: str) -> dict[str, object]:
    """The persisted user/assistant messages of one conversation, in order.

    The operator console's transcript read (agent console, recouvrement console). The
    customer widget's own resume is NOT this route — it is ``GET /session/transcript``,
    which demands the signed resume capability instead of an operator assertion.

    Degrades to an empty list for an unknown / malformed id.
    """
    try:
        messages = await transcript.load_transcript(UUID(conversation_id))
        return {
            "available": True,
            "conversation_id": conversation_id,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role in ("user", "assistant")
            ],
        }
    except Exception as exc:  # never break the console
        sys.stderr.write(f"tessera.observability.conversation_messages: failed: {exc}\n")
        return {"available": False, "messages": []}


@router.get("/observability/session-detail")
async def observability_session_detail(
    conversation_id: str, at: str | None = None
) -> dict[str, object]:
    """Turn-by-turn detail of one conversation with per-turn agent attribution.

    Shows which agent handled each turn (so a handed-over conversation reads as a clear
    hand-over) plus the S1 handoff events. ``at`` bounds the handoff read (as-of).
    Degrades to ``available: false`` for an unknown/empty conversation.

    Subject-scoped: each turn carries the customer's ``question`` and the agent's ``answer``.
    """
    try:
        return await session_detail_mod.compute_session_detail(conversation_id, at)
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.session_detail: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/agent-console/feedback")
async def observability_agent_console_feedback(conversation_id: str) -> dict[str, object]:
    """Return the persisted ``{turn: rating}`` operator feedback for a conversation.

    The payload is ratings, not content — but it is keyed by a named conversation, so a
    stranger learns that the conversation exists and how it was judged. Subject-scoped by
    its question, not by its answer.
    """
    return {"ratings": console_feedback_mod.console_feedback(conversation_id)}


@router.get("/observability/replays")
async def observability_replays() -> dict[str, object]:
    """List the captured turns available for regression replay (newest last).

    Subject-scoped, and the bulkiest of them all: a ``ReplayBundle`` carries ``question``,
    ``context`` and ``original_answer`` — real captured traffic — and this route serializes
    every field of every bundle.
    """
    return {"bundles": [asdict(b) for b in replay_mod.recent_bundles()]}


@router.get("/observability/trace-snapshot")
async def observability_trace_snapshot() -> dict[str, object]:
    """Golden-trace snapshot diff of executed-node shapes across turns (#41).

    Reads as an aggregate and is not one: ``drifts[].question`` carries the verbatim user
    question of every turn whose node shape drifted, untruncated. The one a reviewer waves
    through.
    """
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(trace_snapshot_mod.diff_traces(turns))


@router.get("/observability/trajectory/{bundle_id}")
async def observability_trajectory(bundle_id: str) -> dict[str, object]:
    """Step-by-step trajectory of a captured turn (session theater).

    Subject-scoped: the ``input`` step's detail is the customer's question and the
    ``answer`` step's detail is what the agent replied.
    """
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    return asdict(trajectory_mod.build_trajectory(bundle))


@router.get("/observability/provenance/{bundle_id}")
async def observability_provenance(bundle_id: str) -> dict[str, object]:
    """Claim-level attribution of a captured turn to its retrieved chunks.

    Subject-scoped: it attributes the captured ``original_answer`` against the ``context``
    that produced it — both real traffic.
    """
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    report = await provenance_mod.attribute(bundle.original_answer, chunks)
    util = retrieval_quality_mod.utilization(report, len(chunks))
    return {**asdict(report), "utilization": asdict(util)}


@router.get("/observability/erasure/{conversation_id}")
async def observability_erasure_preview(conversation_id: str) -> dict[str, object]:
    """Preview the telemetry that a GDPR erasure of this subject would purge (#180).

    Subject-scoped: it carries no free text, but it answers *"how much do you hold about
    this person?"* for a caller-named subject — an existence-and-volume disclosure, which is
    precisely the question an Art. 15 request asks and precisely the one a stranger may not.
    """
    return asdict(
        erasure_mod.footprint(
            conversation_id,
            bundles=replay_mod.recent_bundles(),
            scores=read_scores(),
        )
    )


@router.get("/observability/handoffs")
async def observability_handoffs() -> dict[str, object]:
    """Delegation-chain handoff tracing and broken-handoff detection (#189).

    Subject-scoped, and NOT found by reading the code — found by the canary sweep. It reads
    like a delegation aggregate; ``analyze_handoffs`` is handed ``(b.question, nodes)`` per
    turn and carries the verbatim question through into its rows. Same shape as
    ``trace-snapshot`` and ``context-overflow``: a real user question used as a row label.
    """
    turns = [(b.question, list((b.latency_ms or {}).keys())) for b in replay_mod.recent_bundles()]
    return asdict(handoffs_mod.analyze_handoffs(turns))


@router.get("/observability/context-overflow")
async def observability_context_overflow() -> dict[str, object]:
    """Context truncation/overflow vs the input window across captured turns (#89).

    Subject-scoped: ``analyze_overflow`` receives each turn's question *and* its retrieved
    context chunks, and labels the overflowing turns with them.
    """
    turns = [
        (b.question, [c for c in b.context.split("\n\n") if c.strip()])
        for b in replay_mod.recent_bundles()
    ]
    return asdict(context_overflow_mod.analyze_overflow(turns))


@router.get("/observability/agent-historique")
async def observability_agent_historique(
    agent_id: str = DEFAULT_AGENT_ID,
    lang: str = "fr",
) -> dict[str, object]:
    """Agent Session History dashboard (reference image 30).

    Inner tab strip, KPI strip, filterable sessions table, chart row (trend, sessions by
    agent, score distribution, success gauge), watchlist, quick actions and a per-session
    detail panel. Deterministic fixture; degrades to ``available: false``. ``agent_id``
    scopes the in-page navigation links; ``lang`` localizes the chrome (fr / de / en).

    A **hybrid** payload, and that is exactly why it leaked: the eval half is a synthetic
    fixture (stamped as such), but ``live_conversations`` is real — the transcript's
    conversation list, whose ``title`` is each customer's opening message. One real block in
    a synthetic dashboard is enough to make the whole response subject-scoped.
    """
    try:
        payload: dict[str, object] = {
            "available": True,
            **agent_historique_mod.compute_agent_historique(agent_id, lang),
        }
        # The eval-session half of this payload — KPI strip, trend, sessions-by-agent,
        # score distribution, success gauge, watchlist — is a deterministic fixture. It is
        # shaped like telemetry, so without this stamp the operator UI presents it as live.
        # Read from the capability registry rather than written as a literal, so the stamp
        # cannot drift from the declaration (the snapshot's ScopeReport does the same).
        payload["synthetic"] = capability_for("agent_historique").synthetic
        # Real live conversations from the transcript, surfaced ALONGSIDE the eval
        # sessions (additive — the eval KPIs/charts stay untouched). These are the
        # operator's actual turns, not scored runs, so they get their own honest
        # block rather than fabricated eval scores.
        payload["live_conversations"] = _serialize_conversations(
            await transcript.list_conversations(agent_id, limit=50)
        )
        return payload
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_historique: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/memory-inventory")
async def observability_memory_inventory() -> dict[str, object]:
    """What the agent remembers: long-term store inventory (GDPR access, #135).

    Subject-scoped. ``InventorySample`` calls itself "a redacted preview row" and only
    *truncates*: ``preview`` is the first 80 characters of a stored memory and ``subject``
    the first 12 of the subject id. A slice of someone's personal data is their personal
    data; do not trust that docstring.
    """
    from tessera.memory.persistent import list_inventory
    from tessera.observability.memory_inventory import InventoryItem

    try:
        rows = await list_inventory()
    except Exception as exc:  # store may be offline / empty — never break the dashboard
        sys.stderr.write(f"tessera.observability.memory_inventory: failed: {exc}\n")
        return asdict(memory_inventory_mod.summarize_inventory([]))
    items = [
        InventoryItem(
            memory_id=row.memory_id,
            subject_id=row.subject_id,
            kind=row.kind,
            text=row.text,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
        for row in rows
    ]
    return asdict(memory_inventory_mod.summarize_inventory(items))
