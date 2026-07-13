"""A witness interrogates the thing, never its neighbourhood (ADR 0026).

`make dev-status` claimed to report the code a server was running. It ran ``lsof`` to find the
process's **working directory**, then asked **git** about that **directory**, and printed the
answer under a column named ``git``. Every reader — including the person who wrote it — took that
to mean *the code this server is serving*. It never was.

On 2026-07-13 the operator's backend had booted the previous night at 23:56, before the ledger fix
landed. `dev-status` printed the sha **of the fix**. His browser paid 1 087 ms for a badge that
costs 20 ms, and every witness on the machine agreed everything was fine.

The property that ends it is one line long: **the identity is captured when the code is loaded,
and frozen.** Everything in this file exists to keep that line true, because the tempting change —
"just recompute it, it's cheap" — silently restores the original bug: a recomputed value describes
the **disk**, and the disk is not the process.
"""

# ruff: noqa: TCH002 — `pytest` is used at runtime here (monkeypatch, raises), not only in hints.

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from scripts import dev_status

from tessera import code_identity
from tessera.api.routes import health
from tessera.verdict import EXIT_OK, CannotSay, NotOk, Ok, Verdict, exit_code

_PACKAGE = Path(code_identity.__file__).resolve().parent


class TestTheIdentityIsFrozenWhenTheCodeIsLoaded:
    """The whole design. If only one test in this file survives, keep this one."""

    def test_moving_the_source_under_a_live_process_does_not_change_what_it_reports(
        self, tmp_path: Path
    ) -> None:
        """The exact incident, reproduced: the files change, the process must not budge.

        A file is slipped into the package while the "process" (this test) is running. The digest
        the process captured at import must be **unchanged** — it is a fact about what was loaded,
        not about what is on disk now. And to prove the freeze is doing real work rather than
        nothing having happened, the live re-hash of the very same directory is asserted to have
        MOVED.
        """
        before = code_identity.identity()
        live_before = code_identity.source_digest(_PACKAGE)
        assert before.digest == live_before  # nothing has changed yet — the baseline

        probe = _PACKAGE / "_witness_probe_test.py"
        probe.write_text('"""A checkout moving under a live server."""\n', encoding="utf-8")
        try:
            live_after = code_identity.source_digest(_PACKAGE)
            after = code_identity.identity()
        finally:
            probe.unlink()

        assert live_after != live_before, (
            "the probe did not change the on-disk digest — this test proves nothing; "
            "check that source_digest really walks the package directory"
        )
        assert after.digest == before.digest, (
            "the process's reported identity CHANGED when a file appeared on disk. It is being "
            "recomputed, so it now describes the DIRECTORY and not the PROCESS — which is the "
            "exact bug ADR 0026 exists to make impossible."
        )

    def test_the_health_endpoint_reports_the_frozen_identity_not_the_disk(
        self,
    ) -> None:
        """Behavioural, not textual: drive the real handler across a change on disk.

        A grep for ``subprocess`` in ``health.py`` would pass on a handler that called a helper
        that called git. This calls the endpoint, moves the files underneath it, and calls it
        again — the answer must be the same one, because it is an answer about the process.
        """
        first = asyncio.run(health.liveness())

        probe = _PACKAGE / "_witness_probe_route.py"
        probe.write_text('"""A checkout moving under a live server."""\n', encoding="utf-8")
        try:
            second = asyncio.run(health.liveness())
        finally:
            probe.unlink()

        assert second.code_digest == first.code_digest
        assert second.code_sha == first.code_sha


