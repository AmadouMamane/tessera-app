"""Typed policy and decision objects for the guard layer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from tessera.authz import Auth
from tessera.guard.limes_backend import injection_rules
from tessera.settings import LanguageCode, get_settings

__all__ = [
    "Decision",
    "DecisionKind",
    "Policy",
    "RuleViolationError",
    "ToolPolicy",
    "load_policy",
]


class DecisionKind(StrEnum):
    """The three possible outcomes of a guard check."""

    ALLOW = "allow"
    DENY = "deny"
    TRANSFORM = "transform"


@dataclass(frozen=True, slots=True)
class Decision:
    """The structured result of a single guard check."""

    kind: DecisionKind
    rule: str
    rationale: str
    redactions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleViolationError(Exception):
    """Raised internally when a deny rule fires; never surfaces to callers."""

    rule: str
    rationale: str

    def __str__(self) -> str:  # pragma: no cover  trivial
        return f"{self.rule}: {self.rationale}"


@dataclass(frozen=True, slots=True)
class ArgumentRule:
    """Per-argument validation rule for a tool."""

    pattern: re.Pattern[str] | None = None
    #: When true, an absent or null value is a DENY. Validation used to mean "check it IF
    #: present": a call with the argument simply missing skipped every pattern and came back
    #: ``allow`` with the rationale "passed all pre-flight checks" — an Ok with no evidence
    #: (ADR 0027), on the one seam whose whole job is to have some.
    required: bool = False
    redact_in_audit: bool = False


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Validation rules for a single tool name."""

    name: str
    allow: bool = False
    requires_confirmation: bool = False
    #: Argument name a human confirmation is BOUND to, e.g. ``card_last_four``. When set, an
    #: approval authorises this tool *for that value only* — approving the blocking of card
    #: 4242 is not approving the blocking of whatever card the model names next.
    confirmation_binds: str | None = None
    require_languages: frozenset[LanguageCode] = field(default_factory=frozenset)
    # Minimum session authorization to invoke this tool (ADR 0008/0009). ``None``
    # = no auth floor (e.g. simulators, escalation). Account/PII tools declare
    # ``customer-auth`` so an anonymous session is denied them at the guard.
    require_auth: Auth | None = None
    max_calls_per_turn: int = 1
    arguments: dict[str, ArgumentRule] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Policy:
    """Top-level guard policy."""

    version: int
    tools: dict[str, ToolPolicy]
    prompt_injection_deny: tuple[re.Pattern[str], ...]
    prompt_injection_transforms: tuple[tuple[re.Pattern[str], str], ...]
    pii_patterns: tuple[re.Pattern[str], ...]
    # Conjunctive egress rule (``pii.exfiltration_patterns``): a user turn
    # matching EVERY pattern (egress verb + e-mail address + account-data term)
    # is refused at input — see guard.adapter.check_exfiltration. Empty = off.
    exfiltration_patterns: tuple[re.Pattern[str], ...] = ()
    # Conjunctive third-party PII rules (``pii.third_party_*_patterns``): a
    # user turn matching EVERY pattern of either block (a relation noun + a
    # third-person-possessed account datum + a disclosure ask, or a
    # singling-out correlation ask) is refused at input — see
    # guard.adapter.check_third_party_pii. Empty = off.
    third_party_data_patterns: tuple[re.Pattern[str], ...] = ()
    third_party_singling_patterns: tuple[re.Pattern[str], ...] = ()

    def tool(self, name: str) -> ToolPolicy:
        """Return the policy for ``name`` or a deny-all fallback."""
        return self.tools.get(name, ToolPolicy(name=name, allow=False))


def _compile_arg(rule_raw: dict[str, object]) -> ArgumentRule:
    pattern_raw = rule_raw.get("pattern")
    pattern = re.compile(str(pattern_raw)) if pattern_raw else None
    return ArgumentRule(
        pattern=pattern,
        required=bool(rule_raw.get("required", False)),
        redact_in_audit=bool(rule_raw.get("redact_in_audit", False)),
    )


