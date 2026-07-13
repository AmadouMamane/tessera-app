"""Ratchets (a) and (b) — a ROLE is not a WRITER, and a tool that cannot tell you apart says so.

The incident, 2026-07-13. `agents/claude/` is one worktree. **Seven** live Claude sessions had
their working directory in it. `make claim` resolved an agent's identity like this:

    def whoami() -> str:
        "This agent's name: TESSERA_AGENT, else THE WORKTREE'S DIRECTORY NAME."

So all seven resolved to the owner `"claude"`. Each read the marker, **found its own name in it,
and concluded it was home.** The marker refused nobody; it had never been able to. One of those
sessions then wrote eleven files into the tree while another's gate was running — the gate voided
correctly (that witness worked), and `make claim`, the tool built for exactly this, said nothing.

It was measuring the neighbourhood: the *directory* is adjacent to the *writer*, and the adjacency
held right up until the moment two writers shared a directory. ADR 0026's fourth instance, inside
the instrument built to police its third.

Every test below runs against a REAL git repo in a tmp dir whose leaf is named `claude`, so the
old fallback would still resolve to the same role it always did. That is the point: the role is
identical in every one of these tests, and the tool refuses anyway.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from scripts.worktree_owner import (
    MARKER,
    ROLE_ENV,
    SESSION_ENV,
    SESSION_PID_ENV,
    check,
    claim,
    main,
    read_owner,
    release,
    role,
)

from tessera.verdict import EXIT_REFUSED, CannotSay, NotOk, Ok, exit_code

if TYPE_CHECKING:
    from pathlib import Path

_SESSION_A = "3797cfdf-afc0-419f-8584-60ca6fc9e4e5"
_SESSION_B = "9f2c1a04-77bd-4e15-b0aa-2e5c1d9f3311"


@pytest.fixture
def lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git worktree at `…/agents/claude` — the incident's own shape, in a tmp dir.

    A real repo, not a stub: `_worktree_root()` shells out to `git rev-parse --show-toplevel`, and
    a test that faked that away would be testing a mock instead of the thing (ADR 0026).
    """
    tree = tmp_path / "agents" / "claude"
    tree.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=tree, check=True)  # noqa: S603, S607
    monkeypatch.chdir(tree)
    for var in (SESSION_ENV, SESSION_PID_ENV, ROLE_ENV):
        monkeypatch.delenv(var, raising=False)
    return tree


def _become(monkeypatch: pytest.MonkeyPatch, session: str, *, pid: int | None = None) -> None:
    """Assert an identity, the way a session does: by declaring it."""
    monkeypatch.setenv(SESSION_ENV, session)
    if pid is None:
        monkeypatch.delenv(SESSION_PID_ENV, raising=False)
    else:
        monkeypatch.setenv(SESSION_PID_ENV, str(pid))


