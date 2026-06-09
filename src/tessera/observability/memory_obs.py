"""Memory observability (ADR 0010, idea #23; memory layer is ADR 0007).

Long-term memory is the agent's least-observed subsystem and its most dangerous:
a fact extracted from a malicious turn is a *stored prompt-injection* (OWASP
LLM03) that resurfaces turns or days later. The memory layer already screens
candidates on both write and read and audits every action into the guard trail;
this module rolls those audit records up into the signals an operator needs:

* **write** acceptance vs rejection (poisoning / PII candidates blocked at write);
* **recall hit/miss** — how often a read actually returned a memory vs nothing;
* **stored-injection caught on read** — items the on-read screen dropped, i.e. a
  poisoned memory neutralised before it reached the prompt;
* **erasure** activity.

It parses the ``recalled N/M`` and ``persisted N/M`` rationales the reflector and
persistent backend emit, so the hit-rate and the screened-out count are exact,
not estimated. The aggregation is pure over audit-entry dicts; the endpoint feeds
it the guard audit log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["MemoryObsReport", "aggregate_memory_audit"]

# "recalled 2/3 item(s) after screening" / "persisted 1/4 candidate fact(s)".
_FRACTION_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")
_MEMORY_TARGETS = {"memory.write", "memory.read", "memory.forget"}


@dataclass(frozen=True, slots=True)
class MemoryObsReport:
    """Rolled-up memory-layer activity from the audit trail."""

    n_actions: int
    n_writes: int
    writes_allowed: int
    writes_denied: int  # poisoning / PII candidates rejected at write
    n_reads: int
    recall_hits: int  # reads that returned at least one memory
    recall_misses: int  # reads that returned nothing
    recall_hit_rate: float
    items_recalled: int  # total memories surfaced
    items_screened_out: int  # poisoned/PII items dropped on read (LLM03 caught)
    n_forgets: int


def _fraction(rationale: str) -> tuple[int, int] | None:
    """Parse the ``N/M`` in a rationale like 'recalled 2/3 item(s)'."""
    match = _FRACTION_RE.search(rationale)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def aggregate_memory_audit(entries: Iterable[dict[str, object]]) -> MemoryObsReport:
    """Aggregate memory governance actions from audit entries.

    Args:
        entries: Parsed audit-log objects (``type == 'tessera.guard.audit'``).
            Only entries whose ``target`` is a ``memory.*`` action are counted.

    Returns:
        A :class:`MemoryObsReport`.
    """
    n_actions = n_writes = writes_allowed = writes_denied = 0
    n_reads = recall_hits = recall_misses = items_recalled = items_screened_out = 0
    n_forgets = 0

    for entry in entries:
        target = entry.get("target")
        if target not in _MEMORY_TARGETS:
            continue
        n_actions += 1
        outcome = entry.get("outcome")
        rationale = ""
        decisions = entry.get("decisions")
        if isinstance(decisions, list) and decisions and isinstance(decisions[0], dict):
            rationale = str(decisions[0].get("rationale", ""))

        if target == "memory.write":
            n_writes += 1
            if outcome == "denied":
                writes_denied += 1
            else:
                writes_allowed += 1
        elif target == "memory.read":
            n_reads += 1
            frac = _fraction(rationale)
            if frac is not None:
                surfaced, found = frac
                items_recalled += surfaced
                items_screened_out += max(0, found - surfaced)
                if surfaced > 0:
                    recall_hits += 1
                else:
                    recall_misses += 1
            else:
                recall_misses += 1
        elif target == "memory.forget":
            n_forgets += 1

    hit_rate = recall_hits / n_reads if n_reads else 0.0
    return MemoryObsReport(
        n_actions=n_actions,
        n_writes=n_writes,
        writes_allowed=writes_allowed,
        writes_denied=writes_denied,
        n_reads=n_reads,
        recall_hits=recall_hits,
        recall_misses=recall_misses,
        recall_hit_rate=hit_rate,
        items_recalled=items_recalled,
        items_screened_out=items_screened_out,
        n_forgets=n_forgets,
    )
