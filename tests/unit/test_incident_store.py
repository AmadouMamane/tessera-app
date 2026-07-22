"""Lot 10 — the durable incident store (create-the-source).

The store starts EMPTY (an incident records that someone decided something was
one); every act on it is attributed and journalled; vocabularies are closed.
"""

from __future__ import annotations

import datetime as _dt
from typing import TYPE_CHECKING

import pytest

from tessera.observability import incident_store as store

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(store, "_incidents_path", lambda: tmp_path / "incidents.json")


def test_the_store_starts_empty_and_creation_is_attributed() -> None:
    assert store.load_incidents() == []
    inc = store.create_incident(
        title="Pic d'injections bloquées",
        severity="eleve",
        domain="securite",
        opened_by="bob@bank.eu",
    )
    assert str(inc["incident_id"]).startswith("INC-")
    assert inc["opened_by"] == "bob@bank.eu"
    assert inc["status"] == "ouvert"
    journal = inc["journal"]
    assert isinstance(journal, list) and journal[0]["actor"] == "bob@bank.eu"
    # Durable: a fresh read sees it; the sidebar helper counts it.
    assert len(store.load_incidents()) == 1
    assert store.open_durable_counts() == (1, 0)


def test_closed_vocabularies_refuse_loudly() -> None:
    with pytest.raises(ValueError, match="title"):
        store.create_incident(title="  ", severity="moyen", domain="x", opened_by="bob")
    with pytest.raises(ValueError, match="closed"):
        store.create_incident(title="t", severity="apocalyptique", domain="x", opened_by="bob")
    with pytest.raises(store.IncidentNotFoundError):
        store.get_incident("INC-ghost")


def test_lifecycle_transitions_are_journalled_and_reversible() -> None:
    inc = store.create_incident(
        title="Chaîne d'audit rompue",
        severity="critique",
        domain="conformite",
        opened_by="bob@bank.eu",
    )
    iid = str(inc["incident_id"])
    moved = store.transition_incident(iid, "en_cours", by="claire@bank.eu")
    assert moved["status"] == "en_cours"
    resolved = store.transition_incident(iid, "resolu", by="claire@bank.eu")
    assert resolved["closed_by"] == "claire@bank.eu"
    assert resolved["closed_at"] is not None
    assert store.open_durable_counts() == (0, 0)
    # Re-opening clears the closure stamps — and every move is in the journal.
    reopened = store.transition_incident(iid, "ouvert", by="bob@bank.eu")
    assert reopened["closed_at"] is None
    actions = [e["action"] for e in reopened["journal"]]
    assert actions == [
        "ouverture (manual)",
        "statut → en_cours",
        "statut → resolu",
        "statut → ouvert",
    ]
    with pytest.raises(ValueError, match="closed"):
        store.transition_incident(iid, "perdu", by="bob@bank.eu")


def test_playbook_attach_is_declared_catalogue_only() -> None:
    inc = store.create_incident(
        title="Dérive qualité", severity="moyen", domain="qualite", opened_by="bob@bank.eu"
    )
    iid = str(inc["incident_id"])
    attached = store.attach_playbook(iid, "pb-quality-review", by="claire@bank.eu")
    assert attached["playbook_id"] == "pb-quality-review"
    assert any("pb-quality-review" in e["action"] for e in attached["journal"])
    with pytest.raises(ValueError, match="catalogue"):
        store.attach_playbook(iid, "pb-imaginaire", by="claire@bank.eu")


class _Clock:
    """A scriptable ``datetime`` stand-in: ``now`` reads the scripted instant."""

    current = _dt.datetime(2026, 7, 22, 10, 0, tzinfo=_dt.UTC)
    fromisoformat = _dt.datetime.fromisoformat

    @classmethod
    def now(cls, tz: object = None) -> _dt.datetime:  # noqa: ARG003 — datetime.now signature
        return cls.current


class TestIncidentsAsOf:
    """The durable incidents at T are a journal replay, never today's rows."""

    @staticmethod
    def _script(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(store, "datetime", _Clock)
        _Clock.current = _dt.datetime(2026, 7, 22, 10, 0, tzinfo=_dt.UTC)
        store.create_incident(
            title="Fuite PII", severity="critique", domain="conformite", opened_by="alice"
        )
        inc_id = store.load_incidents()[0]["incident_id"]
        _Clock.current = _dt.datetime(2026, 7, 22, 11, 0, tzinfo=_dt.UTC)
        store.transition_incident(inc_id, "en_cours", by="bob")
        _Clock.current = _dt.datetime(2026, 7, 22, 11, 30, tzinfo=_dt.UTC)
        store.attach_playbook(inc_id, "pb-pii-purge", by="bob")
        _Clock.current = _dt.datetime(2026, 7, 22, 12, 0, tzinfo=_dt.UTC)
        store.transition_incident(inc_id, "resolu", by="carol")
        _Clock.current = _dt.datetime(2026, 7, 22, 13, 0, tzinfo=_dt.UTC)
        store.create_incident(
            title="Dérive qualité", severity="moyen", domain="qualite", opened_by="alice"
        )

    def test_mid_life_state_is_replayed_not_todays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._script(monkeypatch)
        folded = store.incidents_as_of(_dt.datetime(2026, 7, 22, 11, 45, tzinfo=_dt.UTC))
        assert len(folded) == 1  # the 13h incident does not exist at T
        one = folded[0]
        assert one["status"] == "en_cours"  # today's store says "resolu"
        assert one["playbook_id"] == "pb-pii-purge"
        assert one["closed_at"] is None
        assert len(one["journal"]) == 3  # ouverture + statut + playbook, ≤ T only

    def test_closure_and_late_rows_appear_at_their_instant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._script(monkeypatch)
        folded = store.incidents_as_of(_dt.datetime(2026, 7, 22, 12, 30, tzinfo=_dt.UTC))
        assert len(folded) == 1
        assert folded[0]["status"] == "resolu"
        assert folded[0]["closed_by"] == "carol"

        later = store.incidents_as_of(_dt.datetime(2026, 7, 22, 14, 0, tzinfo=_dt.UTC))
        assert len(later) == 2

        before = store.incidents_as_of(_dt.datetime(2026, 7, 22, 9, 0, tzinfo=_dt.UTC))
        assert before == []