class TestTheRoleIsNotTheWriter:
    """RATCHET (a) — two sessions, one role, one tree: the second is REFUSED, and names the first.

    The role is IDENTICAL in every test below. That is the point of every test below.
    """

    def test_the_second_session_in_the_same_lane_is_refused(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The incident, reproduced. Before this fix, BOTH sessions were told they were home.

        Mutation: make `check()` compare `role()` instead of `session_id()`. Both sessions resolve
        to `'claude'`, both get an Ok, and this goes red — which is precisely the state the repo
        shipped in, green, for a day.
        """
        _become(monkeypatch, _SESSION_A)
        assert isinstance(claim(force=False), Ok)
        assert role() == "claude", "the fixture must reproduce the lane, or it proves nothing"

        _become(monkeypatch, _SESSION_B)
        assert role() == "claude", "SAME ROLE — that is the whole point of this test"

        verdict = check()

        assert isinstance(verdict, NotOk), (
            "a second Claude session in agents/claude was told the tree was ITS OWN. This is the "
            "2026-07-13 incident, and it is green again."
        )
        assert _SESSION_A in verdict.reason, "the refusal must NAME who holds the tree"
        assert exit_code(verdict) == EXIT_REFUSED

    def test_the_second_session_cannot_claim_it_either(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`claim` must refuse too — a silent overwrite is how the first incident started."""
        _become(monkeypatch, _SESSION_A)
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        verdict = claim(force=False)

        assert isinstance(verdict, NotOk)
        assert _SESSION_A in verdict.reason
        holder = read_owner()
        assert holder is not None
        assert holder.session_id == _SESSION_A, "the refused claim OVERWROTE the marker anyway"

    def test_the_same_session_is_still_at_home(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fix must not lock a session out of its own tree: `check` twice is not a collision."""
        _become(monkeypatch, _SESSION_A)
        claim(force=False)

        verdict = check()

        assert isinstance(verdict, Ok)
        assert _SESSION_A in verdict.evidence

    def test_force_takes_the_tree_and_says_so(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Taking a tree is a DECISION. It is allowed, and it is never silent."""
        _become(monkeypatch, _SESSION_A)
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        verdict = claim(force=True)

        assert isinstance(verdict, Ok)
        assert "TAKEN by --force" in verdict.evidence
        assert _SESSION_A in verdict.evidence, "the eviction must name who was evicted"
        holder = read_owner()
        assert holder is not None
        assert holder.session_id == _SESSION_B

    def test_a_session_cannot_release_another_sessions_claim(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _become(monkeypatch, _SESSION_A)
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        verdict = release()

        assert isinstance(verdict, NotOk)
        assert (lane / MARKER).exists(), "another session's claim was released out from under it"


class TestAWitnessThatCannotSeeReportsABlindSpot:
    """RATCHET (b) — no session identity ⇒ CANNOT SAY ⇒ exit 2. Never "you are home"."""

    def test_an_unclaimed_tree_is_not_a_free_pass_to_an_anonymous_caller(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**The sentence that was wrong.** The old code said, on an unclaimed tree:

            "[worktree] … is unclaimed — proceeding as 'claude'"   → exit 0

        It could not tell who the caller was, and it let them through *while naming them*. That is
        a confident answer to a question nobody could answer. It is a blind spot, and blind spots
        do not get to pass.

        Mutation: return `Ok(...)` when `session_id()` is None. Red here, instantly.
        """
        verdict = check()

        assert isinstance(verdict, CannotSay), (
            "an anonymous caller was told an unclaimed tree was fine to work in — which is how "
            "seven sessions each believed they were the only writer"
        )
        assert exit_code(verdict) == EXIT_REFUSED
        assert SESSION_ENV in verdict.blind_spot, "the blind spot must say how to fix it"

    def test_no_verdict_to_an_anonymous_caller_is_ever_an_ok(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Across every command and every state of the tree: an unidentified caller never gets 0."""
        _become(monkeypatch, _SESSION_A)
        claim(force=False)
        monkeypatch.delenv(SESSION_ENV)

        for verdict in (check(), claim(force=False), claim(force=True), release()):
            assert isinstance(verdict, CannotSay), f"{verdict!r} let an anonymous caller through"
            assert exit_code(verdict) == EXIT_REFUSED

        assert (lane / MARKER).exists(), "an anonymous caller destroyed a live claim"

    def test_the_cli_exit_code_is_the_verdict(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Makefile reads an EXIT CODE, so the exit code is what must be asserted (ADR 0026).

        A green function returning a nice object, wired to a CLI that exits 0 anyway, is precisely
        the shape of the bugs this whole lot is about.
        """
        assert main(["check"]) == EXIT_REFUSED, "anonymous `make whoowns` exited 0"

        _become(monkeypatch, _SESSION_A)
        assert main(["claim"]) == 0
        assert main(["check"]) == 0

        _become(monkeypatch, _SESSION_B)
        assert main(["check"]) == EXIT_REFUSED, "`make gate` proceeded in another session's tree"

    def test_a_legacy_marker_names_a_role_and_therefore_says_nothing(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The markers already on disk — `{"agent": "claude", …}` — cannot identify a writer.

        Upgrading them silently ("it says claude, I am claude, it's mine") would re-enact the bug
        during the very migration that fixes it. It is a blind spot, and it is named as one.
        """
        (lane / MARKER).write_text(
            json.dumps(
                {"agent": "claude", "pid": 98111, "claimed_at": "2026-07-13T09:56:44+00:00"}
            ),
            encoding="utf-8",
        )
        _become(monkeypatch, _SESSION_A)

        verdict = check()

        assert isinstance(verdict, CannotSay)
        assert "role" in verdict.blind_spot
        assert "FORCE=1" in verdict.blind_spot, "a blind spot must say how to get out of it"


class TestTheMarkerRecordsFactsAndNotFabrications:
    """The fifth instance, hiding in the same file: the pid it recorded was ALWAYS dead."""

    def test_the_marker_never_records_the_pid_of_the_process_that_wrote_it(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The old marker stored `os.getpid()` — the pid of the ephemeral `claim` subprocess.

        That process exits within a second. So the field was a liveness signal **guaranteed to be
        false**, and any staleness check built on it would have declared every tree abandoned. The
        session's pid is a fact only the session has; if it does not declare one, we say `None`.
        `None` is an answer (ADR 0024). A number we made up is not.
        """
        _become(monkeypatch, _SESSION_A)  # declares no pid

        claim(force=False)

        record = json.loads((lane / MARKER).read_text(encoding="utf-8"))
        assert record["pid"] is None, (
            "the marker invented a pid the session never declared — and the only pid available "
            "here is this subprocess's, which is dead the moment the claim is written"
        )
        assert record["pid"] != os.getpid()

    def test_a_declared_pid_is_recorded_and_its_liveness_is_reported(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A session that names its pid gets liveness in the refusal: the --force cue."""
        _become(monkeypatch, _SESSION_A, pid=os.getpid())  # a pid that IS alive: our own
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        verdict = check()

        assert isinstance(verdict, NotOk)
        assert "is ALIVE" in verdict.reason

    def test_a_dead_owner_is_a_fact_to_state_not_a_tree_to_seize(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale marker is STATED, never silently overwritten. Advisory — but an honest one.

        The tool does not decide that a dead pid means an abandoned tree (pids are recycled, and a
        session can outlive the shell it named). It puts the facts in front of the human and names
        the one command that takes the tree.
        """
        _become(monkeypatch, _SESSION_A, pid=_a_dead_pid())
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        verdict = check()

        assert isinstance(verdict, NotOk)
        assert "is GONE" in verdict.reason, "a dead owner must be reported as dead"
        assert "FORCE=1" in verdict.reason, "…and the way to take the tree must be named"
        holder = read_owner()
        assert holder is not None
        assert holder.session_id == _SESSION_A, "a stale marker was seized without being asked"

    def test_the_role_is_recorded_for_the_human_and_decides_nothing(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The role stays in the marker — an operator must still see WHICH LANE holds the tree."""
        _become(monkeypatch, _SESSION_A)
        claim(force=False)

        record = json.loads((lane / MARKER).read_text(encoding="utf-8"))
        assert record["role"] == "claude", "the human-facing lane was dropped"
        assert record["session_id"] == _SESSION_A
        assert "agent" not in record, "the old key that conflated role and identity must be gone"

    def test_a_declared_role_does_not_buy_you_another_sessions_tree(
        self, lane: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting TESSERA_AGENT to the holder's role must not get you in. The role is not a key."""
        _become(monkeypatch, _SESSION_A)
        monkeypatch.setenv(ROLE_ENV, "claude")
        claim(force=False)

        _become(monkeypatch, _SESSION_B)
        monkeypatch.setenv(ROLE_ENV, "claude")  # same lane, deliberately

        assert isinstance(check(), NotOk), "impersonating the ROLE opened another session's tree"


def _a_dead_pid() -> int:
    """A pid that has certainly exited: spawn a process and wait for it."""
    proc = subprocess.Popen(["true"])  # noqa: S603, S607
    proc.wait()
    return proc.pid