class TestItSaysWhatItCannotKnow:
    """ "I do not know" is an answer. A default that reads like knowledge is a lie (ADR 0024)."""

    def test_no_git_and_no_build_stamp_yields_an_honest_unknown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A directory that is not a repository, in a process nobody stamped.

        ``sha`` is ``None`` — not ``""``, not ``"unknown"``, not the string ``"HEAD"``. A caller
        that renders it will render a blank, and a blank is honest. A placeholder that *looks*
        like a sha would be believed.
        """
        monkeypatch.delenv(code_identity.BUILD_SHA_ENV, raising=False)
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")

        captured = code_identity._capture(tmp_path)

        assert captured.sha is None
        assert captured.sha_source == "unknown"
        assert captured.dirty is None
        assert captured.digest  # the EVIDENCE survives: a digest needs no repository

    def test_a_build_stamp_is_used_and_does_not_invent_a_clean_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A container has no working tree. ``dirty`` is therefore ``None`` — never ``False``.

        ``False`` would assert "there were no uncommitted edits", which nobody checked. The
        difference between *no news* and *good news* is the whole of this codebase's honesty rules.
        """
        monkeypatch.setenv(code_identity.BUILD_SHA_ENV, "deadbeefcafe")
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")

        captured = code_identity._capture(tmp_path)

        assert captured.sha == "deadbeefcafe"
        assert captured.sha_source == "env"
        assert captured.dirty is None

    def test_a_half_answer_from_git_is_not_rounded_up_to_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``rev-parse`` answered, ``status`` did not. We know the commit; we do NOT know dirty."""
        monkeypatch.delenv(code_identity.BUILD_SHA_ENV, raising=False)
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")

        def _half(_dir: Path, *args: str) -> str | None:
            return "abc123" if args[0] == "rev-parse" else None

        monkeypatch.setattr(code_identity, "_git", _half)
        captured = code_identity._capture(tmp_path)

        assert captured.sha == "abc123"
        assert captured.dirty is None, "an unanswered `git status` must not read as a clean tree"

    def test_a_real_repository_is_reported_as_one(self) -> None:
        """The live case: this package IS in a git checkout, so it says so."""
        captured = code_identity.identity()

        assert captured.sha_source in {"git", "env"}
        if captured.sha_source == "git":
            head = subprocess.run(  # noqa: S603
                ["git", "-C", str(_PACKAGE), "rev-parse", "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            assert captured.sha == head


class TestTheDigestIsEvidence:
    def test_a_moved_file_is_a_different_program(self, tmp_path: Path) -> None:
        """The path is hashed, not only the bytes. A rename changes the program; say so."""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "one.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b" / "two.py").write_text("x = 1\n", encoding="utf-8")

        assert code_identity.source_digest(tmp_path / "a") != code_identity.source_digest(
            tmp_path / "b"
        )

    def test_the_same_content_at_the_same_paths_is_the_same_program(self, tmp_path: Path) -> None:
        for name in ("a", "b"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "one.py").write_text("x = 1\n", encoding="utf-8")

        assert code_identity.source_digest(tmp_path / "a") == code_identity.source_digest(
            tmp_path / "b"
        )

    def test_a_one_byte_edit_moves_the_digest(self, tmp_path: Path) -> None:
        (tmp_path / "one.py").write_text("x = 1\n", encoding="utf-8")
        before = code_identity.source_digest(tmp_path)

        (tmp_path / "one.py").write_text("x = 2\n", encoding="utf-8")

        assert code_identity.source_digest(tmp_path) != before


class TestTheWitnessReportsItsBlindSpots:
    """A witness that cannot see must say so. It must never say ``ok``.

    **And "ok" is not only a word on a terminal.** Until 2026-07-13 every assertion in this class
    was about the *string* the witness printed, and every one of them passed — while
    ``dev_status.main()`` ended in a bare ``return 0``. The script printed ``⚠ CANNOT SAY`` and
    told its caller **zero**, which is the only channel `make` can hear. The tests were true and
    the tool was a false green, because the tests asked the same question the tool did: *what does
    it say?* Nobody asked *what does it return?*

    So every case below now asserts on the **exit code** as well. That is the assertion the fifth
    instance of ADR 0026 would have failed.
    """

    def test_a_server_that_will_not_say_what_it_loaded_is_not_pronounced_healthy(self) -> None:
        """The reassuring silence — the failure mode that let a stale server look fine for a week.

        An older backend has no ``code_digest``. The verdict must name the blind spot and ask for
        a restart. If this ever returns a green tick, the witness has gone back to certifying what
        it cannot see.
        """
        loaded, verdict = dev_status._verdict({"status": "ok", "version": "0.3.0"}, cwd=None)

        assert loaded == "?"
        assert isinstance(verdict, CannotSay)
        assert "RESTART" in verdict.blind_spot
        assert exit_code(verdict) != EXIT_OK, "a blind spot exited 0 — it told its caller 'ok'"

    def test_a_matching_digest_is_the_only_way_to_earn_a_tick(self, tmp_path: Path) -> None:
        """Green is earned by evidence: the process's digest equals the checkout's, right now."""
        package = tmp_path / "src" / "tessera"
        package.mkdir(parents=True)
        (package / "mod.py").write_text("x = 1\n", encoding="utf-8")
        digest = code_identity.source_digest(package)

        _, green = dev_status._verdict({"code_digest": digest, "code_sha": "abc"}, cwd=tmp_path)
        assert isinstance(green, Ok)
        assert exit_code(green) == EXIT_OK

        (package / "mod.py").write_text("x = 2\n", encoding="utf-8")  # the checkout moves

        _, stale = dev_status._verdict({"code_digest": digest, "code_sha": "abc"}, cwd=tmp_path)
        assert isinstance(stale, NotOk)
        assert "STALE" in stale.reason
        assert "RESTART" in stale.reason
        assert exit_code(stale) != EXIT_OK, (
            "STALE exited 0. `make dev-status` would be GREEN on a server that is not running the "
            "code in this checkout — which is the incident ADR 0026 was written for, reported by "
            "the very witness written to end it."
        )

    def test_a_process_that_cannot_be_asked_is_not_a_process_that_is_absent(self) -> None:
        """``lsof`` refusing to run and ``lsof`` finding nothing are DIFFERENT FACTS.

        The old `_listening_pid` collapsed both to ``None``, and the caller printed
        ``(not running)`` — a machine that could not be interrogated, reported as a machine that
        is not there. Four lines, the whole disease.
        """
        listening = dev_status._listening_pid("0")  # port 0: lsof runs, and matches nothing
        assert isinstance(listening, dev_status.Listening)
        assert listening.pid is None

    def test_the_exit_code_is_the_worst_verdict_never_the_most_convenient(self) -> None:
        """One stale server poisons the run. A green row may not out-vote a red one."""
        rows: list[Verdict] = [Ok("the frontend is a proxy"), NotOk("STALE · RESTART")]
        assert isinstance(dev_status._worst(rows), NotOk)

        rows = [Ok("the frontend is a proxy"), CannotSay("it will not say what it loaded")]
        assert isinstance(dev_status._worst(rows), CannotSay)

        rows = [Ok("current"), Ok("also current")]
        assert isinstance(dev_status._worst(rows), Ok)

    def test_dev_status_no_longer_asks_git_about_a_directory(self) -> None:
        """The literal regression, refused: the Makefile recipe may not re-derive the sha itself.

        The old recipe was ``git -C "$cwd" rev-parse --short HEAD`` — an answer about a directory,
        printed as an answer about a process. The target now delegates to the script, which asks
        the server. A future one-liner that "just quickly checks git" fails here.
        """
        makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("\ndev-status:", 1)[1].split("\n\n", 1)[0]

        assert "rev-parse" not in recipe, (
            "`make dev-status` is deriving a sha from a DIRECTORY again. That is a statement "
            "about the neighbourhood of the process, not about the process (ADR 0026). Ask the "
            "server what it loaded: it publishes it on /healthz."
        )
        assert "dev_status.py" in recipe
