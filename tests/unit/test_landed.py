"""Ratchet — `make landed` answers by CONTENT. If it ever consults the graph, this file goes red.

Ratified doctrine, 2026-07-12: **sha ancestry is not landing.**

`git merge-base --is-ancestor` answers *"is this SHA in main's history?"*. Nobody asks that. The
question is *"is this WORK on main?"*, and the two diverge the instant a lane rebases or
re-implements another's commits — routine here.

The trap is perfect, and it cost a live P1: six of a branch's seven commits had landed under
**different shas**, the seventh (the GDPR erasure's author) had not, and `--is-ancestor` returned
"not merged" for **all seven**. Its answer looked like an answer while hiding exactly which one
was missing. The erasure stayed anonymous on main for a day.

So the tool must be structurally incapable of taking that shortcut, and this file is what makes
that structural rather than a promise:

1. `landed.py` must not invoke `--is-ancestor` / `merge-base --is-ancestor` at all — asserted on
   the source, because the shortcut is *tempting*: it is one call and it is almost always right.
2. It must actually catch a replayed commit — the real scenario, reproduced in a scratch repo:
   identical content, different sha. Ancestry says "not merged"; the truth is "landed".
3. It must catch the inverse — the file that did NOT land — which is the failure that cost us
   the P1 and the only reason the tool exists.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from scripts.landed import EXIT_NOT_LANDED, classify, main, touched_files

if TYPE_CHECKING:
    from collections.abc import Iterator

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "landed.py"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def replayed_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The exact shape of the incident, in a real repo.

    `main` carries the branch's work **replayed under a different sha** — except for one file,
    which never made it. Ancestry will call the whole branch "unmerged" and tell you nothing
    about which file is the gap. Content will name it.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "branch", "-M", "main")

    # The branch: two files.
    _git(tmp_path, "checkout", "-qb", "lane")
    (tmp_path / "landed.txt").write_text("the work that got replayed\n", encoding="utf-8")
    (tmp_path / "orphan.txt").write_text("the seventh commit\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "lane work")

    # main REPLAYS one of them under a different sha, and drops the other on the floor.
    _git(tmp_path, "checkout", "-q", "main")
    (tmp_path / "landed.txt").write_text("the work that got replayed\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "same content, different sha")

    monkeypatch.chdir(tmp_path)
    yield tmp_path


class TestTheToolCannotTakeTheShortcut:
    """The shortcut is one call and it is almost always right. That is what makes it dangerous."""

    def test_landed_py_never_asks_the_graph_whether_work_landed(self) -> None:
        """Walked with `ast`, ignoring docstrings — the tool's own prose QUOTES the trap.

        A line-grep flags the module docstring, which explains why `--is-ancestor` is banned.
        Silencing that with a noqa would be the second mistake, and a ratchet you are trained to
        silence polices nothing. So the check reads the code and not the commentary: it looks for
        the string as an *executed* value, which is the only way it could reach git.
        """
        tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
        docstrings = {
            id(ast.get_docstring(node, clean=False))
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        }
        prose = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }

        offending = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node not in prose
            and id(node.value) not in docstrings
            and ("--is-ancestor" in node.value or "merge-base" in node.value)
        ]

        assert not offending, (
            f"landed.py executes {offending} — it consults ancestry. `--is-ancestor` answers 'is "
            "this SHA in main's history', not 'is this WORK on main', and when a lane replays a "
            "commit the two disagree. Its answer LOOKS like an answer, which is what made it cost "
            "a P1. Compare blobs."
        )

    def test_the_incident_itself_would_have_been_caught(self, replayed_history: Path) -> None:
        """Ancestry says 'unmerged' about everything; content names the one file that is missing."""
        ancestry = subprocess.run(  # noqa: S603
            ["git", "merge-base", "--is-ancestor", "lane", "main"],  # noqa: S607
            cwd=replayed_history,
            check=False,
            capture_output=True,
        )
        assert ancestry.returncode != 0, "precondition: the graph calls this branch unmerged"

        verdicts = {p: classify("main", "lane", p) for p in touched_files("main", "lane")}

        assert verdicts["landed.txt"] == "LANDED", (
            "a commit replayed under a different sha has landed — its CONTENT is on main. "
            "Ancestry cannot see that, and this tool exists because of it."
        )
        assert verdicts["orphan.txt"] == "MISSING", (
            "the file that never made it is the whole point: ancestry said 'unmerged' about all "
            "of them, which hid exactly which one was the gap"
        )


class TestTheVerdicts:
    """Three verdicts, and DIVERGED is the honest one — it must never be counted as landed."""

    def test_a_file_the_base_changed_is_diverged_not_landed(self, replayed_history: Path) -> None:
        _git(replayed_history, "checkout", "-q", "main")
        (replayed_history / "landed.txt").write_text("main moved on\n", encoding="utf-8")
        _git(replayed_history, "add", "-A")
        _git(replayed_history, "commit", "-qm", "main edits it further")

        assert classify("main", "lane", "landed.txt") == "DIVERGED", (
            "the base has the file with other content — that is not 'landed'. It is 'I cannot "
            "tell you'. Silently calling it landed is how a branch gets deleted with work in it."
        )

    def test_the_exit_code_says_work_is_missing(self, replayed_history: Path) -> None:
        """Exit 4, not 1: a Makefile must tell 'work is missing' from 'the tool broke'."""
        assert main(["--branch", "lane", "--base", "main"]) == EXIT_NOT_LANDED

    def test_a_fully_landed_branch_exits_zero(self, replayed_history: Path) -> None:
        _git(replayed_history, "checkout", "-q", "main")
        (replayed_history / "orphan.txt").write_text("the seventh commit\n", encoding="utf-8")
        _git(replayed_history, "add", "-A")
        _git(replayed_history, "commit", "-qm", "the gap, closed")

        assert main(["--branch", "lane", "--base", "main"]) == 0


def test_the_cli_runs(replayed_history: Path) -> None:
    """As the Makefile calls it — a real subprocess, a real repo, a real verdict."""
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(_SCRIPT), "--branch", "lane", "--base", "main"],
        check=False,
        capture_output=True,
        text=True,
        cwd=replayed_history,
    )

    assert proc.returncode == EXIT_NOT_LANDED
    assert "MISSING" in proc.stdout
    assert "orphan.txt" in proc.stdout
