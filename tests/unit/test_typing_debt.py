"""The typing debt is a NUMBER, never an intention.

``make gate`` ran ``mypy`` over ``src/tessera`` and nothing else. So every ``assert_never`` in the
eval harness — the construct that turns an exhaustive ``match`` from a *hope* into a **proof** —
was **decoration**: mypy never looked at the file it lived in. A proof nobody runs is a comment.

This lot closed that for ``eval/`` (it now typechecks clean under ``--strict``, and the gate runs
it). What it did **not** close is ``scripts/``, and rather than write "TODO: type scripts/" in a
docstring where it will be true forever, the residue is frozen here as a set of file names that
**may only shrink**.

Two ways it goes red, and both are the point:

* **A new untyped script.** Someone adds ``scripts/foo.py`` with a ``--strict`` error and it is not
  in the registry. Red. The debt does not grow quietly.
* **A script that got fixed and was not struck off.** Someone types one properly and the registry
  still names it. Red. The debt does not *shrink* quietly either — because a number nobody has to
  argue with is a number nobody looks at, and the whole reason this file exists is that
  ``mypy src/tessera`` was such a number for months.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parents[2]

#: mypy's contract: ``0`` clean, ``1`` errors found. Anything else is a *fatal* — a bad config, a
#: missing module, a crash — and it means this test **could not look**.
_MYPY_LOOKED: Final = (0, 1)

#: Scripts that do **not** typecheck under ``--strict``, as of 2026-07-13. **This set may only
#: shrink.** It is not a wish list: it is the exact residue of a debt that was declared out loud
#: (`make gate` typechecked `src/tessera` alone) and half-paid in the same lot — `eval/` is now
#: clean and gated, and these ten files are what is left.
#:
#: ``scripts/worktree_owner.py`` is in here and that is worth a sentence: it is the tool that
#: decides **who owns a worktree**, it publishes a proper ``Verdict``, and it still has a
#: ``--strict`` error. A witness can be right about the question and wrong about its own types.
OWED_UNTYPED_SCRIPTS: Final[frozenset[str]] = frozenset(
    {
        "scripts/backfill_agent_attribution.py",
        "scripts/backfill_agent_judge.py",
        "scripts/backfill_compliance_trend.py",
        "scripts/backfill_model_judge.py",
        "scripts/compare_eval.py",
        "scripts/config_inventory.py",
        "scripts/generate_traffic.py",
        "scripts/ingest_transcript_traffic.py",
        "scripts/probe_retrieval.py",
        "scripts/worktree_owner.py",
    }
)


def _files_with_strict_errors(targets: list[str]) -> set[str]:
    """Run mypy over ``targets`` and return the files it reports errors in.

    It **runs the checker** rather than reading a cached list — a registry of typing debt that never
    invoked the type checker would be a witness asking its neighbourhood, which is the failure this
    repository has spent a week closing.

    And it asserts that mypy **looked**. If the checker cannot start — a bad config, a missing
    module, a crash — it emits no ``: error:`` lines, this function returns an empty set, and every
    assertion below passes with flying colours while measuring **nothing**. A blind witness
    reporting "no debt" is the exact bug the debt exists to pay off, so it raises instead.

    Raises:
        AssertionError: If mypy did not run to a verdict.
    """
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mypy", *targets],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        check=False,
    )
    if proc.returncode not in _MYPY_LOOKED:
        msg = (
            f"mypy did not run to a verdict (exit {proc.returncode}). This test CANNOT SEE the "
            f"typing debt it exists to freeze — and an empty error list from a checker that never "
            f"started would read as 'no debt'. That is a green light over a hole.\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
        raise AssertionError(msg)
    return {
        line.split(":", 1)[0]
        for line in proc.stdout.splitlines()
        if ": error:" in line and line.startswith(("scripts/", "eval/", "src/"))
    }


class TestTheTypingDebtIsFrozen:
    def test_eval_typechecks_clean__the_assert_nevers_are_proofs_now(self) -> None:
        """``eval/`` carries the taxonomy's exhaustiveness proofs. It must be *checked*.

        ``eval/discrimination.py`` matches on seven run classes under ``assert_never``; a class
        added without a branch must fail the build. Before this lot the gate never ran mypy on that
        file, so the line proved nothing at all.
        """
        assert _files_with_strict_errors(["eval"]) == set(), (
            "eval/ no longer typechecks under --strict. Every `assert_never` in the harness is now "
            "decoration again, and an exhaustive `match` is back to being a hope."
        )

    def test_the_scripts_debt_may_only_shrink(self) -> None:
        """**The frozen number.** A debt nobody has to argue with is a debt nobody pays."""
        scripts = sorted(str(p.relative_to(_ROOT)) for p in (_ROOT / "scripts").glob("*.py"))
        failing = _files_with_strict_errors(scripts)

        new = failing - OWED_UNTYPED_SCRIPTS
        fixed = OWED_UNTYPED_SCRIPTS - failing
        assert not new, (
            f"the typing debt GREW: {sorted(new)} do not typecheck under --strict and are not in "
            f"OWED_UNTYPED_SCRIPTS. Type them, or add them to the registry — but the debt does not "
            f"grow quietly."
        )
        assert not fixed, (
            f"{sorted(fixed)} typecheck now. Strike them off OWED_UNTYPED_SCRIPTS so the debt "
            f"shrinks ON THE RECORD. A number nobody has to argue with is a number nobody looks at."
        )
