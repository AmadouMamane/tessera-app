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

The tool allow/deny, auth-floor, language and argument checks are first-party
and policy-driven (:mod:`tessera.guard.decisions`). Prompt-injection DETECTION
is delegated to the ``limes`` package through :mod:`tessera.guard.limes_backend`
— the declared backend this seam (ADR 0028) was built for, and the single source
of truth for injection patterns (ADR 0029). A ``CannotSay`` verdict from limes
blocks (fail-closed): a detector that could not look is never a pass.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tessera.agent.sdk.instrument import tool_span
from tessera.authz import auth_satisfies
from tessera.guard.audit import (
    GUARD_ACTOR,
    confirmed_tools,
    current_auth_state,
    current_tool_call_counts,
    emit_audit,
    guard_disabled,
)
from tessera.guard.decisions import (
    Decision,
    DecisionKind,
    Policy,
    ToolPolicy,
    load_policy,
)
from tessera.guard.limes_backend import check_injection
from tessera.observability import semconv
from tessera.observability.metrics import GUARD_DECISIONS_TOTAL
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    import re
    from collections.abc import Awaitable, Callable

    # Runtime-imported lazily inside the functions below to avoid a
    # guard.adapter -> agent.state -> agent.graph -> guard.adapter import cycle.
    from tessera.agent.state import GuardDecisionRecord

__all__ = [
    "GuardedResult",
    "InputCheckResult",
    "check_exfiltration",
    "check_third_party_pii",
    "check_user_input",
    "emit_refuse_policy",
    "guarded_invoke",
]


