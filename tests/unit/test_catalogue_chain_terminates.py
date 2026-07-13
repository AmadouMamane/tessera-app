"""**A self-consistent chain of artefacts proves nothing about the world.**

This is the deepest failure this repository has produced, and it produced it inside the very lot
written to close the class it belongs to.

On 2026-07-13 a case file was deleted:

    $ rm eval/failures/26_citation_fabrication_cjue.json   # the +100 pp and +87 pp runs
    $ make eval-power
      MEASURE THE MODEL: 5/63 cases, 6/174 runs
    [OK] 174 runs of catalogue 63-071edbdc re-derived from the committed matrix …
    >>> EXIT = 0

The catalogue holds **three** Holm-certified discriminators. **Two of them had just been erased**,
and the ratchet built to defend exactly that number reported green.

It was not a bug in the arithmetic. Every artefact it read agreed with every other artefact it
read. The committed verdict matrix held 63 cases' worth of columns. The committed null floor named
63 cases. The frozen classification named 63 cases. All three carried
``catalogue_version = "63-071edbdc"``. All three were **mutually consistent**, and all three were
**fossils** — not one of them had ever opened ``eval/failures/``.

A system in which every artefact derives its identity from another artefact is perfectly coherent
*and* perfectly fossilisable. **Somewhere the chain has to END**, in exactly one witness that opens
the source. That witness is :func:`eval.ratchet.catalogue_on_disk`, and this file is what makes it
impossible to build a verdict that never reaches it.

The rule, stated so a machine can hold it:

    Every artefact that CLAIMS a ``catalogue_version`` is a link, never a terminus. Any code path
    that turns such an artefact into a VERDICT must pass through ``catalogue_on_disk()``.

The registry below names every claiming artefact and every judging path. It is frozen. A new
artefact that carries a ``catalogue_version``, or a new judge that reads one, fails this file until
somebody says — on the record — which it is and where its chain ends.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Final

import pytest

from eval.ratchet import CATALOGUE_DIR, catalogue_on_disk, catalogue_version

_ROOT: Final = Path(__file__).resolve().parents[2]

#: Every committed artefact that **claims** a ``catalogue_version``. Each is a link in a chain and
#: **none of them is a terminus**: each one's version is a *quotation*, and a quotation of a
#: quotation is still a quotation. They are listed so that adding one without saying where its
#: chain ends is a red, not a shrug.
_CLAIMING_ARTEFACTS: Final[tuple[str, ...]] = (
    # The measured floor. Every contribution number in the product is a subtraction from it.
    "eval/baselines/null-control.json",
    # What the catalogue measures — the certified inversions the release gate now refuses on.
    "eval/baselines/discrimination.json",
    # The evidence the classification is re-derived from, one bitstring per pass.
    "eval/baselines/discrimination-samples.json",
    # EVIDENCE, not a judge: no production path turns it into a verdict, it is cited in the
    # contribution gate's own warning about its uncalibrated bar. It is listed anyway, and this is
    # the point of listing — the first run of this ratchet FOUND it, and an artefact that quotes a
    # catalogue_version and that nobody checks against the source is a fossil with a plausible
    # shape, whether or not anything reads it *today*.
    "eval/baselines/contribution-calibration.json",
)

#: Every module that turns one of those artefacts into a **verdict** a human or a machine acts on.
#: Each MUST reach :func:`eval.ratchet.catalogue_on_disk` — directly, or through a callee named
#: here. A judge that only ever compares two artefacts to each other is judging a fossil.
_JUDGES: Final[dict[str, str]] = {
    # The discrimination ratchet — the one that was green over the hole.
    "scripts/check_discrimination.py": "catalogue_on_disk",
    # The release gate. It refuses a model certified worse than silence, and that certification is
    # only usable if it still describes the catalogue on disk.
    "src/tessera/observability/eval_floor.py": "catalogue_on_disk",
}


def _reads(path: Path, name: str) -> bool:
    """Whether the module's AST mentions ``name`` — imported and called, not merely quoted."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = any(
        isinstance(n, ast.ImportFrom)
        and any(a.name == name for a in n.names)
        or isinstance(n, ast.Import)
        and any(a.name.endswith(name) for a in n.names)
        for n in ast.walk(tree)
    )
    called = any(
        isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id == name)
            or (isinstance(n.func, ast.Attribute) and n.func.attr == name)
        )
        for n in ast.walk(tree)
    )
    return imported and called


