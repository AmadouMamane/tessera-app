"""The attach/detach act is governed: attributed, journalled S1, silent on a no-op.

This was the registry's last named rail debt (OT-01 / Connaissances): the
``source-state`` route mutated the durable store behind ``require_operator`` but
wrote NOTHING to the chain — an act with no entry has no author, so the sheet
could show no per-source trace. The witnesses below capture the entry where the
attribution ratchet does — at ``_append_to_chain``, the fully built entry — and
assert the three facts the substrate rests on:

* the entry names the verified principal (ADR 0024), the target names the object;
* the entry lands BEFORE the store write (a failed store leaves a visible
  attempt, never a silent act);
* a no-op writes nothing — "nothing changed" must never read as "change recorded".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tessera.api.main import build_app
from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.guard import audit as audit_mod
from tessera.observability import knowledge as knowledge_mod
from tessera.settings import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

PRINCIPAL = "bob@bank.eu"


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The real assembly — the route is exercised through its real guard."""
    return build_app()


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Record ledger appends and store writes in the order they happen.

    The chain capture sits at ``_append_to_chain`` (the entry is the fact); the
    store is stubbed so the test owns the prior state and the payload rebuild
    does not touch postgres.
    """
    recorded: list[tuple[str, Any]] = []
    monkeypatch.setattr(get_settings().api, "operator_assertion_signing_key", SecretStr("k"))
    monkeypatch.setattr(
        audit_mod,
        "_append_to_chain",
        lambda entry, _sink, _file: recorded.append(("ledger", entry)),
    )
    monkeypatch.setattr(
        knowledge_mod,
        "source_state_of",
        lambda _cat: {"attached": True, "active": True},
    )
    monkeypatch.setattr(
        knowledge_mod,
        "set_source_state",
        lambda cat, **kw: recorded.append(("store", (cat, kw))),
    )

    async def _payload(_lang: str = "fr") -> dict[str, object]:
        return {}

    monkeypatch.setattr(knowledge_mod, "build_connaissances", _payload)
    return recorded


def _mutate(app: FastAPI, body: dict[str, Any]) -> int:
    token = issue_operator_assertion(principal=PRINCIPAL, role="admin")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/observability/agent-connaissances/source-state",
        json=body,
        headers={OPERATOR_ASSERTION_HEADER: token},
    )
    return response.status_code


def test_a_state_change_is_journalled_with_its_author_before_the_store(
    app: FastAPI, events: list[tuple[str, Any]]
) -> None:
    status = _mutate(app, {"key": "cnil", "active": False})

    assert status == 200
    kinds = [kind for kind, _ in events]
    assert kinds == ["ledger", "store"], (
        f"expected the S1 entry BEFORE the store write, got {kinds} — the reverse order loses "
        "the act on exactly the runs where the store fails"
    )
    entry = events[0][1]
    assert entry["target"] == "knowledge_source.cnil"
    assert entry["actor"] == PRINCIPAL, "the act names the verified principal, nobody else"
    assert entry["arguments"]["active"] is False
    assert entry["arguments"]["was_active"] is True


def test_a_noop_writes_no_entry(app: FastAPI, events: list[tuple[str, Any]]) -> None:
    status = _mutate(app, {"key": "cnil", "active": True})  # already the prior state

    assert status == 200
    kinds = [kind for kind, _ in events]
    assert "ledger" not in kinds, (
        "the requested state already held — an entry here would record a change that never "
        "happened"
    )
    assert kinds == ["store"], "the idempotent store write still runs"


def test_an_unknown_source_is_refused_before_any_act(
    app: FastAPI, events: list[tuple[str, Any]]
) -> None:
    status = _mutate(app, {"key": "not-a-source", "active": False})

    assert status == 404
    assert events == [], "a refused act leaves no trace and mutates nothing"