def _record_guard_decision(target: str, decision: str) -> None:
    """Count one guard decision, partitioned by tool, verdict and agent (ADR 0015 §B).

    The ``agent_id`` label makes ``GUARD_DECISIONS_TOTAL`` sliceable per agent (its
    Phase-1 gap). The acting agent is resolved lazily from the turn contextvar to avoid
    the adapter -> agent import cycle.
    """
    from tessera.agent.identity import resolve_agent_id

    GUARD_DECISIONS_TOTAL.labels(
        target=target, decision=decision, agent_id=resolve_agent_id() or "none"
    ).inc()


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

    # Auth-floor gate (ADR 0008/0009): a tool reaching customer data requires an
    # authenticated session. auth_state is server-derived (the signed cookie), read
    # from the contextvar set at the turn boundary — never from a tool argument.
    auth_state = current_auth_state.get()
    if policy.require_auth is not None and not auth_satisfies(auth_state, policy.require_auth):
        return [
            Decision(
                kind=DecisionKind.DENY,
                rule=f"tool.{policy.name}.require_auth",
                rationale=(
                    f"tool {policy.name!r} requires {policy.require_auth.value}; "
                    f"session auth-state is {auth_state.value}"
                ),
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

    if policy.requires_confirmation and policy.name not in confirmed_tools.get():
        return [
            Decision(
                kind=DecisionKind.DENY,
                rule=f"tool.{policy.name}.requires_confirmation",
                rationale=(
                    f"tool {policy.name!r} requires an explicit human confirmation "
                    "from the action-control channel"
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

    counts = current_tool_call_counts.get()
    if not decisions and counts is not None:
        used = counts.get(policy.name, 0)
        if used >= policy.max_calls_per_turn:
            decisions.append(
                Decision(
                    kind=DecisionKind.DENY,
                    rule=f"tool.{policy.name}.max_calls_per_turn",
                    rationale=(
                        f"tool {policy.name!r} reached its per-turn limit "
                        f"of {policy.max_calls_per_turn}"
                    ),
                )
            )
        else:
            counts[policy.name] = used + 1

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_user_input(
    text: str,
    *,
    policy: Policy | None = None,
) -> InputCheckResult:
    """Check raw user input for prompt injection (limes) and role-play sanitisation.

    Called at the start of every turn — before the LLM sees anything — so that
    injected instructions never reach the language model. Injection DETECTION is
    delegated to the ``limes`` package (ADR 0028/0029), the single source of
    truth for it: Tessera keeps no second copy of the patterns. A ``Deny`` or a
    ``CannotSay`` verdict blocks (the latter fail-closed). The ``policy`` argument
    still drives the first-party transform (sanitisation) layer.

    Returns:
        An :class:`InputCheckResult` whose ``allowed`` flag is ``False`` when
        limes refused (or could not look), or ``True`` with a (potentially
        redacted) ``sanitised_text`` when the input is acceptable.
    """
    from tessera.agent.state import GuardDecisionRecord

    active_policy = policy or load_policy()
    settings = get_settings()
    records: list[GuardDecisionRecord] = []

    # Injection detection is delegated to limes (ADR 0029): Tessera holds no
    # second copy of the patterns. The caller (Tessera) supplies the timestamp;
    # limes never reads the wall clock, so a decision re-derives on replay.
    outcome = check_injection(text, observed_at=datetime.now(UTC).isoformat())
    if outcome.blocked:
        record = GuardDecisionRecord(
            target="user_input",
            decision=DecisionKind.DENY.value,
            policy_rule=outcome.rule,
            rationale=outcome.rationale,
        )
        records.append(record)
        emit_audit(
            target="user_input",
            arguments={"text": "[redacted — injection refused by limes]"},
            decisions=records,
            sink=settings.guard.audit_sink,
            actor=GUARD_ACTOR,
            outcome="denied",
        )
        _record_guard_decision("user_input", "denied")
        return InputCheckResult(
            allowed=False,
            sanitised_text=text,
            decisions=tuple(records),
        )

    # First-party sanitisation (allow-with-redaction) — a DECLARED, separate
    # layer from limes' detection, never a second copy of its deny set. Empty
    # today; kept so role-play cues limes ALLOWED can still be masked from the
    # LLM without ever being confused with a duplicated injection detector.
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
                policy_rule=outcome.rule,
                rationale=outcome.rationale,
            )
        )

    return InputCheckResult(
        allowed=True,
        sanitised_text=sanitised,
        decisions=tuple(records),
    )


def check_exfiltration(
    text: str,
    *,
    policy: Policy | None = None,
) -> GuardDecisionRecord | None:
    """Detect a request to push account data to an external e-mail address.

    The agent has no outbound e-mail channel, so a message combining an egress
    verb, an e-mail address and an account-data term is never legitimate
    (harness case 46 — user-driven exfiltration). The rule is the conjunctive
    ``pii.exfiltration_patterns`` block of the policy: every pattern must
    match, so a bare address ("my new e-mail is x@y.com") or a bare verb
    ("send me my statement") never trips it. The router refuses the matched
    turn at input, before any tool or LLM call.

    Returns:
        The DENY :class:`GuardDecisionRecord` when every pattern matched,
        ``None`` otherwise.
    """
    from tessera.agent.state import GuardDecisionRecord

    active_policy = policy or load_policy()
    patterns = active_policy.exfiltration_patterns
    if not patterns or not all(pattern.search(text) for pattern in patterns):
        return None
    record = GuardDecisionRecord(
        target="user_input",
        decision=DecisionKind.DENY.value,
        policy_rule="pii.exfiltration_patterns",
        rationale="user asked to send account data to an external e-mail address",
    )
    emit_audit(
        target="user_input",
        arguments={"text": "[redacted — exfiltration request]"},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="denied",
    )
    _record_guard_decision("user_input", "denied")
    return record


def check_third_party_pii(
    text: str,
    *,
    policy: Policy | None = None,
) -> GuardDecisionRecord | None:
    """Detect a request to disclose another person's account data.

    The agent only ever serves the authenticated session's own account;
    third-party data requires a mandate handled in-branch, never in chat
    (harness cases 13/14/15/47 — named third party's salary / history / IBAN /
    balance — and 31, the balance tool aimed at a colleague's account). A
    second conjunctive block catches the singling-out linkage attack (case 16
    — "the only customer born in 1987 who transferred to Spain"). Both rules
    live in ``pii.third_party_*_patterns`` of the policy: every pattern of a
    block must match, so "what is MY balance", a joint-account ask or a
    procedural "how do I close her account" never trips them. The router
    refuses the matched turn at input, before any tool or LLM call.

    Returns:
        The DENY :class:`GuardDecisionRecord` when every pattern of one block
        matched, ``None`` otherwise.
    """
    from tessera.agent.state import GuardDecisionRecord

    active_policy = policy or load_policy()
    blocks: tuple[tuple[str, tuple[re.Pattern[str], ...], str], ...] = (
        (
            "pii.third_party_data_patterns",
            active_policy.third_party_data_patterns,
            "refuse_third_party_pii: user asked to disclose another person's account data",
        ),
        (
            "pii.third_party_singling_patterns",
            active_policy.third_party_singling_patterns,
            "refuse_third_party_pii: user asked to single out a customer via correlated attributes",
        ),
    )
    for rule, patterns, rationale in blocks:
        if not patterns or not all(pattern.search(text) for pattern in patterns):
            continue
        record = GuardDecisionRecord(
            target="user_input",
            decision=DecisionKind.DENY.value,
            policy_rule=rule,
            rationale=rationale,
        )
        emit_audit(
            target="user_input",
            arguments={"text": "[redacted — third-party data request]"},
            decisions=[record],
            sink=get_settings().guard.audit_sink,
            actor=GUARD_ACTOR,
            outcome="denied",
        )
        _record_guard_decision("user_input", "denied")
        return record
    return None


def emit_refuse_policy(policy_key: str) -> GuardDecisionRecord:
    """Record a ``refuse_policy`` decision for a deterministic policy refusal.

    The router's policy short-circuit historically answered without leaving a
    guard decision; refusal-shaped short-circuits (investment advice,
    confidential procedures, fraud evasion, credit decision, …) now feed the
    same surfaces as every guard decision: the turn's ``guard_decisions``,
    the hash-chained audit trail and ``GUARD_DECISIONS_TOTAL``.
    """
    from tessera.agent.state import GuardDecisionRecord

    record = GuardDecisionRecord(
        target="user_input",
        decision=DecisionKind.DENY.value,
        policy_rule=f"policy.{policy_key}",
        rationale=f"refuse_policy: deterministic policy short-circuit {policy_key}",
    )
    emit_audit(
        target="user_input",
        arguments={"policy_key": policy_key},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        actor=GUARD_ACTOR,
        outcome="denied",
    )
    _record_guard_decision("user_input", "denied")
    return record


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
    active_policy = policy or load_policy()
    tool_policy = active_policy.tool(tool_name)
    settings = get_settings()
    decisions = _check_tool(tool_policy, arguments, language)
    records = [_to_record(d, target=tool_name) for d in decisions]
    # The sandbox console can disable guard categories for a turn (guard_disabled);
    # everywhere else (eval, prod) the contextvar is empty so the full policy holds.
    # PII off → no output redaction; tools off → policy DENYs are recorded for
    # audit but no longer block the call.
    disabled = guard_disabled.get()
    pii_patterns = () if "pii" in disabled else active_policy.pii_patterns
    audit_args = _redacted_arguments(tool_policy, arguments, pii_patterns)

    denied = "tools" not in disabled and any(d.kind is DecisionKind.DENY for d in decisions)

    # execute_tool span (ADR 0010, #4): carries the guard verdict so a backend
    # can show why a tool was allowed/denied without reading the audit log.
    with tool_span(tool_name, language) as span:
        if denied:
            deny_rule = next((d.rule for d in decisions if d.kind is DecisionKind.DENY), None)
            span.set_attribute(semconv.TESSERA_GUARD_DECISION, "denied")
            if deny_rule is not None:
                span.set_attribute(semconv.TESSERA_GUARD_RULE, deny_rule)
            emit_audit(
                target=tool_name,
                arguments=audit_args,
                decisions=records,
                sink=settings.guard.audit_sink,
                actor=GUARD_ACTOR,
                outcome="denied",
            )
            _record_guard_decision(tool_name, "denied")
            return GuardedResult(
                allowed=False,
                result=None,
                error="guard: tool invocation denied by policy",
                decisions=tuple(records),
            )

        try:
            result = invoke()
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            span.set_attribute(semconv.TESSERA_GUARD_DECISION, "error")
            span.record_exception(exc)
            emit_audit(
                target=tool_name,
                arguments=audit_args,
                decisions=records,
                sink=settings.guard.audit_sink,
                actor=GUARD_ACTOR,
                outcome="error",
                error=str(exc),
            )
            _record_guard_decision(tool_name, "error")
            if settings.guard.fail_closed:
                return GuardedResult(
                    allowed=True,
                    result=None,
                    error=f"tool {tool_name!r} raised: {exc}",
                    decisions=tuple(records),
                )
            raise

        span.set_attribute(semconv.TESSERA_GUARD_DECISION, "allowed")
        emit_audit(
            target=tool_name,
            arguments=audit_args,
            decisions=records,
            sink=settings.guard.audit_sink,
            actor=GUARD_ACTOR,
            outcome="allowed",
        )
        _record_guard_decision(tool_name, "allowed")
        return GuardedResult(
            allowed=True,
            result=result,
            error=None,
            decisions=tuple(records),
        )
