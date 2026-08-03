"""One euro format, written in one place, checked against itself.

There were three formatters. ``agent/recouvrement.py`` wrote the amount due grouped
(``1 260,50 €``) and the monthly instalment ungrouped (``1260,50 €``); ``recouvrement/
scoring.py`` re-derived the label a third time, ungrouped, to check it against the number it
came from. Below 1 000 € all three agree, which is why every fixture passed. From 1 000 €
they diverge, ``amount_label_mismatch`` fires, and ``amount_consistency`` — a governance KPI
on the compliance page — reads **0.0** for a case whose amounts never disagreed.

A check that re-derives what it verifies is only ever checking its own copy.
"""

from __future__ import annotations

from tessera.observability.business_events import BusinessEventName
from tessera.recouvrement.money import format_euro
from tessera.recouvrement.scoring import _amount_consistency

#: The threshold is where the two old formatters parted company, so it is where the test
#: lives. 840,00 € would have passed against the buggy code.
_ABOVE_GROUPING = 1260.50
_BELOW_GROUPING = 840.00


def _slots_row(amount: float) -> dict[str, object]:
    return {
        "event_name": BusinessEventName.SLOTS_EXTRACTED.value,
        "payload": {"amount_due": amount, "amount_due_label": format_euro(amount)},
    }


def test_the_grouped_form_is_what_the_scorer_expects() -> None:
    assert format_euro(_ABOVE_GROUPING) == "1 260,50 €"
    assert format_euro(_BELOW_GROUPING) == "840,00 €"


def test_a_four_figure_amount_scores_consistent() -> None:
    score = _amount_consistency([_slots_row(_ABOVE_GROUPING)])
    assert score.status == "scored"
    assert score.score == 1.0
    assert score.reason == "amount_label_matches_numeric_amount"


def test_a_three_figure_amount_still_scores_consistent() -> None:
    """The case that always passed must keep passing — the fix is not a widened tolerance."""
    score = _amount_consistency([_slots_row(_BELOW_GROUPING)])
    assert score.score == 1.0


def test_a_genuinely_wrong_label_still_scores_zero() -> None:
    """Proves the check can still refuse: it compares, it does not merely agree."""
    row = _slots_row(_ABOVE_GROUPING)
    payload = row["payload"]
    assert isinstance(payload, dict)
    payload["amount_due_label"] = format_euro(_BELOW_GROUPING)
    score = _amount_consistency([row])
    assert score.score == 0.0
    assert score.reason == "amount_label_mismatch"


def test_negative_amounts_keep_their_sign_when_grouped() -> None:
    assert format_euro(-1260.50) == "-1 260,50 €"
