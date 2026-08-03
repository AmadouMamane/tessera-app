"""Structured audit-trail emission for guard decisions.

**The sink is a transport; the ledger is the store (ADR 0023).** These are two independent
things, and the chain is never a function of the sink. The sink chooses where the
human-readable / observability *copy* of an entry goes; the opposable hash chain is persisted
separately, upstream, into the promoted append-only Postgres ledger (fed by the fsync spool,
linked by the drain under an advisory lock — ADR 0015).

The audit sink is chosen at start-up from :attr:`GuardSettings.audit_sink`:

* ``stdout`` — JSON-Lines on stdout, useful for local dev and tests.
* ``cloud_logging`` — Google Cloud Logging; the observability copy in staging/prod. It is a
  *transport*, not the store: the entry is chained into the ledger regardless.
* ``file`` — a single-writer flat file; in pre-cut file mode the file itself IS the chain.
* ``postgres`` — the persistence IS the ledger spool/drain (upstream), so this sink adds no
  separate copy; it never silently degrades to stdout.

Whichever sink is chosen, every entry lands chained in the opposable ledger — or, in an
exposed posture whose configuration cannot persist the chain, the process refuses to boot
(:func:`validate_audit_chain_config`). Audit 2026-07-12, **F-6**: before ADR 0023 the ledger
feed ran only ``if sink == "file"``, so ``cloud_logging`` (the documented staging sink) emitted
to Cloud Logging and chained *nothing*.

The on-disk schema is shared across sinks and matches
``docs/compliance.md``'s "audit record" section.
"""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path  # noqa: TCH003  used at runtime by the file sink
from typing import TYPE_CHECKING, Any, Final, Literal

# Leaf import (stdlib-only module): the authz vocabulary is shared with the agent
# registry but lives outside ``tessera.agent`` so the guard never pulls the
# LangGraph at import time (no cycle).
from tessera.authz import Actor, AuthState

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from tessera.agent.state import GuardDecisionRecord

__all__ = [
    "AGENT_INVOCATION_TYPE",
    "AGENT_LIFECYCLE_PHASES",
    "AGENT_TURN_ACTOR",
    "CANARY_ACTOR",
    "CANARY_INVOCATION_TYPE",
    "GUARD_ACTOR",
    "HANDOFF_TYPE",
    "LEDGER_ATTESTATION_TYPE",
    "LEDGER_SEAL_TYPE",
    "SEAL_ACTOR",
    "SUPERVISOR_ACTOR",
    "ChainStatus",
    "build_ledger_attestation_entry",
    "build_ledger_seal_entry",
    "chain_persists_for",
    "confirmed_tools",
    "current_auth_state",
    "current_model",
    "current_tool_call_counts",
    "emit_agent_invocation",
    "emit_agent_lifecycle",
    "emit_agent_proposed",
    "emit_audit",
    "emit_business_event_audit",
    "emit_canary_invocation",
    "emit_governance_mutation",
    "emit_handoff",
    "emit_ledger_attestation",
    "emit_ledger_seal",
    "emit_routing",
    "guard_disabled",
    "install_turn_context",
    "turn_context",
    "validate_audit_chain_config",
    "verify_audit_chain",
]

#: The postures where the opposable audit chain is MANDATORY — the ones reachable from outside
#: (ADR 0023). Symmetric with the three fail-closed key checks (``security.py``,
#: ``_BEARER_REQUIRED_ENVIRONMENTS``): the question is not *"is this production?"* but *"can a
#: stranger reach this?"*, and an exposed agent that cannot chain its ledger has silently lost
#: the one guarantee the product is built on. Dev and CI are the only unexposed postures, and
#: they keep the hermetic ``TESSERA_LEDGER_DUAL_WRITE=0`` loop.
_CHAIN_REQUIRED_ENVIRONMENTS = frozenset({"staging", "production"})


def chain_persists_for(sink: str, ledger_source: str, dual_write: bool) -> bool:
    """Does this ``(sink, ledger_source, dual_write)`` triple durably persist the chain?

    The single source of truth for the store decision (ADR 0023), used both by the emitter
    (:func:`_append_to_chain`) and the boot check (:func:`validate_audit_chain_config`), so the
    two can never disagree about what "chainable" means. Deliberately independent of the sink
    except for the one mode where the sink IS the store:

    * ``ledger_source == "postgres"`` with dual-write on — the drain persists it, for ANY sink;
    * ``ledger_source == "file"`` with ``sink == "file"`` — the flat file itself is the chain.

    Everything else stores the chain nowhere durable (an in-process hash thrown away, or a
    transport-only copy on stdout/cloud_logging).
    """
    if ledger_source == "postgres":
        return dual_write
    return sink == "file"


def _unchainable_message(sink: str, ledger_source: str, dual_write: bool) -> str:
    """The boot-refusal text — one function, so the test asserts what the operator reads."""
    return (
        f"The audit chain cannot be persisted with audit_sink={sink!r}, "
        f"TESSERA_LEDGER_SOURCE={ledger_source!r}, TESSERA_LEDGER_DUAL_WRITE="
        f"{'1' if dual_write else '0'} — so guard decisions and business events would be "
        "emitted to the sink but NEVER chained into the opposable ledger (ADR 0023, audit "
        "F-6). The sink is a transport; the ledger is the store. Refusing to start rather than "
        "silently running without opposability. Fix: keep TESSERA_LEDGER_SOURCE=postgres with "
        "dual-write ON (any sink then chains), or set audit_sink=file for the flat-file chain."
    )


def validate_audit_chain_config() -> None:
    """Fail-closed startup check: an exposed deployment must be able to PERSIST the chain.

    Audit 2026-07-12, **P1 F-6** (ADR 0023). ``enqueue_ledger_entry`` — the only path to the
    opposable ledger — used to run only ``if sink == "file"``. With the baked default
    ``ledger_source=postgres`` and the documented staging sink ``cloud_logging``, entries were
    emitted to Cloud Logging and never chained. An operator following the staging docs turned
    opposability off with no signal.

    Called once at ``build_app()`` alongside the three signing-key checks (ADR 0020). No-op in
    dev/CI — the exemption is *not exposed*, drawn exactly as narrowly as the bearer's, so the
    hermetic ``TESSERA_LEDGER_DUAL_WRITE=0`` loop is untouched.
    """
    from tessera.guard.ledger_store import dual_write_enabled, ledger_source
    from tessera.settings import get_settings

    settings = get_settings()
    if settings.environment.value not in _CHAIN_REQUIRED_ENVIRONMENTS:
        return
    sink = settings.guard.audit_sink
    source = ledger_source()
    dual_write = dual_write_enabled()
    if not chain_persists_for(sink, source, dual_write):
        raise RuntimeError(_unchainable_message(sink, source, dual_write))


