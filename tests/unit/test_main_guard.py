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
import sys
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


def _merge_ff_only(repo: Path, branch: str) -> subprocess.CompletedProcess[str]:
    """The exact command both lanes ran on 2026-07-13, and it looked completely innocent."""
    return subprocess.run(  # noqa: S603  literal argv, hermetic temp repo
        ["git", "merge", "--ff-only", branch],  # noqa: S607
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def _install_guard(repo: Path) -> None:
    """Wire the guard into ``repo`` **exactly as `make hooks` wires it into this one**.

    Two details here are load-bearing, and the first version of this fixture had both wrong —
    which made the hook test pass *for the wrong reason*, i.e. it made it an instance of the
    disease it was written to catch.

    * **A real interpreter at `.venv/bin/python`.** The hook runs that one and nothing else (the
      system python3 on macOS is 3.9, and `verdict.py` needs 3.11+). With no interpreter there,
      the hook never gets as far as the guard: it refuses with *"no interpreter"*, git aborts the
      transaction, the string `main-guard` duly appears in stderr — and an assertion looking for
      that string goes green **while the guard has not run at all**. The merge was refused because
      the witness was ASLEEP, not because it looked and objected.

    * **Installed into the COMMON `.git/hooks/`** — never `core.hooksPath`, which is the precise
      mis-wiring this guard exists to have survived (relative, it resolves against each worktree's
      own root, so it never reached `main`). The old fixture set `core.hooksPath` — testing the
      guard through a wiring that `test_core_hookspath_is_not_hijacked` forbids the Makefile from
      ever using again. A test that installs a thing the way nobody installs it is testing a
      fiction.
    """
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "main_guard.py").write_text(
        (_ROOT / "scripts" / "main_guard.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "src" / "tessera").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "tessera" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "tessera" / "verdict.py").write_text(
        (_ROOT / "src" / "tessera" / "verdict.py").read_text(encoding="utf-8"), encoding="utf-8"
    )

    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    (venv_bin / "python").symlink_to(sys.executable)

    common = Path(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    )
    hooks = common / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    installed = hooks / _HOOK.name
    installed.write_text(_HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    installed.chmod(0o755)


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
        """An all-zero oid is a creation or a deletion. There is no divergent history to make.

        Through the **CLI**, deliberately: `advance` is the verb the hook actually invokes, and
        this test called the guard's *previous* argument shape (a bare tip, no subcommand) for as
        long as it took to notice — it raised `SystemExit(2)` inside argparse, which is the same
        exit code as a refusal. A test that drives an interface the caller does not use is a test
        of a program nobody runs.
        """
        assert main_guard.main(["advance", "0" * 40]) == EXIT_OK

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

    So the hook is not read. It is **installed into a real repository, wired up the way `make
    hooks` wires it, given a real interpreter — and the real forbidden `git merge --ff-only` is
    run against it.** `KNOWN_AUTH_GUARDS` certified an anonymous DELETE because membership of a
    list had been asserted by nobody; this file does not repeat that.

    .. rubric:: And the first version of this class WAS GREEN FOR THE WRONG REASON

    Which is worth spelling out, because it is the disease the whole file is about, caught inside
    the test written to catch it. The fixture installed no interpreter at `.venv/bin/python`. So
    the hook never reached the guard at all: it refused with *"no interpreter at .venv/bin/python"*,
    git aborted the transaction, the string `main-guard` appeared in stderr — and the sole
    assertion, ``assert "main-guard" in merge.stderr``, passed. **A hook that could not run the
    guard produced a green test for a guard that never ran.** The sha of the remote's actual tip
    appeared nowhere in that output, for the excellent reason that nobody had asked the remote.

    So the assertion is now the one thing a wrong implementation *cannot fake*: **the refusal must
    name the sha `origin/main` is actually at.** A hook that cannot run cannot print it. A guard
    reading `refs/remotes/origin/main` cannot print it either — the stale cache has never seen it.
    A test must demand the evidence of what was LOOKED AT, not merely the fact that something spoke.
    """

    def test_a_real_forking_merge_is_refused_by_git_itself(
        self, forked: dict[str, Path | str]
    ) -> None:
        """The incident, end to end: a legal-looking fast-forward, aborted by the hook — and the
        refusal NAMES THE FORK it prevented.

        Mutation: `chmod -x` the installed hook, or make it `exit 0`. The merge succeeds and
        `main` forks — in a test, this time.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        _install_guard(us)
        # Fetched, so the guard holds BOTH tips as real objects and can be precise about the fork.
        # (The unfetched case — the incident verbatim — is the next test, and it refuses too.)
        _git(us, "fetch", "origin")
        theirs = str(forked["theirs"])

        before = _git(us, "rev-parse", "main").stdout.strip()
        merge = _merge_ff_only(us, "our-lane")

        assert merge.returncode != 0, (
            "`git merge --ff-only` FORKED THE TRUNK and git reported success. The hook did not "
            "fire, or it fired and passed. This is the incident, reproduced, unguarded."
        )
        assert "no interpreter" not in merge.stderr, (
            "the merge was refused because THE HOOK COULD NOT RUN THE GUARD — not because the "
            "guard looked and objected. That is a green test for a witness that never woke up, "
            f"and it is exactly how this test passed before it was fixed:\n{merge.stderr}"
        )
        assert theirs[:12] in merge.stderr, (
            "the refusal does not name the sha origin/main is ACTUALLY at. A hook that never "
            "reached the guard could not print it; a guard reading the stale cached ref could not "
            "print it either. This sha IS the proof that the remote itself was asked — it is what "
            f"separates a guard that was right from a guard that merely spoke:\n{merge.stderr}"
        )
        assert (
            "fork" in merge.stderr.lower()
        ), f"the refusal does not say what it prevented:\n{merge.stderr}"
        assert _git(us, "rev-parse", "main").stdout.strip() == before, (
            "the merge was refused and `main` MOVED ANYWAY — the transaction was not aborted. "
            "PUBLISHING A VERDICT IS NOT ENFORCING IT: this hook, first written into git's "
            "`committed` phase, printed its refusal IN FULL while git answered `Fast-forward` "
            "and exited 0."
        )

    def test_the_unfetched_incident_is_refused_as_a_blind_spot(
        self, forked: dict[str, Path | str]
    ) -> None:
        """And **without** the fetch — which is the incident, verbatim: *nobody fetched*.

        Here the guard cannot resolve the remote's tip as a local object, so it cannot count how
        far behind you are. What it must not do is shrug. It refuses, it names the sha the remote
        just gave it, and it says the word `fetch`. *A witness that cannot see reports a blind
        spot — it may never report "ok".*
        """
        us = forked["us"]
        assert isinstance(us, Path)
        _install_guard(us)  # NO fetch. That omission IS the incident.

        before = _git(us, "rev-parse", "main").stdout.strip()
        merge = _merge_ff_only(us, "our-lane")

        assert merge.returncode != 0, "the unfetched fork — the incident itself — was let through"
        assert "no interpreter" not in merge.stderr, merge.stderr
        assert (
            str(forked["theirs"])[:12] in merge.stderr
        ), f"the blind-spot refusal does not name the tip the remote reported:\n{merge.stderr}"
        assert (
            "fetch" in merge.stderr.lower()
        ), f"it refused without saying what would make the answer knowable:\n{merge.stderr}"
        assert _git(us, "rev-parse", "main").stdout.strip() == before

    def test_the_hook_lets_a_reconciled_advance_through(
        self, forked: dict[str, Path | str]
    ) -> None:
        """It must also **not** refuse — and nothing above proves that.

        A hook of `echo main-guard >&2; exit 1` satisfies every assertion in the two tests above.
        It also refuses every legal advance, and so it is torn out within a day, which leaves the
        trunk exactly as unguarded as it was before anybody wrote a guard. *A guard that refuses
        everything is a guard that will not be there tomorrow.*

        So: reconcile the branch onto the remote's tip, and the same `git merge --ff-only` must
        now SUCCEED — and actually move `main`.
        """
        us = forked["us"]
        assert isinstance(us, Path)
        _install_guard(us)
        _git(us, "fetch", "origin")
        _git(us, "checkout", "our-lane")
        _git(us, "rebase", "origin/main")
        reconciled = _git(us, "rev-parse", "HEAD").stdout.strip()
        _git(us, "checkout", "main")

        merge = _merge_ff_only(us, "our-lane")

        assert merge.returncode == 0, (
            f"the hook REFUSED A LEGAL ADVANCE — it cries wolf, and a guard that cries wolf is "
            f"uninstalled by Friday:\n{merge.stdout}\n{merge.stderr}"
        )
        assert _git(us, "rev-parse", "main").stdout.strip() == reconciled, (
            "the hook exited 0 and `main` did not move — it aborted the transaction in silence, "
            "which is a refusal that does not even know it is one."
        )


class TestAnUninstalledGuardIsAWitnessThatDoesNotRun:
    """The eighth instance — and the first version of this file **was** it.

    It shipped a hook and never checked that git would ever reach it. `make hooks` set
    ``core.hooksPath = .githooks``, and a *relative* hooksPath resolves against **each worktree's
    own root** — so the hook existed only in trees whose branch happened to carry `.githooks/`,
    and **`main` did not**. The guard did not run in the checkout where the trunk lives. It also
    hijacked git's whole hook lookup, so `.git/hooks/pre-commit` became unreachable: a second hook,
    silently disabled, armed and waiting.

    An uninstalled guard is not a *weak* guard. It is a **witness that does not run** — it refuses
    nothing, and it protects exactly the trees that opted in, *and the fork was made of not opting
    in*.

    So `make gate` and `make claim` ask **git** — not `core.hooksPath` — where it would look, and
    they **refuse** when the answer is nowhere. Not a warning above an exit 0: this repository has
    now paid three times for the difference between *publishing* a verdict and *enforcing* one.
    """

    @pytest.fixture
    def tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """A repo that ships the guard's hook and has not installed it."""
        _git(tmp_path, "init", "--initial-branch=main", str(tmp_path / "repo"))
        repo = tmp_path / "repo"
        (repo / ".githooks").mkdir()
        (repo / ".githooks" / "reference-transaction").write_text(
            _HOOK.read_text(encoding="utf-8"), encoding="utf-8"
        )
        monkeypatch.chdir(repo)
        return repo

    def _hooks_dir(self, repo: Path) -> Path:
        out = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        return Path(out.stdout.strip()) / "hooks"

    def test_an_uninstalled_hook_is_refused_not_warned_about(self, tree: Path) -> None:
        """`git rev-parse --git-path` says where git WOULD look. Nothing is there ⇒ NotOk."""
        verdict = main_guard.check_installed()

        assert isinstance(verdict, NotOk)
        assert "UNGUARDED" in verdict.reason
        assert "make hooks" in verdict.reason
        assert exit_code(verdict) != EXIT_OK, (
            "an unguarded trunk exited 0. That is a warning printed above a pass — the exact shape "
            "of `dev-status` printing ⚠ STALE and returning 0."
        )

    def test_an_installed_hook_that_git_would_run_is_ok(self, tree: Path) -> None:
        """And it names the path git resolved, and the digest it matched. Evidence, not a tick."""
        hooks = self._hooks_dir(tree)
        hooks.mkdir(parents=True, exist_ok=True)
        installed = hooks / "reference-transaction"
        installed.write_text(_HOOK.read_text(encoding="utf-8"), encoding="utf-8")
        installed.chmod(0o755)

        verdict = main_guard.check_installed()

        assert isinstance(verdict, Ok)
        assert str(installed) in verdict.evidence

    def test_a_non_executable_hook_is_refused(self, tree: Path) -> None:
        """**Git skips a non-executable hook IN SILENCE.** The file is there and nothing runs it."""
        hooks = self._hooks_dir(tree)
        hooks.mkdir(parents=True, exist_ok=True)
        installed = hooks / "reference-transaction"
        installed.write_text(_HOOK.read_text(encoding="utf-8"), encoding="utf-8")
        installed.chmod(0o644)

        verdict = main_guard.check_installed()

        assert isinstance(verdict, NotOk)
        assert "not executable" in verdict.reason
        assert exit_code(verdict) != EXIT_OK

    def test_a_drifted_copy_is_refused(self, tree: Path) -> None:
        """**What git runs is the COPY.** Checking the tracked source would check a file nobody
        executes — the neighbourhood, one last time, in the guard that exists to name it.
        """
        hooks = self._hooks_dir(tree)
        hooks.mkdir(parents=True, exist_ok=True)
        installed = hooks / "reference-transaction"
        installed.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")  # a hook that refuses nothing
        installed.chmod(0o755)

        verdict = main_guard.check_installed()

        assert isinstance(verdict, NotOk)
        assert "NOT the one this checkout ships" in verdict.reason
        assert exit_code(verdict) != EXIT_OK


class TestTheGateRefusesAnUnguardedTrunk:
    """A green gate is a LICENCE TO LAND. It may not be granted over an unguarded trunk."""

    def test_gate_and_claim_check_the_installation_first(self) -> None:
        """And they check it FIRST — before the tree fingerprint, before anything.

        Mutation: delete either line. Red. A gate that certifies a tree whose trunk nothing
        protects is handing out a licence to fork it.
        """
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")

        for target in ("gate", "claim"):
            recipe = makefile.split(f"\n{target}:\n", 1)[1].split("\n\n", 1)[0]
            first = recipe.strip().splitlines()[0]
            assert "main_guard.py installed" in first, (
                f"`make {target}` does not check that the trunk guard is installed, or does not "
                f"check it first. Its first line is:\n    {first}\n"
                "An uninstalled guard is a witness that does not run."
            )

    def test_the_gate_does_not_silently_install_it(self) -> None:
        """`gate: hooks` would make the check UNFAILABLE — a green light with a name.

        The gate must be able to go red for the reason it exists. A check that repairs the thing
        it checks has not checked anything.
        """
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "\ngate: hooks" not in makefile and "\ngate:hooks" not in makefile, (
            "`gate` now depends on `hooks`, so it installs the guard and then verifies the guard "
            "it just installed. That check can never fail, and a check that cannot fail is not a "
            "check — it is a decoration with a name (F-14: detect-secrets scanned into /dev/null "
            "and reported success for a year)."
        )

    def test_core_hookspath_is_not_hijacked(self) -> None:
        """The first version set `core.hooksPath` and **silently disabled pre-commit's slot**.

        `pre-commit install` writes `.git/hooks/pre-commit`. With `core.hooksPath = .githooks`, git
        never looks there again — and says nothing. The guard dug the exact kind of hole it exists
        to name.
        """
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("\nhooks:\n", 1)[1].split("\n\n", 1)[0]

        assert "git config core.hooksPath" not in recipe, (
            "`make hooks` is setting core.hooksPath again. A relative one resolves against EACH "
            "WORKTREE'S ROOT (so it misses `main`, which carries no .githooks/), and it hides "
            "`.git/hooks/pre-commit` from git entirely. Install into the COMMON hooks dir instead: "
            "git resolves `hooks/` there from every worktree, whatever branch it carries."
        )
        assert "--git-common-dir" in recipe

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
