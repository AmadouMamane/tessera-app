"""Ratchet — a gate verdict without the identity of the tree it ran on is unfalsifiable.

2026-07-12, process **P0**. Two ``make gate`` runs returned **exit 0** on two *different trees*:
a concurrent agent stashed the working changes and switched the worktree to its own branch
between the passes. The test counts differed (1862, then 1858), nobody noticed, and it read as a
clean twice-green. CI is billing-blocked, so the local gate is this project's only witness — and
a witness that cannot say what it saw is not one.

Three invariants, and the third is the one the incident demanded:

1. **Every verdict names its tree.** The `gate` target cannot produce an exit code without going
   through the witness — asserted against the Makefile itself, because that is where a future
   author would "simplify" the wrapper away.
2. **A run whose tree MOVED is VOID, not red.** Distinct exit code (3): conflating "unusable"
   with "failed" would let a void run be read as an honest red, and vice-versa.
3. **Twice-green is two green passes ON ONE TREE**, asserted by machine. Two green passes on two
   trees are REFUSED, and the refusal says why. That is the exact false-green of 2026-07-12,
   reproduced here so it can never be green again.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from scripts.gate_witness import (
    EXIT_VOID,
    TreeIdentity,
    cmd_twice,
    describe_drift,
    fingerprint,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPO = Path(__file__).resolve().parents[2]


def _identity(**overrides: object) -> TreeIdentity:
    base = {
        "worktree": "/w/agents/claude",
        "branch": "claude/lot",
        "head": "a" * 40,
        "dirty": False,
        "dirty_files": 0,
        "digest": "d" * 64,
    }
    return TreeIdentity(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def in_a_scratch_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A real git repo, because a fingerprint that mocks git proves nothing about git."""

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "first")
    monkeypatch.chdir(tmp_path)
    yield tmp_path


class TestTheFingerprintIsTheTreeAndNotJustTheCommit:
    """A commit id is not a tree. The digest must move when the CONTENT moves."""

    def test_a_clean_tree_fingerprints_itself(self, in_a_scratch_repo: Path) -> None:
        identity = fingerprint()

        assert identity.worktree == str(in_a_scratch_repo.resolve())
        assert identity.dirty is False
        assert identity.dirty_files == 0
        assert len(identity.digest) == 64

    def test_editing_a_tracked_file_changes_the_digest(self, in_a_scratch_repo: Path) -> None:
        before = fingerprint()

        (in_a_scratch_repo / "a.txt").write_text("two\n", encoding="utf-8")
        after = fingerprint()

        assert after.digest != before.digest
        assert after.dirty is True

    def test_rewriting_a_dirty_file_in_place_still_changes_the_digest(
        self, in_a_scratch_repo: Path
    ) -> None:
        """THE case a coarser check would miss — and the exact shape of the incident.

        The stash that corrupted the witness left `M src/tessera/guard/audit.py` dirty *before
        and after*: same branch, same HEAD, same dirty-file count. A fingerprint of
        (branch, head, dirty?) would have called those two trees identical. Only hashing the
        PATCH catches 241 lines being taken away.
        """
        (in_a_scratch_repo / "a.txt").write_text("mine\n", encoding="utf-8")
        before = fingerprint()

        (in_a_scratch_repo / "a.txt").write_text("theirs\n", encoding="utf-8")
        after = fingerprint()

        assert (before.branch, before.head, before.dirty_files) == (
            after.branch,
            after.head,
            after.dirty_files,
        ), "precondition: everything a coarse check looks at is unchanged"
        assert after.digest != before.digest, (
            "the content was rewritten in place and the fingerprint did not notice — this is "
            "exactly how a stash corrupted the 2026-07-12 witness"
        )
        assert "CONTENT REWRITTEN IN PLACE" in " ".join(describe_drift(before, after))

    def test_a_branch_switch_is_named_as_such(self) -> None:
        """The refusal must name the mechanism, not just say 'the trees differ'."""
        drift = describe_drift(
            _identity(branch="claude/mine", digest="1" * 64),
            _identity(branch="claude/theirs", digest="2" * 64),
        )

        assert any("BRANCH SWITCHED" in reason for reason in drift)
        assert any("re-pointed this worktree" in reason for reason in drift)


