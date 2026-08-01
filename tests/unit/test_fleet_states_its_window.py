"""CLASS E — an answer bounded by an interval says which interval.

Every figure in the fleet payload — conversations, turns, escalation rate, latency — is bounded
by a window the CALLER chose, and until 2026-08-01 the answer never named it. Two surfaces asked
for two different windows:

* `/agents` (the Flotte directory) reads **all history**;
* every SURVEILLER domain page reads a **trailing 7 days**.

Both got a payload of identical shape carrying incomparable numbers, and an operator moving from
one page to the other had nothing on either screen telling them the counts were not the same
measurement. That is ADR 0026 in the temporal dimension: the payload reported a result without
reporting what it looked at.

**This file interrogates the PRODUCER, not a recording.** `tests/unit/fixtures/
fleet_real_responses.json` holds three captures taken before the field existed; they were
back-filled with the all-history window their route answers, because that is what the
un-parameterised route returns and the capture format has no way to record a request. A test
that only replays those captures would go green forever on a server that had stopped emitting
the field entirely — the recording cannot notice what the recorder stopped recording.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tessera.observability import fleet as fleet_mod


def test_window_bounds_and_the_reported_window_are_the_same_derivation() -> None:
    """The payload must not RE-derive its window — that is one more copy of one derivation.

    `compute_fleet` computes `since, until = _window_bounds(period_days, at)` and every query
    below it is scoped by that pair. The reported window is that same pair, serialised. If the
    two ever came apart, the payload would name an interval it did not query, which is strictly
    worse than naming none.
    """
    at = "2026-07-24T12:00:00+00:00"
    since, until = fleet_mod._window_bounds(7, at)

    assert until == datetime.fromisoformat(at)
    assert since is not None
    assert (until - since).days == 7


@pytest.mark.parametrize(
    ("period_days", "at", "expect_bounded"),
    [
        (None, None, False),  # the Flotte directory — all history, and it says so
        (7, None, True),  # a SURVEILLER domain page — trailing week ending now
        (30, "2026-07-24T12:00:00+00:00", True),  # an as-of read — window ends at T
    ],
)
def test_every_window_shape_is_expressible(
    period_days: int | None, at: str | None, expect_bounded: bool
) -> None:
    """All history is a real answer, not a missing one, and must not read as absence.

    `period_days: None` with `since: None` is the honest encoding of "everything ever". Had it
    been rendered as an absent `window`, the operator's screen could not tell "all history" from
    "this server does not report its window" — the two demand opposite reactions.
    """
    since, until = fleet_mod._window_bounds(period_days, at)
    assert (since is not None) is expect_bounded
    if at is not None:
        assert until == datetime.fromisoformat(at)
    if period_days is None and at is None:
        assert (since, until) == (None, None)


def test_the_payload_contract_requires_the_window() -> None:
    """`available: true` GUARANTEES every field — including this one.

    Declared as required rather than optional on purpose. The alternative was to widen the
    model so the pre-2026-08-01 captures kept validating, which would have let a server that
    silently stopped emitting the window go on passing every test in this repo.
    """
    from tessera.api.routes.observability.schemas_fleet import FleetPayload

    field = FleetPayload.model_fields["window"]
    assert field.is_required(), (
        "the window went optional. A payload whose interval is unstated is exactly the defect "
        "this field exists to remove — two pages showing incomparable numbers under one shape."
    )


def test_the_utc_now_case_is_bounded_and_ends_now() -> None:
    """A trailing window with no `at` ends at the read instant, not at some cached stamp."""
    before = datetime.now(UTC)
    since, until = fleet_mod._window_bounds(7, None)
    after = datetime.now(UTC)

    assert until is not None and since is not None
    assert before <= until <= after
    assert (until - since).days == 7
