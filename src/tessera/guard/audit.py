"""Structured audit-trail emission for guard decisions.

The audit sink is chosen at start-up from :attr:`GuardSettings.audit_sink`:

* ``stdout`` — JSON-Lines on stdout, useful for local dev and tests.
* ``cloud_logging`` — Google Cloud Logging, used in staging and prod.
* ``postgres`` — a dedicated audit table; for regulatory replay only.

The on-disk schema is shared across sinks and matches
``docs/compliance.md``'s "audit record" section.
"""

from __future__ import annotations

import json
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path  # noqa: TCH003  used at runtime by the file sink
from typing import TYPE_CHECKING, Any, Literal

from tessera.observability.context import current_conversation_hash, current_request_id, current_turn_id
from tessera.observability.instrumentation import current_trace_id, emit_event
from tessera.observability.profiles import resolve_profile
from tessera.observability.schema import TelemetryEvent

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from tessera.agent.state import GuardDecisionRecord

__all__ = ["current_model", "emit_audit"]

_Outcome = Literal["allowed", "denied", "error"]

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
) -> dict[str, Any]:
    return {
        "type": "tessera.guard.audit",
        "version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "target": target,
        "outcome": outcome,
        "model": model,
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
) -> None:
    """Emit a single audit entry to ``sink``.

    The function is fire-and-forget: callers do not need to await on it.
    Failures in the sink are swallowed and logged to stderr so that audit
    issues never block the agent's main path.
    """
    from tessera.settings import LLMProfile, get_settings

    settings = get_settings()
    profile = resolve_profile(settings)
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
    )
    entry["request_id"] = current_request_id.get()
    entry["trace_id"] = current_trace_id()
    entry["conversation_id_hash"] = current_conversation_hash.get()
    entry["turn_id"] = current_turn_id.get()
    entry["observability_profile"] = profile.name.value
    entry["assurance_level"] = profile.assurance_level.value
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
        emit_event(
            TelemetryEvent.AUDIT_EMITTED,
            {
                "target": target,
                "outcome": outcome,
                "model": model,
            },
        )
    except Exception as exc:
        sys.stderr.write(f"tessera.guard.audit: sink {sink!r} failed: {exc}\n")
