"""The budget tile on Fiabilité & coût said "month" and meant "window", and its badge
answered a question about milliseconds.

Three defects sat in the same card:

* **"Dépensé (ce mois)"** was the *analysis window's* spend, so moving the period rail from
  7 to 30 days changed how much the month had cost.
* **"Prévision fin de mois"** was ``spent * (30 / max(1, n_requests)) * n_requests`` — an
  expression in which ``n_requests`` cancels exactly, leaving ``spent * 30`` whatever the
  window. On a 30-day window it forecast thirty months of spend, and nothing in it referred
  to the month it claimed to forecast.
* **"Dans le budget"** was driven by ``obs_cost.measure_overhead().within_budget`` — whether
  instrumentation span overhead fits a *millisecond* budget — while rendering directly under
  three euro figures. A green verdict about the neighbourhood of the question (ADR 0026).
"""

from __future__ import annotations

from datetime import UTC, datetime

from tessera.observability import reliability as rel


class _Bundle:
    """The three fields :func:`_month_to_date` reads off a persisted replay bundle."""

    def __init__(self, captured_at: str) -> None:
        self.captured_at = captured_at
        self.question = "combien coûte un virement instantané ?"
        self.context = "barème tarifaire"
        self.original_answer = "le virement instantané est gratuit jusqu'à 1000 EUR"


def test_a_month_is_bounded_by_its_own_first_and_next_first() -> None:
    starts = rel._month_bounds(datetime(2026, 8, 4, 19, 30, tzinfo=UTC))
    assert [d.isoformat() for d in starts] == [
        "2026-08-01T00:00:00+00:00",
        "2026-09-01T00:00:00+00:00",
    ]


def test_december_rolls_into_the_next_year() -> None:
    """The one arithmetic a naive ``month + 1`` gets wrong."""
    _, nxt = rel._month_bounds(datetime(2026, 12, 31, 23, 0, tzinfo=UTC))
    assert nxt.isoformat() == "2027-01-01T00:00:00+00:00"


def test_february_is_short_and_the_projection_knows_it() -> None:
    """The projection scales by the real month length, not by a hardcoded 30."""
    start, nxt = rel._month_bounds(datetime(2024, 2, 10, tzinfo=UTC))
    assert (nxt - start).days == 29, "2024 is a leap year"


def test_spend_is_month_to_date_not_the_analysis_window() -> None:
    """A bundle from last month is not this month's spend; one from this month is."""
    end = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    bundles = [
        _Bundle("2026-07-30T12:00:00+00:00"),  # before the 1st — excluded
        _Bundle("2026-08-02T12:00:00+00:00"),
        _Bundle("2026-08-14T12:00:00+00:00"),
    ]
    spent, _ = rel._month_to_date(bundles, end)
    only_this_month, _ = rel._month_to_date(bundles[1:], end)
    assert spent > 0
    assert spent == only_this_month, "a bundle from the previous month was counted"


def test_the_projection_scales_by_the_fraction_of_the_month_elapsed() -> None:
    """Half a month of spend forecasts about twice itself — never thirty times itself."""
    end = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)  # 15 of 31 days elapsed
    spent, projected = rel._month_to_date([_Bundle("2026-08-02T12:00:00+00:00")], end)
    assert spent > 0
    expected = spent * (31 / 15)
    assert abs(projected - expected) < 0.01, f"{projected} is not {expected}"
    assert projected < spent * 30, "the old formula (spend x 30) is back"


def test_the_projection_grows_as_the_month_runs_out_of_room() -> None:
    """Same spend, read later in the month, forecasts less: there is less left to add.

    Enough turns to clear the tile's cent rounding — one local turn costs a fraction of a
    cent, and a projection rounded to euros-and-cents cannot show a difference that never
    reaches one. The rounding is the published contract, so the test lives with it rather
    than reaching past it.
    """
    bundles = [_Bundle("2026-08-02T12:00:00+00:00")] * 3000
    _, early = rel._month_to_date(bundles, datetime(2026, 8, 5, tzinfo=UTC))
    _, late = rel._month_to_date(bundles, datetime(2026, 8, 28, tzinfo=UTC))
    assert early > late > 0


def test_no_spend_no_forecast_and_no_division_by_zero() -> None:
    """Negative control at the edge: the first instant of a month has nothing to extrapolate."""
    spent, projected = rel._month_to_date([], datetime(2026, 8, 1, 0, 0, tzinfo=UTC))
    assert (spent, projected) == (0.0, 0.0)


def test_the_within_budget_badge_agrees_with_the_euros_printed_beside_it() -> None:
    """Asked of the real report, not of the source that builds it (ADR 0026)."""
    report = rel.compute_reliability()
    assert report.budget_monthly_eur > 0
    assert report.within_budget is (report.budget_projected_eur <= report.budget_monthly_eur)
    assert (
        report.budget_spent_eur <= report.budget_projected_eur + 1e-6
    ), "a month-end forecast below what is already spent is not a forecast"


def test_the_badge_goes_red_when_the_forecast_passes_the_budget(monkeypatch) -> None:
    """Negative control: a verdict that cannot go red is not a verdict.

    Drops the monthly target below any real spend, so the *same* measured month must now
    read as an overrun. If the badge still came from the millisecond overhead benchmark it
    would not move at all.
    """
    baseline = rel.compute_reliability()
    monkeypatch.setattr(rel, "_MONTHLY_BUDGET_EUR", -1.0)
    breached = rel.compute_reliability()
    assert (
        breached.budget_projected_eur == baseline.budget_projected_eur
    ), "the measured forecast moved — the control changed more than the target"
    assert breached.within_budget is False
