"""A frozen measurement must name the grader it was taken under, or be refused.

``catalogue_version`` tracks *which* cases exist, never *what they grade* (``eval.ratchet``:
it hashes ids alone, by design). So a ``pass_criteria`` edit changes the grader's meaning
under every frozen baseline while no pin moves — the catalogue version is the same string,
the stored verdict matrix the same bits, the classification reproducible from that matrix. A
self-consistent fossil, which is exactly the failure
[ADR 0026](../../docs/decisions/0026-a-witness-interrogates-the-thing.md) and
``catalogue_on_disk`` were written against.

``eval/baselines/grader_provenance.json`` closes the hole for grading criteria: it records
the ``grader_criteria_sha`` each frozen baseline was measured under. This witness recomputes
that sha from the case files on disk and refuses a *silent* divergence: if the criteria have
changed, the provenance must **declare** the baseline stale (``remeasure_owed: true``) and
point at the host command that clears it. A declared blind spot is honest; a silent one is
the fossil. When the host re-measures under the fixed grader and updates the pin, the two
shas agree again and ``remeasure_owed`` must return to false.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.ratchet import grader_criteria_sha

REPO = Path(__file__).resolve().parents[2]
PROVENANCE = REPO / "eval" / "baselines" / "grader_provenance.json"

_CATEGORY = "prompt_injection"


def test_the_provenance_file_exists() -> None:
    assert PROVENANCE.exists(), f"the grader provenance is missing: {PROVENANCE}"


def test_injection_baseline_provenance_matches_or_declares_staleness() -> None:
    record = json.loads(PROVENANCE.read_text(encoding="utf-8"))[_CATEGORY]
    measured_under = str(record["measured_under_criteria_sha"])
    owed = bool(record["remeasure_owed"])
    current = grader_criteria_sha(_CATEGORY)

    if current == measured_under:
        assert not owed, (
            "the criteria match what the baseline was measured under, yet it still claims a "
            "re-measure is owed — clear remeasure_owed."
        )
        return

    # The criteria moved. The baseline is stale-by-construction; the only acceptable state is
    # that it SAYS SO and names how to clear it (ADR 0026: a witness that cannot see may not
    # report ok — but it may report a blind spot).
    assert owed, (
        f"the injection grading criteria moved (baseline measured under {measured_under!r}, "
        f"the case files now grade at {current!r}) and the provenance does NOT declare a "
        f"re-measure owed. A frozen classification graded by a grader that no longer exists "
        f"is a silent fossil. Set remeasure_owed=true and re-run on the host, or "
        f"measured_under_criteria_sha if the baseline was genuinely re-measured."
    )
    assert record.get("reason"), "a declared-stale baseline must carry its reason"
    assert record.get("remeasure_command"), "a declared-stale baseline must name how to clear it"
