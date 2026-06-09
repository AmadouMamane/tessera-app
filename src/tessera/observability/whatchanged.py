"""Root-cause "what changed" (ADR 0010, idea #17).

When a turn's quality drops, the first question is *what changed* — a model swap,
an edited prompt, a tightened policy, or different retrieved documents. Because
every turn already carries its bill of materials (:mod:`lineage`, #10), the
answer is a diff: line up two turns, compare their lineage, and attribute the
score delta to whatever moved between them. It turns "the agent got worse" into
"faithfulness fell 0.3 after the prompt hash changed."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tessera.observability.lineage import Lineage

__all__ = ["FieldChange", "WhatChangedReport", "what_changed"]

_REGRESSION_EPS = 1e-9  # a drop smaller than this is noise, not a regression


@dataclass(frozen=True, slots=True)
class FieldChange:
    """One lineage field that differs between two turns."""

    field: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class WhatChangedReport:
    """Attribution of a score delta to lineage changes between two turns."""

    score_before: float
    score_after: float
    score_delta: float  # after minus before (negative = regression)
    regressed: bool
    changes: list[FieldChange] = field(default_factory=list)
    docs_added: list[str] = field(default_factory=list)
    docs_removed: list[str] = field(default_factory=list)
    attributed: bool = False  # a regression with at least one lineage change


def what_changed(
    *,
    prev_lineage: Lineage,
    prev_score: float,
    curr_lineage: Lineage,
    curr_score: float,
) -> WhatChangedReport:
    """Diff two turns' lineage and attribute the score change.

    Args:
        prev_lineage: The earlier turn's bill of materials.
        prev_score: The earlier turn's faithfulness score.
        curr_lineage: The later turn's bill of materials.
        curr_score: The later turn's faithfulness score.

    Returns:
        A :class:`WhatChangedReport` with the per-field changes and whether the
        regression can be attributed to them.
    """
    changes: list[FieldChange] = []
    for name in ("model", "prompt_version", "guard_policy_version"):
        before = getattr(prev_lineage, name)
        after = getattr(curr_lineage, name)
        if before != after:
            changes.append(FieldChange(field=name, before=str(before), after=str(after)))

    prev_docs = set(prev_lineage.doc_sources)
    curr_docs = set(curr_lineage.doc_sources)
    docs_added = sorted(curr_docs - prev_docs)
    docs_removed = sorted(prev_docs - curr_docs)

    delta = curr_score - prev_score
    regressed = delta < -_REGRESSION_EPS
    has_change = bool(changes or docs_added or docs_removed)
    return WhatChangedReport(
        score_before=prev_score,
        score_after=curr_score,
        score_delta=delta,
        regressed=regressed,
        changes=changes,
        docs_added=docs_added,
        docs_removed=docs_removed,
        attributed=regressed and has_change,
    )