# TESS-LEDGER-001 — the attestation entry type (point 4): a signed, appended entry that ratifies
# historical ledger anomalies (forks/orphans) WITHOUT rewriting them (append-only is absolute).
# Defined here (the entry-builder layer) so :mod:`tessera.guard.ledger_store` can import it
# without a cycle; the verifier keys "attested" on this type.
LEDGER_ATTESTATION_TYPE = "tessera.ledger.attestation"

# ADR 0015 §Amendment 3 pt3 / §Correction 3c pt4 — the Hica seal entry type: an appended entry
# carrying a third-party attestation (an RFC 3161 timestamp token) of the chain HEAD at seal time.
# The seal ENRICHES opposability; it never stores ledger content. Living inside the one chain keeps
# the "one consolidated journal" property (§Corr.3b) and reuses the serialized, fork-proof writer —
# each seal transitively covers every prior row. Design note: 0022-hica-seal-design-note.md.
LEDGER_SEAL_TYPE = "tessera.ledger.seal"

# ADR 0019 §4 — every cockpit→agent invocation is a governed act, so a scheduled canary turn
# emits ONE S1 event recording who tested which agent, when, over which binding, and the verdict.
# A test is an action on a governed system, and the ledger is where actions live; the same entry
# is the durable freshness record the canary descriptor reads (no second store).
CANARY_INVOCATION_TYPE = "tessera.agent.canary"

# The agent→agent handoff event (S1). Named here because the fleet now COUNTS these in SQL rather
# than by loading every ledger entry and filtering in Python: a type that is queried needs one
# spelling, not one literal at the emitter and another at each of its readers.
HANDOFF_TYPE = "tessera.agent.handoff"

# ADR 0019 §I3/§4 — the operator-driven counterpart of the canary event: one S1 entry per Console
# (or other declared-consumer) invocation over the http binding, recording WHO tested (the operator
# principal from the verified assertion, never "system"), which agent, the binding, and the verdict.
# Stamped ``synthetic`` like the canary — a test turn can never pollute business metrics (§4).
AGENT_INVOCATION_TYPE = "tessera.agent.invocation"

_Outcome = Literal["allowed", "denied", "error"]
_Sink = Literal["stdout", "file", "cloud_logging", "postgres"]

# ── Tamper-evident hash chain (ADR 0010, idea #3) ─────────────────────────────
# Each audit entry carries the hash of the previous entry and its own SHA-256,
# so any insertion, deletion, or edit breaks the chain and is detectable by
# verify_audit_chain. The genesis link is all-zero.
_GENESIS_HASH = "0" * 64
_last_hash: str | None = None


