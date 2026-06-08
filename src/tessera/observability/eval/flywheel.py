"""Trace → dataset flywheel — confirmed failures become regression cases (#6).

When online evaluation confirms a failure (low score, or a guard↔judge
disagreement that a human upheld), the offending turn is curated into the
offline non-regression harness as a new ``eval/failures/NNN_*.json`` case,
validated against ``eval/failures/_schema.json``. Production thereby feeds the
regression suite, closing the eval loop.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import jsonschema

if TYPE_CHECKING:
    from tessera.observability.eval.judge import JudgeVerdict

__all__ = ["curate_failure", "next_case_number"]

# src/tessera/observability/eval/flywheel.py → parents[4] is the repo root.
_DEFAULT_FAILURES_DIR: Path = Path(__file__).resolve().parents[4] / "eval" / "failures"

# Which harness category a failing metric maps to.
_METRIC_TO_CATEGORY: dict[str, str] = {"faithfulness": "hallucination"}

_NUM_RE = re.compile(r"^(\d{2,3})_")


def next_case_number(failures_dir: Path) -> int:
    """Return the next free case number in ``failures_dir`` (1-based)."""
    numbers = [
        int(match.group(1))
        for path in failures_dir.glob("[0-9]*_*.json")
        if (match := _NUM_RE.match(path.name))
    ]
    return max(numbers) + 1 if numbers else 1


def curate_failure(
    *,
    verdict: JudgeVerdict,
    question: str,
    language: str,
    expected_behavior: str,
    slug: str | None = None,
    failures_dir: Path | None = None,
) -> Path:
    """Write a confirmed failure as a schema-valid regression case.

    Args:
        verdict: The judge verdict that confirmed the failure.
        question: The user prompt that produced the bad turn.
        language: The conversation language (``fr``/``de``/``en``).
        expected_behavior: A description (≥20 chars) of the correct behaviour.
        slug: Optional kebab/snake slug; derived from the metric otherwise.
        failures_dir: Override for tests; defaults to ``eval/failures``.

    Returns:
        The path of the written case file.
    """
    target_dir = failures_dir or _DEFAULT_FAILURES_DIR
    number = next_case_number(target_dir)
    case_slug = slug or f"curated_low_{verdict.metric}"
    case_id = f"{number:03d}_{case_slug}"
    category = _METRIC_TO_CATEGORY.get(verdict.metric, "hallucination")

    case: dict[str, object] = {
        "id": case_id,
        "title": f"Curated from production: low {verdict.metric}",
        "category": category,
        "source_reference": {
            "citation": (
                f"Curated from a production trace; judge {verdict.judge_model} scored "
                f"{verdict.metric}={verdict.score:.2f}."
            )
        },
        "languages": [language],
        "prompts": {language: {"user": question}},
        "expected_behavior": expected_behavior,
        "pass_criteria": {},
        "tags": ["curated", "flywheel", verdict.metric],
    }

    schema = json.loads((target_dir / "_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(case, schema)

    path = target_dir / f"{case_id}.json"
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
