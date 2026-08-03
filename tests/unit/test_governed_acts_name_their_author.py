"""RATCHET #3 — the ATTRIBUTION ratchet. A governed act names its author, or the gate is red.

Three ratchets now guard the same frontier, and each asks a question the other two cannot:

1. ``test_mutation_routes_carry_auth.py`` — **who may come in?** Every mutating route carries a
   guard, and every guard *refuses a stranger* (behavioural: the guard is CALLED with the request
   a stranger actually sends, and must raise 401).
2. ``test_subject_reads_carry_auth.py`` — **what does a stranger see?** A canary is seeded into
   every subject store and every GET is swept anonymously; the canary must never come back. The
   payload is the judge, not the handler's intent.
3. **this file** — **does the register name the author?** The first two close the door. Neither
   makes what happens *behind* it accountable. F-5 shut out the anonymous eraser and left the
   ledger recording that *a subject had been erased* with no way, ever, to say by whom.

The rule, stated once:

    Every governed act names its author, derived from a signal the SERVER verified.

The three ways to break it are all represented below, because all three were live in this
codebase on 2026-07-12:

* the act emits **no actor at all** (``audit_memory`` had no such field);
* the act emits an actor the **caller chose** (F-1's ``requested_by`` body field);
* the act emits a **plausible constant** — ``"operator"``, ``"system"``, ``"Julie Dubois"``, or
  the LLM's model name — which is worse than nothing, because a gap gets found and a lie does not.

**The judge is the ledger entry**, not the call arguments. These tests capture what
``_append_to_chain`` actually receives — the fully built, about-to-be-hashed entry — for exactly
the reason the read ratchet sweeps payloads instead of reading handlers: the GDPR erasure was
*fixed* once already, by a change that wrote the actor into ``arguments["actor"]`` where no
reader looks. That fix would have passed any test that inspected the call. The entry is the fact.
"""

from __future__ import annotations

import ast
import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tessera.api.main import build_app
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.api.security import require_operator, require_subject_reader
from tessera.authz import SYSTEM_ROLE, Actor
from tessera.guard import audit as audit_mod
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi import FastAPI

#: The verified operator every probe below acts as. The ratchet asserts the ledger names THIS
#: principal — not a role literal, not a service, not the subject, not the model.
PRINCIPAL = "bob@bank.eu"
ROLE = "admin"

#: The person the acts are performed ON. Deliberately distinct from :data:`PRINCIPAL`, because
#: confusing the two is not hypothetical: the SIEM export shipped the *erased data subject* to
#: the bank's SOC as the author of their own erasure.
SUBJECT = str(uuid.UUID(int=0xDEADBEEF))

#: The identity guards. A route behind one of these has a *person* behind it, so the acts it
#: performs have an author and the ledger must say who. Imported rather than named, so that a
#: guard renamed in ``security.py`` breaks this file loudly instead of silently un-scoping it.
IDENTITY_GUARDS: frozenset[Callable[..., object]] = frozenset(
    {require_operator, require_subject_reader}
)

# ─────────────────────────────────────────────────────────────────────────────────────────
# The governed acts of the GDPR plane, each with the request that performs it.
#
# Frozen with ``==`` against the real app below: a new route on these routers cannot ship
# without a driver here, which means it cannot ship without someone deciding, in review, what
# its ledger entry says about who acted. That is the whole mechanism — the alternative is a
# route that quietly emits an unattributed act and a suite that reads green over it.
# ─────────────────────────────────────────────────────────────────────────────────────────
GOVERNED_ACTS: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {
    ("DELETE", "/memory/{conversation_id}"): (f"/memory/{SUBJECT}", {}),
    ("GET", "/memory/{conversation_id}/items"): (f"/memory/{SUBJECT}/items", {}),
    ("PATCH", "/memory/{conversation_id}/items/{memory_id}"): (
        f"/memory/{SUBJECT}/items/7",
        {"json": {"text": "corrected fact"}},
    ),
    ("DELETE", "/memory/{conversation_id}/items/{memory_id}"): (f"/memory/{SUBJECT}/items/7", {}),
    ("PUT", "/memory/{conversation_id}/consent"): (
        f"/memory/{SUBJECT}/consent",
        {"json": {"granted": True}},
    ),
}


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The real assembly. The finding lived at the mount site once; it will not hide there again."""
    return build_app()


@pytest.fixture
def _operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings().api, "operator_assertion_signing_key", SecretStr("k"))


@pytest.fixture
def ledger(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture the entries as the CHAIN receives them, with the storage stubbed *underneath*.

    Two decisions here are load-bearing, and both were learned the expensive way:

    * **Capture at** ``_append_to_chain``. That is downstream of ``_build_entry``, so what lands
      in the list is the real entry — top-level ``actor`` included. Capturing at ``emit_audit``
      or ``audit_memory`` would inspect the *arguments* and would have certified the fix that
      wrote the actor into ``arguments["actor"]``, where the Journal and the SIEM never look.
    * **Stub UNDER the emitter, never the emitter.** ``erase_subject`` is the canonical erasure
      AND the thing that emits the erasure event. A test that stubs it out goes green while the
      real path drops the attribution on the floor — that exact mistake was made, and caught,
      on this branch. So the four storage deletes are stubbed and ``erase_subject`` itself runs.
    """
    entries: list[dict[str, Any]] = []
    monkeypatch.setattr(
        audit_mod, "_append_to_chain", lambda entry, _sink, _file: entries.append(entry)
    )

    async def _n(*_a: object, **_k: object) -> None:
        return None

    async def _one(*_a: object, **_k: object) -> int:
        return 1

    async def _true(*_a: object, **_k: object) -> bool:
        return True

    async def _none_list(*_a: object, **_k: object) -> list[object]:
        return []

    async def _no_keys(*_a: object, **_k: object) -> tuple[str, ...]:
        return ()

    # Under erase_subject — never erase_subject itself. The deletes count rows now, so the
    # stubs must return counts: a receipt built from None would fail while summing, and the
    # point of this test is the AUTHOR, not the arithmetic.
    monkeypatch.setattr("tessera.memory.transcript.subject_ids_for", _no_keys)
    monkeypatch.setattr("tessera.memory.persistent.delete_subject", _one)
    monkeypatch.setattr("tessera.memory.summary.delete_summary", _one)
    monkeypatch.setattr("tessera.memory.transcript.delete_transcript", _one)
    monkeypatch.setattr("tessera.memory.governance.delete_consent", _one)
    monkeypatch.setattr("tessera.observability.erasure.purge_telemetry", lambda _s: None)
    # Under the other four routes.
    monkeypatch.setattr("tessera.memory.persistent.list_subject_memories", _none_list)
    monkeypatch.setattr("tessera.memory.persistent.update_memory_text", _true)
    monkeypatch.setattr("tessera.memory.persistent.delete_memory", _true)
    monkeypatch.setattr("tessera.memory.governance.set_consent", _n)
    yield entries


