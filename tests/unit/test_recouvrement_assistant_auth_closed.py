"""F-1 — the recouvrement assistant's two POSTs are no longer anonymous.

Audit 2026-07-12, **P0 F-1** — `routes/recouvrement_assistant.py:61-107` · `main.py:351` ·
`app/api/recouvrement-assistant/{message,action}/route.ts`.

The exact class closed on 2026-07-11 for the 26 cockpit mutations, missed here: the router
was mounted with no dependency at all, and the BFF proxied anonymous visitors through with
the service bearer attached. Both routes write — the message workflow emits ~30 business
events per turn into the ledger, the action route executes governed artifact transitions.
And the action route's ``requested_by`` — the name the ledger records as having acted —
was a body field with a default: the audit attribution was whatever the caller typed.

The fix mirrors the cockpit's, with the business plane's role set
(``COLLECTIONS_MUTATION_ROLES``): ``collections`` acts, the ``auditor`` reads and does not
write, an anonymous caller is refused before the body is parsed, and ``requested_by``
derives from the verified assertion — the body field is gone from the contract entirely.

Every test in the first two classes fails against the pre-fix tree.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from tessera.api.operator import (
    COLLECTIONS_MUTATION_ROLES,
    MUTATION_ROLES,
    OPERATOR_ASSERTION_HEADER,
    issue_operator_assertion,
)
from tessera.api.routes import recouvrement_assistant
from tessera.api.security import require_collections_operator
from tessera.authz import Actor, Surface
from tessera.settings import get_settings

#: Two handlers, each registered on its canonical path and its ``/api`` alias.
EXPECTED_ROUTE_COUNT = 4

_ALL_PATHS = [
    "/recouvrement-assistant/message",
    "/api/recouvrement-assistant/message",
    "/recouvrement-assistant/action",
    "/api/recouvrement-assistant/action",
]

#: A minimal, otherwise-valid action body — what a real console turn sends.
_ACTION_BODY: dict[str, Any] = {
    "case_id": "RC-2048",
    "artifact": {"id": "RC-2048-reminder-v1", "type": "reminder_draft_v1"},
    "action_name": "insert_artifact_in_case",
}


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(recouvrement_assistant.router)
    return app


@pytest.fixture
def operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a real signing key, so the assertions minted below actually verify."""
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr("test-key"))


def _client_as(role: str, principal: str | None = None) -> TestClient:
    """A client carrying a genuinely signed operator assertion for ``role``.

    Minted on the ``dedicated-ui`` surface — recouvrement's own console, the surface the
    BFF now mints for these routes. Not a stub: real HMAC, verified by the real
    ``resolve_request_context``.
    """
    token = issue_operator_assertion(
        principal=principal or role, role=role, surface=Surface.DEDICATED_UI
    )
    return TestClient(
        _app(),
        headers={OPERATOR_ASSERTION_HEADER: token},
        raise_server_exceptions=False,
    )


def test_both_routes_and_both_aliases_are_accounted_for() -> None:
    """Two POSTs, two paths each. A new route added here inherits the guard — but if a
    THIRD handler appears, this count forces the author past this file on the way in."""
    assert len(recouvrement_assistant.router.routes) == EXPECTED_ROUTE_COUNT
    methods = {
        m
        for route in recouvrement_assistant.router.routes
        for m in route.methods  # type: ignore[attr-defined]
    }
    assert methods == {"POST"}


def test_the_router_declares_its_guard() -> None:
    """The guard lives on the router, not the mount site — the ``mutations.py`` model.

    Declared here, a route added to this module cannot forget it; declared at the mount,
    a second mount (or a test app, like this file's) silently loses it.
    """
    guards = [dep.dependency for dep in recouvrement_assistant.router.dependencies]
    assert require_collections_operator in guards


@pytest.mark.parametrize("path", _ALL_PATHS)
def test_an_anonymous_caller_is_refused_before_the_body_is_read(path: str) -> None:
    """The finding, closed — on the canonical paths AND the ``/api`` aliases.

    Pre-fix, an anonymous POST entered the workflow (or got a 422, meaning the body was
    validated first). 401 is asserted specifically: the refusal must precede any look at
    the payload, because reaching validation already puts the caller inside the
    handler's blast radius.
    """
    client = TestClient(_app(), raise_server_exceptions=False)

    response = client.post(path, json={})

    assert response.status_code == 401, (
        f"{path} answered {response.status_code} to an anonymous caller — "
        "a business-plane write must refuse before it looks at the body"
    )
    assert response.json()["detail"] == "operator authentication required"