def _compile_tool(name: str, raw: dict[str, object]) -> ToolPolicy:
    arguments_raw = raw.get("arguments") or {}
    if not isinstance(arguments_raw, dict):
        raise TypeError(f"tool {name!r}: arguments must be a mapping")
    languages_raw = raw.get("require_languages") or []
    if not isinstance(languages_raw, list):
        raise TypeError(f"tool {name!r}: require_languages must be a list")
    languages: frozenset[LanguageCode] = frozenset(LanguageCode(item) for item in languages_raw)
    auth_raw = raw.get("require_auth")
    require_auth = Auth(str(auth_raw)) if auth_raw else None  # fail-fast on a bad value
    return ToolPolicy(
        name=name,
        allow=bool(raw.get("allow", False)),
        requires_confirmation=bool(raw.get("requires_confirmation", False)),
        confirmation_binds=(
            str(binds) if isinstance(binds := raw.get("confirmation_binds"), str) else None
        ),
        require_languages=languages,
        require_auth=require_auth,
        max_calls_per_turn=int(raw.get("max_calls_per_turn") or 1),  # type: ignore[call-overload]
        arguments={
            arg_name: _compile_arg(arg_raw)
            for arg_name, arg_raw in arguments_raw.items()
            if isinstance(arg_raw, dict)
        },
    )


@lru_cache(maxsize=4)
def load_policy(path: Path | None = None) -> Policy:
    """Load and compile the guard policy from ``path`` (default: settings)."""
    resolved = path or get_settings().guard.policy_path
    raw_text = Path(resolved).read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_text)
    if not isinstance(parsed, dict):
        raise TypeError("guard policy must be a YAML mapping at the root")

    tools_raw = parsed.get("tools") or {}
    if not isinstance(tools_raw, dict):
        raise TypeError("guard policy: tools must be a mapping")
    tools = {
        name: _compile_tool(name, raw) for name, raw in tools_raw.items() if isinstance(raw, dict)
    }

    pi_raw = parsed.get("prompt_injection") or {}
    # Injection patterns live in `limes` now (ADR 0029), the single source of
    # truth. The YAML deny list MUST stay empty — re-adding a pattern here would
    # be the divergence bug ADR 0029 forbids, so we refuse it — and the field is
    # DERIVED from limes, so every display / trajectory / retraction surface that
    # reads policy.prompt_injection_deny reflects the one source, not a copy.
    # (check_user_input runs the limes DETECTOR directly; see guard.adapter.)
    if pi_raw.get("deny_patterns"):
        raise ValueError(
            "guard policy: prompt_injection.deny_patterns must be empty — injection "
            "patterns moved to limes (ADR 0029). Add rules to limes' detector policy, "
            "not here; this field is derived from limes at load time."
        )
    deny = tuple(pattern for _label, pattern in injection_rules())
    transforms_raw = pi_raw.get("transform_patterns", []) or []
    transforms = tuple(
        (re.compile(str(item["match"])), str(item.get("replacement", "[redacted]")))
        for item in transforms_raw
        if isinstance(item, dict) and "match" in item
    )

    pii_raw = parsed.get("pii") or {}
    pii_patterns = tuple(re.compile(str(p)) for p in pii_raw.get("redact_patterns", []) or [])

    def _conjunctive(key: str) -> tuple[re.Pattern[str], ...]:
        block = pii_raw.get(key) or {}
        if not isinstance(block, dict):
            return ()
        return tuple(re.compile(str(p)) for p in block.values())

    return Policy(
        version=int(parsed.get("version", 0)),
        tools=tools,
        prompt_injection_deny=deny,
        prompt_injection_transforms=transforms,
        pii_patterns=pii_patterns,
        exfiltration_patterns=_conjunctive("exfiltration_patterns"),
        third_party_data_patterns=_conjunctive("third_party_data_patterns"),
        third_party_singling_patterns=_conjunctive("third_party_singling_patterns"),
    )


# Convenience re-export for callers that just want the literal type aliases.
DecisionLiteral = Literal["allow", "deny", "transform"]