def _guarded_routes(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    """Every route on the real app whose dependency tree contains an identity guard."""
    found: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        calls: set[Callable[..., object]] = set()
        stack = list(route.dependant.dependencies)
        while stack:
            dep = stack.pop()
            if dep.call is not None:
                calls.add(dep.call)
            stack.extend(dep.dependencies)
        if calls & IDENTITY_GUARDS:
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                found[(method, route.path)] = route
    return found


def _act_as_operator(app: FastAPI, method: str, url: str, **kwargs: Any) -> int:
    token = issue_operator_assertion(principal=PRINCIPAL, role=ROLE)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(
        method,
        url,
        headers={OPERATOR_ASSERTION_HEADER: token},
        **kwargs,  # type: ignore[arg-type]
    )
    return response.status_code


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE RATCHET
# ─────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_operator_key")
@pytest.mark.parametrize(("method", "path"), sorted(GOVERNED_ACTS))
def test_every_governed_act_names_the_principal_who_performed_it(
    app: FastAPI, ledger: list[dict[str, Any]], method: str, path: str
) -> None:
    """Perform the act as a verified operator; every entry it writes must name that operator.

    The three failure modes are asserted separately, because they fail for different reasons and
    a reader of a red gate deserves to know which one they are looking at.
    """
    url, kwargs = GOVERNED_ACTS[(method, path)]

    status = _act_as_operator(app, method, url, **kwargs)

    assert status < 400, f"{method} {path} answered {status} — the probe never reached the act"
    assert ledger, (
        f"{method} {path} performed a governed act on a person's data and wrote NOTHING to the "
        "chain. An act with no entry cannot have an author; it cannot be reviewed, disputed, or "
        "reconstructed. (This is how `PUT /memory/{id}/consent` shipped: it changed the lawful "
        "basis for retaining someone's data and left no trace at all.)"
    )
    for entry in ledger:
        actor = entry.get("actor")
        assert actor, f"{method} {path} wrote an entry with an EMPTY actor: {entry.get('target')}"
        assert not str(actor).startswith(f"{SYSTEM_ROLE}:"), (
            f"{method} {path} attributed a HUMAN's act to the system ({actor!r}). A route behind "
            "an identity guard has a person behind it, and the system is not that person."
        )
        assert actor == PRINCIPAL, (
            f"{method} {path} named {actor!r} as the author, but the verified assertion said "
            f"{PRINCIPAL!r}. The name in the ledger must be the principal the SERVER verified — "
            "never a role literal, never the bearer's service, never the data subject."
        )
        assert entry.get("actor_role") == ROLE


@pytest.mark.usefixtures("_operator_key")
def test_the_actor_cannot_be_chosen_by_the_caller(
    app: FastAPI, ledger: list[dict[str, Any]]
) -> None:
    """F-1's attack, on the GDPR plane: the caller tries to pin the erasure on someone else.

    Two independent defences must hold, and the test asserts the OUTCOME so it survives a
    refactor of either: every request model on this router is ``extra="forbid"`` (so an ``actor``
    field is a 422), and the handler never reads the body for a name anyway. Whatever the caller
    sends, the trail says who they actually are.
    """
    _act_as_operator(
        app,
        "PUT",
        f"/memory/{SUBJECT}/consent",
        json={"granted": True, "actor": "mallory@evil.example"},
    )

    for entry in ledger:
        assert "evil.example" not in str(entry.get("actor", "")), (
            "the ledger took its actor from the request body — an attribution a caller can "
            "choose is a forgery with a hash on it"
        )


def test_the_governed_acts_of_the_gdpr_plane_are_exactly_these(app: FastAPI) -> None:
    """Frozen with ``==``, both directions. A new route cannot dodge the ratchet by being new.

    ``<=`` would let a route be added to the app and simply not be driven here — present, mutating
    a person's record, and never asked what it writes about who did it. ``==`` means adding one
    puts this file in the diff, in review, with somebody stating on the record what its entry
    says. A stale entry (a route deleted from the app) fails just as loudly, so the list cannot
    rot into a fiction either.
    """
    guarded = _guarded_routes(app)
    on_the_memory_plane = {k for k in guarded if k[1].startswith("/memory/")}

    assert on_the_memory_plane == set(GOVERNED_ACTS), (
        "the GDPR plane's guarded routes and the acts driven by this ratchet have diverged: "
        f"undriven={sorted(on_the_memory_plane - set(GOVERNED_ACTS))} "
        f"stale={sorted(set(GOVERNED_ACTS) - on_the_memory_plane)}"
    )


# ─────────────────────────────────────────────────────────────────────────────────────────
# The STRUCTURAL half. The behavioural half above proves the GDPR plane attributes its acts.
# This one proves no S1 emitter can EXIST without an actor slot — which is the bug `emit_audit`
# was: the one builder in `guard/audit.py` with no top-level actor key, so the actor it was
# eventually given had nowhere to go and ended up somewhere nobody reads.
# ─────────────────────────────────────────────────────────────────────────────────────────


#: One driver per ``emit_*`` in ``guard/audit.py``. Frozen with ``==`` against the module below.
#:
#: This list exists because the test underneath it **used to claim it did not need one**. Its
#: docstring read *"Discovered from the module, not from a list: an emitter added tomorrow is
#: swept in automatically"* — and its body was five hardcoded calls. Five of the ten emitters
#: were never exercised, including ``emit_agent_lifecycle``, which is the one that signs an
#: agent's promotion to production. The sentence was true of the design somebody intended and
#: false of the code, which is the most expensive kind of comment there is.
#:
#: Worse, the sweep was *certifying the bug*: it called ``emit_agent_proposed(name="x")`` with no
#: actor and asserted the entry had one. It passed — because the default ``actor: str =
#: "operator"`` supplied it. A ratchet whose green depended on the very literal it existed to
#: forbid. So the emitters are now discovered for real, every one is driven, and the drivers pass
#: their actor explicitly: an emitter added tomorrow breaks the ``==`` and its author must decide,
#: in review, what its entry says about who acted.
_HUMAN = Actor(principal=PRINCIPAL, role=ROLE)

EMITTER_DRIVERS: dict[str, Callable[[], object]] = {
    "emit_audit": lambda: audit_mod.emit_audit(
        target="t",
        arguments={},
        decisions=[],
        sink="stdout",
        outcome="allowed",
        actor=audit_mod.GUARD_ACTOR,
    ),
    "emit_governance_mutation": lambda: audit_mod.emit_governance_mutation(
        target="guard.rule_state",
        detail={"rule": "r", "enabled": False},
        actor=_HUMAN,
        sink="stdout",
    ),
    "emit_handoff": lambda: audit_mod.emit_handoff(
        from_agent="a", to_agent="b", conversation_id="c", turn_id="t", reason="r", sink="stdout"
    ),
    "emit_routing": lambda: audit_mod.emit_routing(
        agent_id="a", conversation_id="c", turn_id="t", reason="r", handoff=False, sink="stdout"
    ),
    "emit_business_event_audit": lambda: audit_mod.emit_business_event_audit(
        event={
            "event_name": "intent.routed",
            "author_principal": PRINCIPAL,
            "author_role": ROLE,
            "actor": "operator",
        },
        sink="stdout",
    ),
    "emit_agent_proposed": lambda: audit_mod.emit_agent_proposed(
        name="x", actor=_HUMAN, sink="stdout"
    ),
    "emit_agent_lifecycle": lambda: audit_mod.emit_agent_lifecycle(
        agent_id="a", phase="released", actor=_HUMAN, sink="stdout"
    ),
    "emit_canary_invocation": lambda: audit_mod.emit_canary_invocation(
        agent_id="a",
        binding="b",
        verdict="pass",
        conversation_id="c",
        turn_id="t",
        actor=audit_mod.CANARY_ACTOR,
        sink="stdout",
    ),
    "emit_agent_invocation": lambda: audit_mod.emit_agent_invocation(
        agent_id="a",
        binding="b",
        verdict="pass",
        actor=_HUMAN,
        conversation_id="c",
        turn_id="t",
        sink="stdout",
    ),
    "emit_ledger_attestation": lambda: audit_mod.emit_ledger_attestation(
        incident="i",
        cause="c",
        decision="d",
        evidence={},
        forks=[],
        orphans=[],
        actor=_HUMAN,
        sink="stdout",
    ),
    "emit_ledger_seal": lambda: audit_mod.emit_ledger_seal(
        sealed_head="h",
        prev_sealed_head=None,
        provider="noop",
        tsa=None,
        token_b64="",
        sealed_at="2026-07-13T00:00:00+00:00",
        qualified=False,
        actor=audit_mod.SEAL_ACTOR,
        sink="stdout",
    ),
}


def test_every_s1_emitter_is_driven_by_this_file() -> None:
    """Frozen with ``==``. An emitter cannot dodge the sweep below by being new.

    The previous version of this ratchet *said* it discovered emitters from the module and did
    not. This is the discovery it promised — and it is a ``==``, not a ``<=``, so a stale driver
    (an emitter deleted from the module) fails just as loudly as a missing one. A list that is
    allowed to rot becomes a fiction, and a fiction that reads green is what we are here to stop.
    """
    live = {
        name
        for name in vars(audit_mod)
        if name.startswith("emit_") and callable(getattr(audit_mod, name))
    }

    assert live == set(EMITTER_DRIVERS), (
        "the S1 emitters and the drivers in this file have diverged: "
        f"undriven={sorted(live - set(EMITTER_DRIVERS))} "
        f"stale={sorted(set(EMITTER_DRIVERS) - live)}. An emitter with no driver has never been "
        "asked what its entry says about who acted."
    )


@pytest.mark.parametrize("emitter", sorted(EMITTER_DRIVERS))
def test_every_s1_emitter_stamps_a_top_level_actor_and_role(
    monkeypatch: pytest.MonkeyPatch, emitter: str
) -> None:
    """Every entry that enters the opposable chain names an author AND the authority they held.

    ``actor_role`` is asserted too, and that is not symmetry for its own sake: it is what lets a
    reader separate ``system:`` principals (the guard, the seal cycle, the scheduler — they acted
    on policy and cannot be asked what they were thinking) from a person who can be. Nine of the
    ten emitters wrote a bare ``actor`` and no role at all, so the Journal's role column was
    inferred by heuristic from the event's shape — inference is exactly what a recorded field
    replaces.
    """
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(audit_mod, "_append_to_chain", lambda entry, _s, _f: captured.append(entry))
    monkeypatch.setattr(get_settings().guard, "audit_sink", "stdout")

    EMITTER_DRIVERS[emitter]()

    assert captured, f"{emitter} chained nothing — the driver proves nothing"
    for entry in captured:
        actor = entry.get("actor")
        assert isinstance(actor, str) and actor, (
            f"{emitter} enters the opposable chain with no top-level `actor` key. Every reader of "
            "this journal — the cockpit Journal, the governance feed, the SIEM export — looks "
            "there and only there. An entry without it is an act nobody performed."
        )
        assert entry.get("actor_role"), (
            f"{emitter} names an author but not the authority they held. `system:seal-cycle` and "
            "`bob@bank.eu` are answerable in entirely different ways, and a reader must not have "
            "to infer which one they are holding from the shape of the event."
        )
        assert actor != SYSTEM_ROLE, (
            f"{emitter} wrote the bare string {SYSTEM_ROLE!r}. That is the one value that cannot "
            "be told apart from an omission: `Actor.system(task)` exists so that 'the seal cycle "
            "did this' never renders identically to 'the code forgot to say who did this'."
        )


def test_the_audit_entry_version_says_whether_an_actor_was_recordable() -> None:
    """v3 is not cosmetic: it is what lets a reader distinguish "old" from "broken".

    A v2 entry has no author because the schema had none — an honest historical gap. A v3 entry
    always has one. Adding the field silently would have collapsed those two into a single
    unreadable state, and a regulator resolves an ambiguity like that against the controller.
    """
    entry = audit_mod._build_entry(
        target="memory.forget",
        arguments={"subject_id": SUBJECT},
        decisions=[],
        outcome="allowed",
        error=None,
        model="llama3.2:3b",
        data_residency="eu",
        agent_id="support-client",
        actor=audit_mod.Actor(principal=PRINCIPAL, role=ROLE),
        synthetic=False,
    )

    assert entry["version"] == 3
    assert entry["actor"] == PRINCIPAL
    assert entry["actor_role"] == ROLE
    assert entry["synthetic"] is False
    assert entry["model"] == "llama3.2:3b", "the model is recorded, and it is not the author"


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE CLASS, on EVERY plane. The behavioural half above drives the GDPR routes; a route on
# another plane could still take its author from the body and never be asked about it.
#
# One did. `POST /observability/curation/decision` sat on the mutations router — hardened with
# `require_operator` since the 26 anonymous mutations were closed — and wrote
# `decided_by=body.decided_by` straight into the register. A verified operator could therefore
# sign a curation decision in ANYONE's name. The door was locked and the register was left open
# beside it.
#
# AUTHENTICATION IS NOT ATTRIBUTION. The guard answers *may you come in*; only a server-derived
# `Actor` answers *who signed*. These two tests close that as a class, structurally, across
# every router — because the behavioural sweep can only ever cover the routes someone thought
# to drive, and the point of a class ratchet is to catch the one nobody thought of.
# ─────────────────────────────────────────────────────────────────────────────────────────

#: Field names that answer "WHO did this". A request model may not declare one, and a handler
#: may not read one off a body: whoever can choose the name in the register can sign for someone
#: else. `assignee` is deliberately NOT here — it names who a task is given TO, not who acted.
ACTOR_FIELD_NAMES = (
    "actor",
    "decided_by",
    "requested_by",
    "performed_by",
    "approved_by",
    "created_by",
    "author",
    "principal",
    "operator",
)

_API_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera" / "api"
#: The class ratchet below walks **all** of it. The body/model ratchets police the wire; an
#: identity default is a lie the wire never sees, and it lived two thousand lines from any route.
_SRC = Path(__file__).resolve().parents[2] / "src" / "tessera"


#: The names a route binds a request body to. An attribute read off one of these, whose name
#: answers "who did this", is the finding — whatever the handler then does with it.
_BODY_PARAMS = frozenset({"body", "payload", "request", "req"})


def test_no_handler_takes_its_actor_from_a_request_body() -> None:
    """`decided_by=body.decided_by` — F-1's exact shape, alive inside a router we had hardened.

    Walked with `ast`, not a grep, and the difference is the whole reliability of the check. A
    regex over these files flags `principal = payload.get("principal")` in `operator.py` — which
    is the *verifier* reading a signed assertion, the one place a name legitimately arrives from
    the wire — and it flags the prose in this very file that quotes the bug. Both are false, both
    would have been silenced with a noqa, and a ratchet that trains you to silence it polices
    nothing. The AST sees attribute access on a body and nothing else.
    """
    guilty: list[str] = []
    for path in _API_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in _BODY_PARAMS
                and node.attr in ACTOR_FIELD_NAMES
            ):
                where = f"{path.relative_to(_API_SRC)}:{node.lineno}"
                guilty.append(f"{where} — {node.value.id}.{node.attr}")

    assert not guilty, (
        f"{guilty} attributes a governed act to a name taken from the REQUEST BODY. The caller "
        "chooses it, so the register records whoever they pleased — an attribution a caller can "
        "pick is a forgery with a timestamp. Derive it from the verified session: "
        "`actor_of(session)`, or `Actor.system(<task>)` when no human ordered the act."
    )


