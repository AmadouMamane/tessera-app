"""`make` collapses every non-zero exit into 2, and this repo documented the opposite.

The doctrine here has a three-valued exit surface and takes it seriously: **0 ok · 1 refused ·
2 blind**, with the third state carrying its whole weight — a witness that could not look may
never report "ok" (ADR 0026). `served_check.py`, `deploy_diff.py` and `tessera-preflight` all
speak it correctly.

Then each of them is reached through a Makefile target, and make exits **2 on any failed
recipe**. Through `make served-check`, "REFUSED — rebuild the image" and "blind — nothing is
answering" arrive as the same number. Those are opposite instructions.

That would be a footnote if the repository had not gone on to *describe* the flattened targets as
carrying the tri-state: CLAUDE.md attributed "0 ok · 1 refused · 2 blind" to `make served-check`,
the `preflight` recipe said its code was "passed through unlaundered", and the exit-witness
registry classified these targets `delegate` — a word that reads as "the script's code reaches
you". A caller branching on `$? -eq 2` to mean *blind* would read every refusal as a blind spot.

So the mechanism is **measured**, on the make that is actually installed, and pinned. A comment
saying "make flattens exit codes" is a claim; this is the observation. The failure it guards
against is the specific one this repo keeps paying for: a witness whose exit surface is narrower
than the vocabulary its documentation promises.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

#: What each probe recipe exits with, and what make is then expected to exit with. The 4 is not
#: decoration: `scripts/landed.py` really does exit 4, and it flattens to 2 exactly like the rest.
_CASES = [(0, 0), (1, 2), (2, 2), (4, 2)]


@pytest.fixture
def probe_makefile(tmp_path: Path) -> Path:
    """A makefile whose only job is to exit with a chosen code."""
    path = tmp_path / "exitprobe.mk"
    path.write_text(
        "".join(f"code{code}:\n\t@exit {code}\n" for code, _ in _CASES),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(("recipe_exit", "expected_make_exit"), _CASES)
def test_make_reports_2_for_every_failed_recipe(
    probe_makefile: Path, recipe_exit: int, expected_make_exit: int
) -> None:
    """The measurement. 1, 2 and 4 are three different verdicts and one exit code."""
    make = shutil.which("make")
    if make is None:
        pytest.skip("no make on PATH — nothing to interrogate")

    result = subprocess.run(  # noqa: S603 — fixed argv, a temp makefile we just wrote
        [make, "-f", str(probe_makefile), f"code{recipe_exit}"],
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected_make_exit, (
        f"a recipe exiting {recipe_exit} left make at {result.returncode}. If make has started "
        f"preserving recipe exit codes, the warnings in the Makefile and CLAUDE.md about the "
        f"tri-state being lost are now WRONG and must come out — a stale caveat teaches people "
        f"to distrust the accurate ones."
    )


def test_the_distinction_that_is_lost_is_refused_versus_blind(probe_makefile: Path) -> None:
    """Stated as the property, not as two numbers: the two states become indistinguishable.

    This is the assertion that would have caught the documentation. `served_check.py` exits 1 to
    say *the stack is stale, rebuild it* and 2 to say *I could not see anything*. One is an
    instruction, the other is an admission — and through make they are one integer.
    """
    make = shutil.which("make")
    if make is None:
        pytest.skip("no make on PATH — nothing to interrogate")

    codes = {
        label: subprocess.run(  # noqa: S603 — fixed argv, a temp makefile we just wrote
            [make, "-f", str(probe_makefile), f"code{code}"],
            capture_output=True,
            check=False,
        ).returncode
        for label, code in (("refused", 1), ("blind", 2))
    }
    assert (
        codes["refused"] == codes["blind"]
    ), "make now distinguishes them — see the note above; the caveats can go"
    assert codes["refused"] != 0, "a refusal must at least not read as success"
