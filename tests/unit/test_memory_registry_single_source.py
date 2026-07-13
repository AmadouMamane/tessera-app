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

#: An insight heading, in **either** convention the registry actually uses:
#:
#:     ## Insight 12          ← 139 headings
#:     ### 12. Some Title     ←  60 headings
#:
#: The second was invisible here until 2026-07-13, and that is the whole story of this constant.
#: The old pattern required the literal word ``Insight``, so it read 139 of the registry's 199
#: headings and reported on "the registry" — while ``### 2.`` named two different insights in
#: the 30% it could not see. Green, for as long as this ratchet has existed. It was a witness
#: interrogating the *neighbourhood* of the thing it claimed to police (ADR 0026/0027), and the
#: first thing it did once it could see was find 58 collisions.
#:
#: Still deliberately excluded, and not duplicates: ``Insight 39b`` (a sub-label) and
#: ``Insight 100+`` (a section heading meaning "past 100"). Hence ``+`` and ``\w`` in the
#: lookahead.
INSIGHT_NUMBER = re.compile(r"^#{2,3} (?:Insight )?(\d+)(?![\d+\w])", re.MULTILINE)

#: **The debt.** Numbers that already name more than one insight, because two numbering
#: conventions grew side by side for months and nothing read both. 58 of them — and ``2`` names
#: *three*.
#:
#: They are NOT renumbered here. An insight's number is cited from other insights, from
#: `synthesis_tessera.md`, and from commit messages; CLAUDE.md's own rule is *never renumber an
#: existing insight*. So the damage is frozen, counted, and made unable to grow — exactly like
#: `OWED_BOOL_VERDICTS` and `OWED_COUNT`. A number that names two insights names neither, and what a
#: ratchet can still guarantee is that **no new one is born.**
#:
#: This may only go DOWN — by renumbering the YOUNGER insight of a pair to the tail of the
#: registry and leaving a note under it saying where it came from.
_FROZEN_COLLISIONS: frozenset[int] = frozenset(
    {1, 2, *range(4, 60)}  # 1, 2, and 4..59 — every number below 60 except 3
)


#: The registry has TWO conventions, so "the highest number" is not what the headings that look
#: like yours say. An agent counting only `### N.` would have answered 60 — and `## Insight 60`
#: was already taken. That is not hypothetical: it happened, to me, while fixing this ratchet.
def next_free_number(text: str) -> int:
    """One past the highest number ANY heading uses, in EITHER convention."""
    numbers = [int(match) for match in INSIGHT_NUMBER.findall(text)]
    return max(numbers, default=0) + 1


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


def _collisions() -> tuple[list[int], str]:
    """Numbers naming more than one insight, and the registry's real path."""
    copies = _copies_of("insights_tessera.md")
    if not copies:
        pytest.skip("no insights registry on this machine — nothing to police here")
    text = copies[0].read_text(encoding="utf-8")
    numbers = [int(match) for match in INSIGHT_NUMBER.findall(text)]
    return sorted({n for n in numbers if numbers.count(n) > 1}), os.path.realpath(copies[0])


def test_no_new_insight_number_collision() -> None:
    """RULE B — one number, one insight. The 58 already broken are frozen; a 59th is RED.

    Two agents appending "Insight 101" from two sessions is the same bomb as two files, one
    level down: the number stops identifying the insight.

    And the clause this ratchet could not enforce, until 2026-07-13, is the one it exists for.
    It read only `## Insight N` headings — 139 of the registry's 199 — so it policed 70% of the
    file and said "ok" about all of it, while `### 2.` named two different insights in the part
    it could not see.
    """
    collisions, path = _collisions()
    new = sorted(set(collisions) - _FROZEN_COLLISIONS)

    assert not new, (
        f"\nA NEW NUMBER NAMES TWO INSIGHTS: {new}\nin {path}\n\n"
        f"A number that names two insights names neither.\n\n"
        f"  · Take the next number from the WHOLE file, not from the headings that look like\n"
        f"    yours. The registry uses TWO conventions (`## Insight N` and `### N. Title`), and\n"
        f"    counting only one of them is exactly how this happened. The next free number is\n"
        f"    `next_free_number()` — today {_next_free()}.\n"
        f"  · Renumber the YOUNGER insight. Never the elder: old numbers are cited from other\n"
        f"    insights, from synthesis_tessera.md, and from commit messages.\n"
        f"  · Merge nothing. Delete nothing.\n"
    )


def test_the_collision_debt_only_goes_down() -> None:
    """A resolved collision must LEAVE the frozen set, or the number stops meaning anything.

    The same two-sided freeze as `OWED_BOOL_VERDICTS`: it may shrink, never grow. A debt that is
    paid and still reported as owed is a number nobody trusts, and an untrusted number is not a
    ratchet — it is a decoration with an integer in it.

    It is also what makes the ratchet unable to go quietly blind again. Narrow the pattern back
    to the literal `Insight ` and this test goes RED — it would see zero collisions and report
    all 58 as resolved. A witness that stops seeing now says so.
    """
    collisions, _ = _collisions()
    fixed = sorted(_FROZEN_COLLISIONS - set(collisions))

    assert not fixed, (
        f"\ncollision(s) {fixed} are RESOLVED — excellent. Remove them from _FROZEN_COLLISIONS\n"
        f"so the debt shrinks ON THE RECORD. It currently stands at {len(_FROZEN_COLLISIONS)}.\n"
    )


def _next_free() -> int:
    copies = _copies_of("insights_tessera.md")
    return next_free_number(copies[0].read_text(encoding="utf-8")) if copies else 1