def test_no_request_model_declares_a_field_that_names_the_author() -> None:
    """The upstream half: if the wire cannot carry an author, no handler can be tempted by one.

    Asserted on the Pydantic models rather than the handlers, because the two failures are
    different and both are real: a handler that *reads* the field (above), and a model that
    *accepts* it while the handler ignores it — which is worse than it sounds, since a silently
    dropped identity field and an honoured one are indistinguishable to the caller. Removing the
    field with `extra="forbid"` turns that silence into a 422.
    """
    from pydantic import BaseModel

    import tessera.api.main as api_main  # noqa: F401  imports every route module

    offenders: list[str] = []
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if not name.startswith("tessera.api"):
            continue
        for attr in vars(module).values():
            if not isinstance(attr, type) or not issubclass(attr, BaseModel):
                continue
            if attr is BaseModel:
                continue
            if attr.__module__ != name:  # only models DECLARED here
                continue
            named = set(attr.model_fields) & set(ACTOR_FIELD_NAMES)
            # A RESPONSE model must name the author — that is the whole point of the ledger view.
            # Only what arrives on the WIRE from a caller is banned, and a request model is what
            # a route binds to a body: those, and only those, are what this test walks.
            if named and any(k.endswith(("Body", "Request")) for k in (attr.__name__,)):
                offenders.append(f"{name}.{attr.__name__} declares {sorted(named)}")

    assert not offenders, (
        f"{offenders} — a REQUEST model declares a field that names the author. Whatever the "
        "handler does with it, the wire now accepts an identity the caller chose. Delete the "
        "field and set `extra='forbid'`, so a caller who still sends one gets a loud 422 "
        "instead of a silently ignored forgery."
    )


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE CLASS: an identity that has a DEFAULT VALUE — wherever it lives.
#
# The two ratchets above police the WIRE: a body may not carry an author, a request model may
# not declare one. Both are about what a caller can send. Neither could see the finding that
# outlived them both.
#
#     agent/recouvrement.py:2298    requested_by: str = "Julie Dubois"
#
# Not on a route. Not on a model. Not reachable from the wire at all — a default on a keyword
# argument, one call below the handler, in a file no authz ratchet had any reason to read. F-1
# removed the body field and hardened the route, and this sat underneath it the whole time,
# ready to sign a governed action in the name of a person who does not exist for any caller that
# simply omitted the argument. Nine tests did exactly that, in green, for two months.
#
# It survived because it was never EXECUTED in production — the route always passed a name. A lie
# that never runs is never caught, and it decays into furniture. By 2026-07-13 `security.py:184`
# named `"Julie Dubois"` in its own doctrine as the canonical anti-pattern while, two thousand
# lines away, the value itself was still the default. The codebase was describing the bug it had.
#
# So the rule is stated as a CLASS and enforced structurally, everywhere:
#
#     An identity field may not have a default value. Anywhere.
#
# The asymmetry with a *classification* is the whole content of the rule, and it is why
# `business_events.actor` (the §A2.1 party KIND) was renamed to `ActorKind` rather than carved
# out with an exception. "Which category of party" has a safe answer when nobody says — `system`
# — and getting it wrong mislabels a row. "Who did this" has none: every candidate default is a
# plausible constant, and a plausible constant in the author column is worse than a gap, because
# a gap gets found and a lie does not. An exception list would have said "this looks like an
# identity but trust us". The rename says what was actually true, and then no exception is needed.
# ─────────────────────────────────────────────────────────────────────────────────────────