def _canonical(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_core(core: Mapping[str, Any]) -> str:
    """SHA-256 of an entry's canonical form (the entry without its own hash)."""
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()


def _event_identity(entry: Mapping[str, Any]) -> str:
    """A stable, position-independent identity for an audit entry (TESS-LEDGER-001).

    SHA-256 of the entry's content EXCLUDING its chain position (``prev_hash``, ``hash``)
    and its own ``event_id``. Because it does not depend on where the entry lands, it is the
    idempotence key the Postgres drain uses: a re-drain after a crash recomputes the SAME
    ``event_id`` and skips the already-durable row. The chain ``hash`` (which DOES include
    ``prev_hash``) is assigned once, at the serialized insert, and so is never duplicated —
    this is what lets the drain (re)link entries under the advisory lock without risking a
    duplicate on replay.
    """
    core = {k: v for k, v in entry.items() if k not in {"prev_hash", "hash", "event_id"}}
    return _hash_core(core)


def _seed_last_hash(path: Path) -> str:
    """Resume the chain from the last hash already on disk (or genesis)."""
    if not path.exists():
        return _GENESIS_HASH
    last = _GENESIS_HASH
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                # skip a corrupt journal line while seeding the head hash — best-effort; the
                # chain verifier (verify_audit_chain) does NOT skip, so a real break surfaces there
                continue
            candidate = obj.get("hash")
            if isinstance(candidate, str):
                last = candidate
    return last


# Effective chat model for the current turn (the UI picker override). Set at the
# turn boundary so audit entries record what actually ran, not just the server
# default. Each API request runs in its own asyncio task, so there is no
# cross-request leak; when unset (e.g. the eval harness) emit_audit falls back to
# the configured default.
current_model: ContextVar[str | None] = ContextVar("tessera_audit_model", default=None)

# Guard categories disabled for the current turn (sandbox console playground).
# Set at the turn boundary, same task-isolation guarantees as current_model;
# empty by default so the full policy applies everywhere else (eval, prod).
guard_disabled: ContextVar[frozenset[str]] = ContextVar(
    "tessera_guard_disabled", default=frozenset()
)

# Server-derived authorization of the current session (ADR 0008/0009). Set at the
# turn boundary from the signed session cookie — never from the request body — so
# the guard's tool allowlist can gate account/PII tools on the real auth-state.
# ANONYMOUS by default (safe), with the same task-isolation guarantees as above.
current_auth_state: ContextVar[AuthState] = ContextVar(
    "tessera_auth_state", default=AuthState.ANONYMOUS
)

# Explicit action confirmations, mapping a confirmed tool to the argument value the
# approval was BOUND to (``{"card_block": "4242"}``), or ``None`` when the policy binds
# nothing.
#
# It used to be a bare set of tool names, filled straight from the request body. Being a
# separate channel from natural-language text made it unforgeable by the MODEL, which is
# what its comment claimed and all it ever proved; the CALLER could still assert it, and a
# value the caller chooses can never carry a fact about what a human did (ADR 0024). The
# route now fills this only from a server-minted, server-verified confirmation token.
#
# The bound value is what makes the approval specific. "A human approved blocking a card"
# is not a permission to block *any* card: the guard checks that the argument about to be
# used is the one that was shown and agreed to.
confirmed_tools: ContextVar[Mapping[str, str | None]] = ContextVar(
    "tessera_confirmed_tools", default={}
)

# One mutable counter map is installed at the request boundary and inherited by
# every concurrently-dispatched worker in that turn.  The check + increment in
# the guard is synchronous (contains no await), so parallel tasks cannot cross
# the configured maximum between two event-loop yields.
current_tool_call_counts: ContextVar[dict[str, int] | None] = ContextVar(
    "tessera_tool_call_counts", default=None
)


def install_turn_context(
    *,
    auth_state: AuthState = AuthState.ANONYMOUS,
    confirmations: Mapping[str, str | None] | None = None,
    guard_overrides: Iterable[str] = (),
) -> None:
    """Set the guard's per-turn ambient state in the CURRENT context, without unsetting it.

    For the streaming route, whose generator outlives the function that prepares the turn:
    the contextvars are task-local, so the turn's copies die with the request task. Everywhere
    else prefer :func:`turn_context`, which scopes them. See it for why this seam exists.
    """
    current_auth_state.set(auth_state)
    confirmed_tools.set(dict(confirmations or {}))
    current_tool_call_counts.set({})
    guard_disabled.set(frozenset(guard_overrides))


@contextmanager
def turn_context(
    *,
    auth_state: AuthState = AuthState.ANONYMOUS,
    confirmations: Mapping[str, str | None] | None = None,
    guard_overrides: Iterable[str] = (),
) -> Iterator[None]:
    """Install the guard's per-turn ambient state, and take it back down afterwards.

    **A guarantee carried by ambient state reaches exactly as far as whoever sets it.**
    ``current_auth_state`` and ``current_tool_call_counts`` were posted in exactly one place —
    the ``/chat`` route — and the guard reads ``max_calls_per_turn`` only ``if counts is not
    None``. So on every other path that runs the graph (the eval harness, the recouvrement
    workflow, any programmatic invocation) the per-turn call ceiling did not exist, and the
    auth floor saw the ``ANONYMOUS`` default. Measured: ``loan_simulate`` ran 6/6 times under
    a limit of 5 with no context installed, and 5/6 with it.

    That is an argument about the caller, not about the tool — which is what makes it a
    defect rather than a policy. This context manager is the one seam every turn goes
    through, so the reach of the guarantee stops being a property of who remembered to set
    it up. Audit 2026-08-03.

    Args:
        auth_state: the SERVER-derived session posture. Never read from a request body.
        confirmations: verified human approvals, tool → the argument value the approval was
            bound to. Only a server-minted, server-verified token may produce one.
        guard_overrides: sandbox categories disabled for this turn (operator surfaces only).
    """
    tokens = (
        current_auth_state.set(auth_state),
        confirmed_tools.set(dict(confirmations or {})),
        current_tool_call_counts.set({}),
        guard_disabled.set(frozenset(guard_overrides)),
    )
    try:
        yield
    finally:
        current_auth_state.reset(tokens[0])
        confirmed_tools.reset(tokens[1])
        current_tool_call_counts.reset(tokens[2])
        guard_disabled.reset(tokens[3])


def _record_to_dict(record: GuardDecisionRecord) -> dict[str, Any]:
    return {
        "target": record.target,
        "decision": record.decision,
        "policy_rule": record.policy_rule,
        "rationale": record.rationale,
        "redactions": list(record.redactions),
        "occurred_at": record.occurred_at.isoformat(),
    }


def _coerce_arguments(arguments: Mapping[str, object]) -> dict[str, Any]:
    """Coerce argument values to JSON-serialisable primitives."""
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str | int | float | bool) or value is None:
            safe[key] = value
        else:
            safe[key] = repr(value)
    return safe


#: The guard's own actor: it screened an input, refused a tool call, redacted an output. No
#: human *ordered* any of that — the guard decided, on policy, and the decision is the event.
#: Named rather than blank, so a reader can tell "the guard did this" from "the code forgot to
#: say who did this"; the two are indistinguishable the moment either is allowed to be empty.
#:
#: The turn's *caller* is not lost by this: the entry already carries ``agent_id``, the
#: conversation, and the screened ``arguments``. This field answers a different question —
#: who is answerable for the act — and for a policy decision the answer is the policy engine.
GUARD_ACTOR: Final = Actor.system("guard")

#: The supervisor's own actor: it routed a turn, or moved it between agents. No human chose the
#: destination — the router did, on the turn's intent. Named, because the bare string ``"system"``
#: these two emitters used to write is the one value that cannot be told apart from an omission.
SUPERVISOR_ACTOR: Final = Actor.system("supervisor")

#: The scheduler that fires synthetic canary turns (ADR 0019 §4). It is not an operator, and
#: writing ``"canary-scheduler"`` as a bare literal made it look like one to every reader that
#: does not know the vocabulary by heart. ``system:canary-scheduler`` says both things at once.
CANARY_ACTOR: Final = Actor.system("canary-scheduler")

#: The off-chronology cycle that seals the chain head with an external TSA (ADR 0015 §Amend. 3).
SEAL_ACTOR: Final = Actor.system("seal-cycle")

#: The agent's own turn: the workflow evaluated a policy, built an artifact, drafted a reply.
#: A human opened the conversation, but a human did not *perform* these — the graph did, and
#: attributing them to the operator who typed the message would be a fresh lie of exactly the
#: family this module exists to kill. What the human ordered is the ACTION path, and that one
#: carries the verified operator (see ``run_recouvrement_action_workflow_v1``).
AGENT_TURN_ACTOR: Final = Actor.system("agent-turn")


