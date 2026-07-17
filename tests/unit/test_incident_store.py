"""Lot 10 — the durable incident store (create-the-source).

The store starts EMPTY (an incident records that someone decided something was
one); every act on it is attributed and journalled; vocabularies are closed.
"""

from __future__ import annotations

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
