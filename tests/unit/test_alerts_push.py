"""Push alerts fire on TRANSITIONS, journal their delivery, and never speak while blind.

ADR 0055. The specific failures these tests pin down:

* a steady red must not re-page every beat (an alert channel that repeats itself trains
  its reader to ignore it);
* a beat that could not read a condition (``active=None``) must neither page nor declare
  a recovery — a blind witness may never report "ok" (ADR 0026);
* the journalled delivery outcome comes from the HTTP response, never from the intent —
  a dead sink reads ``delivered: false`` with the error, not silence;
* the very first sighting of a QUIET condition records a baseline without paging
  "recovered" about an alert that never fired.

State and journal land in the per-test state dir (``TESSERA_GUARD__AUDIT_FILE``'s parent,
pinned to ``tmp_path`` by conftest), so nothing here touches shared state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.observability import alerts

if TYPE_CHECKING:
    import pytest

_T0 = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)

_STACK = alerts.AlertReading(
    condition="stack_down",
    active=True,
    message="Composant indisponible",
    recovery="Composant rétabli",
)


def _reading(active: bool | None) -> alerts.AlertReading:
    return alerts.AlertReading(
        condition="stack_down",
        active=active,
        message="Composant indisponible",
        recovery="Composant rétabli",
    )


def test_entering_the_active_state_fires_once_and_stays_quiet_after() -> None:
    first = alerts.process_beat([_reading(True)], now=_T0)
    assert [e["kind"] for e in first] == ["critical"]
    # The same red on the next beat is a steady state, not news.
    second = alerts.process_beat([_reading(True)], now=_T0)
    assert second == []


def test_recovery_fires_its_own_event_with_the_recovery_text() -> None:
    alerts.process_beat([_reading(True)], now=_T0)
    events = alerts.process_beat([_reading(False)], now=_T0)
    assert [e["kind"] for e in events] == ["recovered"]
    assert events[0]["text"] == "Composant rétabli"


def test_a_blind_reading_freezes_the_state_instead_of_recovering_it() -> None:
    """active=None between a red and the next red must not manufacture a second page."""
    alerts.process_beat([_reading(True)], now=_T0)
    assert alerts.process_beat([_reading(None)], now=_T0) == []
    # Still active as far as anyone could SAY — the next red is steady, not a new alert.
    assert alerts.process_beat([_reading(True)], now=_T0) == []


def test_first_sighting_of_a_quiet_condition_is_a_silent_baseline() -> None:
    assert alerts.process_beat([_reading(False)], now=_T0) == []
    report = alerts.alerts_report()
    assert report["conditions"] == {"stack_down": False}
    assert report["recent"] == []


def test_without_a_webhook_the_event_is_journalled_and_the_skip_is_named() -> None:
    events = alerts.process_beat([_STACK], now=_T0)
    delivery = events[0]["delivery"]
    assert delivery == {"delivered": False, "skipped": "no-webhook"}
    report = alerts.alerts_report()
    assert report["configured"] is False
    assert [e["condition"] for e in report["recent"]] == ["stack_down"]


def test_delivery_is_read_off_the_response_not_the_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured but dead sink journals delivered=false with the error, and survives."""
    from tessera.settings import get_settings

    monkeypatch.setenv("TESSERA_OBS_ALERT_WEBHOOK_URL", "https://hooks.invalid/dead")
    get_settings.cache_clear()
    try:

        def _dead_sink(_url: str, _text: str) -> dict[str, object]:
            return {"delivered": False, "error": "connection refused"}

        monkeypatch.setattr(alerts, "push_webhook", _dead_sink)
        events = alerts.process_beat([_STACK], now=_T0)
        assert events[0]["delivery"] == {"delivered": False, "error": "connection refused"}
        assert alerts.alerts_report()["configured"] is True
    finally:
        get_settings.cache_clear()


def test_the_journal_is_append_only_and_the_report_reads_its_tail() -> None:
    alerts.process_beat([_reading(True)], now=_T0)
    alerts.process_beat([_reading(False)], now=_T0)
    kinds = [e["kind"] for e in alerts.alerts_report()["recent"]]
    assert kinds == ["critical", "recovered"]
