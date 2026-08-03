"""The single euro formatter for the Recouvrement domain.

This module exists because there were three of them, and two disagreed.

``agent/recouvrement.py`` wrote the amount due as ``1 260,50 €`` (thousands grouped, the
historical French label) and the monthly instalment as ``1260,50 €`` (ungrouped), while
``recouvrement/scoring.py`` re-derived the label a third time, ungrouped, in order to check
it against the number it was built from. Below 1 000 € the three agree and everything looks
well; at 1 000 € they diverge, ``amount_label_mismatch`` fires, and the ``amount_consistency``
KPI reads **0.0** — a governance signal reporting a conflict between an amount and itself.

A check that re-derives what it verifies is only ever checking its own copy. So there is one
function, the presentation is the grouped French form, and the scorer imports it rather than
spelling it again.
"""

from __future__ import annotations

from typing import Final

__all__ = ["format_euro"]

_THOUSANDS_GROUPING_MIN: Final[float] = 1000.0


def format_euro(value: float) -> str:
    """Format ``value`` as a French euro label: ``840,00 €``, ``1 260,50 €``.

    Args:
        value: The amount in euros.

    Returns:
        The amount with two decimals, a comma decimal separator, a space between thousands
        from 1 000 € upwards, and a trailing euro sign.
    """
    int_part, dec_part = f"{value:.2f}".split(".")
    if abs(value) >= _THOUSANDS_GROUPING_MIN:
        sign = "-" if int_part.startswith("-") else ""
        int_part = sign + f"{abs(int(int_part)):,}".replace(",", " ")
    return f"{int_part},{dec_part} €"
