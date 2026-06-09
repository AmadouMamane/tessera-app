"""Unit tests for root-cause "what changed" (ADR 0010, #17)."""

from __future__ import annotations

import pytest

from tessera.observability.lineage import Lineage
from tessera.observability.whatchanged import what_changed


def _lineage(*, model: str, prompt: str, policy: str, docs: list[str]) -> Lineage:
    return Lineage(
        model=model, prompt_version=prompt, guard_policy_version=policy, doc_sources=docs
    )


def test_no_change_no_attribution() -> None:
    lin = _lineage(model="m", prompt="p1", policy="g1", docs=["a#1"])
    report = what_changed(prev_lineage=lin, prev_score=0.9, curr_lineage=lin, curr_score=0.9)
    assert report.regressed is False
    assert report.changes == []
    assert report.attributed is False


def test_regression_attributed_to_model_swap() -> None:
    prev = _lineage(model="opus", prompt="p1", policy="g1", docs=["a#1"])
    curr = _lineage(model="llama", prompt="p1", policy="g1", docs=["a#1"])
    report = what_changed(prev_lineage=prev, prev_score=0.9, curr_lineage=curr, curr_score=0.6)
    assert report.regressed is True
    assert report.attributed is True
    assert report.score_delta == pytest.approx(-0.3)
    assert any(c.field == "model" and c.after == "llama" for c in report.changes)


def test_doc_changes_detected() -> None:
    prev = _lineage(model="m", prompt="p1", policy="g1", docs=["a#1", "b#2"])
    curr = _lineage(model="m", prompt="p1", policy="g1", docs=["a#1", "c#3"])
    report = what_changed(prev_lineage=prev, prev_score=0.8, curr_lineage=curr, curr_score=0.8)
    assert report.docs_added == ["c#3"]
    assert report.docs_removed == ["b#2"]
    # no regression → not attributed even though docs moved
    assert report.attributed is False