def _build_entry(
    *,
    target: str,
    arguments: Mapping[str, object],
    decisions: Iterable[GuardDecisionRecord],
    outcome: _Outcome,
    error: str | None,
    model: str | None,
    data_residency: str,
    agent_id: str,
    actor: Actor,
    synthetic: bool,
) -> dict[str, Any]:
    """Build one S1 guard-audit entry. It names its author, or it does not get built.

    ``actor`` sits at the **top level**, beside ``target`` and ``outcome`` — never inside
    ``arguments``. That is where the eight sibling emitters in this module put it, and where
    the three readers look: the cockpit Journal (``api/routes/audit.py``), the governance feed,
    and the SIEM export. This builder was the only one in the file with no actor slot at all,
    which is why the GDPR erasure could be *fixed* and still read wrong — a name written where
    nobody looks is durable and unread, and the Journal went on printing the LLM's model name
    in the author column while the trail quietly held the truth. Worse than absent: a false
    assurance.

    **Version 3** — the schema gained ``actor``/``actor_role``, and the bump is load-bearing. A
    *v2* entry has no author because it predates the field; a *v3* entry always has one. A
    reader can therefore tell *"no author recorded, because this is old"* from *"no author
    recorded, because something is broken"* — which adding the field silently would have made
    indistinguishable, and which is exactly the ambiguity a regulator resolves against you. The
    chain is unaffected: every entry hashes its own content, so the walk crosses the boundary
    unbroken and old entries keep verifying.
    """
    # Bitemporal stamps (S1 substrate): valid_* is when the event is effective
    # for the agent, recorded_at is when Tessera learned it (transaction time).
    # A guard decision is effective the instant it is taken and stays so (open
    # interval), and is recorded at the same instant. Both feed the hash.
    now = datetime.now(UTC).isoformat()
    return {
        "type": "tessera.guard.audit",
        "version": 3,
        "occurred_at": now,
        "agent_id": agent_id,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "target": target,
        "outcome": outcome,
        "actor": actor.principal,
        "actor_role": actor.role,
        # The turn posture belongs on the decision event itself. Inferring it later from a
        # separate invocation row cannot join reliably when older in-process turns have no
        # invocation event. Historical entries omit the key and are treated as real.
        "synthetic": synthetic,
        "model": model,
        "data_residency": data_residency,
        "arguments": _coerce_arguments(arguments),
        "decisions": [_record_to_dict(d) for d in decisions],
        "error": error,
    }


