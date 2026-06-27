"""Unit tests for the time-rail data-availability bound (`/observability/data-range`).

The bound feeds the "Aller à une date" calendar: days before the earliest real
data are disabled, so the user can never anchor the window on an empty past.
"""

from tessera.api.routes.observability import _data_availability_start


def test_returns_none_when_no_data() -> None:
    assert _data_availability_start([], []) is None


def test_earliest_score_when_only_scores() -> None:
    scores = [
        {"scored_at": "2026-05-10T08:00:00+00:00"},
        {"scored_at": "2026-05-03T08:00:00+00:00"},
        {"scored_at": "2026-05-07T08:00:00+00:00"},
    ]
    assert _data_availability_start(scores, []) == "2026-05-03T08:00:00+00:00"


def test_earliest_across_both_sources() -> None:
    # The audit log predates every score → it sets the bound.
    scores = [{"scored_at": "2026-05-10T08:00:00+00:00"}]
    audit = [
        {"occurred_at": "2026-04-29T23:30:00+00:00"},
        {"occurred_at": "2026-05-12T10:00:00+00:00"},
    ]
    assert _data_availability_start(scores, audit) == "2026-04-29T23:30:00+00:00"


def test_blank_and_missing_stamps_are_ignored() -> None:
    scores = [{"scored_at": ""}, {"metric": "faithfulness"}]  # no usable stamp
    audit = [{"occurred_at": ""}, {"occurred_at": "2026-05-01T00:00:00+00:00"}]
    assert _data_availability_start(scores, audit) == "2026-05-01T00:00:00+00:00"


def test_all_blank_is_none() -> None:
    assert _data_availability_start([{"scored_at": ""}], [{"occurred_at": ""}]) is None