class TestTwiceGreenIsAssertedNotRemembered:
    """Two green passes are a twice-green ONLY on one tree. This is the 2026-07-12 false green."""

    @staticmethod
    def _record(
        slot: int,
        *,
        exit_code: int,
        tree: TreeIdentity,
        void: bool = False,
        recorded_at: float | None = None,
    ) -> None:
        Path(".gate").mkdir(exist_ok=True)
        Path(f".gate/pass-{slot}.json").write_text(
            json.dumps(
                {
                    "slot": slot,
                    "gate_exit_code": exit_code,
                    "verdict_exit_code": EXIT_VOID if void else exit_code,
                    "void": void,
                    "drift": ["BRANCH SWITCHED: a → b"] if void else [],
                    "recorded_at": time.time() if recorded_at is None else recorded_at,
                    "tree_before": asdict(tree),
                    "tree_after": asdict(tree),
                }
            ),
            encoding="utf-8",
        )

    def test_two_green_passes_on_one_tree_are_a_twice_green(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        one_tree = _identity(digest="c" * 64)
        self._record(1, exit_code=0, tree=one_tree)
        self._record(2, exit_code=0, tree=one_tree)

        assert cmd_twice() == 0
        assert "TWICE-GREEN" in capsys.readouterr().out

    def test_a_leftover_slot_from_another_day_is_not_a_second_pass(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same false green, on the time axis (audit 2026-08-03).

        `make gate` alone rewrites slot 1 and `gate-twice` never clears `.gate/`. So a slot 2
        left from a previous day, on an unchanged commit and a clean tree, matched today's
        fingerprint EXACTLY — same worktree, branch, HEAD, digest — and `twice` reported
        TWICE-GREEN over a single pass that ran today. Identity was checked; simultaneity
        was not.
        """
        one_tree = _identity(digest="c" * 64)
        now = time.time()
        self._record(1, exit_code=0, tree=one_tree, recorded_at=now)
        self._record(2, exit_code=0, tree=one_tree, recorded_at=now - 26 * 3600)

        assert cmd_twice() != 0, "a slot from yesterday was accepted as today's second pass"
        err = capsys.readouterr().err
        assert "TWICE-GREEN REFUSED" in err
        assert "apart" in err, "the refusal must say WHY, not merely that it refused"

    def test_a_record_without_a_clock_is_refused_rather_than_trusted(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A pass predating this check cannot prove when it ran, so it cannot count.

        The honest answer to "I cannot tell" is a refusal, never a pass (ADR 0026).
        """
        one_tree = _identity(digest="c" * 64)
        self._record(1, exit_code=0, tree=one_tree)
        self._record(2, exit_code=0, tree=one_tree)
        stale = json.loads(Path(".gate/pass-2.json").read_text(encoding="utf-8"))
        del stale["recorded_at"]
        Path(".gate/pass-2.json").write_text(json.dumps(stale), encoding="utf-8")

        assert cmd_twice() != 0
        assert "recorded_at" in capsys.readouterr().err

    def test_two_green_passes_on_different_trees_are_refused(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """THE proof this lot exists for.

        Both passes exit 0. Both are honest. And they ran on different trees, so together they
        prove nothing — which is precisely what happened on 2026-07-12 and read as clean.
        """
        self._record(1, exit_code=0, tree=_identity(branch="claude/mine", digest="1" * 64))
        self._record(2, exit_code=0, tree=_identity(branch="claude/theirs", digest="2" * 64))

        verdict = cmd_twice()

        assert verdict != 0, "two green passes on two different trees were accepted as twice-green"
        err = capsys.readouterr().err
        assert "TWICE-GREEN REFUSED" in err
        assert "DIFFERENT TREES" in err
        assert "BRANCH SWITCHED" in err, "the refusal must say WHY, not merely that it refused"

    def test_a_void_pass_cannot_be_half_of_a_twice_green(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A run whose tree moved under it is unusable — its exit 0 describes a dead tree."""
        one_tree = _identity(digest="c" * 64)
        self._record(1, exit_code=0, tree=one_tree, void=True)
        self._record(2, exit_code=0, tree=one_tree)

        assert cmd_twice() != 0
        assert "VOID" in capsys.readouterr().err

    def test_a_missing_pass_is_refused_rather_than_assumed(
        self, in_a_scratch_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Absence of proof is not proof — the repo's own doctrine, applied to its own witness."""
        self._record(1, exit_code=0, tree=_identity())

        assert cmd_twice() != 0
        assert "no record" in capsys.readouterr().err


class TestTheGateCannotDeliverAVerdictWithoutAnIdentity:
    """The ratchet proper: the Makefile is where a future author removes the wrapper."""

    @staticmethod
    def _target(name: str) -> str:
        text = (_REPO / "Makefile").read_text(encoding="utf-8")
        match = re.search(rf"^{re.escape(name)}:.*?(?=^\S|\Z)", text, re.MULTILINE | re.DOTALL)
        assert match, f"the Makefile has no `{name}` target"
        return match.group(0)

    def test_the_gate_target_runs_through_the_witness(self) -> None:
        """A bare `gate: gate-py gate-web` restores the unfalsifiable verdict. It fails here."""
        body = self._target("gate")

        assert "gate_witness.py run" in body, (
            "`make gate` can produce an exit code without recording the tree it ran on — that "
            "verdict is unfalsifiable, which is the whole of the 2026-07-12 process P0"
        )

    def test_the_gate_target_refuses_a_worktree_it_does_not_own(self) -> None:
        body = self._target("gate")

        assert "worktree_owner.py check" in body

    def test_gate_twice_asserts_by_machine(self) -> None:
        """`gate-twice` must COMPARE the passes, not merely run the gate twice and hope."""
        body = self._target("gate-twice")

        assert "gate_witness.py twice" in body, (
            "`make gate-twice` runs the gate twice without comparing what each pass saw — that "
            "is the ritual that produced two green passes on two different trees"
        )


def test_the_witness_cli_is_runnable(in_a_scratch_repo: Path) -> None:
    """End to end, as the Makefile calls it: a real subprocess, a real tree, a real fingerprint."""
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(_REPO / "scripts" / "gate_witness.py"), "fingerprint"],
        check=False,
        capture_output=True,
        text=True,
        cwd=in_a_scratch_repo,
    )

    assert proc.returncode == 0
    assert "tree=" in proc.stdout
    assert "branch=" in proc.stdout
