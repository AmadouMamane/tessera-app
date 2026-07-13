"""The trunk guard — and the one test that separates it from a guard that would have failed.

On 2026-07-13 `main` forked. Both lanes were, at every moment, *doing the right thing*: each
advanced `main` by an ordinary fast-forward from a base it believed was current. The belief came
from `refs/remotes/origin/main` — **a local cache of a remote fact** — and the cache was stale in
exactly the way that mattered, in both lanes, at once.

A guard that reads that cached ref would have said "all clear" to both. Twice. With composure.

So the test that matters here is not "does it refuse a fork" — any implementation refuses a fork it
can see. It is **`test_a_stale_cache_does_not_fool_it`**: the remote is advanced, the cache is left
untouched (*no fetch* — the fetch is the event that did not happen), and the guard must still
refuse. That test is red for a guard that asks the neighbourhood and green only for one that asks
the thing (ADR 0026).

Everything here is hermetic: the "remote" is a bare repository on disk, and `git ls-remote` speaks
to a path exactly as it speaks to a URL. No network, and therefore no reason to ever skip it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from scripts import main_guard

from tessera.verdict import EXIT_OK, CannotSay, NotOk, Ok, exit_code, render

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT = Path(__file__).resolve().parents[2]
_HOOK = _ROOT / ".githooks" / "reference-transaction"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # S603/S607: the subject of this file IS git, and the repositories are hermetic temp dirs
    # built by this module. There is no untrusted input here, and no way to test a git hook
    # without running git.
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607  `git` from PATH, as every other caller in this repo does
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(cwd: Path, lane: str, message: str) -> str:
    """One file per lane — two lanes editing one file is a *content* conflict, and this file is
    about a *history* conflict. Conflating them would make the fixture prove the wrong thing.
    """
    (cwd / f"{lane}.txt").write_text(message, encoding="utf-8")
    _git(cwd, "add", f"{lane}.txt")
    _git(cwd, "commit", "-m", message)
    return _git(cwd, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def forked(tmp_path: Path) -> Iterator[dict[str, Path | str]]:
    """The incident, rebuilt from nothing.

    A bare "remote"; two clones. One of them pushes — so the remote's `main` moves. The other
    never fetches, and therefore still believes the remote is where it was. That second clone is
    every agent in this repository on 2026-07-13.
    """
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))

    # The first clone establishes the base and pushes it.
    them = tmp_path / "them"
    _git(tmp_path, "clone", str(remote), str(them))
    _git(them, "config", "user.email", "them@test")
    _git(them, "config", "user.name", "Them")
    base = _commit(them, "base", "base")
    _git(them, "push", "origin", "main")

    # The second clone takes the base — and from here on it is looking at a photograph.
    us = tmp_path / "us"
    _git(tmp_path, "clone", str(remote), str(us))
    _git(us, "config", "user.email", "us@test")
    _git(us, "config", "user.name", "Us")

    # The other lane lands work on the remote. WE DO NOT FETCH. This is the whole incident.
    theirs = _commit(them, "their-lane", "their lane")
    _git(them, "push", "origin", "main")

    # Our lane builds its own work on the base, in a branch, exactly as the convention prescribes.
    _git(us, "checkout", "-b", "our-lane")
    ours = _commit(us, "our-lane", "our lane")
    _git(us, "checkout", "main")

    yield {"remote": remote, "us": us, "base": base, "theirs": theirs, "ours": ours}


class TestItAsksTheRemoteNotTheRefNamedAfterIt:
    """The one that would have caught it. Everything else is bookkeeping."""

    def test_a_stale_cache_does_not_fool_it(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The remote has moved. The cache has not. **No fetch.** The guard must still refuse.

        This is the test. A guard that consults `refs/remotes/origin/main` passes it happily — the
        cached ref still points at the base, the base *is* an ancestor of our work, and everything
        looks fine. It looked fine on 2026-07-13 too, to both lanes, simultaneously.

        The discriminator is not merely "did it refuse". It is: **the verdict names a sha the stale
        cache has never seen.** A guard reading the cache is *incapable* of printing that sha —
        which makes this assertion something a wrong implementation cannot fake, rather than
        something it merely fails.

        Mutation: change `remote_trunk()` to read `refs/remotes/origin/main`. Green everywhere else
        in this file, red here. That asymmetry is the whole module.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)

        # The cache still says "base" — we never fetched, exactly like the incident.
        cached = _git(us, "rev-parse", "refs/remotes/origin/main").stdout.strip()
        assert cached == forked["base"], "the fixture is wrong: the cache should be stale here"

        verdict = main_guard.check_advance(str(forked["ours"]))

        assert not isinstance(verdict, Ok), (
            "the guard was FOOLED BY A STALE CACHED REF — the incident, verbatim. It must ask the "
            "REMOTE (`git ls-remote`), never the local photograph of it."
        )
        assert exit_code(verdict) != EXIT_OK

        theirs = str(forked["theirs"])
        assert theirs[:12] in render(verdict), (
            "the refusal does not name the remote's ACTUAL tip. A guard that read the cached ref "
            "could not possibly print this sha — so this assertion is what proves the guard went "
            "to the remote and did not merely happen to be right."
        )

    def test_it_names_how_far_behind_you_are(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Having fetched, the advance is *still* illegal — and now the guard can be precise.

        Before a fetch, the remote's tip is not an object we hold, so the honest answer is
        `CannotSay: fetch first`. After one, it is `NotOk`, and it says exactly how much you are
        missing. A refusal that does not say how far behind you are sends the reader hunting.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)
        _git(us, "fetch", "origin")

        verdict = main_guard.check_advance(str(forked["ours"]))

        assert isinstance(verdict, NotOk)
        assert "1 commit" in verdict.reason
        assert "fork" in verdict.reason.lower()


class TestItFailsClosed:
    """A witness that cannot see may never report "ok" — and offline is not "probably fine"."""

    def test_an_unreachable_remote_is_a_blind_spot_not_a_pass(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The most tempting bug in the file, refused.

        "I could not reach origin, so I will assume it has not moved" is a `CannotSay` wearing an
        `Ok`, and assuming the remote had not moved is *literally* what forked the trunk.

        Mutation: `return Ok(...)` when `remote_trunk()` is None. Red, here.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)
        _git(us, "remote", "set-url", "origin", str(us / "does-not-exist.git"))

        verdict = main_guard.check_advance(str(forked["ours"]))

        assert isinstance(verdict, CannotSay)
        assert exit_code(verdict) != EXIT_OK, "an unreachable remote exited 0 — it said 'ok'"

    def test_an_object_it_has_never_seen_is_a_blind_spot_not_a_refusal(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """And the symmetric trap: *not knowing* is not the same as *no*.

        Before a fetch, the remote's tip is not an object we hold. `git merge-base --is-ancestor`
        exits 128 there — not 1 — and reading that as "not an ancestor" would produce a refusal
        that is *right by accident*, on a question that was never answered. A false red is the same
        disease as a false green, and it is worse in one way: it trains you to ignore reds.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)

        verdict = main_guard.check_advance(str(forked["ours"]))

        # It is NotOk (it looked, having failed to resolve the object, it re-asked) or CannotSay —
        # but it is never Ok, and if it is CannotSay it says the object is unknown, not that we are
        # forked. What it may NOT do is claim knowledge it does not have.
        assert not isinstance(verdict, Ok)
        if isinstance(verdict, CannotSay):
            assert "fetch" in verdict.blind_spot


