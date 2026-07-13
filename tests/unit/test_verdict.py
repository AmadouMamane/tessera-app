"""Ratchet (c) — an ``Ok`` cannot be built without its evidence, and no verdict is a boolean.

Three incidents in ADR 0026, a fourth in `scripts/worktree_owner.py`, and every one of them
reduced a verdict to a **bit** and threw away what it looked at. You cannot ask ``True`` what it
examined. So the bit is made unrepresentable, and this file is what holds that shut.

The two properties that carry the weight, and they are asserted at two different levels on purpose:

* **the type checker refuses ``Ok()``** — not just the interpreter. A test that only proves
  ``TypeError`` at runtime proves that *this* call site was caught; mypy proves that no call site
  can be written. That is the difference between a guard and a ratchet, so mypy is actually run.
* **``bool(verdict)`` raises.** Without it the type is decoration: every object is truthy, so
  ``if check(tree):`` would read a ``NotOk`` — and a ``CannotSay`` — as SUCCESS, and we would have
  rebuilt the original bug on top of its own fix.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tessera.verdict import (
    EXIT_OK,
    EXIT_REFUSED,
    CannotSay,
    NoEffect,
    NotOk,
    Ok,
    Power,
    exit_code,
    render,
)

_ROOT = Path(__file__).resolve().parents[2]


class TestANullResultCarriesItsPower:
    """The fourth verdict, and the same idea as the first.

    ``Ok`` may not be built without its evidence. ``NoEffect`` may not be built without its
    **power** — because "no effect" is the one claim a *badly designed* experiment produces for
    free, and this repository has the receipt: the eval catalogue was sampled at five passes per
    model, where the best p a **perfect** separation can produce (``1/C(10,5)`` = 0.0040) sits
    ABOVE the corrected threshold it would have to clear (``0.05/174`` = 0.00029). "Zero
    discriminating cases" was guaranteed by the design — as true of a perfect catalogue as of a
    worthless one — and nothing in the code would have stopped the sentence being written.
    """

    def test_the_type_checker_refuses_a_null_result_with_no_power(self, tmp_path: Path) -> None:
        """**The ratchet.** mypy — not the interpreter — must reject `NoEffect("no effect")`.

        Mutation: give `power` a default (`power: Power | None = None`). mypy then accepts the
        bare claim, this test goes red, and the type stops being a type: any witness could publish
        an absence it never had the power to observe. A returncode of 0 here IS the red.
        """
        snippet = tmp_path / "snippet.py"
        snippet.write_text(
            "from tessera.verdict import NoEffect\n"
            "\n"
            "# The sentence this class exists to make unwritable. No power: MUST NOT compile.\n"
            'verdict = NoEffect("no discriminating cases in the catalogue")\n',
            encoding="utf-8",
        )

        proc = _mypy(snippet, tmp_path)

        assert proc.returncode != 0, (
            "mypy ACCEPTED `NoEffect('no discriminating cases in the catalogue')` — a null result "
            "is now publishable by a test that could not have detected anything, and the type is "
            f"decoration. mypy said:\n{proc.stdout}"
        )
        assert "call-arg" in proc.stdout, (
            "mypy rejected the snippet, but not for the missing power. The ratchet must fail for "
            f"the RIGHT reason, or it is measuring its neighbourhood too:\n{proc.stdout}"
        )

    def test_power_refuses_the_design_that_could_not_have_seen_anything(self) -> None:
        """The runtime half, and the ten lines that carry the whole idea.

        Even holding a ``Power`` object, a witness cannot fabricate one: the constructor asks what
        the *most extreme observable result* of the design would have scored, and refuses when even
        that would have failed to clear the threshold. Such a test has no null result to report —
        it has a blind spot, and it must say so.
        """
        with pytest.raises(ValueError, match="CANNOT reject the null"):
            Power(
                samples=5,
                threshold=0.05 / 174,  # 0.000287
                best_achievable_p=0.00397,  # 1/C(10,5): a PERFECT separation at n=5
                minimum_detectable_effect=100.0,
                effect_unit="percentage points",
            )

    def test_a_power_that_could_see_is_accepted__and_says_what_it_could_have_seen(self) -> None:
        power = Power(
            samples=15,
            threshold=0.05 / 174,
            best_achievable_p=6.45e-9,  # 1/C(30,15)
            minimum_detectable_effect=66.7,
            effect_unit="percentage points of pass rate",
        )
        assert "66.7 percentage points" in str(power)
        assert "n=15" in str(power)

    def test_an_unnamed_absence_is_refused(self) -> None:
        power = Power(
            samples=15,
            threshold=0.05 / 174,
            best_achievable_p=6.45e-9,
            minimum_detectable_effect=66.7,
            effect_unit="pp",
        )
        with pytest.raises(ValueError, match="names no absence"):
            NoEffect(claim="   ", power=power)

    def test_a_bare_effect_size_with_no_unit_is_refused(self) -> None:
        with pytest.raises(ValueError, match="in WHAT"):
            Power(
                samples=15,
                threshold=0.05 / 174,
                best_achievable_p=6.45e-9,
                minimum_detectable_effect=66.7,
                effect_unit="",
            )

    def test_a_null_result_is_not_an_ok__it_may_not_open_a_gate_by_itself(self) -> None:
        """A witness that came back empty-handed has not established that the thing is fine.

        Whether a bounded absence is good news depends entirely on what the caller was hoping for
        — green for "did I break anything?", red for "does this case discriminate?" — and a type
        must not guess. So it exits with the other non-Ok verdicts, and a caller for whom the null
        result really *is* the good news must convert it deliberately, which forces the power into
        the evidence where a human reads it.
        """
        power = Power(
            samples=15,
            threshold=0.05 / 174,
            best_achievable_p=6.45e-9,
            minimum_detectable_effect=66.7,
            effect_unit="pp",
        )
        verdict = NoEffect(claim="the two models do not separate on this run", power=power)
        assert exit_code(verdict) == EXIT_REFUSED
        assert exit_code(verdict) != EXIT_OK
        assert render(verdict).startswith("[NO EFFECT] ")
        assert "66.7 pp" in render(verdict)

    def test_a_null_result_may_not_be_used_as_a_boolean_either(self) -> None:
        power = Power(
            samples=15,
            threshold=0.05 / 174,
            best_achievable_p=6.45e-9,
            minimum_detectable_effect=66.7,
            effect_unit="pp",
        )
        with pytest.raises(TypeError, match="not a boolean"):
            bool(NoEffect(claim="they do not separate", power=power))


class TestOkCarriesItsEvidence:
    """An ``Ok`` with nothing to show for itself must not exist."""

    def test_the_type_checker_refuses_an_ok_with_no_evidence(self, tmp_path: Path) -> None:
        """**The ratchet.** mypy — not the interpreter — must reject `Ok()`.

        Mutation: give `evidence` a default (`evidence: str = ""`). mypy accepts `Ok()`, this test
        goes red, and the type stops being a type: a witness could then mint a verdict about
        nothing, which is the whole disease.
        """
        snippet = tmp_path / "snippet.py"
        snippet.write_text(
            "from tessera.verdict import Ok\n"
            "\n"
            "verdict = Ok()  # no evidence: this MUST NOT type-check\n",
            encoding="utf-8",
        )

        proc = _mypy(snippet, tmp_path)

        assert proc.returncode != 0, (
            "mypy ACCEPTED `Ok()` — an Ok that observed nothing is now constructible, and the "
            f"type is decoration. mypy said:\n{proc.stdout}"
        )
        assert "call-arg" in proc.stdout, (
            "mypy rejected the snippet, but not for the missing evidence. The ratchet must fail "
            f"for the RIGHT reason, or it is measuring its neighbourhood too:\n{proc.stdout}"
        )

    def test_the_type_checker_refuses_a_fourth_verdict(self, tmp_path: Path) -> None:
        """The union is closed: `@final` means nobody invents `MostlyOk(Ok)` next quarter."""
        snippet = tmp_path / "snippet.py"
        snippet.write_text(
            "from tessera.verdict import Ok\n"
            "\n"
            "class MostlyOk(Ok):  # subclassing a @final verdict MUST NOT type-check\n"
            "    pass\n",
            encoding="utf-8",
        )

        proc = _mypy(snippet, tmp_path)

        assert proc.returncode != 0, f"mypy allowed a subclass of a @final verdict:\n{proc.stdout}"
        assert "misc" in proc.stdout or "final" in proc.stdout.lower(), proc.stdout

    def test_the_interpreter_refuses_it_too(self) -> None:
        """Belt and braces: `evidence` is positional and has no default."""
        with pytest.raises(TypeError, match="evidence"):
            Ok()  # type: ignore[call-arg]  — deliberately the illegal call

    def test_no_verdict_field_has_a_default(self) -> None:
        """Structural, and instant: a default is the one way an empty verdict could sneak back.

        The same rule ADR 0024 earned for identity fields, arriving from the other side: *no
        default that reads like knowledge*.
        """
        for cls in (Ok, NotOk, CannotSay):
            (field,) = dataclasses.fields(cls)
            assert (
                field.default is dataclasses.MISSING
            ), f"{cls.__name__}.{field.name} has a default"
            assert field.default_factory is dataclasses.MISSING, f"{cls.__name__} has a factory"

    @pytest.mark.parametrize("empty", ["", "   ", "\n\t "])
    def test_empty_evidence_is_not_evidence(self, empty: str) -> None:
        """`Ok("")` type-checks. It must not *run* — the empty string is the last loophole."""
        with pytest.raises(ValueError, match="not evidence"):
            Ok(empty)
        with pytest.raises(ValueError, match="what is wrong"):
            NotOk(empty)
        with pytest.raises(ValueError, match="could not see"):
            CannotSay(empty)


class TestAVerdictIsNotABoolean:
    """The single most load-bearing line in the module. Remove it and the type is a comment."""

    @pytest.mark.parametrize(
        "verdict",
        [
            Ok("I looked, and here is what I saw"),
            NotOk("it is broken"),
            CannotSay("I could not look"),
        ],
    )
    def test_bool_raises(self, verdict: Ok | NotOk | CannotSay) -> None:
        """Every object in Python is truthy. So a Verdict must refuse to be asked.

        Mutation: delete `__bool__` from `_Verdict`. This goes red — and, far more importantly,
        `if check(tree):` starts silently reading a REFUSAL as permission to proceed.
        """
        with pytest.raises(TypeError, match="not a boolean"):
            bool(verdict)

    def test_the_natural_mistake_is_the_one_that_raises(self) -> None:
        """`if verdict:` — the line a hurried caller actually writes — must explode, not pass."""
        verdict: Ok | NotOk | CannotSay = NotOk("this tree is held by another session")
        with pytest.raises(TypeError, match="would read a NotOk"):
            if verdict:
                pytest.fail("a NotOk was read as truthy — the exact bug this type forbids")

    def test_a_cannot_say_is_not_quietly_a_pass(self) -> None:
        """`CannotSay` is neither `Ok` nor falsy-and-therefore-ignorable. It stops you."""
        assert exit_code(CannotSay("no session id")) == EXIT_REFUSED
        assert exit_code(CannotSay("no session id")) != EXIT_OK


class TestTheVerdictReachesTheCaller:
    """Exit codes and rendering: what a Makefile acts on, and what a human reads."""

    def test_only_ok_exits_zero(self) -> None:
        assert exit_code(Ok("the tree is yours")) == EXIT_OK
        assert exit_code(NotOk("not yours")) == EXIT_REFUSED
        assert exit_code(CannotSay("cannot tell")) == EXIT_REFUSED

    def test_the_kind_is_never_lost_in_the_rendering(self) -> None:
        """`[CANNOT SAY]` in a terminal is the difference between a known hole and a false pass."""
        assert render(Ok("session 3797 holds it")).startswith("[OK] ")
        assert render(NotOk("held by session 9f2c")).startswith("[NOT OK] ")
        assert render(CannotSay("no TESSERA_SESSION_ID")).startswith("[CANNOT SAY] ")

    def test_the_payload_survives(self) -> None:
        """The whole point: the evidence travels WITH the verdict, all the way to the reader."""
        assert "pid 14340 alive" in render(Ok("session 3797 holds this tree, pid 14340 alive"))


def _mypy(snippet: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run mypy --strict on one file, in isolation from the repo's own config and cache.

    `cwd=tmp_path` so mypy does not pick up `pyproject.toml` (we want the bare `--strict` rules,
    not this repo's tuning), and `MYPYPATH` so `tessera.verdict` still resolves from source
    regardless of how the package happens to be installed.
    """
    env = dict(os.environ)
    env["MYPYPATH"] = str(_ROOT / "src")
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--follow-imports=silent",
            "--no-incremental",
            "--no-error-summary",
            "--cache-dir",
            str(tmp_path / ".mypy_cache"),
            str(snippet),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