def _names_somebody(default: ast.expr | None) -> bool:
    """Whether this default puts a NAME where a person should be.

    The precise class, and the distinction is the doctrine's own sentence — *a gap gets found and
    a lie does not*:

    * ``= None`` **names nobody.** It is an honest absence. A reader sees a hole and asks about
      it; nothing is asserted that is untrue. Allowed — and it costs nothing, because the
      *envelope's* author (``BusinessEvent.author_principal``, ``Actor``) is required with no
      default at all, so a governed act still cannot reach the ledger unattributed. The empty
      case is caught behaviourally, by the emitter sweep, where the entry is the judge.
    * ``= "operator"`` / ``"system"`` / ``"seal-cycle"`` / ``"Julie Dubois"`` / ``"audit-log"``
      **name somebody.** Every one is plausible, constant, and false, and the trail reads
      *complete* while identifying no one. That is strictly worse than the hole.

    So: a default that evaluates to ``None`` is fine; anything else on an identity field is the
    finding. Banning ``None`` too would have been the tidier rule and the wrong one — it would
    have forced ``requested_by`` onto payloads that genuinely have no requester, and a required
    field with nothing true to put in it is how fabricated values get born in the first place.
    """
    return default is not None and not (isinstance(default, ast.Constant) and default.value is None)


