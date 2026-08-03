"""Every Makefile target that builds no file must be declared ``.PHONY``.

Audit 2026-08-03. 18 of the repository's 71 targets were missing from ``.PHONY`` — including
``hooks``, ``land``, ``memory-check``, ``format-check`` and the whole ``eval-*`` family.

The failure mode is silence. Make treats a target name as a filename: if a file or directory
of that name exists and is newer than its prerequisites, the target is "up to date" and its
recipe **does not run**, with no error. ``install`` depends on ``hooks``; ``gate`` depends on
``install``. So a stray ``hooks/`` directory in the repository root would have stopped
installing the trunk guard, and every gate afterwards would have run — green — with the guard
uninstalled. That is precisely a witness reporting success over a hole (ADR 0026).

The risk was already known once: ``eval`` is declared phony because ``eval/`` exists on disk.
The precaution was taken for the one case somebody hit, and never generalised. This test
generalises it.

Nothing in this Makefile produces a file whose name is its target, so the rule is simply
*all of them*. If a real file-producing rule is ever added, exempt it here **by name**, with
the artefact it builds — an exemption is a place where a defect can live, so it must be one
line somebody has to write on purpose.
"""

from __future__ import annotations

import re
from pathlib import Path

_MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"

#: Targets that legitimately build the file they are named after. Empty, deliberately.
_FILE_PRODUCING: frozenset[str] = frozenset()

#: A Makefile with fewer targets than this means the parser broke, not that the file shrank.
_MIN_TARGETS = 40


def _joined_source() -> str:
    """The Makefile with line continuations resolved, as make itself reads it."""
    return _MAKEFILE.read_text(encoding="utf-8").replace("\\\n", " ")


def _declared_phony(source: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"^\.PHONY:\s*(.*)$", source, re.M):
        names.update(match.group(1).split())
    return names


def _targets(source: str) -> set[str]:
    """Rule targets, excluding variable assignments (``FOO := bar``) and special dot-targets."""
    return {
        match.group(1)
        for match in re.finditer(r"^([a-zA-Z0-9_][a-zA-Z0-9_.-]*)\s*:(?!=)", source, re.M)
    }


def test_the_parser_still_finds_the_targets() -> None:
    """Anti-vacuity: a regex that stopped matching would make every assertion below pass."""
    found = _targets(_joined_source())
    assert len(found) >= _MIN_TARGETS, (
        f"only {len(found)} targets parsed — the Makefile's shape changed and this test is "
        "now green over a hole. Fix the parser rather than lowering _MIN_TARGETS."
    )


def test_the_parser_honours_line_continuations() -> None:
    """``.PHONY`` is declared across continued lines; reading them raw hides most of the list.

    Worth pinning: the first pass of this audit read the file line by line, concluded that
    ``eval`` was unprotected, and was wrong.
    """
    source = _joined_source()
    assert "eval" in _declared_phony(source)
    assert len(_declared_phony(source)) > len(
        _declared_phony(_MAKEFILE.read_text(encoding="utf-8"))
    )


def test_every_target_is_phony() -> None:
    source = _joined_source()
    missing = sorted(_targets(source) - _declared_phony(source) - _FILE_PRODUCING)
    assert not missing, (
        "these Makefile targets are not declared .PHONY, so a file or directory of the same "
        "name makes make skip them in silence: " + ", ".join(missing)
    )


def test_phony_names_a_target_that_exists() -> None:
    """A phony name with no rule is dead text that outlives the target it once protected."""
    source = _joined_source()
    ghosts = sorted(_declared_phony(source) - _targets(source))
    assert not ghosts, (
        "declared .PHONY but no such target — remove the stale name(s): " + ", ".join(ghosts)
    )
