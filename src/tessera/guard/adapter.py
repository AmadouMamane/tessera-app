"""Adapter that turns the guard policy into runtime decisions.

The adapter is the single chokepoint between every worker and every tool. It
performs three jobs:

1. **Pre-flight check** — apply tool allow/deny, language restrictions, and
   argument validation; refuse to invoke the underlying tool if the check
   fails.
2. **Invoke** — call the underlying tool through a caller-supplied closure,
   so this layer never has to know which tool signature lives where.
3. **Post-flight audit** — record a :class:`GuardDecisionRecord` per decision
   into an audit sink (see :mod:`tessera.guard.audit`).

When the upstream :mod:`mcp_firewall` library is importable, the adapter
delegates its decision logic to it; otherwise it falls back to the
policy-based implementation in this module. Either way the *interface* is
identical so callers do not branch on backend availability.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tessera.guard.audit import emit_audit
from tessera.guard.decisions import (
    Decision,
    DecisionKind,
    Policy,
    ToolPolicy,
    load_policy,
)
from tessera.observability.instrumentation import emit_event, start_span
from tessera.observability.metrics import GUARD_DECISIONS_TOTAL, SENSITIVE_ACTION_TRANSACTIONS_TOTAL
from tessera.observability.schema import TelemetryEvent, TelemetrySpan
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    # Runtime-imported lazily inside the functions below to avoid a
    # guard.adapter -> agent.state -> agent.graph -> guard.adapter import cycle.
    from tessera.agent.state import GuardDecisionRecord
    from tessera.observability.actions import DecisionProof

__all__ = ["GuardedResult", "InputCheckResult", "check_user_input", "guarded_invoke"]


@dataclass(frozen=True, slots=True)
class InputCheckResult:
    """Outcome of checking the raw user input against the guard policy."""

    allowed: bool
    sanitised_text: str
    decisions: tuple[GuardDecisionRecord, ...]


@dataclass(frozen=True, slots=True)
class GuardedResult:
    """Outcome of a guarded tool invocation."""

    allowed: bool
    result: Any
    error: str | None
    decisions: tuple[GuardDecisionRecord, ...] = field(default_factory=tuple)
    decision_proof: DecisionProof | None = None


# ---------------------------------------------------------------------------
# Optional mcp-firewall backend
# ---------------------------------------------------------------------------


def _load_mcp_firewall() -> Any | None:
    """Return the mcp_firewall module if installed, else ``None``."""
    try:
        import mcp_firewall
    except ImportError:
        return None
    return mcp_firewall


_MCP_FIREWALL = _load_mcp_firewall()


# ---------------------------------------------------------------------------
# Policy-driven pre-flight
# ---------------------------------------------------------------------------


def _check_tool(
    policy: ToolPolicy,
    arguments: dict[str, object],
    language: LanguageCode,
) -> list[Decision]:
    """Apply :class:`ToolPolicy` to ``arguments``; return the decision list."""
    if not policy.allow:
        return [
            Decision(
                kind=DecisionKind.DENY,
                rule=f"tool.{policy.name}.allow",
                rationale=f"tool {policy.name!r} is not in the allowlist",
            )
        ]

    if policy.require_languages and language not in policy.require_languages:
        allowed = ", ".join(sorted(lang.value for lang in policy.require_languages))
        return [
            Decision(
                kind=DecisionKind.DENY,
                rule=f"tool.{policy.name}.require_languages",
                rationale=(
                    f"tool {policy.name!r} only allowed for languages [{allowed}]; "
                    f"current language is {language.value}"
                ),
            )
        ]

    decisions: list[Decision] = []
    for arg_name, arg_rule in policy.arguments.items():
        if arg_rule.pattern is None:
            continue
        value = arguments.get(arg_name)
        if value is None:
            continue
        if not arg_rule.pattern.fullmatch(str(value)):
            decisions.append(
                Decision(
                    kind=DecisionKind.DENY,
                    rule=f"tool.{policy.name}.argument.{arg_name}",
                    rationale=(
                        f"argument {arg_name!r} did not match the configured " "validation pattern"
                    ),
                )
            )

    if not decisions:
        decisions.append(
            Decision(
                kind=DecisionKind.ALLOW,
                rule=f"tool.{policy.name}.allow",
                rationale=f"tool {policy.name!r} passed all pre-flight checks",
            )
        )
    return decisions


def _redacted_arguments(
    policy: ToolPolicy,
    arguments: dict[str, object],
    pii_patterns: tuple[Any, ...],
) -> dict[str, object]:
    """Return a copy of ``arguments`` with policy-redacted fields masked."""
    redacted: dict[str, object] = {}
    for key, value in arguments.items():
        rule = policy.arguments.get(key)
        if rule is not None and rule.redact_in_audit:
            redacted[key] = "[redacted]"
            continue
        rendered = str(value)
        for pattern in pii_patterns:
            rendered = pattern.sub("[redacted]", rendered)
        redacted[key] = rendered if rendered != str(value) else value
    return redacted


def _to_record(decision: Decision, target: str) -> GuardDecisionRecord:
    from tessera.agent.state import GuardDecisionRecord

    return GuardDecisionRecord(
        target=target,
        decision=decision.kind.value,
        policy_rule=decision.rule,
        rationale=decision.rationale,
        redactions=decision.redactions,
    )


def _observe_guard_records(records: list[GuardDecisionRecord]) -> None:
    """Record guard decision metrics and canonical policy events."""
    for record in records:
        GUARD_DECISIONS_TOTAL.labels(target=record.target, decision=record.decision).inc()
        emit_event(
            TelemetryEvent.POLICY_EVALUATED,
            {
                "target": record.target,
                "guard_verdict": record.decision,
                "rule_id": record.policy_rule,
            },
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_user_input(
    text: str,
    *,
    policy: Policy | None = None,
) -> InputCheckResult:
    """Check raw user input against prompt-injection deny and transform patterns.

    Called at the start of every turn — before the LLM sees anything — so that
    injected instructions never reach the language model.

    Returns:
        An :class:`InputCheckResult` whose ``allowed`` flag is ``False`` when a
        deny pattern matched, or ``True`` with a (potentially redacted)
        ``sanitised_text`` when the input is acceptable.
    """
    from tessera.agent.state import GuardDecisionRecord

    with start_span(TelemetrySpan.GUARD_DECISION, {"target": "user_input"}):
        active_policy = policy or load_policy()
        settings = get_settings()
        records: list[GuardDecisionRecord] = []

        for pattern in active_policy.prompt_injection_deny:
            if pattern.search(text):
                record = GuardDecisionRecord(
                    target="user_input",
                    decision=DecisionKind.DENY.value,
                    policy_rule="prompt_injection.deny_patterns",
                    rationale=f"user input matched injection deny pattern: {pattern.pattern!r}",
                )
                records.append(record)
                _observe_guard_records(records)
                emit_audit(
                    target="user_input",
                    arguments={"text": "[redacted — matched deny pattern]"},
                    decisions=records,
                    sink=settings.guard.audit_sink,
                    outcome="denied",
                )
                return InputCheckResult(
                    allowed=False,
                    sanitised_text=text,
                    decisions=tuple(records),
                )

        sanitised = text
        for pattern, replacement in active_policy.prompt_injection_transforms:
            sanitised = pattern.sub(replacement, sanitised)

        if sanitised != text:
            record = GuardDecisionRecord(
                target="user_input",
                decision=DecisionKind.TRANSFORM.value,
                policy_rule="prompt_injection.transform_patterns",
                rationale="role-play or persona cue redacted from user input",
            )
            records.append(record)

        if not records:
            records.append(
                GuardDecisionRecord(
                    target="user_input",
                    decision=DecisionKind.ALLOW.value,
                    policy_rule="prompt_injection.deny_patterns",
                    rationale="user input passed all injection checks",
                )
            )

        _observe_guard_records(records)
        return InputCheckResult(
            allowed=True,
            sanitised_text=sanitised,
            decisions=tuple(records),
        )


async def guarded_invoke(
    *,
    tool_name: str,
    invoke: Callable[[], Awaitable[Any] | Any],
    arguments: dict[str, object],
    language: LanguageCode,
    policy: Policy | None = None,
) -> GuardedResult:
    """Run ``invoke`` under the guard policy.

    Args:
        tool_name: The policy key for this tool (must match ``tools.<name>``).
        invoke: A zero-argument callable that performs the tool invocation.
            Synchronous and async callables are both supported.
        arguments: The argument map; used for validation and for the audit
            trail. Sensitive fields are redacted per policy.
        language: The active conversation language; some tools restrict.
        policy: Optional pre-loaded policy; defaults to
            :func:`load_policy` against the settings path.

    Returns:
        A :class:`GuardedResult` containing the result (or error), the
        allow/deny verdict, and every decision recorded for audit.
    """
    from tessera.observability.actions import (
        active_policy_hash,
        issue_decision_proof,
        requires_decision_proof,
        validate_decision_proof,
    )

    with start_span(TelemetrySpan.GUARD_DECISION, {"target": tool_name, "language": language.value}):
        active_policy = policy or load_policy()
        tool_policy = active_policy.tool(tool_name)
        settings = get_settings()
        decisions = _check_tool(tool_policy, arguments, language)
        records = [_to_record(d, target=tool_name) for d in decisions]
        audit_args = _redacted_arguments(tool_policy, arguments, active_policy.pii_patterns)
        policy_hash = active_policy_hash()
        proof_context: dict[str, object] = {"language": language.value, "tool_name": tool_name}
        _observe_guard_records(records)

        denied = any(d.kind is DecisionKind.DENY for d in decisions)
        if denied:
            SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="blocked").inc()
            emit_event(
                TelemetryEvent.TOOL_EXECUTION_BLOCKED,
                {"target": tool_name, "guard_verdict": "deny"},
            )
            emit_audit(
                target=tool_name,
                arguments=audit_args,
                decisions=records,
                sink=settings.guard.audit_sink,
                outcome="denied",
            )
            return GuardedResult(
                allowed=False,
                result=None,
                error="guard: tool invocation denied by policy",
                decisions=tuple(records),
            )

        emit_event(
            TelemetryEvent.TOOL_EXECUTION_STARTED,
            {"target": tool_name, "guard_verdict": "allow"},
        )
        SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="execution_started").inc()
        decision_proof = None
        if requires_decision_proof(tool_name):
            decision_proof = issue_decision_proof(
                tool_name=tool_name,
                arguments=arguments,
                context=proof_context,
                policy_hash=policy_hash,
                rule_id=records[0].policy_rule if records else f"tool.{tool_name}.allow",
                verdict="allowed",
                reason_code="guard_preflight_allowed",
            )
            emit_event(
                TelemetryEvent.PROOF_ISSUED,
                {
                    "target": tool_name,
                    "rule_id": decision_proof.rule_id,
                    "proof_quality": "complete",
                },
            )
            SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="proof_issued").inc()
            validation = validate_decision_proof(
                decision_proof,
                tool_name=tool_name,
                arguments=arguments,
                context=proof_context,
                policy_hash=policy_hash,
            )
            if not validation.valid:
                SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="blocked").inc()
                emit_audit(
                    target=tool_name,
                    arguments=audit_args,
                    decisions=records,
                    sink=settings.guard.audit_sink,
                    outcome="denied",
                    error=validation.reason_code,
                )
                return GuardedResult(
                    allowed=False,
                    result=None,
                    error=f"guard: decision proof invalid ({validation.reason_code})",
                    decisions=tuple(records),
                    decision_proof=decision_proof,
                )
        try:
            result = invoke()
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="execution_failed").inc()
            emit_audit(
                target=tool_name,
                arguments=audit_args,
                decisions=records,
                sink=settings.guard.audit_sink,
                outcome="error",
                error=str(exc),
            )
            if settings.guard.fail_closed:
                return GuardedResult(
                    allowed=True,
                    result=None,
                    error=f"tool {tool_name!r} raised: {exc}",
                    decisions=tuple(records),
                    decision_proof=decision_proof,
                )
            raise

        SENSITIVE_ACTION_TRANSACTIONS_TOTAL.labels(target=tool_name, state="execution_succeeded").inc()
        emit_event(
            TelemetryEvent.TOOL_EXECUTION_ALLOWED,
            {"target": tool_name, "guard_verdict": "allow"},
        )
        emit_audit(
            target=tool_name,
            arguments=audit_args,
            decisions=records,
            sink=settings.guard.audit_sink,
            outcome="allowed",
        )
        return GuardedResult(
            allowed=True,
            result=result,
            error=None,
            decisions=tuple(records),
            decision_proof=decision_proof,
        )