def _identity_defaults_in(path: Path) -> list[str]:
    """Every default that NAMES somebody on an identity-named field, in one file. AST, not regex.

    Two shapes, because both were live on 2026-07-13:

    * a **parameter** with a default — ``def f(*, actor: str = "operator")``. Seven of the ten
      S1 emitters, ``request_release`` (which signs an agent's promotion to production), and the
      ghost itself.
    * a **declared field** with a value — ``actor: str = "audit-log"`` on the audit *response*
      model, which meant an entry reaching the Journal without an author was rendered as having
      been performed by a thing called "audit-log". Nothing ever hit it. That is not a defence:
      it is exactly how ``"Julie Dubois"`` survived two months and three fixes that walked past it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            positional = args.posonlyargs + args.args
            pad = len(positional) - len(args.defaults)
            pairs: list[tuple[ast.arg, ast.expr | None]] = [
                (arg, args.defaults[i - pad] if i >= pad else None)
                for i, arg in enumerate(positional)
            ]
            pairs += list(zip(args.kwonlyargs, args.kw_defaults, strict=True))
            for arg, default in pairs:
                if arg.arg in ACTOR_FIELD_NAMES and _names_somebody(default):
                    found.append(
                        f"{path.name}:{node.lineno} — "
                        f"def {node.name}({arg.arg}={ast.unparse(default)})"  # type: ignore[arg-type]
                    )
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in ACTOR_FIELD_NAMES
            and _names_somebody(node.value)
        ):
            found.append(
                f"{path.name}:{node.lineno} — {node.target.id} = {ast.unparse(node.value)}"  # type: ignore[arg-type]
            )
    return found


def test_no_identity_field_anywhere_in_the_package_has_a_default() -> None:
    """THE CLASS. Walks all of ``src/tessera`` — not the routes, not the models: everything.

    Fourteen fields failed this on 2026-07-13, and only one of them (`recouvrement.py`) was
    written down anywhere as a finding. That ratio is the argument for the ratchet: a review
    catches the instance somebody thought to look for, and a class ratchet catches the thirteen
    nobody did — including ``build_ledger_seal_entry(actor="seal-cycle")``, which signs the
    chain's own external seal, and ``request_release(actor="operator")``, which signs an agent's
    promotion to production.
    """
    guilty = sorted(f for path in _SRC.rglob("*.py") for f in _identity_defaults_in(path))

    assert not guilty, (
        "an identity field has a DEFAULT VALUE:\n  "
        + "\n  ".join(guilty)
        + "\n\nA default here lets an author omit the one field that makes the record worth "
        "keeping — and read green while doing it. Every candidate default is a plausible "
        'constant: `"operator"` is a role and not a person, `"system"` cannot be told apart '
        'from an omission, `"Julie Dubois"` is a person who does not exist. Require an `Actor`: '
        "`actor_of(session)` for a human, `Actor.system(<task>)` when no human ordered the act. "
        "If the field is a CLASSIFICATION and not an identity, it is misnamed — rename it "
        "(`ActorKind`), do not except it."
    )


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE GOVERNANCE PLANE — behavioural. Never an ImportError; always the real route, the real
# emitter, and the real entry.
#
# ADR 0024 §Owed listed three governed acts that changed the system and wrote NOTHING:
#
#   * `POST /observability/agent-garde-fous/rule-state` — switching a guardrail off.
#   * `PUT  /settings/synthesis-admin`                  — a superadmin privilege grant.
#   * `POST /observability/agents/release`              — promoting an agent to production,
#                                                          signed by the literal "operator".
#
# The first two left no residue at all. Every incident review that ever asked "was the injection
# screen on at 14:05, and who turned it off?" would have been answered from the guard's CURRENT
# state — the one thing that cannot testify about the past. The third wrote an entry and signed
# it with a role, so two people promoting two agents produced two byte-identical attributions.
#
# Asking the question as a CLASS rather than route-by-route immediately found a fourth nobody had
# written down: `POST /observability/automations/rule-state`, the guardrail toggle's exact twin.
# That is the entire argument for a ratchet over a checklist.
# ─────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Act:
    """One governed act: the request that performs it, and the role it takes to be allowed."""

    method: str
    url: str
    role: str
    json: dict[str, Any] | None = None


#: Frozen with ``==`` against the app's real governance-mutation routes, below. A cockpit
#: mutation added tomorrow cannot ship without a driver here — which means it cannot ship
#: without someone stating, on the record, what its ledger entry says about who acted.
GOVERNANCE_ACTS: dict[str, _Act] = {
    "switch a guardrail off": _Act(
        "POST",
        "/observability/agent-garde-fous/rule-state",
        "admin",
        {"key": "__RULE__", "enabled": False},
    ),
    "switch an automation rule off": _Act(
        "POST",
        "/observability/automations/rule-state",
        "admin",
        {"rule_id": "__AUTOMATION__", "enabled": False},
    ),
    "suspend every automation rule": _Act(
        "POST",
        "/observability/automations/rules-state",
        "admin",
        {"enabled": False},
    ),
    "open a durable incident": _Act(
        "POST",
        "/observability/incidents",
        "admin",
        {"title": "probe incident", "severity": "moyen"},
    ),
    "transition an incident": _Act(
        "POST",
        "/observability/incidents/transition",
        "admin",
        {"incident_id": "INC-probe-001", "status": "en_cours"},
    ),
    "attach a playbook to an incident": _Act(
        "POST",
        "/observability/incidents/playbook",
        "admin",
        {"incident_id": "INC-probe-001", "playbook_id": "pb-injection"},
    ),
    "freeze an evidence-pack manifest": _Act(
        "POST",
        "/observability/evidence-packs",
        "admin",
        {},
    ),
    "decide an automation approval": _Act(
        "POST",
        "/observability/automations/approve",
        "admin",
        {"approval_id": "probe-approval", "approved": True},
    ),
    "promote an agent to production": _Act(
        "POST", "/observability/agents/release", "admin", {"agent_id": "support-client"}
    ),
    "propose an agent for the fleet": _Act(
        "POST", "/observability/agents/propose", "admin", {"name": "new-agent"}
    ),
    "grant an admin sight of the synthesis": _Act(
        "PUT", "/settings/synthesis-admin", "superadmin", {"enabled": True}
    ),
    "set a governed config override": _Act(
        "PUT",
        "/settings/overrides",
        "superadmin",
        {"key": "llm.chat_model", "value": "llama3.2:3b", "reason": "ratchet probe"},
    ),
    "revert a governed config override": _Act(
        "POST",
        "/settings/overrides/revert",
        "superadmin",
        {"key": "llm.chat_model", "reason": "ratchet probe"},
    ),
    # 12th act, 2026-07-17 (ADR 0031): a sampling-slider save changes production
    # behaviour, so it joined the governed acts — and this registry's scope was
    # widened to SEE its route (it was previously outside governed_prefixes,
    # green by blind spot — ADR 0026).
    "save an agent sampling slider": _Act(
        "POST",
        "/observability/agent-configurations/config",
        "admin",
        {"changes": {"temperature": 0.35}, "lang": "fr"},
    ),
    # 13th/14th acts, 2026-07-18 (ADR 0037): the prompt-overlay lifecycle — an
    # operator proposes, a superadmin reviews; both change what production
    # serves, both name their author. The registry's scope was widened to see
    # their routes at the same time (Insight 177 protocol).
    "propose an agent prompt overlay": _Act(
        "POST",
        "/observability/agent-prompt-overlay/propose",
        "admin",
        {"agent_id": "support-client", "text": "probe overlay"},
    ),
    "review an agent prompt overlay": _Act(
        "POST",
        "/observability/agent-prompt-overlay/review",
        "superadmin",
        {"agent_id": "support-client", "action": "revoke"},
    ),
    # 15th/16th acts, 2026-07-22 (WF-01): a queue-item transition is a governed
    # act — it moves a human case along its lifecycle. Both endpoints journal
    # the transition with the verified author and emit to the chain; the
    # registry's scope was widened to see their routes at the same time
    # (Insight 177 protocol).
    "transition a business queue item": _Act(
        "POST",
        "/observability/inbox/item-state",
        "admin",
        {"item_id": "ITEM-probe-001", "status": "progress"},
    ),
    "transition an eval queue item": _Act(
        "POST",
        "/observability/agent-a-faire/item-state",
        "admin",
        {"item_id": "ITEM-probe-001", "status": "done"},
    ),
}


@pytest.fixture
def _governance_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the STORES, never the emitters — the lesson the GDPR ratchet paid for.

    Stubbing an emitter is how a suite certifies a fix that never happened. So each store's
    write is neutralised (they want Postgres and a JSON file on disk) and every ledger call
    above them runs for real, through the real route, into the real ``_append_to_chain``.
    """

    async def _set_flag(*, enabled: bool) -> bool:
        return enabled

    monkeypatch.setattr("tessera.api.routes.settings.set_synthesis_admin", _set_flag)
    monkeypatch.setattr(
        "tessera.observability.agent_garde_fous.set_rule_state", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "tessera.observability.automation_store.set_rule_enabled", lambda *_a, **_k: None
    )

    def _decide_approval(approval_id: str, *, approved: bool, decided_by: str) -> dict[str, object]:
        return {
            "id": approval_id,
            "rule_id": "low_faith_review",
            "status": "approved" if approved else "rejected",
            "decided_by": decided_by,
        }

    monkeypatch.setattr("tessera.observability.automation_store.decide_approval", _decide_approval)

    # The override store wants Postgres; stub the store (patching the copies the
    # route imported), keep the route + emitter + chain real (ADR 0030 / 0024).
    from datetime import UTC, datetime

    from tessera.api.config_overrides import Override

    async def _set_override(key: str, value: str, *, author: str, reason: str) -> Override:
        return Override(
            key=key, value=value, author=author, reason=reason, updated_at=datetime.now(UTC)
        )

    async def _delete_override(key: str) -> None:
        return None

    monkeypatch.setattr("tessera.api.routes.settings.set_override", _set_override)
    monkeypatch.setattr("tessera.api.routes.settings.delete_override", _delete_override)

    # Evidence packs + incidents (lots 7/10): stub the STORES, keep the routes,
    # emitters and chain real — the same discipline as every stub above.
    def _create_pack(*, created_by: str) -> dict[str, object]:
        return {"pack_id": "PK-probe-001", "created_by": created_by, "sha256": "0" * 64}

    monkeypatch.setattr("tessera.observability.evidence_pack_store.create_pack", _create_pack)

    def _create_incident(
        *, title: str, severity: str, domain: str, opened_by: str, source: str = "manual"
    ) -> dict[str, object]:
        return {"incident_id": "INC-probe-001", "opened_by": opened_by, "severity": severity}

    def _transition_incident(incident_id: str, status: str, *, by: str) -> dict[str, object]:
        return {"incident_id": incident_id, "status": status, "closed_by": by}

    def _attach_playbook(incident_id: str, playbook_id: str, *, by: str) -> dict[str, object]:
        return {"incident_id": incident_id, "playbook_id": playbook_id}

    monkeypatch.setattr("tessera.observability.incident_store.create_incident", _create_incident)
    monkeypatch.setattr(
        "tessera.observability.incident_store.transition_incident", _transition_incident
    )
    monkeypatch.setattr("tessera.observability.incident_store.attach_playbook", _attach_playbook)

    # Agent-configurations save (12th act, ADR 0031): stub the STORE write (it
    # wants a JSON file on disk) and the runtime-effectiveness read (it wants
    # the ADR 0030 override store); route, emitter and chain stay real. The
    # stub reports every posted key as changed so the act fires.
    def _set_agent_config(
        changes: dict[str, object], agent_id: str = "", *, author: str | None = None
    ) -> list[str]:
        assert author, "the route must pass the verified principal, never None"
        return sorted(changes)

    async def _serving(_slug: str) -> tuple[str, str, tuple[str, ...], str]:
        return "llama3.2:3b", "ollama", ("temperature",), "base"

    monkeypatch.setattr(
        "tessera.observability.agent_configurations.set_agent_config", _set_agent_config
    )
    monkeypatch.setattr(
        "tessera.observability.agent_configurations._serving_effectiveness", _serving
    )

    # Prompt-overlay lifecycle (13th/14th acts, ADR 0037): stub the STORE (it
    # wants a JSON file on disk and the limes guard); route, emitter and chain
    # stay real. The stubs assert the routes pass the verified principal.
    def _propose_overlay(agent_id: str, text: str, *, actor: Actor) -> dict[str, object]:
        assert actor.principal, "the propose route must pass the verified principal"
        return {
            "draft": {"text": text, "author": actor.principal, "at": "probe"},
            "approved": None,
            "history": [],
        }

    def _review_overlay(agent_id: str, action: str, *, reviewer: str) -> dict[str, object]:
        assert reviewer, "the review route must pass the verified principal"
        return {"draft": None, "approved": None, "history": []}

    monkeypatch.setattr("tessera.observability.prompt_overlay.propose_overlay", _propose_overlay)
    monkeypatch.setattr("tessera.observability.prompt_overlay.review_overlay", _review_overlay)

    # Queue-item transitions (15th/16th acts, WF-01): stub the STORE write (it
    # wants a JSON file + the JSONL journal on disk), the partition read and
    # the rebuilt page payloads; route, emitter and chain stay real.
    def _set_item_state(
        item_id: str, *, status: str | None = None, assignee: str | None = None, by: str
    ) -> None:
        assert by, "the route must pass the verified principal, never empty"

    monkeypatch.setattr("tessera.observability.operator_items.set_item_state", _set_item_state)
    monkeypatch.setattr(
        "tessera.observability.operator_items.available_item_ids",
        lambda _nature: {"ITEM-probe-001"},
    )
    monkeypatch.setattr("tessera.observability.inbox.compute_inbox_overview", lambda *_a, **_kw: {})
    monkeypatch.setattr(
        "tessera.observability.agent_a_faire.compute_agent_a_faire", lambda *_a, **_kw: {}
    )


