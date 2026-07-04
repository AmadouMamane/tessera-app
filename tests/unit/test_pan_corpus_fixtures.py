"""Frozen real-corpus fixtures for the input-side PAN mask (merge gate §5.1).

``tests/unit/fixtures/pan_corpus.json`` is produced by
``scripts/calibrate_pan_mask.py`` — a replay of ``mask_pan`` over **every**
persisted conversation message (3,260 rows / 1,630 user turns across the
``public`` and ``tessera_local`` schemas at freeze time), cross-checked against
an independent SQL census of 13-19 digit runs. Every masked span and every
declined candidate was reviewed by hand before freezing:

* masked — the one true Luhn-valid test PAN a user pasted (correct last four);
* unmasked — the one card-shaped probe reference (Luhn-invalid), untouched.

The real corpus carries almost no card-shaped runs, so the discrimination
burden (IBAN bodies, references, phones, amounts) lives in the synthetic
must/must-not suite of ``test_pan_input_mask.py``; this file pins the *real
traffic* behaviour so any mask change that would alter it fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tessera.guard.redaction import mask_pan

_FIXTURES: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "pan_corpus.json").read_text(encoding="utf-8")
)


def test_fixtures_carry_reviewed_provenance() -> None:
    assert _FIXTURES["source"].startswith("scripts/calibrate_pan_mask.py")
    assert _FIXTURES["rows_scanned"] >= 3260  # the corpus only grows
    assert _FIXTURES["masked"], "the reviewed masked set must never silently vanish"
    assert _FIXTURES["unmasked"], "the reviewed must-not-mask set must never silently vanish"


@pytest.mark.parametrize(
    "item", _FIXTURES["masked"], ids=[m["masked_as"] for m in _FIXTURES["masked"]]
)
def test_reviewed_masked_spans_stay_masked(item: dict[str, str]) -> None:
    result = mask_pan(item["excerpt"])
    assert item["span"] not in result.text
    assert item["masked_as"] in result.text
    assert result.changed


@pytest.mark.parametrize(
    "item", _FIXTURES["unmasked"], ids=[u["reason"] for u in _FIXTURES["unmasked"]]
)
def test_reviewed_unmasked_runs_stay_untouched(item: dict[str, str]) -> None:
    result = mask_pan(item["excerpt"])
    assert result.text == item["excerpt"]
    assert not result.changed