class TestTheBusinessPlaneRoleSet:
    """``COLLECTIONS_MUTATION_ROLES`` — who acts on recouvrement, and who does not."""

    def test_collections_is_admitted(self, operator_key: None) -> None:
        """The role this console exists for passes the guard.

        This is the one behaviour ``require_operator`` could not provide — its role set
        is the cockpit control plane's, which refuses ``collections`` by design. Asserted
        on the guard directly: its clean return IS the authorization decision, without
        dragging the store-backed workflow into an authz test.
        """
        token = issue_operator_assertion(
            principal="collections", role="collections", surface=Surface.DEDICATED_UI
        )
        request = Request(
            {
                "type": "http",
                "headers": [(OPERATOR_ASSERTION_HEADER.encode(), token.encode())],
            }
        )

        session = require_collections_operator(request)  # must not raise

        assert session.subject_id == "collections"

    @pytest.mark.parametrize("role", ["admin", "superadmin"])
    def test_the_platform_writers_may_supervise(self, operator_key: None, role: str) -> None:
        """admin/superadmin keep write authority here, as on every plane."""
        token = issue_operator_assertion(principal=role, role=role, surface=Surface.DEDICATED_UI)
        request = Request(
            {
                "type": "http",
                "headers": [(OPERATOR_ASSERTION_HEADER.encode(), token.encode())],
            }
        )

        require_collections_operator(request)  # must not raise

    def test_the_auditor_reads_and_does_not_write_here_either(self, operator_key: None) -> None:
        """403, not 401 — authenticated, known, and still refused (ADR 0009 doctrine).

        The auditor may *enter* the recouvrement console (the front's
        ``hasCollectionsAccess``) — and acting from it is a different right. An audit
        role that can write what it audits is not an audit role, on any plane.
        """
        response = _client_as("auditor").post("/recouvrement-assistant/action", json=_ACTION_BODY)

        assert response.status_code == 403
        assert response.json()["detail"] == (
            "this role is read-only on the recouvrement business plane"
        )

    def test_the_two_planes_differ_by_exactly_collections(self) -> None:
        """The whole point of the second role set, frozen as arithmetic.

        Wider, and ``collections`` would administer the platform; narrower, and the
        business console loses its own role. Whoever edits either set must move the
        other — or this line — with it.
        """
        assert MUTATION_ROLES | {"collections"} == COLLECTIONS_MUTATION_ROLES


class TestAttributionComesFromTheAssertion:
    """``requested_by`` — who the ledger says acted — is no longer the caller's to choose."""

    def test_a_body_that_asserts_an_identity_is_a_contract_violation(
        self, operator_key: None
    ) -> None:
        """422 on ``requested_by`` in the body — the spoof vector is dead, not ignored.

        ``extra="forbid"`` turns the old field into a validation error, so a client that
        still sends it fails loudly instead of silently having its claim dropped. Loud
        beats quiet here: a caller who *believes* they control attribution should learn
        otherwise at the contract, not by reading the ledger later.
        """
        client = _client_as("collections")

        response = client.post(
            "/recouvrement-assistant/action",
            json={**_ACTION_BODY, "requested_by": "Julie Dubois"},
        )

        assert response.status_code == 422

    def test_the_ledger_records_the_verified_principal(
        self, operator_key: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The workflow receives the assertion's principal — the name that was PROVEN.

        The workflow itself is stubbed (store-backed, ~30 ledger events — not an authz
        concern); what is under test is the seam: the route must pass the identity the
        HMAC verified, and nothing else, because the body no longer carries one.

        What crosses the seam is now an :class:`Actor`, not a ``str``, and that is the half of
        F-1 this test could not previously reach. It asserted ``requested_by == "julie.moreau"``
        and passed — while one call below, ``run_recouvrement_action_workflow_v1`` still declared
        ``requested_by: str = "Julie Dubois"``. The seam was right and the floor beneath it was
        rotten: any caller that simply *omitted* the argument got a fabricated human, and nine
        tests did exactly that, in green. A ``str`` parameter cannot tell those two apart. An
        ``Actor`` has no default to fall through to, so there is no longer a second answer.
        """
        captured: dict[str, Any] = {}

        def _capture(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {"ok": True}

        monkeypatch.setattr(recouvrement_assistant, "run_recouvrement_action_workflow_v1", _capture)
        client = _client_as("collections", principal="julie.moreau")

        response = client.post("/recouvrement-assistant/action", json=_ACTION_BODY)

        assert response.status_code == 200
        assert "requested_by" not in captured, "the caller-chosen name has no way in at all"
        assert captured["actor"] == Actor(principal="julie.moreau", role="collections")