def _resolve(act: _Act) -> _Act:
    """Fill the placeholders from the live stores — a driver must use a REAL rule id."""
    from tessera.observability import agent_garde_fous, automation_store

    body = dict(act.json or {})
    if body.get("key") == "__RULE__":
        body["key"] = sorted(agent_garde_fous.available_rules())[0]
    if body.get("rule_id") == "__AUTOMATION__":
        body["rule_id"] = sorted(automation_store.available_rule_ids())[0]
    return replace(act, json=body)


@pytest.mark.usefixtures("_operator_key", "_governance_stores")
@pytest.mark.parametrize("name", sorted(GOVERNANCE_ACTS))
def test_every_governance_act_writes_an_entry_that_names_its_author(
    app: FastAPI, ledger: list[dict[str, Any]], name: str
) -> None:
    """Perform the act as a verified operator. It must write, and the entry must name them.

    Two assertions, two different bugs, and the first is the one ADR 0024 could not close:

    * ``assert ledger`` — the act wrote **something**. Switching a guardrail off wrote nothing
      at all; an act that leaves no trace is not governed, whatever the compliance page says.
    * ``actor == PRINCIPAL`` — and it wrote the **person**, not ``"operator"``. A role is true
      of everyone and identifies no one.
    """
    act = _resolve(GOVERNANCE_ACTS[name])
    token = issue_operator_assertion(principal=PRINCIPAL, role=act.role)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.request(
        act.method, act.url, headers={OPERATOR_ASSERTION_HEADER: token}, json=act.json
    )

    assert (
        response.status_code < 400
    ), f"{name}: the probe answered {response.status_code} and never reached the act"
    assert ledger, (
        f"{name} changed the system and wrote NOTHING to the chain. An act with no entry has no "
        "author, no timestamp and no way to be disputed — it did not happen, as far as any "
        "reviewer can ever prove. (This is how switching a guardrail off shipped.)"
    )
    for entry in ledger:
        actor = entry.get("actor")
        assert actor == PRINCIPAL, (
            f"{name} named {actor!r} as its author, but the verified assertion said "
            f'{PRINCIPAL!r}. `"operator"` is a ROLE — it answers what authority acted and '
            "answers *who* with a word that is true of everyone."
        )
        assert entry.get("actor_role") == act.role


