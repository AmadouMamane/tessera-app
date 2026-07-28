"""Ratchet — no public route emits subject content. The payload is the only judge.

The symmetric twin of ``test_mutation_routes_carry_auth.py``. That file closed the class
"a mutation with no auth story"; this one closes "a READ that hands out personal data to
anyone" — the class F-4 lived in (audit 2026-07-12, P1). The mutation ratchet said nothing
about reads, and reads were where the GDPR hole was: ``GET /observability/conversation-
messages?conversation_id=…`` returned any conversation's full transcript to anyone, and
``GET /observability/conversations`` published the ids next to the ``title`` — which
``memory/transcript.py`` defines as the conversation's opening user message. A directory,
then a transcript. No credentials at any step.

**The criterion is the PAYLOAD.** Not "read vs mutation" (the mutation ratchet already
showed that axis is the wrong one). Not "which store does the handler touch" — the first
draft of this file tried exactly that and it does not work: ``/observability/citations`` and
``/observability/pii-leak`` read the same captured turns as ``/observability/replays`` and
emit only counts. Touching personal data is not disclosing it, and a ratchet that confuses
the two either over-locks the public cockpit or drowns in waivers nobody reads.

So this test asks the real question, mechanically: **seed a canary into every store that
holds a person's words, sweep every GET route as an anonymous caller, and fail if the canary
comes back.** No suspicion heuristic, no indirection blind spot — if the string reaches the
wire, whatever path it took, the sweep sees it. That is what "can this response identify
someone?" means, executed rather than reasoned about.

The ratchet is two-sided on purpose. It fails if a subject-scoped read leaks (the finding),
and it fails if a public aggregate GAINS a guard (over-locking): the cockpit's aggregate
surface is public by declaration (ADR 0009), and locking the 126 GETs would break the very
operators this change protects. Both failures are one-liners to fix; neither can happen by
accident.
"""

from __future__ import annotations

import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tessera.agent.state import ConversationMessage
from tessera.api.operator import OPERATOR_ROLES, SUBJECT_READ_ROLES
from tessera.api.security import require_operator, require_subject_reader
from tessera.memory.transcript import ConversationSummary
from tessera.observability.replay import ReplayBundle

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi import FastAPI

#: The words a person said. If any of these reaches an anonymous caller, that is the finding.
CANARY_QUESTION = "CANARY-QUESTION-je-mappelle-Amadou-mon-IBAN-est-FR76"
CANARY_ANSWER = "CANARY-ANSWER-votre-solde-est-de-1234-euros"
CANARY_CONTEXT = "CANARY-CONTEXT-dossier-client-confidentiel"
CANARY_TITLE = "CANARY-TITLE-opening-user-message"
CANARY_MEMORY = "CANARY-MEMORY-le-client-prefere-etre-appele-le-matin"
CANARY_SUBJECT = "CANARY-SUBJECT-ID-0001"

CANARIES: frozenset[str] = frozenset(
    {
        CANARY_QUESTION,
        CANARY_ANSWER,
        CANARY_CONTEXT,
        CANARY_TITLE,
        CANARY_MEMORY,
        CANARY_SUBJECT,
    }
)

#: The conversation the canary lives in — the id every subject-scoped route is asked for.
CANARY_CONVERSATION = str(uuid.UUID(int=0x7E55E7A))
CANARY_BUNDLE = "canary-bundle-0001"

#: The liveness/readiness probes. Excluded from the sweep, and for a reason worth writing
#: down: ``/readyz``'s JOB is to dial the external stacks (it pings Ollama at :11434), so
#: sweeping it drags a live TCP connection — and a dependency on whether the developer
#: happens to have Ollama up — into a security ratchet. They return a status and a check
#: list; no store, no subject, nothing a canary could ever reach.
NOT_SWEPT: frozenset[str] = frozenset({"/healthz", "/readyz"})

#: The subject-scoped reads, by name. Frozen with ``==`` below, so a guard cannot quietly
#: fall off one and a new one cannot appear without this file in the diff.
#: The last three were NOT found by reading the code — the canary sweep found them, after the
#: audit and a dedicated payload review had both classified them as aggregates. That is the
#: case for a ratchet that executes rather than reasons.
SUBJECT_SCOPED_READS: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/observability/conversations"),
        ("GET", "/observability/conversation-messages"),
        ("GET", "/observability/session-detail"),
        ("GET", "/observability/agent-console/feedback"),
        ("GET", "/observability/replays"),
        ("GET", "/observability/trace-snapshot"),
        ("GET", "/observability/trajectory/{bundle_id}"),
        ("GET", "/observability/provenance/{bundle_id}"),
        ("GET", "/observability/erasure/{conversation_id}"),
        ("GET", "/observability/memory-inventory"),
        ("GET", "/memory/{conversation_id}/items"),
        ("GET", "/observability/handoffs"),
        ("GET", "/observability/context-overflow"),
        ("GET", "/observability/agent-historique"),
        ("GET", "/observability/recouvrement-queue"),
        ("GET", "/observability/recouvrement-case/{case_id}"),
    }
)