class TestTheLegalAdvance:
    """It must not cry wolf. A guard that refuses everything is uninstalled within a day."""

    def test_an_advance_that_contains_the_remote_is_allowed(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reconciled case: our branch is rebuilt on top of the remote. One trunk, still."""
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)
        _git(us, "fetch", "origin")
        _git(us, "checkout", "our-lane")
        _git(us, "rebase", "origin/main")
        reconciled = _git(us, "rev-parse", "HEAD").stdout.strip()

        verdict = main_guard.check_advance(reconciled)

        assert isinstance(verdict, Ok)
        assert exit_code(verdict) == EXIT_OK

    def test_a_deletion_has_no_history_to_fork(self) -> None:
        """An all-zero oid is a creation or a deletion. There is no divergent history to make."""
        assert main_guard.main(["0" * 40]) == EXIT_OK

    def test_the_bypass_passes_but_says_so_out_loud(
        self, forked: dict[str, Path | str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Taking the trunk is a decision, so it is spelled out — never a silent pass."""
        us = forked["us"]
        assert isinstance(us, Path)
        monkeypatch.chdir(us)
        monkeypatch.setenv(main_guard.BYPASS_ENV, "1")

        verdict = main_guard.check_advance(str(forked["ours"]))

        assert isinstance(verdict, Ok)
        assert "NOT checked" in verdict.evidence, (
            "the bypass passed QUIETLY. An override that does not announce itself is how a "
            "temporary exception becomes the permanent state of a repository."
        )


class TestTheHookIsWhatActuallyRefuses:
    """*A guard is what refuses a stranger* — not what appears in a list of guards (ADR 0026).

    So the hook is not read. It is **installed into a real repository, and the real forbidden
    `git merge --ff-only` is run against it.** `KNOWN_AUTH_GUARDS` certified an anonymous DELETE
    because membership of a list had been asserted by nobody; this file does not repeat that.
    """

    def test_a_real_forking_merge_is_refused_by_git_itself(
        self, forked: dict[str, Path | str]
    ) -> None:
        """The incident, end to end: a legal-looking fast-forward, aborted by the hook.

        Mutation: `chmod -x .githooks/reference-transaction`, or make it `exit 0`. The merge
        succeeds and `main` forks — in a test, this time.
        """
        us = forked["us"]
        assert isinstance(us, Path)

        # Install the guard exactly as a checkout would carry it.
        (us / "scripts").mkdir()
        (us / "scripts" / "main_guard.py").write_text(
            (_ROOT / "scripts" / "main_guard.py").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (us / "src" / "tessera").mkdir(parents=True)
        (us / "src" / "tessera" / "__init__.py").write_text("", encoding="utf-8")
        (us / "src" / "tessera" / "verdict.py").write_text(
            (_ROOT / "src" / "tessera" / "verdict.py").read_text(encoding="utf-8"), encoding="utf-8"
        )
        hooks = us / ".githooks"
        hooks.mkdir()
        installed = hooks / "reference-transaction"
        installed.write_text(_HOOK.read_text(encoding="utf-8"), encoding="utf-8")
        installed.chmod(0o755)
        _git(us, "config", "core.hooksPath", ".githooks")

        before = _git(us, "rev-parse", "main").stdout.strip()

        # The exact command both lanes ran on 2026-07-13, and it looked completely innocent.
        merge = subprocess.run(  # noqa: S603  literal argv, hermetic temp repo
            ["git", "merge", "--ff-only", "our-lane"],  # noqa: S607
            cwd=us,
            check=False,
            capture_output=True,
            text=True,
        )

        assert merge.returncode != 0, (
            "`git merge --ff-only` FORKED THE TRUNK and git reported success. The hook did not "
            "fire, or it fired and passed. This is the incident, reproduced, unguarded."
        )
        assert "main-guard" in merge.stderr, f"the refusal did not name itself:\n{merge.stderr}"
        assert (
            _git(us, "rev-parse", "main").stdout.strip() == before
        ), "the merge was refused and `main` MOVED ANYWAY — the transaction was not aborted."

    def test_the_hook_is_executable_and_delegates_to_the_guard(self) -> None:
        """A hook that is not executable is a file. Git skips it in silence — a guard that is not
        there, and nothing anywhere says so.
        """
        assert _HOOK.exists(), ".githooks/reference-transaction is gone — the trunk is unguarded"
        assert _HOOK.stat().st_mode & 0o111, (
            "the hook is not executable. Git skips a non-executable hook SILENTLY, so the trunk "
            "would be unguarded and every witness on the machine would say it was fine."
        )

        body = _HOOK.read_text(encoding="utf-8")
        assert "scripts/main_guard.py" in body
        assert "refs/heads/main" in body
        assert "prepared" in body, (
            "the hook must act in the `prepared` phase — that is the only one whose non-zero exit "
            "ABORTS the ref transaction. In any other phase it would print a refusal and let the "
            "trunk fork anyway: a witness that speaks and is not heard."
        )

    def test_make_install_wires_the_hook_up(self) -> None:
        """The guard is only mechanical if it is INSTALLED without anybody choosing to.

        `install` is a prerequisite of the gate, the tests, the lint — of everything. So the hook
        is in place before any other target in this repository can run. A guard you have to
        remember to install is the social rule again, wearing a shell script.
        """
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "\ninstall: hooks\n" in makefile, (
            "`make install` no longer depends on `hooks`, so a fresh checkout is unguarded until "
            "somebody remembers a target. The fork was MADE OF not remembering."
        )
        assert "core.hooksPath .githooks" in makefile