def test_the_governance_acts_are_exactly_these(app: FastAPI) -> None:
    """Frozen ``==`` against the app. A new cockpit mutation cannot dodge the ratchet by being new.

    Scoped to the routers that carry governance mutations. ``<=`` would let a route be added and
    simply never driven — present, changing the system, and never asked what it records about
    who did it. ``==`` puts this file in the diff instead.
    """
    driven = {(a.method, a.url) for a in GOVERNANCE_ACTS.values()}
    live = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods - {"HEAD", "OPTIONS"}
        if _is_governance_mutation(route, method)
    }

    assert live == driven, (
        "the app's governance mutations and the acts driven here have diverged: "
        f"undriven={sorted(live - driven)} stale={sorted(driven - live)}"
    )


def _is_governance_mutation(route: APIRoute, method: str) -> bool:
    """A write on the cockpit control plane, or the settings plane — the acts §Owed named."""
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    governed_prefixes = (
        "/observability/agent-garde-fous/",
        "/observability/automations/rule-state",
        "/observability/automations/rules-state",
        "/observability/automations/approve",
        "/observability/agents/",
        "/observability/evidence-packs",
        "/observability/incidents",
        # 2026-07-17 (ADR 0031): the sampling-slider save became a governed act.
        "/observability/agent-configurations/config",
        # 2026-07-18 (ADR 0037): the prompt-overlay lifecycle joined (2 acts).
        "/observability/agent-prompt-overlay/",
        # 2026-07-22 (WF-01): queue-item transitions joined (2 acts).
        "/observability/inbox/item-state",
        "/observability/agent-a-faire/item-state",
        "/settings/",
    )
    return route.path.startswith(governed_prefixes)


