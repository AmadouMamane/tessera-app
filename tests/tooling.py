"""A test that cannot run is a BLIND SPOT, not a failure — and a blind spot that hides is worse.

**The false red.** On a worktree where `pnpm install` had never run, `make gate` went red like
this, and every layer laundered the cause:

    corepack pnpm exec biome  → 254  ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL  Command "biome" not found
      └─ generate_zod.py (check=True)      → 1     CalledProcessError
          └─ test_zod_codegen.py (check=True) → FAILED test_the_checked_in_zod_matches_…
              └─ pytest → make gate-py → Error 1  →  make gate → exit 2

The operator is told **"the checked-in zod is stale"** — an accusation against code that is
perfectly fine. The truth was *"node was never installed in this tree"*, and it was unrecoverable
from the message. This is the gate answering, with total confidence, a question about the **CODE**
when the question it was actually asked was about the **ENVIRONMENT** (ADR 0026, from the other
direction).

A false red is the same disease as a false green, and in one way it is worse: **a false green
lulls you; a false red TRAINS YOU TO IGNORE REDS.** It is the mechanism by which a suite becomes
decorative.

**The trap in fixing it.** A silent skip is a false green — it is exactly F-14, where
`detect-secrets` with no baseline was a permanently-green job that checked nothing, and a green
job that checks nothing is worse than an absent one *because an absent one is visible*. So the
skip may not hide:

* it is **named** — the real cause, verbatim from the tool that failed, not a guess;
* it is **counted** — :data:`BLIND_SPOTS`, censused at the end of every session, printed even when
  the count is zero, so "nothing was skipped" is itself something a witness said out loud;
* and inside the gate it **cannot happen at all**. `gate-checks` now runs `gate-web` (which
  installs the toolchain) *before* `gate-py`, and `gate-py` exports ``TESSERA_GATE=1``, under which
  a missing tool is not a skip but a **red that names the tool** — because there, its absence does
  not mean "this machine is bare", it means **the gate is broken**.

The zero-skip claim is therefore not a hope. It is :func:`census`, asserted at session end.
"""

from __future__ import annotations

import os
import subprocess
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from tessera.verdict import CannotSay, NotOk, Ok, Verdict

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Armed by the Makefile's `gate-py` and by CI. Its meaning is precise: *the toolchain has already
#: been installed by an earlier target*. That is the only reason a missing tool may be fatal here.
GATE_ENV: Final = "TESSERA_GATE"

_FRONTEND: Final = Path(__file__).resolve().parents[1] / "webapp" / "frontend"

#: Generous: corepack may have to fetch pnpm itself on a cold machine. A probe that times out and
#: reports "missing" would be a *fabricated* blind spot, which is its own small lie.
_PROBE_TIMEOUT_S: Final = 120.0

#: Every tooling blind spot this session stepped over. Appended by :func:`require_node_tool`,
#: read by the census in `conftest.pytest_sessionfinish`. A module-level list on purpose: the
#: census must see what the whole session saw, not what one test saw.
BLIND_SPOTS: list[str] = []


@cache
def probe_node_tool(tool: str) -> Verdict:
    """Can this process actually RUN the tool? Answered by running it. Never by looking for a file.

    ADR 0026: *a witness interrogates the thing.* ``node_modules/.bin/biome`` existing on disk is
    the **neighbourhood** — the binary can be there and be the wrong architecture, corepack itself
    can be absent, the store can be half-installed. ``pnpm exec biome --version`` exiting 0 is the
    **thing**. And the difference is not academic: whatever the real reason turns out to be, it is
    the one that ends up quoted in the blind spot, instead of a guess we made on its behalf.

    Args:
        tool: The binary, as `pnpm exec` resolves it from the frontend's `node_modules`.

    Returns:
        :class:`~tessera.verdict.Ok` carrying the version it just ran, or
        :class:`~tessera.verdict.CannotSay` carrying the tool's own last line of stderr.
    """
    argv = ["corepack", "pnpm", "exec", tool, "--version"]
    printable = " ".join(argv)
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell, no user input
            argv,
            cwd=_FRONTEND,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CannotSay(f"`{printable}` could not even be launched in {_FRONTEND}: {exc}")

    if proc.returncode != 0:
        said = (proc.stderr or proc.stdout).strip().splitlines()
        # The tool's OWN last line. `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL  Command "biome" not found`
        # is worth a hundred words of ours, and it is the only version that stays true when the
        # reason changes.
        cause = said[-1].strip() if said else f"exit {proc.returncode}, and it said nothing"
        return CannotSay(f"`{printable}` exited {proc.returncode}: {cause}")

    return Ok(f"{tool} {proc.stdout.strip()} — ran from {_FRONTEND}/node_modules")


