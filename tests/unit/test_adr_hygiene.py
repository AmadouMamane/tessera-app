"""A8 — the decision record stops drifting.

Audit 2026-07-10, P1 `adr-hygiene` (docs/decisions/): two 0008, two 0010, two 0017, two 0019,
and 0015 held by four files — with execution logs, an incident report and overnight-run
journals squatting real ADR numbers.

Half of that was not an ADR problem at all: the logs are not decisions and had no business
carrying an ADR number. They now live in ``docs/status/`` and ``docs/incidents/``, which
dissolves the 0015/0017/0019 collisions without renumbering anything.

What remains is three genuine collisions, and they are FROZEN rather than fixed. "ADR 0010" is
referenced 138 times across code and docs — meaning *frontier-observability* in some and
*recouvrement* in others — and "ADR 0008" 55 times, equally ambiguously. Renumbering means
reassigning every reference by judgment; one wrong call and the decision record asserts
something false. A duplicate number is an annoyance. A decision record that lies is a defect.

So the ratchet: the known set can SHRINK, never grow. The same discipline as the boundary
ratchet — exact equality, zero tolerance for a new one.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[2] / "docs"
_DECISIONS = _DOCS / "decisions"

#: The collisions that exist today. This set may only ever get SMALLER.
#: Renumbering plan: docs/decisions/README.md.
_FROZEN_COLLISIONS: frozenset[str] = frozenset({"0008", "0010", "0015"})

#: Filename patterns that are NOT decisions and must never live in docs/decisions/.
_NOT_A_DECISION = re.compile(r"execution-status|incident|overnight", re.IGNORECASE)


def _numbered_adrs() -> dict[str, list[str]]:
    by_number: dict[str, list[str]] = defaultdict(list)
    for path in sorted(_DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md")):
        by_number[path.name[:4]].append(path.name)
    return by_number


def test_no_new_adr_number_collision() -> None:
    """A new duplicate prefix fails the gate. The frozen three are the ceiling, not a licence."""
    collisions = {number for number, files in _numbered_adrs().items() if len(files) > 1}

    new = collisions - _FROZEN_COLLISIONS
    assert not new, (
        f"new ADR number collision(s): {sorted(new)}. Pick the next free number — "
        f"the existing duplicates are frozen debt, not a precedent."
    )


def test_a_fixed_collision_is_removed_from_the_frozen_set() -> None:
    """The ratchet must not go stale: once renumbered, delete it from the frozen set.

    Without this half, the frozen set silently keeps claiming debt that no longer exists —
    and a stale exception list is how a ratchet quietly stops ratcheting.
    """
    collisions = {number for number, files in _numbered_adrs().items() if len(files) > 1}

    fixed = _FROZEN_COLLISIONS - collisions
    assert not fixed, (
        f"collision(s) {sorted(fixed)} are resolved — remove them from _FROZEN_COLLISIONS "
        f"(and from docs/decisions/README.md)."
    )


def test_decisions_directory_holds_only_decisions() -> None:
    """An execution log is not a decision and must not squat an ADR number."""
    intruders = [path.name for path in _DECISIONS.glob("*.md") if _NOT_A_DECISION.search(path.name)]
    assert intruders == [], (
        f"{intruders} are not decisions — put status logs in docs/status/ and incident "
        f"reports in docs/incidents/."
    )


def test_every_decision_is_listed_in_the_index() -> None:
    """An index nobody updates is worse than no index."""
    index = (_DECISIONS / "README.md").read_text(encoding="utf-8")
    missing = [
        path.name
        for path in sorted(_DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md"))
        if path.name not in index
    ]
    assert missing == [], f"not listed in docs/decisions/README.md: {missing}"


def test_the_relocated_logs_are_where_the_index_says() -> None:
    """The move is real, not just described."""
    assert (_DOCS / "status" / "0017-execution-status.md").exists()
    assert (_DOCS / "incidents" / "0015-incident-TESS-LEDGER-001-status.md").exists()
