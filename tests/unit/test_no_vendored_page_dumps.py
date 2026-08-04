"""The repository distributes no foreign page dump.

Two "Save page as…" captures lived under ``docs/ui-reference/`` for a month: 24 files,
36 MB of compiled Next.js/React bundles (``main-app.js``, ``webpack.js``, ``layout.css``)
plus their HTML shells. Nothing referenced them; the directory's own README declares its
purpose to be *screenshots*. They were removed on 2026-08-04, together with a screenshot
of a real bank's live customer portal and the hand-written clone of that same page.

Three witnesses were green over them the whole time:

* ``check-added-large-files`` (``--maxkb=500``) never saw a 6 MB file, because without
  ``--enforce-all`` it judges only files being **added** — a blob committed a month ago
  is invisible to it forever;
* the local quality gate runs ruff / mypy / tsc / biome / pytest, none of which look at
  ``docs/``;
* ``end-of-file-fixer`` and ``trailing-whitespace`` DID see them — and proposed to
  *reformat* minified third-party bundles, which is the wrong verb entirely.

So this is the witness that asks the right question: **what does this repository ship?**
It reads git's tracked set, not the filesystem, because an untracked scratch file harms
nobody while a tracked one is distributed to every clone.

Declared blind spot: this test judges **paths**, never pixels. It cannot tell a mockup
from a photograph of somebody's real account — the capture removed on 2026-08-04 showed
live balances and no path rule would have caught it. That judgement stays human.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

#: The signature a browser leaves when a page is saved: a sibling ``<name>_files/``
#: directory holding the page's compiled assets.
_SAVED_PAGE_DIR_SUFFIX = "_files"

#: Compiled or editor-generated assets that have no business under ``docs/``. HTML is
#: NOT here: ``docs/prototypes/*.html`` are hand-written reference prototypes.
_FORBIDDEN_DOC_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".css", ".map", ".ts", ".tsx"})

#: Editor and OS droppings, forbidden anywhere in the tracked set.
_FORBIDDEN_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def _tracked_paths() -> list[Path]:
    """Every path git distributes, or a loud failure.

    A witness that cannot see may not report "ok" (ADR 0026): if git is absent or
    refuses, this raises rather than returning an empty set that would pass every
    assertion below.
    """
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell, no user input
            ["git", "-C", str(_REPO), "ls-files", "-z"],  # noqa: S607 — git resolved from PATH
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover — no git
        pytest.fail(f"CANNOT SAY: git could not be run, so the tracked set is unknown: {exc}")
    if completed.returncode != 0:  # pragma: no cover — not a work tree
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        pytest.fail(f"CANNOT SAY: `git ls-files` exited {completed.returncode}: {stderr}")
    entries = completed.stdout.decode("utf-8", "replace").split("\0")
    paths = [Path(entry) for entry in entries if entry]
    if not paths:  # pragma: no cover — an empty repository
        pytest.fail("CANNOT SAY: git tracks no file at all, which cannot be true here")
    return paths


class TestNoForeignPageDump:
    def test_no_saved_page_asset_directory_is_tracked(self) -> None:
        dumps = sorted(
            str(path)
            for path in _tracked_paths()
            if any(part.endswith(_SAVED_PAGE_DIR_SUFFIX) for part in path.parts[:-1])
        )
        assert not dumps, (
            "a browser's 'Save page as…' dump is tracked again — these are compiled "
            f"bundles, not documentation: {dumps[:5]} ({len(dumps)} files)"
        )

    def test_docs_carry_no_compiled_asset(self) -> None:
        compiled = sorted(
            str(path)
            for path in _tracked_paths()
            if path.parts[:1] == ("docs",) and path.suffix in _FORBIDDEN_DOC_SUFFIXES
        )
        assert (
            not compiled
        ), f"docs/ ships compiled or source assets, which belong in the app: {compiled}"

    def test_no_editor_or_os_droppings_are_tracked(self) -> None:
        droppings = sorted(str(path) for path in _tracked_paths() if path.name in _FORBIDDEN_NAMES)
        assert not droppings, f"OS/editor droppings are tracked: {droppings}"


class TestTheWitnessCanActuallySee:
    """The three assertions above pass on an empty list. Prove the list is not empty."""

    def test_it_reads_a_populated_tracked_set(self) -> None:
        paths = _tracked_paths()
        assert len(paths) > 100, f"only {len(paths)} tracked paths — the reader is broken"
        assert Path("pyproject.toml") in paths, "the tracked set lacks pyproject.toml"

    def test_it_would_catch_a_dump(self) -> None:
        """The rule matches the shape that was actually removed."""
        removed = Path("docs/ui-reference/header/Métier — Tessera_files/main-app.js")
        assert any(part.endswith(_SAVED_PAGE_DIR_SUFFIX) for part in removed.parts[:-1])
        assert removed.suffix in _FORBIDDEN_DOC_SUFFIXES
