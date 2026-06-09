"""Tool least-privilege observability (ADR 0010, idea #101; RBAC is ADR 0009).

Least privilege says an agent should be *granted* only the tools it actually
*uses*. Drift in the other direction — tools granted but never called — is
standing attack surface: a prompt-injection that hijacks the agent can only reach
what the agent can reach. This module compares the granted tool set against what
the audit trail shows was actually used, and reports the two failure modes:

* **over-provisioned** — granted but never used (shrink the grant);
* **violations** — used but *not* granted (a privilege the policy did not intend,
  the more serious finding).

The comparison is pure over a granted set and a usage count; the endpoint derives
usage from the guard audit trail (every tool call is audited) and passes the
canonical granted set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Set as AbstractSet

__all__ = ["PrivilegeReport", "ToolUsage", "analyze_privilege"]


@dataclass(frozen=True, slots=True)
class ToolUsage:
    """Usage count for one granted tool."""

    tool: str
    used: int


@dataclass(frozen=True, slots=True)
class PrivilegeReport:
    """Least-privilege posture of the granted tool set."""

    n_granted: int
    n_used: int  # distinct granted tools actually called
    n_over_provisioned: int
    n_violations: int
    utilization_rate: float  # used granted tools / granted tools
    over_provisioned: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    usage: list[ToolUsage] = field(default_factory=list)


def analyze_privilege(
    granted: AbstractSet[str],
    usage: Mapping[str, int],
) -> PrivilegeReport:
    """Compare granted tools against observed usage.

    Args:
        granted: The tools the agent is permitted to call.
        usage: Observed call counts per tool name (from the audit trail).

    Returns:
        A :class:`PrivilegeReport` with over-provisioned grants and violations.
    """
    used_names = {name for name, count in usage.items() if count > 0}
    used_granted = sorted(granted & used_names)
    over_provisioned = sorted(granted - used_names)
    violations = sorted(used_names - granted)

    return PrivilegeReport(
        n_granted=len(granted),
        n_used=len(used_granted),
        n_over_provisioned=len(over_provisioned),
        n_violations=len(violations),
        utilization_rate=len(used_granted) / len(granted) if granted else 0.0,
        over_provisioned=over_provisioned,
        violations=violations,
        usage=[
            ToolUsage(tool=name, used=usage.get(name, 0))
            for name in sorted(granted, key=lambda n: usage.get(n, 0), reverse=True)
        ],
    )
