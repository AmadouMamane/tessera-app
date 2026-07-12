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
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path  # noqa: TCH003  used at runtime by the file sink
from typing import TYPE_CHECKING, Any, Literal

# Leaf import (stdlib-only module): the authz vocabulary is shared with the agent
# registry but lives outside ``tessera.agent`` so the guard never pulls the
# LangGraph at import time (no cycle).
from tessera.authz import AuthState

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from tessera.agent.state import GuardDecisionRecord

__all__ = [
    "AGENT_INVOCATION_TYPE",
    "AGENT_LIFECYCLE_PHASES",
    "CANARY_INVOCATION_TYPE",
    "LEDGER_ATTESTATION_TYPE",
    "LEDGER_SEAL_TYPE",
    "ChainStatus",
    "build_ledger_attestation_entry",
    "build_ledger_seal_entry",
    "chain_persists_for",
    "current_auth_state",
    "current_model",
    "emit_agent_invocation",
    "emit_agent_lifecycle",
    "emit_agent_proposed",
    "emit_audit",
    "emit_business_event_audit",
    "emit_canary_invocation",
    "emit_handoff",
    "emit_ledger_attestation",
    "emit_ledger_seal",
    "emit_routing",
    "guard_disabled",
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
) -> dict[str, Any]:
    # Bitemporal stamps (S1 substrate): valid_* is when the event is effective
    # for the agent, recorded_at is when Tessera learned it (transaction time).
    # A guard decision is effective the instant it is taken and stays so (open
    # interval), and is recorded at the same instant. Both feed the hash.
    now = datetime.now(UTC).isoformat()
    return {
        "type": "tessera.guard.audit",
        "version": 2,
        "occurred_at": now,
        "agent_id": agent_id,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "target": target,
        "outcome": outcome,
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
    """Lazily import google-cloud-logging to avoid a hard dep at start-up."""
    try:
        from google.cloud import logging as cloud_logging
    except ImportError:
        _emit_stdout(entry)  # graceful degradation
        return
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
    error: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Emit a single audit entry to ``sink``.

    The function is fire-and-forget: callers do not need to await on it.
    Failures in the sink are swallowed and logged to stderr so that audit
    issues never block the agent's main path.

    ``agent_id`` attributes the event to an agent (per-turn attribution); it
    defaults to the acting agent on the current turn so the data is partitioned
    by agent and the cockpit can scope by it.
    """
    from tessera.agent.identity import resolve_agent_id
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
    )
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
        # Best-effort at the sink: a failed emit is surfaced to stderr, never swallowed
        # silently. Durability for the opposable chain is the spool below, not the sink — so a
        # cloud_logging/postgres transport failure no longer costs the ledger entry.
        sys.stderr.write(f"tessera.guard.audit: sink {sink!r} failed: {exc}\n")

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
        "type": "tessera.agent.handoff",
        "version": 1,
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
        "actor": "system",
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
        "version": 1,
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
        "actor": "system",
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_business_event_audit(
    *,
    event: Mapping[str, Any],
    sink: _Sink | None = None,
) -> None:
    """Append a normalised business event to the opposable S1 audit journal."""
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
        "actor": str(event.get("actor", "system")),
    }
    _append_to_chain(entry, resolved_sink, settings.guard.audit_file)


def emit_agent_proposed(*, name: str, actor: str = "operator", sink: _Sink | None = None) -> None:
    """Emit a governed proposal to add an agent to the fleet (S1 event).

    The registry is approved as a unit (ADR 0012), so creation is a proposal, not
    a runtime mutation: this records the intent as a hash-chained
    ``tessera.agent.proposed`` event feeding the propose -> review -> release flow.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": "tessera.agent.proposed",
        "version": 1,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "proposed_name": name,
        "actor": actor,
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
    actor: str = "operator",
    detail: Mapping[str, Any] | None = None,
    sink: _Sink | None = None,
) -> None:
    """Emit a governed agent lifecycle transition (S1 event).

    Args:
        agent_id: the agent the transition applies to.
        phase: one of :data:`AGENT_LIFECYCLE_PHASES`. The event type is
            ``tessera.agent.<phase>``, hash-chained alongside the proposal.
        actor: who performed the transition (operator/admin/system).
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
        "version": 1,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor,
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
    actor: str = "canary-scheduler",
    sink: _Sink | None = None,
) -> None:
    """Emit one scheduled-canary invocation into the S1 journal (ADR 0019 §4).

    Every cockpit→agent invocation is a governed act: one entry per synthetic canary turn records
    who ran it (``actor`` = the scheduler), which agent, the binding used, the verdict
    (``green`` / ``red``), and the turn ids — hash-chained like every other S1 event and
    reconstructable in État à date. It is also the durable freshness record the canary descriptor
    reads for the synthetic-run facet (no second store). ``synthetic: True`` is stamped so a reader
    can never mistake a canary probe for a real turn.
    """
    from tessera.settings import get_settings

    settings = get_settings()
    resolved_sink: _Sink = sink if sink is not None else settings.guard.audit_sink
    now = datetime.now(UTC).isoformat()
    entry: dict[str, Any] = {
        "type": CANARY_INVOCATION_TYPE,
        "version": 1,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor,
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
    actor: str,
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
        "version": 1,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "agent_id": agent_id,
        "actor": actor,
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
    actor: str = "operator",
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
        "version": 1,
        "occurred_at": now,
        "valid_from": now,
        "valid_to": None,
        "recorded_at": now,
        "actor": actor,
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
    actor: str = "operator",
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
    actor: str = "seal-cycle",
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
        "version": 1,
        "occurred_at": now,
        "recorded_at": now,
        "actor": actor,
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
    actor: str = "seal-cycle",
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
