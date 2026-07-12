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
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tessera.api.main import build_app
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.api.security import require_operator, require_subject_reader
from tessera.authz import SYSTEM_ROLE
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

    # Under erase_subject — never erase_subject itself.
    monkeypatch.setattr("tessera.memory.persistent.delete_subject", _one)
    monkeypatch.setattr("tessera.memory.summary.delete_summary", _n)
    monkeypatch.setattr("tessera.memory.transcript.delete_transcript", _n)
    monkeypatch.setattr("tessera.memory.governance.delete_consent", _n)
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


def test_every_s1_emitter_stamps_a_top_level_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Walk every ``emit_*`` in the audit module and assert the entry it chains names an author.

    Discovered from the module, not from a list: an emitter added tomorrow is swept in
    automatically, and one that forgets its actor cannot pass by being absent from a list nobody
    maintained. This is the sink ratchet's shape (``typing.get_args(_Sink)``) applied to the
    other half of ADR 0023's doctrine — there, no transport may disable the store; here, no
    entry may enter the store without saying who caused it.
    """
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(audit_mod, "_append_to_chain", lambda entry, _s, _f: captured.append(entry))
    monkeypatch.setattr(get_settings().guard, "audit_sink", "stdout")

    audit_mod.emit_audit(
        target="t",
        arguments={},
        decisions=[],
        sink="stdout",
        outcome="allowed",
        actor=audit_mod.GUARD_ACTOR,
    )
    audit_mod.emit_handoff(
        from_agent="a", to_agent="b", conversation_id="c", turn_id="t", reason="r", sink="stdout"
    )
    audit_mod.emit_routing(
        agent_id="a", conversation_id="c", turn_id="t", reason="r", handoff=False, sink="stdout"
    )
    audit_mod.emit_agent_proposed(name="x", sink="stdout")
    audit_mod.emit_canary_invocation(
        agent_id="a", binding="b", verdict="pass", conversation_id="c", turn_id="t", sink="stdout"
    )

    assert captured, "no emitter was exercised — this test would then prove nothing"
    for entry in captured:
        actor = entry.get("actor")
        assert isinstance(actor, str) and actor, (
            f"{entry.get('type')} enters the opposable chain with no top-level `actor` key. "
            "Every reader of this journal — the cockpit Journal, the governance feed, the SIEM "
            "export — looks there and only there. An entry without it is an act nobody performed."
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
    )

    assert entry["version"] == 3
    assert entry["actor"] == PRINCIPAL
    assert entry["actor_role"] == ROLE
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