def require_node_tool(tool: str, *, needed_for: str) -> None:
    """Gate a test on a node tool: a named blind spot outside the gate, a red **inside** it.

    The two halves are the entire design, and neither works without the other:

    * **Outside the gate** — a bare `pytest` in a fresh worktree — the tool genuinely is absent and
      the test genuinely cannot judge the code. It reports a blind spot naming the real cause and
      the exact command that fixes it. It does **not** accuse the code of a regression it did not
      commit.
    * **Inside the gate** the tool is *guaranteed* (gate-web installs it before gate-py runs), so
      its absence cannot mean "bare machine" — it can only mean the gate itself is broken. Skipping
      there would be a green light over a hole. It is RED, and the red names the tool.

    Args:
        tool: The binary this test cannot work without.
        needed_for: What the test is unable to check without it — printed in the census, so a
            reader of the skip knows precisely what went unchecked.
    """
    match probe_node_tool(tool):
        case Ok():
            return
        case NotOk(reason=cause) | CannotSay(blind_spot=cause):
            pass

    message = (
        f"{tool!r} could not be run — {cause}\n"
        f"  UNCHECKED: {needed_for}\n"
        "  This is a BLIND SPOT, not a verdict on the code: the test could not look.\n"
        "  Install the toolchain:  make gate-web"
        "   (or: cd webapp/frontend && corepack pnpm install)"
    )
    BLIND_SPOTS.append(message)

    if in_gate():
        pytest.fail(
            "TOOLING BLIND SPOT *INSIDE THE GATE* — this is a broken gate, not broken code.\n"
            f"{message}\n"
            "  `gate-checks` runs `gate-web` BEFORE `gate-py` precisely so this cannot happen;\n"
            "  if you are seeing it, that ordering has been undone."
        )
    pytest.skip(message)


def in_gate() -> bool:
    """Is the toolchain guaranteed, because a gate target installed it before calling us?"""
    return os.environ.get(GATE_ENV, "") == "1"


def census(blind_spots: Sequence[str], *, in_the_gate: bool) -> Verdict:
    """The session's blind-spot count, as a verdict. **This is the zero-skip ratchet.**

    Pure, so it can be asserted directly rather than inferred from a suite's behaviour:

    * **no blind spots** → ``Ok``, carrying the count. Printed even when it is zero, because
      "0 tests were skipped for missing tooling" is a fact a witness should have to *state*, not
      something a reader has to notice the absence of.
    * **blind spots, inside the gate** → ``NotOk``. The gate installs the toolchain before the
      python suite; a tooling skip there means that guarantee is broken, and the session goes red.
      **This is the assertion that "the count of tooling-skips in the full gate is ZERO".**
    * **blind spots, outside the gate** → ``CannotSay``. A developer on a bare tree is allowed to
      run the suite. They are not allowed to mistake it for a complete one.

    Args:
        blind_spots: The messages recorded by :func:`require_node_tool` this session.
        in_the_gate: Whether the toolchain was guaranteed by an earlier gate target.

    Returns:
        The verdict on the session's coverage — never a bare count, which nobody would read.
    """
    where = "the gate" if in_the_gate else "this run"
    if not blind_spots:
        return Ok(f"0 tooling blind spot(s) in {where}: every test could look at what it judges")

    listed = "\n".join(f"    · {spot}" for spot in blind_spots)
    if in_the_gate:
        return NotOk(
            f"{len(blind_spots)} test(s) could not run for MISSING TOOLING inside the gate.\n"
            f"{listed}\n"
            "  The gate installs the toolchain (gate-web) before the python suite (gate-py), so "
            "this cannot be a bare machine — the gate is broken. A skipped test here would be a "
            "green light over a hole (F-14), so the session is RED instead."
        )
    return CannotSay(
        f"{len(blind_spots)} test(s) could not run for missing tooling — this run has HOLES, and "
        f"its green is not a full green.\n{listed}"
    )
