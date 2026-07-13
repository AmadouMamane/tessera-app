"""The memory registry has ONE source of truth — enforced, not remembered.

On 2026-07-13 the project's insight registry was found to exist in two diverged
copies, under the same name, in two different agent harness directories:

    ~/.claude/projects/<slug>/memory/insights_tessera.md   244 KB, older, 106 insights
    ~/.codex/projects/<slug>/memory/insights_tessera.md    143 KB, newer, 103 blocks

The bigger file was the DEAD one. "Keep the most recent" would have destroyed 98
insights in silence. The two were reconciled into a single canonical file, and both
harness paths became symlinks to it.

Nothing protects that file. No test covered it, no CI job read it, and the registry
is precisely the artifact whose loss is unrecoverable — a bug can be re-found, a
lesson cannot. So the class is closed here, on the two ways it can re-open:

  RULE A — one registry, one file. Two files with the same name and different
           contents is a bomb: the one you write is not the one you read. Symlinks
           and hardlinks collapse to one inode and pass; a second REAL file does not.

  RULE B — one number, one insight. Two agents each appending "Insight 101" is the
           same bomb one level down. This rule would have caught the third writer who
           appended two insights to the canonical file DURING the reconciliation,
           under numbers already taken twice.

Both rules are machine-local by construction: the registry is gitignored (it holds
private steering notes) and lives under $HOME. On a machine that has no registry at
all — a CI runner, a fresh clone — there is nothing to police and the test says so
out loud rather than passing quietly.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

#: Files that must exist at exactly one place. Add to this list, never remove from it.
GUARDED = ("insights_tessera.md", "synthesis_tessera.md")

#: Every directory an agent harness might keep a project memory in. macOS is
#: case-insensitive, so ``.Codex`` and ``.codex`` are the same directory — the
#: realpath dedupe below collapses them.
ROOT_GLOBS = (".claude/projects/*/memory", ".codex/projects/*/memory")

#: ``## Insight 12`` / ``### Insight 12`` — a BARE number. Deliberately does not match
#: ``Insight 39b`` (a deliberate sub-label) nor ``Insight 100+`` (a heading that means
#: "past 100", not the number 100). Both live in the registry and are not duplicates.
INSIGHT_NUMBER = re.compile(r"^#{2,3} Insight (\d+)(?![\d+\w])", re.MULTILINE)


def _memory_roots() -> list[Path]:
    """Every memory directory on this machine, deduplicated by real path."""
    seen: dict[str, Path] = {}
    for pattern in ROOT_GLOBS:
        for path in Path.home().glob(pattern):
            if path.is_dir():
                seen.setdefault(os.path.realpath(path), path)
    return sorted(seen.values())


def _copies_of(name: str) -> list[Path]:
    """Every path serving ``name``, whether a real file or a symlink to one."""
    return [root / name for root in _memory_roots() if (root / name).exists()]


def _describe(path: Path) -> str:
    stat = path.stat()  # follows symlinks — we want the TARGET's identity
    kind = f"symlink -> {os.path.realpath(path)}" if path.is_symlink() else "REAL FILE"
    return f"{path}\n      inode={stat.st_ino}  {stat.st_size:>7} B  {kind}"


@pytest.mark.parametrize("name", GUARDED)
def test_registry_has_exactly_one_source_of_truth(name: str) -> None:
    """RULE A — every path serving a guarded registry resolves to the SAME file.

    A second real file with the same name means the registry you write is not the
    registry the next agent reads. That is how 98 insights nearly died.
    """
    copies = _copies_of(name)
    if not copies:
        pytest.skip(f"no {name} under {[str(r) for r in _memory_roots()]} — nothing to police here")

    inodes = {path.stat().st_ino for path in copies}
    assert len(inodes) == 1, (
        f"\n{name} EXISTS IN {len(inodes)} DIFFERENT FILES — the registry has split again.\n"
        f"The one you write is not the one you read. Do NOT resolve this by keeping the\n"
        f"most recent: on 2026-07-13 the bigger file was the older one, and 'keep the\n"
        f"newest' would have destroyed 98 insights.\n\n"
        f"Reconcile by CONTENT (union, renumber collisions, delete nothing), then leave\n"
        f"exactly one real file and make the others symlinks to it.\n\n"
        + "\n".join(f"    - {_describe(p)}" for p in copies)
    )


def test_no_two_insights_share_a_number() -> None:
    """RULE B — one number, one insight, inside the registry itself.

    Two agents appending "Insight 101" from two sessions is the same collision as two
    files, one level down: the number stops identifying the insight. It has happened
    three times in this registry (101-106 twice over, then 101-102 again).
    """
    copies = _copies_of("insights_tessera.md")
    if not copies:
        pytest.skip("no insights registry on this machine — nothing to police here")

    text = copies[0].read_text(encoding="utf-8")
    numbers = [int(match) for match in INSIGHT_NUMBER.findall(text)]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})

    assert not duplicates, (
        f"\nTWO INSIGHTS SHARE A NUMBER: {duplicates}\n"
        f"in {os.path.realpath(copies[0])}\n\n"
        f"A number that names two insights names neither. Renumber the YOUNGER one to the\n"
        f"tail of the registry (never the elder — old numbers are cited elsewhere) and put\n"
        f"a note under it saying where it came from. Merge nothing, delete nothing.\n"
    )
