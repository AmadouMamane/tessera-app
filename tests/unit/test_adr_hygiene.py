"""A8 — the decision record stops drifting.

Audit 2026-07-10, P1 `adr-hygiene` (docs/decisions/): two 0008, two 0010, two 0017, two 0019,
and 0015 held by four files — with execution logs, an incident report and overnight-run
journals squatting real ADR numbers.

Half of that was not an ADR problem at all: the logs are not decisions and had no business
carrying an ADR number. They now live in ``docs/status/`` and ``docs/incidents/``, which
dissolves the 0015/0017/0019 collisions without renumbering anything.

Three genuine collisions remained, frozen rather than fixed. **Two are now dissolved**
(2026-07-12):

* ``0015`` — the Hica seal design note moved to **0022**. It was referenced *only by filename*:
  zero bare ``ADR 0015`` references meant it, because the seal was **decided** in the spine ADR
  (§Amendment 3 / §Correction 3c) and only **designed** in the annex. A rename and five links.
* ``0008`` — security hardening moved to **0020**. Settled by the creation dates:
  ``0008-security-hardening`` is 2026-05-31, ``0008-agent-audience-and-surface`` is 2026-06-22,
  so every reference written before that cutoff could *only* have meant the former — proof, not
  heuristic. 25 bare references rewritten, each with its evidence recorded in
  ``docs/status/adr-renumber-evidence.md``.

``0010`` is **still frozen, deliberately**. It carries **245+** references — 183 meaning
*frontier-observability* (which therefore keeps the number) and 52 meaning *recouvrement* (which
will become 0021). Some of them **wrap across lines** (``ADR`` ending one line, ``0010 Phase C``
beginning the next), so *no grep-based verification of that rename can be complete*. Rewriting
the project's memory semantically, at that scale, with **no CI to act as an independent
witness**, is exactly what a bounded tolerance of an absent CI has to forbid. It waits for CI.

So the ratchet: the known set can SHRINK, never grow. The same discipline as the boundary
ratchet — exact equality, zero tolerance for a new one, and a resolved collision must be
*removed* from the set or the exception list goes stale.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[2] / "docs"
_DECISIONS = _DOCS / "decisions"

#: The collisions that exist today. This set may only ever get SMALLER.
#: 0008 → 0020 and 0015 → 0022 landed 2026-07-12. **0010 is the last one**, and it is held for
#: CI: 245+ references, some wrapped across lines, and one wrong call makes the decision record
#: assert something false. Plan + per-reference evidence: docs/status/adr-renumber-evidence.md.
_FROZEN_COLLISIONS: frozenset[str] = frozenset({"0010"})

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