def _emit_stdout(entry: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _emit_cloud_logging(entry: dict[str, Any]) -> None:
    """The Cloud Logging transport. It emits, or it FAILS — it never pretends (ADR 0023, F-6).

    Lazily imports google-cloud-logging so the dependency is not needed at start-up. When the
    import is missing, this used to call ``_emit_stdout`` under a comment reading *"graceful
    degradation"* — and there is no such thing on an audit path. The operator asked for entries
    in Cloud Logging; the process wrote them to a container's stdout and said nothing. Every
    dashboard, alert and retention rule built on that sink was quietly empty, and the only way
    to find out was to go looking for something you had no reason to doubt.

    So the ImportError propagates. The sink dispatch in :func:`_append_to_chain` catches it and
    writes a named failure to stderr — loud, and *cheap*, because since ADR 0023 the sink is a
    lateral copy: the opposable chain is persisted upstream, by the store, and a dead transport
    no longer costs a single ledger entry. Failing loudly here is now free of the one thing that
    ever justified degrading gracefully.
    """
    from google.cloud import logging as cloud_logging

    client = cloud_logging.Client()  # type: ignore[no-untyped-call]
    logger = client.logger("tessera-guard-audit")  # type: ignore[no-untyped-call]
    logger.log_struct(entry, severity="INFO")


def _emit_file(entry: dict[str, Any], path: Path) -> None:
    """Append a JSON-Lines entry to ``path``, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _emit_postgres(entry: dict[str, Any], *, chain_persisted: bool) -> None:  # noqa: ARG001  entry unused: persistence is the ledger, upstream
    """The ``postgres`` sink — which never silently falls back to stdout (ADR 0023, F-6).

    The Postgres *persistence* of an audit entry is the opposable ledger (the fsync spool +
    drain, which assigns the hash linkage under the advisory lock), and it runs UPSTREAM of
    this sink, independent of it. So when the ledger is active this sink is genuinely
    redundant — the entry is already durably in the table — and the honest thing is to add no
    second copy, not to write a misleading stdout line pretending "postgres" meant something.

    The old stub did exactly that (``_emit_stdout(entry)``), which is how choosing the
    ``postgres`` sink could persist nothing to any table while looking configured. The
    doctrine is: either the entry is written, or the failure is audible.

    ``chain_persisted`` is the store's own decision, computed once in :func:`_append_to_chain`.
    True → the ledger has it; do nothing. False → the operator asked for ``postgres`` but the
    ledger is NOT persisting this entry (``TESSERA_LEDGER_SOURCE=file`` or
    ``TESSERA_LEDGER_DUAL_WRITE=0``), so raise — the sink dispatch surfaces it to stderr. In an
    exposed posture this combination never boots (:func:`validate_audit_chain_config`).
    """
    if chain_persisted:
        return
    raise RuntimeError(
        "audit_sink=postgres but the opposable ledger is not persisting this entry "
        "(TESSERA_LEDGER_SOURCE=file or TESSERA_LEDGER_DUAL_WRITE=0). The Postgres persistence "
        "IS the ledger spool/drain; enable dual-write with ledger_source=postgres, or choose a "
        "sink whose transport this deployment can honour."
    )


def emit_audit(
    *,
    target: str,
    arguments: Mapping[str, object],
    decisions: Iterable[GuardDecisionRecord],
    sink: Literal["stdout", "file", "cloud_logging", "postgres"],
    outcome: _Outcome,
    actor: Actor,
    error: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Emit a single audit entry to ``sink``. It names WHO acted, or it does not compile.

    The function is fire-and-forget: callers do not need to await on it.
    Failures in the sink are swallowed and logged to stderr so that audit
    issues never block the agent's main path.

    ``agent_id`` attributes the event to an agent (per-turn attribution); it
    defaults to the acting agent on the current turn so the data is partitioned
    by agent and the cockpit can scope by it.

    ``actor`` attributes it to a **principal** — which agent ran is not who ordered the act,
    and an erasure performed by ``support-client`` on behalf of nobody is not a record anyone
    can be held to. It is **required and has no default**, deliberately and permanently:

    * A default here would be the whole bug class back. An author who forgets the actor would
      get a plausible one for free — ``"operator"``, ``"system"``, the model's name — and the
      trail would read *complete* while naming nobody. That is strictly worse than a gap,
      because a gap gets found and a plausible lie does not.
    * There is no honest fallback available at this layer anyway. The bearer names the
      frontend *service*, not a person (``api/security.py``); the request body is chosen by
      the caller, so a caller could frame someone else; and ``agent_id`` names a program. The
      only trustworthy name is the principal of a server-verified assertion, and only the
      caller knows whether it holds one.
    * So the call site must answer the question. :func:`tessera.api.security.actor_of` derives
      it from a verified session; :meth:`Actor.system` names a non-human origin out loud. Both
      are explicit, and that is the point — omission is not one of the options.
    """
    from tessera.agent.identity import current_conversation_id, current_turn_id, resolve_agent_id
    from tessera.observability.business_events import is_synthetic_turn
    from tessera.settings import LLMProfile, get_settings

    settings = get_settings()
    # Record the model that actually ran this turn (UI picker override) when set;
    # otherwise fall back to the configured default for the active profile.
    model = current_model.get()
    if model is None:
        model = (
            settings.ollama.chat_model
            if settings.resolved_llm_profile() is LLMProfile.ON_PREM
            else settings.vertex.chat_model
        )
    entry = _build_entry(
        target=target,
        arguments=arguments,
        decisions=decisions,
        outcome=outcome,
        error=error,
        model=model,
        data_residency=settings.observability.data_residency,
        agent_id=resolve_agent_id(agent_id),
        actor=actor,
        synthetic=is_synthetic_turn(),
    )
    conversation_id = current_conversation_id.get()
    turn_id = current_turn_id.get()
    if conversation_id is not None:
        entry["conversation_id"] = conversation_id
    if turn_id is not None:
        entry["turn_id"] = turn_id
    _append_to_chain(entry, sink, settings.guard.audit_file)


def _seed_chain_head(sink: _Sink, audit_file: Path) -> str:
    """Resume the chain at process start from whichever medium is canonical.

    After the cut (``TESSERA_LEDGER_SOURCE=postgres``) the promoted table is canonical, so
    seed from the TABLE head — the next entry links to the last row, keeping the chain
    continuous across the file→table boundary (``verify`` walks genesis→tail unbroken). If
    the table is empty/unreachable, fall back to the file/genesis rather than silently
    starting a NEW chain (which would fork the walk). Pre-cut, seed from the file sink;
    other sinks chain from genesis.
    """
    from tessera.guard.ledger_store import ledger_head_hash, ledger_source

    if ledger_source() == "postgres":
        head = ledger_head_hash()
        if head is not None:
            return head
    return _seed_last_hash(audit_file) if sink == "file" else _GENESIS_HASH


def _append_to_chain(entry: dict[str, Any], sink: _Sink, audit_file: Path) -> None:
    """Link ``entry`` into the tamper-evident hash chain and emit it to ``sink``.

    Shared by every S1 event type (guard audit, agent handoff, …) so they all live in one
    append-only, hash-chained journal verifiable by :func:`verify_audit_chain`.

    Chain linkage is assigned at the single serialized write point, which differs by the
    active ledger medium (TESS-LEDGER-001 fix — ADR 0015 §Amendment 3 Correction):

    * ``postgres`` (the baked default since the H2 cut) — the promoted table is canonical.
      The per-process head cache (``_last_hash``) is DELIBERATELY NOT used here: it is what
      forked the chain under concurrent writers (each process extended its own in-memory
      head, oblivious to interleaved writes). ``prev_hash``/``hash`` are assigned by the
      durable drain INSIDE a ``pg_advisory_xact_lock`` transaction that reads the true table
      head, so insert order IS chain order and two writers can never extend the same head.
      Emit only stamps the position-independent ``event_id`` (the drain's idempotence key)
      and spools.
    * ``file`` (the operator escape until ``audit.log`` is removed) — the flat file is a
      single writer by construction, so the in-process chain is correct: seed from the file
      tail (survives restarts) and link at emit, exactly as before.
    """
    global _last_hash
    from tessera.guard.ledger_store import dual_write_enabled, enqueue_ledger_entry, ledger_source

    # Position-independent identity, stamped in BOTH modes — the drain's idempotence key
    # (a crash-replayed drain must not recompute a different hash and duplicate the entry).
    entry["event_id"] = _event_identity(entry)
    cut = ledger_source() == "postgres"

    # THE STORE DECISION, computed once and INDEPENDENT OF THE SINK (ADR 0023, audit F-6) —
    # the same predicate the boot check enforces, so emit-time and boot-time can never
    # disagree. Post-cut with dual-write the drain chains it for ANY sink; pre-cut file mode
    # the flat file IS the chain. This replaces the old `if sink == "file"` gate that let a
    # transport choice (stdout/cloud_logging) silently switch opposability off.
    chain_persists = chain_persists_for(sink, ledger_source(), dual_write_enabled())

    if not cut:
        # File-escape mode: a single-writer flat file, so in-process chaining is correct.
        if _last_hash is None:
            _last_hash = _seed_chain_head(sink, audit_file)
        entry["prev_hash"] = _last_hash
        entry["hash"] = _hash_core({k: v for k, v in entry.items() if k != "hash"})
        _last_hash = entry["hash"]

    # THE SINK IS A TRANSPORT — the human-readable / observability copy. It never decides
    # whether the entry is chained; that is the store's job (above: the in-process link for
    # file mode; below: the spool for the opposable ledger).
    try:
        match sink:
            case "stdout":
                _emit_stdout(entry)
            case "file":
                # After the cut (TESSERA_LEDGER_SOURCE=postgres — the default since H2 step 5)
                # the promoted table is canonical, so the flat file write STOPS. The operator
                # escape (=file) resumes it until the file is finally removed.
                if not cut:
                    _emit_file(entry, audit_file)
            case "cloud_logging":
                _emit_cloud_logging(entry)
            case "postgres":
                # The Postgres persistence is the ledger (below), not this sink. Redundant when
                # the chain persists; loud (never silent stdout) when it does not — ADR 0023 #3.
                _emit_postgres(entry, chain_persisted=chain_persists)
    except Exception as exc:
        # A dead TRANSPORT is loud, and it is not a lost proof. Both halves matter: the sink
        # never degrades silently (a "graceful" stdout fallback is how cloud_logging emptied
        # every dashboard built on it), and the operator reading this line must not conclude
        # that opposability was lost — the chain is persisted below, by the store, and this
        # failure did not touch it (ADR 0023). A stderr line that omitted that would send
        # someone hunting a breach that did not happen.
        sys.stderr.write(
            f"tessera.guard.audit: sink {sink!r} FAILED to emit its copy: {exc} — "
            f"the opposable chain is UNAFFECTED (it is persisted by the ledger, not the sink; "
            f"chained here: {chain_persists}). Fix the transport; the trail is intact.\n"
        )

    # THE LEDGER IS A STORE — persistence happens upstream of, and independent from, the sink
    # (ADR 0023). Post-cut the drain assigns the chain linkage under the advisory lock
    # (fork-free); pre-cut file mode mirrors the canonical file into the promoted table. The
    # boot reconcile replays the spool. Audit F-6: this was `if sink == "file"`, so choosing
    # the documented staging sink (cloud_logging) skipped the opposable chain entirely.
    if chain_persists:
        enqueue_ledger_entry(entry)


def emit_handoff(
    *,
    from_agent: str,
    to_agent: str,
    conversation_id: str,
    turn_id: str,
    reason: str,
    sink: _Sink | None = None,
) -> None:
    """Emit an agent->agent handoff event into the S1 journal.

    A handoff is a first-class S1 event (``type: tessera.agent.handoff``),
    **distinct from human escalation** (``ticket_escalate``): it records that the
    supervisor moved a turn from one agent to another, attributed to ``to_agent``
    (the agent that now handles the turn). It is hash-chained like every other S1
    event, so it is tamper-evident and reconstructable in État à date.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": HANDOFF_TYPE,
        "version": 2,
        "occurred_at": now,
        "agent_id": to_agent,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "reason": reason,
        "actor": SUPERVISOR_ACTOR.principal,
        "actor_role": SUPERVISOR_ACTOR.role,
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_routing(
    *,
    agent_id: str,
    conversation_id: str,
    turn_id: str,
    reason: str,
    handoff: bool,
    from_agent: str | None = None,
    sink: _Sink | None = None,
) -> None:
    """Emit the supervisor's routing decision for a turn into the S1 journal.

    Every turn's decision is recorded (``type: tessera.agent.routing``), not only
    the hand-overs — so you can prove *why a turn went to a given agent* from the
    start (``reason``: stay/parcours, intent, policy), not just *that* it switched.
    ``handoff`` flags a switch (which additionally emits a distinct
    :func:`emit_handoff` event). Hash-chained and reconstructable in État à date.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": "tessera.agent.routing",
        "version": 2,
        "occurred_at": now,
        "agent_id": agent_id,
        "from_agent": from_agent,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "reason": reason,
        "handoff": handoff,
        "actor": SUPERVISOR_ACTOR.principal,
        "actor_role": SUPERVISOR_ACTOR.role,
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_business_event_audit(
    *,
    event: Mapping[str, Any],
    sink: _Sink | None = None,
) -> None:
    """Append a normalised business event to the opposable S1 audit journal.

    **One ledger, one meaning for ``actor``.** Until 2026-07-13 this emitter wrote the business
    event's *closed-vocabulary kind* (``system`` / ``operator`` / ``internal_collaborator``,
    ADR 0017 §A2.1) into the ``actor`` key — while every *other* entry type wrote a **person**
    there (``_build_entry``'s ``actor.principal``). One key, two meanings, and the readers cannot
    tell which they are holding: the cockpit Journal, the governance feed and the SIEM export all
    render ``actor`` as *the author*, so a governed action taken by a named collections officer
    was displayed, and exported to the bank's SOC, as having been performed by ``operator`` — a
    role — or by ``system`` — nobody. A union of two types under one key is not a schema; it is a
    coin flip the reader is not told they are making.

    The three keys are now three questions, and each has exactly one answer:

    * ``actor`` — **WHO**: the verified principal, or ``system:<task>``. Same as every other entry.
    * ``actor_role`` — the authority they held.
    * ``actor_kind`` — **WHAT KIND** of party (§A2.1). This is what the 3-level ladder reads, and
      it stays exactly what it was; it simply stops being mistaken for a name.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    occurred_at = str(event.get("timestamp") or event.get("occurred_at") or now)
    entry: dict[str, Any] = {
        "type": "tessera.agent.business_event",
        "version": int(event.get("version", 1)),
        "event_name": str(event.get("event_name", "")),
        "occurred_at": occurred_at,
        "agent_id": str(event.get("agent_id", "none")),
        "workflow_id": event.get("workflow_id"),
        "surface": event.get("surface"),
        "case_id": event.get("case_id"),
        "node_name": event.get("node_name"),
        "artifact_id": event.get("artifact_id"),
        "artifact_type": event.get("artifact_type"),
        "artifact_status": event.get("artifact_status"),
        "decision": event.get("decision"),
        "reason_codes": list(event.get("reason_codes", [])),
        "payload": event.get("payload") if isinstance(event.get("payload"), dict) else {},
        "valid_from": occurred_at,
        "valid_to": None,
        "recorded_at": now,
        "conversation_id": str(event.get("conversation_id", "")),
        "turn_id": str(event.get("turn_id", "")),
        # WHO — a person, or a named system task. Never a role word, never blank.
        "actor": str(event.get("author_principal", "")),
        "actor_role": str(event.get("author_role", "")),
        # WHAT KIND of party (§A2.1) — the ladder's input, no longer masquerading as a name.
        "actor_kind": str(event.get("actor", "system")),
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_governance_mutation(
    *,
    target: str,
    detail: Mapping[str, object],
    actor: Actor,
    sink: _Sink | None = None,
) -> None:
    """Append one **cockpit governance mutation** to the opposable S1 journal.

    ADR 0024 §Owed listed three governed acts that changed the system and wrote *nothing*:
    switching a guardrail off, granting superadmin visibility of the synthesis, and disabling an
    automation rule. Each is a control that the compliance story rests on, each was reachable by
    a verified operator, and each left the chain unchanged — so the ledger's answer to *"who
    turned the injection guard off before that incident?"* was silence. **An act that leaves no
    trace is not governed**, whatever the doc says, and it is the doc that is wrong.

    This is a named wrapper over :func:`emit_audit`, not a new event type, and that is the whole
    point: the three readers of this journal — the cockpit Journal, the governance feed, the SIEM
    export — already parse ``tessera.guard.audit`` and already look at its top-level ``actor``.
    A new type would have been durable and **unread**, which is the failure this codebase has
    already made once (the GDPR erasure's author, written into ``arguments`` where nothing looks).
    Reuse the entry shape that has readers; do not invent one that has none.

    Args:
        target: what was acted on — ``guard.rule_state``, ``settings.synthesis_admin``.
        detail: the act's parameters (which rule, on or off). Not its author.
        actor: WHO did it. ``actor_of(session)``. Required, and there is no honest default.
        sink: override the configured audit sink (tests).
    """
    from tessera.settings import get_settings

    settings = get_settings()
    emit_audit(
        target=target,
        arguments=detail,
        decisions=[],
        sink=sink if sink is not None else settings.guard.audit_sink,
        outcome="allowed",
        actor=actor,
    )


def emit_agent_proposed(*, name: str, actor: Actor, sink: _Sink | None = None) -> None:
    """Emit a governed proposal to add an agent to the fleet (S1 event).

    The registry is approved as a unit (ADR 0012), so creation is a proposal, not
    a runtime mutation: this records the intent as a hash-chained
    ``tessera.agent.proposed`` event feeding the propose -> review -> release flow.

    ``actor`` was ``str = "operator"`` — a **role, not a person** — and the route below it never
    passed one, so every proposal in the chain was signed by the same plausible constant. A
    default on an identity field is the whole bug: it lets the one field that makes the record
    worth keeping be omitted, and read green while it happens.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": "tessera.agent.proposed",
        "version": 2,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "proposed_name": name,
        "actor": actor.principal,
        "actor_role": actor.role,
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


# The governed agent lifecycle: propose -> review -> approve -> release. Each is a
# distinct S1 event in the same hash chain; "released" (go-live) is gated by the
# agent's eval-gate (see tessera.observability.agent_lifecycle).
AGENT_LIFECYCLE_PHASES: tuple[str, ...] = (
    "reviewed",
    "approved",
    "released",
    "release_blocked",
)


def emit_agent_lifecycle(
    *,
    agent_id: str,
    phase: str,
    actor: Actor,
    detail: Mapping[str, Any] | None = None,
    sink: _Sink | None = None,
) -> None:
    """Emit a governed agent lifecycle transition (S1 event).

    **Promoting an agent to production is the most consequential act an operator can take in
    this system**, and until 2026-07-13 the chain recorded it as having been performed by
    ``"operator"`` — the default on this parameter, which the release route never overrode. That
    is a role, not a person: it answers *what authority acted*, and answers *who* with a word
    that is true of everyone and identifies no one. Two agents promoted by two different people
    produced two byte-identical attributions.

    Args:
        agent_id: the agent the transition applies to.
        phase: one of :data:`AGENT_LIFECYCLE_PHASES`. The event type is
            ``tessera.agent.<phase>``, hash-chained alongside the proposal.
        actor: WHO performed the transition. Required, no default — ``actor_of(session)`` for a
            human promotion, :meth:`Actor.system` for a gate that blocked one on its own.
        detail: extra opposable fields (e.g. the gate verdict on release).
        sink: override the configured audit sink (tests).
    """
    if phase not in AGENT_LIFECYCLE_PHASES:
        msg = f"unknown agent lifecycle phase {phase!r}"
        raise ValueError(msg)
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": f"tessera.agent.{phase}",
        "version": 2,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor.principal,
        "actor_role": actor.role,
        **(dict(detail) if detail else {}),
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_canary_invocation(
    *,
    agent_id: str,
    binding: str,
    verdict: str,
    conversation_id: str,
    turn_id: str,
    duration_ms: float | None = None,
    error: str | None = None,
    actor: Actor,
    sink: _Sink | None = None,
) -> None:
    """Emit one scheduled-canary invocation into the S1 journal (ADR 0019 §4).

    Every cockpit→agent invocation is a governed act: one entry per synthetic canary turn records
    who ran it (``actor`` = :data:`CANARY_ACTOR`, the scheduler), which agent, the binding used,
    the verdict (``green`` / ``red``), and the turn ids — hash-chained like every other S1 event
    and reconstructable in État à date. It is also the durable freshness record the canary
    descriptor reads for the synthetic-run facet (no second store). ``synthetic: True`` is stamped
    so a reader can never mistake a canary probe for a real turn.

    ``actor`` is required and typed even though there is only ever one right answer: a default
    here would be a default on an identity field, and the caller passing :data:`CANARY_ACTOR`
    explicitly is what makes the entry say ``system:canary-scheduler`` rather than a bare word
    that a reader has to already know is not a person.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": CANARY_INVOCATION_TYPE,
        "version": 2,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor.principal,
        "actor_role": actor.role,
        "binding": binding,
        "verdict": verdict,
        "synthetic": True,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "duration_ms": duration_ms,
        "error": error,
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_agent_invocation(
    *,
    agent_id: str,
    binding: str,
    verdict: str,
    actor: Actor,
    conversation_id: str,
    turn_id: str,
    duration_ms: float | None = None,
    status_code: int | None = None,
    error: str | None = None,
    sink: _Sink | None = None,
) -> None:
    """Emit one operator-driven cockpit→agent invocation into the S1 journal (ADR 0019 §I3/§4).

    Every invocation over the http binding is a governed act: one entry per test turn records
    WHO tested (``actor`` = the operator principal from the verified assertion — required, never
    a system default), which agent, the binding, the verdict (``green`` / ``red``), the HTTP
    status and the turn ids — hash-chained like every other S1 event and reconstructable in
    État à date. ``synthetic: True`` is stamped so a reader can never mistake a test turn for a
    real one, and the business surfaces exclude it by declaration (§4).
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": AGENT_INVOCATION_TYPE,
        "version": 2,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor.principal,
        "actor_role": actor.role,
        "binding": binding,
        "verdict": verdict,
        "synthetic": True,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "duration_ms": duration_ms,
        "status_code": status_code,
        "error": error,
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def build_ledger_attestation_entry(
    *,
    incident: str,
    cause: str,
    decision: str,
    evidence: Mapping[str, Any],
    forks: Iterable[Mapping[str, Any]],
    orphans: Iterable[str],
    anchor_seq: int | None = None,
    actor: Actor,
) -> dict[str, Any]:
    """Build (do not append) an attestation entry ratifying historical ledger anomalies.

    TESS-LEDGER-001 point 4 — re-anchoring by attestation, NEVER by rewrite: it RECORDS the
    forks + orphans (they stay in the chain — append-only is absolute), the cause, the decision,
    and the point-0 evidence dump hash (chain of custody). Its own integrity is the hash chain it
    is appended into; an external cryptographic seal (Hica) is the enrichment, never the store
    (ADR 0015 §Amendment 3). Pure builder so it is unit-testable without a database.
    """
    fork_list = [dict(f) for f in forks]
    orphan_list = list(orphans)
    now = datetime.now(UTC).isoformat()
    return {
        "type": LEDGER_ATTESTATION_TYPE,
        "version": 2,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "actor": actor.principal,
        "actor_role": actor.role,
        "incident": incident,
        "cause": cause,
        "decision": decision,
        "evidence": dict(evidence),
        "anchor_seq": anchor_seq,
        "forks": fork_list,
        "fork_count": len(fork_list),
        "orphans": orphan_list,
        "orphan_count": len(orphan_list),
    }


def emit_ledger_attestation(
    *,
    incident: str,
    cause: str,
    decision: str,
    evidence: Mapping[str, Any],
    forks: Iterable[Mapping[str, Any]],
    orphans: Iterable[str],
    anchor_seq: int | None = None,
    actor: Actor,
    sink: _Sink | None = None,
) -> dict[str, Any]:
    """Append an attestation entry into the tamper-evident ledger (chained + durable).

    Goes through the normal serialized append (:func:`_append_to_chain` → spool → the
    advisory-locked drain), so the attestation links to the true head and is itself fork-proof
    (it lands above the fork-guard anchor). Returns the entry (with its stamped ``event_id``).
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    entry = build_ledger_attestation_entry(
        incident=incident,
        cause=cause,
        decision=decision,
        evidence=evidence,
        forks=forks,
        orphans=orphans,
        anchor_seq=anchor_seq,
        actor=actor,
    )
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)
    return entry


def build_ledger_seal_entry(
    *,
    sealed_head: str,
    prev_sealed_head: str | None,
    provider: str,
    tsa: str | None,
    token_b64: str,
    sealed_at: str,
    qualified: bool,
    divergence: bool = False,
    actor: Actor,
) -> dict[str, Any]:
    """Build (do not append) a Hica seal entry attesting the chain head at seal time.

    ADR 0015 §Amendment 3 pt3 — the seal ENRICHES opposability, it never stores. ``token_b64`` is
    the externally-verifiable artifact (an RFC 3161 timestamp token): a third party re-validates it
    against the TSA cert with no Tessera code, so the TSA — not Tessera — is the attester; we merely
    keep the receipt inside our own chain. ``divergence`` marks a cycle where head continuity broke
    since the previous seal (a fork/rewrite between seals — the §Correction 3c pt4 detection). Pure
    builder so it is unit-testable without a database.
    """
    now = datetime.now(UTC).isoformat()
    return {
        "type": LEDGER_SEAL_TYPE,
        "version": 2,
        "occurred_at": now,
        "recorded_at": now,
        "actor": actor.principal,
        "actor_role": actor.role,
        "provider": provider,
        "tsa": tsa,
        "qualified": qualified,
        "sealed_head": sealed_head,
        "prev_sealed_head": prev_sealed_head,
        "sealed_at": sealed_at,
        "token_b64": token_b64,
        "divergence": divergence,
    }


def emit_ledger_seal(
    *,
    sealed_head: str,
    prev_sealed_head: str | None,
    provider: str,
    tsa: str | None,
    token_b64: str,
    sealed_at: str,
    qualified: bool,
    divergence: bool = False,
    actor: Actor,
    sink: _Sink | None = None,
) -> dict[str, Any]:
    """Append a Hica seal entry into the tamper-evident ledger (chained + durable).

    Goes through the normal serialized append (:func:`_append_to_chain` → spool → the
    advisory-locked drain), so the seal entry links to the true head and is itself fork-proof (it
    lands above the fork-guard anchor). Appending moves the head to this entry's hash — the next
    cycle seals that head. Returns the entry (with its stamped ``event_id``/``hash``).
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    entry = build_ledger_seal_entry(
        sealed_head=sealed_head,
        prev_sealed_head=prev_sealed_head,
        provider=provider,
        tsa=tsa,
        token_b64=token_b64,
        sealed_at=sealed_at,
        qualified=qualified,
        divergence=divergence,
        actor=actor,
    )
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)
    return entry


@dataclass(frozen=True, slots=True)
class ChainStatus:
    """Result of verifying the audit hash chain (ADR 0010, idea #3)."""

    verified: bool
    length: int
    broken_at: int | None  # 0-based index of the first broken entry, if any


def verify_audit_chain(path: Path) -> ChainStatus:
    """Re-derive the hash chain on disk and report whether it is intact.

    Any inserted, deleted, reordered, or edited entry breaks either the
    prev-hash linkage or an entry's own hash, and is reported as ``broken_at``.

    Args:
        path: The JSON-Lines audit file to verify.

    Returns:
        A :class:`ChainStatus`. An empty/absent log is trivially verified.
    """
    if not path.exists():
        return ChainStatus(verified=True, length=0, broken_at=None)

    prev = _GENESIS_HASH
    index = 0
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                return ChainStatus(verified=False, length=index, broken_at=index)
            stored = obj.get("hash")
            recomputed = _hash_core({k: v for k, v in obj.items() if k != "hash"})
            if obj.get("prev_hash") != prev or stored != recomputed:
                return ChainStatus(verified=False, length=index + 1, broken_at=index)
            prev = stored
            index += 1
    return ChainStatus(verified=True, length=index, broken_at=None)
