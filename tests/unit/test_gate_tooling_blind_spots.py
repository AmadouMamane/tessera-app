"""Ratchet (d) — a test that cannot run is a blind spot; inside the gate there are ZERO of them.

Two failures, and they are the same failure seen from opposite sides.

**The false red.** On a virgin worktree (`pnpm install` never run), `make gate` went red on
`test_the_checked_in_zod_matches_the_current_openapi` — a sentence that means *"your generated
code is stale"*. It was not. `biome` was not installed, `pnpm exec` exited **254**, and three
`check=True` layers laundered that into a bare `1`. The gate answered, with total confidence, a
question about the CODE when it had been asked a question about the ENVIRONMENT. A false red is
the same disease as a false green — and worse in one respect: **a false green lulls you; a false
red trains you to ignore reds.**

**The trap in fixing it.** Turn that red into a skip and you have built F-14: `detect-secrets`
with no baseline was a permanently-green job that checked nothing, and a green job that checks
nothing is worse than an absent one, *because an absent one is visible*. A silent skip is a false
green wearing a fix's clothes.

So the skip is named, counted, and — inside the gate — **impossible**:

1. `gate-checks` runs `gate-web` (which installs the toolchain) BEFORE `gate-py`.
2. `gate-py` exports `TESSERA_GATE=1`, under which a missing tool is not a skip but a RED that
   names the tool, because there its absence cannot mean "bare machine" — only "broken gate".
3. `census()` states the count at the end of EVERY run, including when it is zero.

(1) and (2) are asserted against the Makefile and the CI workflow themselves — that is where a
future author would quietly undo them. (3) is asserted by running a real pytest with the toolchain
made unreachable, and reading what actually comes out.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tessera.verdict import CannotSay, NotOk, Ok
from tests import tooling
from tests.tooling import GATE_ENV, census, probe_node_tool, require_node_tool

_ROOT = Path(__file__).resolve().parents[2]
_MAKEFILE = (_ROOT / "Makefile").read_text(encoding="utf-8")
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

#: A PATH with no `corepack` on it — a virgin worktree's toolchain, without touching a worktree.
_BARE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"

_ZOD_TEST = "tests/unit/test_zod_codegen.py::test_the_checked_in_zod_matches_the_current_openapi"


class TestTheCensusIsTheRatchet:
    """`census()` is a pure function, so "zero skips in the gate" is asserted, not hoped for."""

    def test_zero_blind_spots_is_stated_out_loud(self) -> None:
        """A census that only speaks when it has bad news is one a reader stops looking for."""
        verdict = census([], in_the_gate=True)

        assert isinstance(verdict, Ok)
        assert "0 tooling blind spot" in verdict.evidence

    def test_a_blind_spot_inside_the_gate_is_red(self) -> None:
        """**THE RATCHET.** Inside the gate the toolchain is installed. A skip there is a HOLE.

        Mutation: return `CannotSay` here instead of `NotOk`. The suite goes green with a test
        that never ran — the exact shape of F-14 — and this goes red.
        """
        verdict = census(["biome could not be run"], in_the_gate=True)

        assert isinstance(verdict, NotOk), (
            "a test was skipped for missing tooling INSIDE THE GATE and the session stayed green. "
            "That is a green light over a hole."
        )
        assert "biome" in verdict.reason

    def test_a_blind_spot_outside_the_gate_is_a_named_hole_not_a_pass_and_not_a_red(self) -> None:
        """A developer on a bare tree may run the suite. They may not mistake it for a full one."""
        verdict = census(["biome could not be run"], in_the_gate=False)

        assert isinstance(verdict, CannotSay)
        assert "HOLES" in verdict.blind_spot


class TestTheGateGuaranteesTheToolchainItsTestsNeed:
    """Asserted against the Makefile and the workflow — the two places this would be undone."""

    def test_the_toolchain_is_installed_before_the_suite_that_needs_it(self) -> None:
        """`gate-checks: gate-web gate-py`. Reversing it re-arms the false red on every fresh tree.

        Mutation: swap them back. Red here — and a virgin worktree goes back to being told its
        checked-in zod is stale when the truth is that node was never installed.
        """
        (line,) = (ln for ln in _MAKEFILE.splitlines() if ln.startswith("gate-checks:"))
        prerequisites = line.split(":", 1)[1].split()

        assert prerequisites.index("gate-web") < prerequisites.index("gate-py"), (
            f"gate-py runs before gate-web ({line!r}), so the python suite runs before anything "
            "has installed node_modules — and its one node-dependent test blames the code for it"
        )

    def test_the_gate_arms_the_strict_promotion(self) -> None:
        """`gate-py` must export TESSERA_GATE=1, or a hole in the gate would merely be skipped."""
        recipe = _recipe("gate-py")
        pytest_lines = [ln for ln in recipe if "pytest" in ln]

        assert pytest_lines, "gate-py no longer runs pytest — this ratchet is measuring nothing"
        assert all(f"{GATE_ENV}=1" in ln for ln in pytest_lines), (
            f"gate-py runs pytest WITHOUT {GATE_ENV}=1, so a missing tool would be silently "
            f"skipped inside the gate instead of turning it red:\n{pytest_lines}"
        )

    def test_ci_installs_the_toolchain_before_the_python_suite_too(self) -> None:
        """CI had the identical ordering bug. It never fired only because CI is billing-blocked.

        The steps are read from the PARSED workflow, not from the file's text — and that is not
        fastidiousness. The first version of this ratchet did `_CI.index("make gate-py")`, matched
        the words inside the *comment* that explains the ordering, and reported the fix as broken.
        A witness that reads prose is reading the neighbourhood of the thing that runs. Even here.
        Even while writing the ADR about it.
        """
        steps = yaml.safe_load(_CI)["jobs"]["gate"]["steps"]
        commands = [str(step.get("run", "")) for step in steps]
        web = next(i for i, run in enumerate(commands) if "make gate-web" in run)
        py = next(i for i, run in enumerate(commands) if "make gate-py" in run)

        assert web < py, (
            "ci.yml runs `make gate-py` before `make gate-web`, and only the pnpm STORE is cached "
            "— never node_modules. On a cold runner this is the false red, armed."
        )


class TestAMissingToolIsNamed:
    """The cause must be the tool's own words — never a guess we made on its behalf."""

    def test_the_probe_runs_the_tool_rather_than_looking_for_its_file(self) -> None:
        """ADR 0026: `node_modules/.bin/x` on disk is the neighbourhood; `x --version` is the thing.

        A file check would call a wrong-arch binary present and a broken corepack fine. Running it
        is the only question whose answer is the one we need — and it hands us the REAL cause.
        """
        verdict = probe_node_tool("tessera-not-a-real-tool")

        assert isinstance(verdict, CannotSay)
        assert "tessera-not-a-real-tool" in verdict.blind_spot
        assert "exited" in verdict.blind_spot or "could not even be launched" in verdict.blind_spot

    def test_outside_the_gate_a_missing_tool_skips_and_says_why(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(tooling, "BLIND_SPOTS", [])
        monkeypatch.setattr(
            tooling, "probe_node_tool", lambda _: CannotSay('Command "biome" not found')
        )
        monkeypatch.delenv(GATE_ENV, raising=False)

        with pytest.raises(pytest.skip.Exception, match="biome"):
            require_node_tool("biome", needed_for="whether the zod is stale")

        assert (
            len(tooling.BLIND_SPOTS) == 1
        ), "the skip was not counted — a skip nobody counts hides"
        assert "BLIND SPOT" in tooling.BLIND_SPOTS[0]
        assert "make gate-web" in tooling.BLIND_SPOTS[0], "a blind spot must name the way out"

    def test_inside_the_gate_a_missing_tool_is_red_and_accuses_the_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """And the red must blame the environment, in words. That is the whole repair."""
        monkeypatch.setattr(tooling, "BLIND_SPOTS", [])
        monkeypatch.setattr(
            tooling, "probe_node_tool", lambda _: CannotSay('Command "biome" not found')
        )
        monkeypatch.setenv(GATE_ENV, "1")

        with pytest.raises(pytest.fail.Exception, match="broken gate, not broken code"):
            require_node_tool("biome", needed_for="whether the zod is stale")

        assert len(tooling.BLIND_SPOTS) == 1


@pytest.mark.slow
class TestTheWholeChain:
    """Interrogate the THING: run a real pytest with the toolchain out of reach; read the output.

    `PATH` without `corepack` reproduces a virgin worktree's toolchain exactly, and touches nothing
    — the alternative (renaming `node_modules/.bin/biome`) would mutate the tree a gate is
    fingerprinting, which is the *other* bug this repo has already paid for.
    """

    def test_without_the_gate_the_node_test_reports_a_blind_spot_and_does_not_accuse_the_code(
        self,
    ) -> None:
        proc = _pytest_with_no_toolchain(in_gate=False)

        assert proc.returncode == 0, f"a missing tool went RED outside the gate:\n{proc.stdout}"
        assert "1 skipped" in proc.stdout, proc.stdout
        assert "BLIND SPOT" in proc.stdout
        assert "TOOLING BLIND SPOTS" in proc.stdout, "the census did not print the hole"
        assert "stale" not in proc.stdout, (
            "the output still tells the operator the checked-in zod is STALE — an accusation "
            "against code that is fine. That is the false red, and it is back."
        )

    def test_inside_the_gate_the_same_absence_is_red_and_nothing_is_skipped(self) -> None:
        """**The zero-skip claim, interrogated.** In the gate, a hole cannot hide as a skip.

        Mutation: drop `TESSERA_GATE=1` from gate-py. This run goes GREEN with a skipped test —
        a suite silently one test smaller, which is exactly how 51 failures once belonged to
        somebody else and nobody noticed.
        """
        proc = _pytest_with_no_toolchain(in_gate=True)

        assert (
            proc.returncode != 0
        ), "a test was SKIPPED for missing tooling inside the gate and the run stayed green"
        assert "1 skipped" not in proc.stdout
        assert "broken gate, not broken code" in proc.stdout, (
            "the red does not say it is the environment's fault — so it still reads as a code "
            f"regression:\n{proc.stdout}"
        )


def _recipe(target: str) -> list[str]:
    """The recipe lines of a Makefile target — the tab-indented block under `target:`."""
    lines = _MAKEFILE.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"{target}:"))
    recipe: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("\t"):
            recipe.append(line.strip())
        elif line.strip() and not line.startswith("#"):
            break
    return recipe


def _pytest_with_no_toolchain(*, in_gate: bool) -> subprocess.CompletedProcess[str]:
    """Run the one node-dependent test in a process that genuinely cannot reach corepack."""
    env = {k: v for k, v in os.environ.items() if k != GATE_ENV}
    env["PATH"] = _BARE_PATH
    if in_gate:
        env[GATE_ENV] = "1"
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", _ZOD_TEST, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
