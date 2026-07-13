"""The gate must be able to SEE before it may say anything — including about itself.

`make gate` and `make claim` open by asking `scripts/main_guard.py` whether the trunk is guarded.
**That question cannot be ASKED when the tool that asks it is not in the checkout** — and on
2026-07-13 it was not. The hook was installed into the common `.git/hooks/`; its tool lived on a
branch that had not landed. So the guard refused *every* advance of `main`, including the one
branch that carried the tool. A **bootstrap lock**, and it took a written derogation to break.

The gate did refuse in that state. That is not the bug. The bug is *how*:

    .venv/bin/python3: can't open file '.../scripts/main_guard.py': [Errno 2] No such file
    make: *** [gate] Error 2

**A refusal that is right by accident.** Non-zero — but it publishes no verdict, names no
condition, and offers no command that repairs it. ADR 0026 requires a witness that cannot see to
report a *blind spot*; it may never report "ok", and it may not report gibberish either, because
gibberish is how a blind spot gets mistaken for noise. A red nobody can act on is a red people
learn to ignore, and a false red is the same disease as a false green.

These tests are the ratchet, and they are **mutation tests**: each one takes the tooling away and
demands a named refusal with the exact repair. A ratchet nobody has seen bite is not a ratchet —
this repository has already shipped one that was green under its own mutation.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT: Final = Path(__file__).resolve().parents[2]
_MAKEFILE: Final = _ROOT / "Makefile"

#: The two tools `gate` and `claim` invoke before they are entitled to judge anything.
_TOOLS: Final = ("scripts/main_guard.py", "scripts/worktree_owner.py")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603  literal argv, hermetic temp repo
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_tooling(repo: Path) -> subprocess.CompletedProcess[str]:
    """Run the real `tooling` recipe in a throwaway repo. Its exit code is its verdict."""
    return subprocess.run(  # noqa: S603  literal argv, hermetic temp repo
        ["make", "tooling"],  # noqa: S607
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A git repo carrying the REAL Makefile, one commit deep, with the tooling all present.

    Everything the recipe consults is here: the two scripts, and an executable `.venv/bin/python`.
    Each test then takes exactly one of them away. The scripts' *contents* are irrelevant — the
    recipe asks whether the file is readable, never what it says.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")

    (root / "Makefile").write_text(_MAKEFILE.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "scripts").mkdir()
    for tool in _TOOLS:
        (root / tool).write_text("# stub\n", encoding="utf-8")

    _git(root, "add", "Makefile", *_TOOLS)
    _git(root, "commit", "-m", "base")

    venv = root / ".venv" / "bin"
    venv.mkdir(parents=True)
    python = venv / "python"
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)

    yield root


class TestTheGateRefusesWhenItsOwnToolIsMissing:
    """The mutation that matters: take the guard's tool away and demand a NAMED refusal."""

    def test_all_tooling_present_is_a_pass(self, repo: Path) -> None:
        """The control. Without this, every red below could be red for an unrelated reason."""
        result = _make_tooling(repo)

        assert result.returncode == 0, (
            f"`make tooling` refused a complete checkout — every mutation below is then red for "
            f"the wrong reason and proves nothing.\n{result.stdout}\n{result.stderr}"
        )

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_a_tool_absent_from_the_branch_is_cannot_say_and_names_the_rebase(
        self, repo: Path, tool: str
    ) -> None:
        """THE BOOTSTRAP LOCK OF 2026-07-13, in its exact shape: the branch does not carry it.

        The hook is installed and its tool is on an unlanded branch, so the guard refuses every
        advance of the trunk — *including the branch that would fix it*. The one thing the operator
        needs is the command that gets the tool into this checkout. It must be printed.
        """
        _git(repo, "rm", "-q", tool)
        _git(repo, "commit", "-m", f"drop {tool}")

        result = _make_tooling(repo)
        out = result.stdout + result.stderr

        assert result.returncode == 2, (
            f"the tool is gone and `make tooling` exited {result.returncode}. A gate that cannot "
            f"check the trunk MUST NOT return 0, and 2 is the CannotSay code.\n{out}"
        )
        assert "CANNOT SAY" in out, (
            f"it refused without a verdict. `python3: can't open file` is a refusal that is RIGHT "
            f"BY ACCIDENT — that is the bug this ratchet exists for.\n{out}"
        )
        assert tool in out, f"it refused without naming the missing tool.\n{out}"
        assert "rebase" in out, (
            f"it named no repair. A red nobody can act on is a red people learn to ignore.\n{out}"
        )

    def test_a_tool_deleted_from_the_worktree_names_the_restore_not_the_rebase(
        self, repo: Path
    ) -> None:
        """Tracked at HEAD but gone from disk is a DIFFERENT illness, and gets a different cure.

        Telling someone to rebase when they merely deleted a file is a wrong instruction dressed as
        a helpful one — and it is the class of bug this project keeps paying for: an answer to the
        neighbouring question.
        """
        (repo / "scripts" / "main_guard.py").unlink()

        result = _make_tooling(repo)
        out = result.stdout + result.stderr

        assert result.returncode == 2, out
        assert "CANNOT SAY" in out, out
        assert "git checkout --" in out, (
            f"the file is tracked at HEAD — it was deleted, not absent from the branch. The repair "
            f"is a restore, and the recipe must say THAT.\n{out}"
        )

    def test_a_missing_interpreter_is_cannot_say_and_names_make_install(self, repo: Path) -> None:
        """The hook runs `.venv/bin/python` and no other: macOS's system python3 is 3.9.

        Falling back to it put an ImportError traceback where a verdict belonged — a red that is
        unreadable, and therefore a red people learn to ignore.
        """
        (repo / ".venv" / "bin" / "python").unlink()

        result = _make_tooling(repo)
        out = result.stdout + result.stderr

        assert result.returncode == 2, out
        assert "CANNOT SAY" in out, out
        assert ".venv/bin/python" in out, out
        assert "make install" in out, f"it named no repair.\n{out}"

    def test_a_non_executable_interpreter_is_refused(self, repo: Path) -> None:
        """Present is not the same as runnable. `-x`, never `-f`."""
        (repo / ".venv" / "bin" / "python").chmod(0o644)

        result = _make_tooling(repo)

        assert result.returncode == 2, (
            "a non-executable interpreter passed. The hook would fail to run the guard, and the "
            "trunk would be advanced by a witness that never spoke.\n" + result.stdout
        )


class TestTheCheckCannotBeOrphaned:
    """A check `gate` does not run is a decoration. This is asserted structurally, in the Makefile.

    The behavioural tests above prove the recipe refuses. They say nothing about whether anybody
    CALLS it — and an uninstalled witness refuses nothing. That gap is exactly how `.githooks/`
    guarded every worktree except the one where the trunk lives.
    """

    @pytest.mark.parametrize("target", ["gate", "claim"])
    def test_the_gate_and_claim_both_depend_on_tooling(self, target: str) -> None:
        text = _MAKEFILE.read_text(encoding="utf-8")
        match = re.search(rf"^{target}:(?P<deps>[^\n]*)$", text, re.MULTILINE)

        assert match is not None, f"`{target}` is not a target in the Makefile any more."
        assert "tooling" in match.group("deps").split(), (
            f"`{target}` no longer runs `tooling`, so it will once again meet a missing guard with "
            f"`python3: can't open file` instead of a verdict. Restore: `{target}: tooling`."
        )
