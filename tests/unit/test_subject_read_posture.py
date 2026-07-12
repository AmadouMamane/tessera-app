"""The subject-read posture, PINNED — a conscious choice, dated, not an oversight (ADR 0025).

Audit 2026-07-12, **F-C**. One line in ``api/operator.py``::

    SUBJECT_READ_ROLES: frozenset[str] = (
        OPERATOR_ROLES  # {admin, auditor, superadmin, collections}
    )

So **every verified operator may read every subject** — transcript, memory inventory, turn detail
— including a ``collections`` operator, whose console exists to work one debt file at a time.

The anonymous hole is closed, and that was the emergency: before F-4 the same endpoints returned
any customer's complete transcript to **anyone on the internet**, no credential at all. What
replaced it is *"any verified operator"*. That is a large real improvement, and it is **not a
defensible GDPR posture for a real tenant**, because it contains no notion of *purpose*: nothing
anywhere says "this subject is mine to look at" (Art. 5(1)(b), purpose limitation).

**This file does not fix that.** Binding an operator to a subject — by dossier, by tenant, by
declared purpose — is a product decision with real costs on every read path, and ADR 0025 lays
out the three shapes and declines to choose. What this file does is make the posture a *fact on
the record* rather than an emergent property of a frozenset:

* it asserts what the system does **today**, out loud, in a test whose name says so;
* it therefore **fails the day someone changes it** — which is the point. Narrowing the posture is
  the right thing to do and must be a *reviewed* edit to this file and to ADR 0025, not a silent
  tightening that breaks a console nobody was watching. Widening it further is impossible: it is
  already maximal, and that sentence IS the finding.

A test that pins a known gap is not a test that blesses it. It is the difference between a
weakness someone chose and a weakness nobody noticed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tessera.api.main import build_app
from tessera.api.operator import (
    MUTATION_ROLES,
    OPERATOR_ASSERTION_HEADER,
    OPERATOR_ROLES,
    SUBJECT_READ_ROLES,
    issue_operator_assertion,
)
from tessera.authz import Surface
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI

#: A subject with no relationship to recouvrement whatsoever — not a debt file, not a case, not a
#: dossier the collections console has ever touched. That is the whole point of the probe.
A_STRANGER_TO_RECOUVREMENT = str(uuid.UUID(int=0xC0FFEE))


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return build_app()


@pytest.fixture
def _operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings().api, "operator_assertion_signing_key", SecretStr("k"))


@pytest.fixture
def _no_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Stub the store, so the probe measures the AUTHORIZATION and nothing else.

    A 500 from an absent Postgres would read exactly like a 403 to a careless assertion, and this
    file exists to say something precise about who is allowed to read whom.
    """

    async def _empty(*_a: object, **_k: object) -> list[object]:
        return []

    def _noop(**_k: Any) -> None:
        return None

    monkeypatch.setattr("tessera.memory.persistent.list_subject_memories", _empty)
    monkeypatch.setattr("tessera.memory.governance.audit_memory", _noop)
    yield


def _read_subject_as(app: FastAPI, *, principal: str, role: str) -> int:
    surface = Surface.DEDICATED_UI if role == "collections" else Surface.COCKPIT_EMBEDDED
    token = issue_operator_assertion(principal=principal, role=role, surface=surface)
    client = TestClient(app, raise_server_exceptions=False)
    return client.get(
        f"/memory/{A_STRANGER_TO_RECOUVREMENT}/items",
        headers={OPERATOR_ASSERTION_HEADER: token},
    ).status_code


@pytest.mark.usefixtures("_operator_key", "_no_store")
@pytest.mark.parametrize("role", sorted(OPERATOR_ROLES))
def test_today_every_operator_role_reads_every_subject(app: FastAPI, role: str) -> None:
    """THE POSTURE, 2026-07-12. Every role. Any subject. Including ``collections``.

    If this goes red, someone has narrowed the read plane — which is the RIGHT direction, and
    which must not happen by accident. Read ADR 0025, decide which of the three shapes was
    implemented, and delete this test in the same commit that closes the gap it names.
    """
    status = _read_subject_as(app, principal=f"{role}@bank.eu", role=role)

    assert status == 200, (
        f"the {role!r} operator was refused a subject read ({status}). If that refusal is "
        "deliberate, the posture recorded in ADR 0025 has changed and this test must change with "
        "it — in the same commit, in review. If it is not deliberate, a console just broke."
    )


@pytest.mark.usefixtures("_operator_key", "_no_store")
def test_the_recouvrement_operator_reads_a_subject_that_is_none_of_its_business(
    app: FastAPI,
) -> None:
    """The finding, stated at its sharpest — and asserted, because it is true.

    ``collections`` is the role of one console, working one debt file at a time. It can read the
    memory inventory of a customer who has no debt, no case, and no relationship with recouvrement
    at all. Nothing in the system says otherwise, because nothing in the system has any notion of
    *"this subject is mine"*.

    The trail now records that this happened, and by whom (ADR 0024) — which makes it *visible*,
    and does not make it *right*. Accountability after the fact is not purpose limitation.
    """
    status = _read_subject_as(app, principal="julie@bank.eu", role="collections")

    assert status == 200, "the posture changed — update ADR 0025 in the same breath"


def test_the_read_plane_is_deliberately_wider_than_the_write_plane() -> None:
    """The asymmetry is the doctrine, and it is the one part of this that IS decided.

    The auditor **reads and does not write**, on every plane. So the read set is deliberately not
    narrower than "any operator" — an audit role that cannot read what it audits is not an audit
    role — while the write set is strictly narrower, because an audit role that can change what it
    audits is not one either. That asymmetry is intentional and stays.

    What is NOT decided is the orthogonal question: not *which roles* may read, but *which
    subjects*. Today the answer is "all of them", and ADR 0025 is where that gets settled.
    """
    assert SUBJECT_READ_ROLES == OPERATOR_ROLES
    assert MUTATION_ROLES < OPERATOR_ROLES, "the write plane must stay strictly narrower"
    assert "auditor" in SUBJECT_READ_ROLES
    assert "auditor" not in MUTATION_ROLES
    # And the sentence this whole file exists to make un-ignorable:
    assert SUBJECT_READ_ROLES == OPERATOR_ROLES, (
        "PII reads are gated by ROLE, not by PURPOSE. Every operator reads every subject. "
        "Conscious, dated, and open: ADR 0025."
    )
