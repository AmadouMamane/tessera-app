"""Structured audit-trail emission for guard decisions.

The audit sink is chosen at start-up from :attr:`GuardSettings.audit_sink`:

* ``stdout`` — JSON-Lines on stdout, useful for local dev and tests.
* ``cloud_logging`` — Google Cloud Logging, used in staging and prod.
* ``postgres`` — a dedicated audit table; for regulatory replay only.

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

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from tessera.agent.state import GuardDecisionRecord

__all__ = ["ChainStatus", "current_model", "emit_audit", "verify_audit_chain"]

_Outcome = Literal["allowed", "denied", "error"]

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


def _emit_postgres(entry: dict[str, Any]) -> None:
    """Persist the audit entry to the dedicated audit table.

    The implementation is deferred to a later increment; for now we fall back
    to stdout so the call site does not need to special-case nothingness.
    """
    _emit_stdout(entry)


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
    # Link this entry into the tamper-evident chain (idea #3). The file sink
    # resumes the chain from disk so it survives restarts; other sinks chain
    # in-process from genesis.
    global _last_hash
    if _last_hash is None:
        _last_hash = _seed_last_hash(settings.guard.audit_file) if sink == "file" else _GENESIS_HASH
    entry["prev_hash"] = _last_hash
    entry["hash"] = _hash_core({k: v for k, v in entry.items() if k != "hash"})
    _last_hash = entry["hash"]
    try:
        match sink:
            case "stdout":
                _emit_stdout(entry)
            case "file":
                _emit_file(entry, settings.guard.audit_file)
            case "cloud_logging":
                _emit_cloud_logging(entry)
            case "postgres":
                _emit_postgres(entry)
    except Exception as exc:
        sys.stderr.write(f"tessera.guard.audit: sink {sink!r} failed: {exc}\n")


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