class TestTheChainEndsAtTheSource:
    def test_the_terminus_reads_the_case_files_and_nothing_else(self) -> None:
        """It must derive the identity from the FILES — not from any artefact that claims one."""
        ids = [p.stem for p in sorted(CATALOGUE_DIR.glob("*.json")) if not p.stem.startswith("_")]
        assert ids, "the catalogue is empty — this test cannot see what it judges"
        assert catalogue_on_disk() == catalogue_version(ids)

    def test_a_missing_catalogue_is_a_blind_spot__never_an_empty_one(self, tmp_path: Path) -> None:
        """``catalogue_version([])`` is a perfectly good string. That is the trap.

        A terminus that computed it would have compared two hashes and refused for the *wrong*
        reason — or, far worse, matched an equally empty floor and **passed**. The absence of the
        thing is not a property of the thing.
        """
        assert catalogue_on_disk(tmp_path / "does-not-exist") is None
        assert catalogue_on_disk(tmp_path) is None  # exists, and empty
        assert catalogue_version([]) == "0-e3b0c442"  # …and it would have looked like an answer

    @pytest.mark.parametrize("artefact", _CLAIMING_ARTEFACTS)
    def test_every_claiming_artefact_is_a_link_and_agrees_with_the_source(
        self, artefact: str
    ) -> None:
        """Each one quotes a ``catalogue_version``. Today they all quote the truth — verify it.

        This is the assertion the three fossils would have failed. Not one of them was wrong about
        what it *said*; every one of them was wrong about what still **existed**.
        """
        path = _ROOT / artefact
        assert path.exists(), f"{artefact} is missing — the chain has a hole in it"
        payload = json.loads(path.read_text(encoding="utf-8"))
        claimed = payload.get("catalogue_version")
        assert claimed, f"{artefact} claims no catalogue_version — it cannot be pinned to anything"
        assert claimed == catalogue_on_disk(), (
            f"{artefact} claims catalogue {claimed!r} and the case files on disk are "
            f"{catalogue_on_disk()!r}. Every number in it describes runs that may no longer exist. "
            f"Re-measure — never re-interpret."
        )

    @pytest.mark.parametrize(("module", "terminus"), sorted(_JUDGES.items()))
    def test_every_judge_reaches_the_terminus(self, module: str, terminus: str) -> None:
        """**The ratchet.** A judge that never opens the source is judging a fossil.

        Mutation: delete the ``catalogue_on_disk`` call from ``scripts/check_discrimination.py``
        and this goes red — which is precisely the state that reported ``[OK]`` with two of the
        catalogue's three certified discriminators deleted from disk.
        """
        path = _ROOT / module
        assert path.exists(), f"{module} is in the registry and not on disk"
        assert _reads(path, terminus), (
            f"{module} turns a catalogue-pinned artefact into a VERDICT, and it never calls "
            f"`{terminus}()`. Every artefact it reads agrees with every other artefact it reads — "
            f"which is exactly what three mutually-consistent fossils did on 2026-07-13 while the "
            f"catalogue they described had lost two of its three certified discriminators.\n\n"
            f"A self-consistent chain of artefacts proves NOTHING about the world. The chain must "
            f"end, in one witness that opens eval/failures/."
        )

    def test_the_registry_is_frozen__a_new_claiming_artefact_must_declare_its_chain(self) -> None:
        """Nothing may quietly join the chain.

        A new baseline, a new classification, a new sweep artefact — each one is another fossil
        waiting to happen. Adding one is fine. Adding one *silently* is how this class of bug is
        born, every time.
        """
        found = {
            str(p.relative_to(_ROOT))
            for p in (_ROOT / "eval" / "baselines").glob("*.json")
            if "catalogue_version" in p.read_text(encoding="utf-8")
        }
        assert found == set(_CLAIMING_ARTEFACTS), (
            f"the set of artefacts claiming a catalogue_version moved.\n"
            f"  new (undeclared): {sorted(found - set(_CLAIMING_ARTEFACTS))}\n"
            f"  gone            : {sorted(set(_CLAIMING_ARTEFACTS) - found)}\n\n"
            f"Every one of them is a LINK, never a terminus. Add it to _CLAIMING_ARTEFACTS and "
            f"name the judge that checks it against the source — or it is a fossil with a "
            f"plausible shape."
        )