# ─────────────────────────────────────────────────────────────────────────────────────────
# THE GHOST — `agent/recouvrement.py:2298`, `requested_by: str = "Julie Dubois"`.
# ─────────────────────────────────────────────────────────────────────────────────────────


def test_a_recouvrement_action_writes_the_verified_actor_into_the_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole lane, end to end, through the real workflow: the chain names the real officer.

    The workflow RUNS — thirty-odd business events, the real ``record_business_event``, the real
    ``emit_business_event_audit``, the real ``_append_to_chain``. Only the chain's tail is
    captured. Stubbing the workflow here would test the seam and miss the floor, which is exactly
    the mistake that let ``"Julie Dubois"`` live one call below a route that was already correct.

    Three things are asserted, and each was false until 2026-07-13:

    1. the chain names ``julie.moreau@credit-aurore.eu`` — the principal the HMAC verified;
    2. the entry's ``actor_kind`` says ``internal_collaborator``, so the 3-level ladder finally
       counts this as the human action it is (it read ``system`` for all 32 of these events);
    3. the fabricated human appears **nowhere** in anything the chain received.
    """
    from tessera.agent.recouvrement import run_recouvrement_action_workflow_v1
    from tessera.observability.business_events import reset_business_event_store

    # This test runs the REAL workflow, so it really emits into the process-wide business-event
    # store — and `test_operator_items` reads that store. Left dirty, this probe's RC-2048 case
    # surfaced in another file's operator queue and failed it. Stubbing the workflow would have
    # avoided the leak *and* the proof; resetting the store keeps both.
    reset_business_event_store()
    entries: list[dict[str, Any]] = []
    monkeypatch.setattr(
        audit_mod, "_append_to_chain", lambda entry, _sink, _file: entries.append(entry)
    )
    officer = Actor(principal="julie.moreau@credit-aurore.eu", role="collections")

    run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact={
            "id": "RC-2048-reminder-v1",
            "type": "reminder_draft_v1",
            "task": "artifact_action",
            "title": "Relance",
            "status": "draft",
            "content": {},
        },
        action_name="submit_for_validation",
        actor=officer,
    )

    assert entries, "a governed artifact transition wrote nothing to the chain"
    authored = [e for e in entries if e.get("actor")]
    assert authored, "every entry the action wrote is unattributed"
    for entry in authored:
        assert entry["actor"] == officer.principal, (
            f"the chain says {entry['actor']!r} performed this action. The verified assertion "
            f"said {officer.principal!r}. Before this lane it said 'system' — the envelope's "
            "closed-vocabulary KIND, written into the one key every reader treats as the AUTHOR."
        )
        assert entry.get("actor_role") == "collections"
        assert entry.get("actor_kind") == "internal_collaborator", (
            "the party KIND must say a human ordered this. All 32 of recouvrement's business "
            "events carried kind=system, so the §A2.2 ladder scored a human action as machine."
        )

    blob = repr(entries)
    assert _GHOST not in blob, "the fabricated human reached the opposable chain"

    reset_business_event_store()  # leave the shared store as we found it


def test_the_ghost_is_gone_and_cannot_be_reintroduced_by_omission() -> None:
    """``actor`` is required. Omitting it is a TypeError, not a fabricated human.

    This is the whole difference between a default and a required type, stated as an
    executable sentence. Nine tests called this function without an author and read green.
    """
    from tessera.agent.recouvrement import run_recouvrement_action_workflow_v1

    with pytest.raises(TypeError, match="actor"):
        run_recouvrement_action_workflow_v1(  # type: ignore[call-arg]
            case_id="RC-2048",
            artifact={
                "id": "a",
                "type": "reminder_draft_v1",
                "task": "artifact_action",
                "title": "t",
                "status": "draft",
                "content": {},
            },
            action_name="copy_artifact_text",
        )


#: The fabricated human. Kept as a fragment so this very line is not a hit for its own ratchet.
_GHOST = "Julie" + " Dubois"

_REPO = Path(__file__).resolve().parents[2]


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """The ``id()`` of every string constant that is a DOCSTRING — prose, not a value."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return docstrings


def test_the_fabricated_human_survives_nowhere_as_a_value() -> None:
    """The name may be **quoted** as the anti-pattern. It may not be a **value** anyone can act on.

    The distinction is drawn with the AST, not a file allowlist, because the allowlist is the
    weaker instrument and this codebase has already been burned by exactly that weakness. A
    doctrine must be able to quote the bug it forbids — ``security.py:184`` names this string as
    the canonical plausible-constant — and the *whole finding* was that for two months that
    citation sat two thousand lines away from the live default it was describing. **The codebase
    named its own bug and kept it.** A per-file allowlist cannot tell those two apart; it would
    have had to allowlist ``security.py``, and would then have said nothing at all about a value
    reintroduced in the same file.

    So the rule is structural and exact: a **docstring** may contain the name (that is prose, and
    prose is how a doctrine works); **any other string constant may not** (that is a value, and a
    value is something the ledger can end up carrying). Comments never appear in the AST at all,
    so they are prose for free.

    Scoped to ``src/`` — to the code that RUNS — and that boundary is not laziness. In a test the
    name is an **attack payload**: ``test_recouvrement_assistant_auth_closed`` posts it in a body
    precisely to prove the contract answers 422. Banning it there would delete the proof that it
    is refused, which is the one place the string genuinely earns its keep.
    """
    src = _REPO / "src"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prose = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _GHOST in node.value
                and id(node) not in prose
            ):
                offenders.append(f"{path.relative_to(_REPO)}:{node.lineno} — {node.value[:60]!r}")

    assert not offenders, (
        f"{_GHOST!r} is still a VALUE in the production source:\n  "
        + "\n  ".join(offenders)
        + "\n\nA plausible constant in the author column is worse than a gap: a gap gets found "
        "and a lie does not. If this is meant as a counter-example, it belongs in a DOCSTRING — "
        "which this ratchet allows, deliberately — never in a string a caller can read back out."
    )
