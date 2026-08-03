"""The number of documented failures is COUNTED, never re-typed.

Audit 2026-08-03. The catalogue grew from 40 to 63 cases and the README followed. Four other
places did not: ``CLAUDE.md``, ``AGENTS.md``, ``SECURITY.md``, the ``make help`` line, and a
module docstring in ``failure_clustering.py`` all still said forty. The figure survived in
five files precisely *because* it was written five times — correcting them by hand fixes
today and guarantees the next drift.

So this test does what a reader cannot: it counts the files on disk, then holds every prose
claim to that count. A claim is cheap to add and this makes it expensive to leave stale.

It also carries its own anti-vacuity floor. A scanner that matches nothing reports success
over a hole (ADR 0026), and this one is a regex over prose — exactly the shape that quietly
stops matching after a sentence is reworded.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

#: Files that state the size of the catalogue in prose.
_DOCUMENTS = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "SECURITY.md",
    "Makefile",
    "docs/eval.md",
    "src/tessera/observability/failure_clustering.py",
)

#: Ways the count is phrased across the repository. Each captures the number.
_CLAIM_PATTERNS = (
    re.compile(r"harness (?:over|of) (\d+) publicly documented"),
    re.compile(r"harness (?:over|of) (\d+) documented"),
    re.compile(r"(\d+) documented agent-failure cases"),
    re.compile(r"(\d+)-case regression harness"),
)

#: Below this, the scanner has stopped seeing the prose it polices rather than found it clean.
_MIN_CLAIMS = 4


def _catalogue_size() -> int:
    """The one authority: the case files actually on disk."""
    return len([p for p in (_ROOT / "eval" / "failures").glob("[0-9][0-9]*_*.json") if p.is_file()])


def _claims() -> list[tuple[str, int]]:
    """Every ``(file, number)`` claim about the catalogue's size."""
    found: list[tuple[str, int]] = []
    for name in _DOCUMENTS:
        path = _ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _CLAIM_PATTERNS:
            found.extend((name, int(m.group(1))) for m in pattern.finditer(text))
    return found


def test_the_catalogue_is_not_empty() -> None:
    """A count of zero would make every assertion below trivially true."""
    assert _catalogue_size() > 0


def test_the_scanner_still_sees_the_prose_it_polices() -> None:
    """Anti-vacuity: a regex over prose that matches nothing must fail, not pass."""
    claims = _claims()
    assert len(claims) >= _MIN_CLAIMS, (
        f"only {len(claims)} size claim(s) found across {len(_DOCUMENTS)} documents — the "
        "phrasings were probably reworded, so this test is now green over a hole. Update "
        "_CLAIM_PATTERNS rather than lowering _MIN_CLAIMS."
    )


def test_every_stated_count_matches_the_files_on_disk() -> None:
    expected = _catalogue_size()
    wrong = [(name, n) for name, n in _claims() if n != expected]
    assert not wrong, (
        f"the catalogue holds {expected} cases; these documents say otherwise: "
        + ", ".join(f"{name} says {n}" for name, n in wrong)
    )
