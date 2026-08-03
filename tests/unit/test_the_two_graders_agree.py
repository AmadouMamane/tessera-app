"""There are two graders, and the second one must keep reflecting the first.

`eval/runner.py` decides whether a run passed. `webapp/frontend/lib/eval-criteria.ts` recomputes
the deterministic half of that verdict so the case sheet can point at the exact substring that
decided it — a reconstruction the harness's own `reasons` string cannot give.

A second copy of a derivation is a liability. Its failure mode is not that it breaks; it is that
it quietly stops reflecting, and then the screen shows an operator a verdict nobody reached.
The polarity check is the newest and the most delicate — it is a list of negation markers in
three languages, and one marker missing on one side is enough to make the two disagree about
whether a refusal was a refusal.

So the Python side reads the TypeScript file and refuses a divergence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from eval.runner import _NEGATION_MARKERS, _SENTENCE_BREAKS, _TRAILING_NEGATION_WINDOW

_MIRROR = Path(__file__).resolve().parents[2] / "webapp" / "frontend" / "lib" / "eval-criteria.ts"


def _source() -> str:
    return _MIRROR.read_text(encoding="utf-8")


def test_the_mirror_exists() -> None:
    assert _MIRROR.exists(), f"the TypeScript grader is missing: {_MIRROR}"


def test_the_negation_markers_are_the_same_list_in_the_same_order() -> None:
    block = re.search(
        r"const NEGATION_MARKERS: readonly string\[\] = \[(.*?)\n\];",
        _source(),
        flags=re.DOTALL,
    )
    assert block is not None, "NEGATION_MARKERS not found in the TypeScript grader"
    mirrored = tuple(
        json.loads(line.strip().rstrip(",")) for line in block.group(1).splitlines() if line.strip()
    )
    assert mirrored == _NEGATION_MARKERS, (
        "the two graders disagree about what counts as a negation. One of them will read a "
        "refusal as an assertion, and only one of them decides whether the release ships.\n"
        f"  only in Python:     {sorted(set(_NEGATION_MARKERS) - set(mirrored))}\n"
        f"  only in TypeScript: {sorted(set(mirrored) - set(_NEGATION_MARKERS))}"
    )


def test_the_window_and_the_sentence_breaks_match() -> None:
    source = _source()
    assert f"const TRAILING_NEGATION_WINDOW = {_TRAILING_NEGATION_WINDOW};" in source
    assert f"const SENTENCE_BREAKS = {json.dumps(_SENTENCE_BREAKS)};" in source


def test_the_mirror_knows_every_criterion_the_schema_declares() -> None:
    """A criterion the front has never heard of is a rule the case sheet silently omits."""
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "eval" / "failures" / "_schema.json").read_text(
            encoding="utf-8"
        )
    )
    declared = set(schema["properties"]["pass_criteria"]["properties"])
    source = _source()
    missing = sorted(name for name in declared if f"pc.{name}" not in source)
    assert not missing, (
        "these criteria exist in the catalogue schema and the TypeScript grader never reads "
        "them, so a case declaring one shows the operator a shorter rule list than the harness "
        "applied:\n  " + "\n  ".join(missing)
    )