@dataclass(frozen=True)
class _CanaryMemory:
    """Shaped like ``persistent.StoredMemory`` — the fields the inventory reads."""

    memory_id: int
    subject_id: str
    kind: str
    text: str
    created_at: datetime
    expires_at: datetime


def _canary_bundle() -> ReplayBundle:
    return ReplayBundle(
        bundle_id=CANARY_BUNDLE,
        captured_at=datetime.now(UTC).isoformat(),
        conversation_id=CANARY_CONVERSATION,
        language="fr",
        question=CANARY_QUESTION,
        context=CANARY_CONTEXT,
        original_answer=CANARY_ANSWER,
        original_model="canary-model",
        original_score=0.5,
        latency_ms={"retrieve": 1.0},
    )


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The real assembly — ``build_app()``. The finding lived at the mount site."""
    from tessera.api.main import build_app

    return build_app()


@pytest.fixture
def seeded(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fill every per-subject store with the canary, without needing Postgres.

    The stores are patched at their source module, so every consumer — direct handler,
    shared helper, or a module three hops away — sees the canary. That is the point: the
    sweep must not care HOW a route reaches the data.
    """
    from tessera.memory import persistent, transcript
    from tessera.observability import console_feedback, replay, session_detail

    now = datetime.now(UTC)
    bundles = [_canary_bundle()]

    # Refuse every outbound connection, so the sweep behaves the same on any machine.
    # Six of the routes dial live stacks — a judge model on Ollama (calibration,
    # failure-clusters, contradictions, embedding-inversion), Langfuse over HTTP (traces-obs)
    # — and on a developer box where Ollama happens to be running that costs ~15s, leaks
    # sockets, and makes a SECURITY ratchet's result depend on which daemons are up. Refusing
    # the connect reproduces CI exactly (nothing listening), and every route then takes its
    # documented degrade path: still swept, still serialized, still checked for the canary —
    # which none of them could hold anyway, since it was never written to those stacks.
    # TestClient is unaffected: it speaks ASGI in-process and never opens a socket.
    def _refused(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no external stack in a unit sweep")

    monkeypatch.setattr(socket.socket, "connect", _refused)

    async def _load_transcript(conversation_id: Any, **_: Any) -> list[ConversationMessage]:
        return [
            ConversationMessage(role="user", content=CANARY_QUESTION),
            ConversationMessage(role="assistant", content=CANARY_ANSWER),
        ]

    async def _list_conversations(agent_id: str, **_: Any) -> list[ConversationSummary]:
        return [
            ConversationSummary(
                conversation_id=CANARY_CONVERSATION,
                title=CANARY_TITLE,
                started_at=now,
                last_at=now,
                message_count=2,
                turn_count=1,
            )
        ]

    async def _list_inventory(*_: Any, **__: Any) -> list[_CanaryMemory]:
        return [
            _CanaryMemory(
                memory_id=1,
                subject_id=CANARY_SUBJECT,
                kind="preference",
                text=CANARY_MEMORY,
                created_at=now,
                expires_at=now,
            )
        ]

    async def _list_subject_memories(*_: Any, **__: Any) -> list[_CanaryMemory]:
        return await _list_inventory()

    async def _session_detail(conversation_id: str, at: str | None = None) -> dict[str, object]:
        return {
            "available": True,
            "conversation_id": conversation_id,
            "title": CANARY_TITLE,
            "turns": [{"question": CANARY_QUESTION, "answer": CANARY_ANSWER}],
        }

    monkeypatch.setattr(transcript, "load_transcript", _load_transcript)
    monkeypatch.setattr(transcript, "list_conversations", _list_conversations)
    monkeypatch.setattr(persistent, "list_inventory", _list_inventory)
    monkeypatch.setattr(persistent, "list_subject_memories", _list_subject_memories)
    monkeypatch.setattr(session_detail, "compute_session_detail", _session_detail)
    monkeypatch.setattr(replay, "recent_bundles", lambda *_a, **_k: list(bundles))
    monkeypatch.setattr(replay, "get_bundle", lambda _bundle_id: bundles[0])
    monkeypatch.setattr(
        console_feedback, "console_feedback", lambda _cid: {"0": f"up:{CANARY_SUBJECT}"}
    )
    yield


def _flat_dependency_calls(route: APIRoute) -> set[Callable[..., object]]:
    """Every dependency callable reachable from the route, router and mount included."""
    calls: set[Callable[..., object]] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependant = stack.pop()
        if dependant.call is not None:
            calls.add(dependant.call)
        stack.extend(dependant.dependencies)
    return calls


def _read_routes(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    return {
        ("GET", route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and "GET" in route.methods
    }


def _concrete(path: str) -> str:
    """Fill path params with the canary's own ids, so the sweep asks for the seeded record."""
    return (
        path.replace("{conversation_id}", CANARY_CONVERSATION)
        .replace("{bundle_id}", CANARY_BUNDLE)
        .replace("{agent_id}", "support-client")
        .replace("{case_id}", "RC-2048")
    )


def test_no_public_read_emits_subject_content(app: FastAPI, seeded: None) -> None:
    """THE ratchet. Sweep every GET as an anonymous caller; the canary must never come back.

    This is the finding, executed: against the pre-fix tree the transcript, the conversations
    directory, the session detail, the replay bundles, the trajectory, the provenance, the
    trace-snapshot drifts and the memory inventory all hand the canary to a caller with no
    session whatsoever.
    """
    client = TestClient(app, raise_server_exceptions=False)
    leaked: dict[str, list[str]] = {}

    for (_method, path), _route in sorted(_read_routes(app).items()):
        if path in NOT_SWEPT:
            continue
        url = _concrete(path)
        params = {"conversation_id": CANARY_CONVERSATION, "agent_id": "support-client"}
        response = client.get(url, params=params)
        if response.status_code in (401, 403):
            continue  # refused — that is the guard doing its job
        body = response.text
        found = sorted(c for c in CANARIES if c in body)
        if found:
            leaked[path] = found

    assert not leaked, (
        "these routes handed a person's own words to an anonymous caller: "
        f"{leaked} — the payload is the judge: move the route onto the pii router "
        "(routes/observability/pii.py), which carries require_subject_reader"
    )


def test_the_subject_scoped_reads_refuse_the_anonymous_caller(app: FastAPI) -> None:
    """Each gated route, by name — 401 with no verified assertion.

    Belt and braces with the sweep above: the sweep proves nothing LEAKS, this proves the
    refusal is an actual refusal (401) and not an empty payload that merely happens to carry
    no canary because the store was cold. "There is no data" and "you may not see it" are
    different answers and the surface must give the second one.
    """
    client = TestClient(app, raise_server_exceptions=False)

    for _method, path in sorted(SUBJECT_SCOPED_READS):
        response = client.get(_concrete(path), params={"conversation_id": CANARY_CONVERSATION})
        assert response.status_code == 401, (
            f"{path} answered {response.status_code} to an anonymous caller — a "
            "subject-scoped read must refuse before it looks anything up"
        )
        assert response.json()["detail"] == "operator authentication required"


def test_the_guarded_reads_are_exactly_the_subject_scoped_ones(app: FastAPI) -> None:
    """The guard is on these eleven, and on nothing else. Frozen with ``==``.

    If a listed route loses the guard, this fails. If an aggregate gains one, this fails.
    Either way the author passes through review with this file in the diff.
    """
    guarded = {
        key
        for key, route in _read_routes(app).items()
        if require_subject_reader in _flat_dependency_calls(route)
    }

    assert guarded == SUBJECT_SCOPED_READS


def test_the_public_aggregate_surface_is_not_locked(app: FastAPI) -> None:
    """Over-correction is a failure too — the shop window stays open (ADR 0009).

    The cockpit's aggregate reads — scores, rates, levels, badges, signals — are public by
    declaration. Locking them would 404 the cockpit for the operators this change protects,
    and would be the *other* way to get this wrong. They carry no subject; they carry no
    guard.
    """
    reads = _read_routes(app)
    public = set(reads) - SUBJECT_SCOPED_READS

    over_locked = {
        key
        for key in public
        if _flat_dependency_calls(reads[key]) & {require_subject_reader, require_operator}
    }
    assert not over_locked, (
        f"these aggregate reads grew an identity guard: {sorted(over_locked)} — if one of "
        "them really started returning subject content, move it to the pii router and add it "
        "to SUBJECT_SCOPED_READS instead of gating it in place"
    )
    # 123rd (ADR 0030): GET /settings/overrides — the operable-knob panel. Model ids,
    # bases and override attributions (operator principals), the same governed-act
    # attribution the public governance feed already shows; no customer subject data.
    # 124-125 (lot 7): GET /observability/evidence-packs/{id}/{manifest,verify} —
    # artifact counts, digests and integrity verdicts; no customer subject data.
    # 126 (2026-07-21): GET /observability/guard-activity — the launcher band's
    # day counters (messages checked/blocked, ADR 0009); no customer subject data.
    # 127 (2026-07-22): GET /observability/comprendre — public proof-tile facts;
    # fleet counts, guard totals, release buckets and chain freshness only.
    # 128 (2026-07-28): GET /observability/fleet-snapshot — the per-agent snapshot
    # fan-out collapsed into one bulk read; the same aggregate signal envelopes as
    # /observability/snapshot, one per registered agent, no customer subject data.
    assert len(public) == 128


def test_the_read_role_set_admits_the_auditor() -> None:
    """The doctrine, asserted: the auditor READS and does not write.

    The mutation plane narrows to writers (``MUTATION_ROLES``); the read plane does not
    narrow at all. An audit role that cannot read what it audits is not an audit role — and
    ``collections`` must stay in, because the recouvrement console's "Récents" list and its
    conversation resume ARE two of these endpoints. Narrowing this set later is a reviewed
    edit, not a silent drift.
    """
    assert SUBJECT_READ_ROLES == OPERATOR_ROLES
    assert {"auditor", "collections", "admin", "superadmin"} <= SUBJECT_READ_ROLES
