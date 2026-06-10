"""Tool-call loop / oscillation detection (ADR 0010, idea #88).

A misbehaving agent can get stuck calling the same tool over and over, or
ping-ponging between two tools (``A → B → A → B``), burning budget and latency
without making progress. This module mines the ordered stream of tool
invocations from the guard audit trail and flags two cycle shapes:

* **repeat** — the same tool fired ``repeat_threshold`` or more times in a row;
* **oscillation** — a period-2 alternation (``A B A B``) repeated enough to look
  like a stuck delegation loop rather than a coincidence.

It is pure and read-only — the route supplies the already-parsed audit stream,
so this module never touches the agent or the audit file directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Loop", "LoopReport", "detect_loops"]

_DEFAULT_REPEAT_THRESHOLD = 3
_OSCILLATION_MIN_CYCLES = 2  # A B A B = two cycles of the period-2 pattern


@dataclass(frozen=True, slots=True)
class Loop:
    """One detected cycle within a single tool-call stream."""

    stream: str
    kind: str  # "repeat" | "oscillation"
    tools: list[str]  # the cycling tool(s): [A] for repeat, [A, B] for oscillation
    length: int  # number of consecutive calls forming the cycle


@dataclass(frozen=True, slots=True)
class LoopReport:
    """Aggregate loop/oscillation findings across all tool-call streams."""

    n_streams: int
    n_calls: int
    n_loops: int
    repeat_threshold: int
    loops: list[Loop] = field(default_factory=list)


def _scan_repeats(stream: str, calls: list[str], threshold: int) -> list[Loop]:
    """Find runs of the same tool repeated ``threshold`` or more times."""
    loops: list[Loop] = []
    run_start = 0
    for i in range(1, len(calls) + 1):
        if i < len(calls) and calls[i] == calls[run_start]:
            continue
        run_len = i - run_start
        if run_len >= threshold:
            loops.append(
                Loop(stream=stream, kind="repeat", tools=[calls[run_start]], length=run_len)
            )
        run_start = i
    return loops


def _scan_oscillations(stream: str, calls: list[str]) -> list[Loop]:
    """Find period-2 alternations ``A B A B …`` with A != B."""
    loops: list[Loop] = []
    i = 0
    n = len(calls)
    while i + 3 < n + 1:  # need at least A B A B
        a, b = calls[i], calls[i + 1] if i + 1 < n else None
        if b is None or a == b:
            i += 1
            continue
        # Extend while the A,B alternation holds.
        j = i + 2
        while j < n and calls[j] == calls[j - 2]:
            j += 1
        length = j - i
        if length >= 2 * _OSCILLATION_MIN_CYCLES:
            loops.append(Loop(stream=stream, kind="oscillation", tools=[a, b], length=length))
            i = j  # don't double-count the same span
        else:
            i += 1
    return loops


def detect_loops(
    streams: dict[str, list[str]], *, repeat_threshold: int = _DEFAULT_REPEAT_THRESHOLD
) -> LoopReport:
    """Detect repeat and oscillation cycles across tool-call streams.

    Args:
        streams: Mapping of a group key (conversation/subject or ``"global"``) to
            its tool-call sequence in invocation order.
        repeat_threshold: Minimum consecutive identical calls to flag a repeat.

    Returns:
        A :class:`LoopReport` listing every detected cycle.
    """
    all_loops: list[Loop] = []
    n_calls = 0
    for stream, calls in streams.items():
        n_calls += len(calls)
        all_loops.extend(_scan_repeats(stream, calls, repeat_threshold))
        all_loops.extend(_scan_oscillations(stream, calls))
    return LoopReport(
        n_streams=len(streams),
        n_calls=n_calls,
        n_loops=len(all_loops),
        repeat_threshold=repeat_threshold,
        loops=all_loops,
    )
