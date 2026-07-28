"""B2 — the 26 operator mutations are no longer anonymous.

Audit 2026-07-10, **P0 `broken-access-control`** — route.ts:25/81 · observability.py (26x) ·
main.py:310.

``ALWAYS_PUBLIC`` contained ``observability`` and the BFF's POST branch checked only the path
segment — no session, no role. The proxy then attached the *service bearer* on the caller's
behalf, so an anonymous visitor's mutation reached the agent perfectly authenticated, and the
agent mounted the observability router with no ``dependencies=`` at all.

What those 26 endpoints do: promote an agent to production, rewrite runtime configuration,
switch a guardrail off, decide curation, mutate the governance stores.

Why ``require_bearer`` alone could not have closed it — and this is the crux — the bearer
answers "did this come from our frontend?", never "who is asking?". The BFF holds it and
attaches it for everyone. Only the HMAC-signed operator assertion, minted from a verified
NextAuth session with a key the browser never holds, answers the second question.

Every test below fails against the pre-fix tree, where the router carried no dependency.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.api.routes.observability import mutations, router as observability_router
from tessera.api.security import require_operator
from tessera.settings import get_settings

# 26 at the 2026-07-10 audit; +3 on 2026-07-17 (lot 10): the durable-incident
# open/transition/playbook acts. +1 on 2026-07-17 (lot 7): the evidence-pack
# freeze (governed, ratchet-driven). +2 on 2026-07-17 (lot 4): automations bulk
# rules-state and the approval decision — both governed, both driven by the
# attribution ratchet (test_governed_acts_name_their_author.py).
# +2 on 2026-07-18 (ADR 0037): the prompt-overlay propose/review lifecycle —
# governed acts 13/14, driven by the attribution ratchet; review additionally
# sits behind require_superadmin.
EXPECTED_MUTATION_COUNT = 34

#: One representative mutation, named for what it does: it puts an agent into production.
#: If any single endpoint in this router deserves an authorization test, it is this one.
A_MUTATION_THAT_MATTERS = "/observability/agents/release"


def _mutation_paths() -> list[str]:
    return sorted({route.path for route in mutations.router.routes})  # type: ignore[attr-defined]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(observability_router)
    return app


@pytest.fixture
def operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure a real signing key, so the assertions minted below actually verify."""
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr("test-key"))


@pytest.fixture
def anonymous_client() -> TestClient:
    """A client with no operator assertion — i.e. anyone on the internet."""
    return TestClient(_app(), raise_server_exceptions=False)


def _client_as(role: str) -> TestClient:
    """A client carrying a genuinely signed operator assertion for ``role``.

    Not a stub: the token is minted with the real HMAC and verified by the real
    ``resolve_request_context``. What is being tested is the authorization decision taken
    *after* authentication succeeds — the case the anonymous tests cannot reach.
    """
    token = issue_operator_assertion(principal=role, role=role)
    return TestClient(
        _app(),
        headers={OPERATOR_ASSERTION_HEADER: token},
        raise_server_exceptions=False,
    )


def test_every_operator_mutation_is_accounted_for() -> None:
    """The audit counted 26; the count is frozen. A new one must not slip in ungated."""
    assert len(mutations.router.routes) == EXPECTED_MUTATION_COUNT
    methods = {m for route in mutations.router.routes for m in route.methods}  # type: ignore[attr-defined]
    assert methods == {"POST"}


def test_the_mutation_router_declares_its_guard() -> None:
    """The guard lives on the router, so a new mutation cannot be added without it."""
    assert mutations.router.dependencies, "the mutations router carries no dependency"


@pytest.mark.parametrize("path", _mutation_paths())
def test_an_anonymous_caller_cannot_reach_a_mutation(
    anonymous_client: TestClient, path: str
) -> None:
    """The finding, closed, endpoint by endpoint.

    Pre-fix every one of these returned a 2xx (or a validation error on the body) to a
    caller with no session whatsoever — including `/observability/agents/release`, which
    promotes an agent to production.

    401 is asserted specifically: a 422 would mean the body was validated FIRST and the
    request had already entered the handler's blast radius.
    """
    response = anonymous_client.post(path, json={})

    assert response.status_code == 401, (
        f"{path} answered {response.status_code} to an anonymous caller — "
        "a mutation must refuse before it looks at the body"
    )
    assert response.json()["detail"] == "operator authentication required"


def test_the_public_reads_are_untouched() -> None:
    """Reads stay public — the cockpit's declared posture. Only the mutation plane is gated.

    Guards against over-correcting: locking the public GETs would 404 the whole cockpit
    for the operators this change is meant to protect. 126 at the audit; +2 on
    2026-07-17 (lot 7): the evidence-pack manifest and verify reads (counts,
    digests, integrity verdicts — no subject data). +2 on 2026-07-17 (lot 9):
    the recouvrement queue/case reads — subject-scoped, guarded by the pii
    router's require_subject_reader (NOT public; counted here because the
    freeze spans every GET on the observability router). +1 on 2026-07-21:
    the launcher's guard-activity aggregate (messages checked/blocked since
    midnight — ADR 0009 showcase-safe day counters, no subject data).
    +1 on 2026-07-22: the `/comprendre` proof aggregate (fleet witnesses,
    day guard totals, release buckets and chain freshness; no subject data).
    +1 on 2026-07-28: GET /observability/fleet-snapshot — the per-agent snapshot
    fan-out collapsed into one bulk read; the SAME aggregate envelopes as
    /observability/snapshot, one per registered agent, no subject data.
    +1 on 2026-07-28: GET /observability/batch — a page's individual public-aggregate
    card reads multiplexed into one response (the SAME handlers, byte-identical panels,
    an allowlist of public keys only; subject-scoped reads deliberately excluded).
    """
    from tessera.api.security import require_operator

    read_routes = [
        route for route in observability_router.routes if "GET" in getattr(route, "methods", set())
    ]
    assert len(read_routes) == 134
    for route in read_routes:
        guards = [dep.dependency for dep in getattr(route, "dependencies", [])]
        assert require_operator not in guards, (
            f"{route.path} is a read and must not require an operator"  # type: ignore[attr-defined]
        )


class TestTheAuditorReadsAndDoesNotWrite:
    """Least privilege on the mutation plane (operator decision, 2026-07-12).

    ``AuthState.OPERATOR`` is ONE BIT. It says *an* operator is asking; it never says *which*.
    An ``auditor`` sets that bit, so gating the mutations on it alone — which is what the rest
    of this file proves the fix does — still left the audit role able to promote an agent to
    production, rewrite runtime configuration and switch a guardrail off.

    ADR 0009 has said the opposite since 2026-06-03: *"auditor (audit + budget + eval detail,
    **not settings**)"*. Only the front ever enforced it, and only by choosing which pages to
    render — which is not access control, it is decoration. An audit role that can change what
    it audits is not an audit role.

    Every test in this class fails against the tree that closed B2 but read no role: there,
    the auditor's signed assertion sailed through ``require_operator`` and got a 2xx/422.
    """

    def test_an_auditor_is_refused_every_mutation(self, operator_key: None) -> None:
        """403 on all 26 — authenticated, and still not allowed."""
        client = _client_as("auditor")

        refused = {path: client.post(path, json={}).status_code for path in _mutation_paths()}

        assert set(refused.values()) == {
            403
        }, f"an auditor reached a mutation: {sorted(p for p, s in refused.items() if s != 403)}"

    def test_the_refusal_is_403_and_not_401(self, operator_key: None) -> None:
        """The two refusals mean different things and must not be collapsed.

        401 says "we do not know who you are" — retry with credentials. The auditor HAS
        credentials, and they are valid; the answer is still no. Telling them to log in again
        is a lie about what went wrong, and it invites them to go looking for a second account.
        """
        anonymous = TestClient(_app(), raise_server_exceptions=False)
        assert anonymous.post(A_MUTATION_THAT_MATTERS, json={}).status_code == 401

        auditor = _client_as("auditor").post(A_MUTATION_THAT_MATTERS, json={})
        assert auditor.status_code == 403
        assert auditor.json()["detail"] == "this role is read-only on the cockpit control plane"

    def test_an_auditor_still_reads(self, operator_key: None) -> None:
        """The other half of the decision: the reads stay open to the auditor.

        This is the test that keeps the fix honest. Least privilege is not "lock everything" —
        the auditor's whole job is to read the audit trail, and a change that quietly took that
        away while claiming to enforce ADR 0009 would have broken the role it was protecting.
        """
        assert _client_as("auditor").get("/observability/access").status_code == 200

    @pytest.mark.parametrize("role", ["admin", "superadmin"])
    def test_the_roles_with_write_authority_are_admitted(
        self, operator_key: None, role: str
    ) -> None:
        """The legitimate operator is unaffected — the point is least privilege, not paralysis.

        Asserted on the GUARD, not through a handler: ``require_operator`` returning cleanly IS
        the authorization decision, and calling it directly says so without dragging 26 handlers
        (and their real network I/O) into an authz test. The mutations' own behaviour is not
        what is under test here — who is allowed to reach them is.
        """
        token = issue_operator_assertion(principal=role, role=role)
        request = Request(
            {
                "type": "http",
                "headers": [(OPERATOR_ASSERTION_HEADER.encode(), token.encode())],
            }
        )

        require_operator(request)  # must not raise

    def test_the_business_plane_role_is_not_a_platform_administrator(
        self, operator_key: None
    ) -> None:
        """`collections` verifies as OPERATOR, and must still not administer the platform.

        Not in the operator's brief, and worth stating plainly: `collections` is recouvrement's
        *business* role (ADR 0010 Phase C). The front has always refused it the cockpit
        (`hasCockpitAccess`), but its assertion verifies as ``AuthState.OPERATOR`` all the same
        — so the AGENT was laxer than its own edge, and a `dedicated-ui` assertion replayed
        against ``/observability/agents/release`` would have been honoured. Reading the role
        closes that gap in the same stroke; leaving it open would have meant shipping a guard
        that the edge already enforced more strictly than the authority behind it.
        """
        assert _client_as("collections").post(A_MUTATION_THAT_MATTERS, json={}).status_code == 403

    def test_the_matrix_the_cockpit_displays_is_the_matrix_it_enforces(self) -> None:
        """The cockpit was *telling operators* the auditor could not act. It was a drawing.

        `/admin/roles-acces` renders `ROLE_CAPS` (`observability/rbac.py`), whose own docstring
        calls it *"the **real** access model … the roles the system **actually enforces**"*. It
        grants `release` to admin/superadmin and gives the auditor only `cockpit_lecture` +
        `audit_lecture`. `observability/access.py` describes the role to the operator in as many
        words: *"Lecture seule sur le cockpit et les journaux d'audit, **sans action**."*

        Both statements were true on screen and false on the wire — `POST
        /observability/agents/release` honoured an auditor's assertion. A governance page that
        asserts an access model the runtime does not enforce is not a governance page; it is the
        same class of defect as serving a fixture as real data.

        This ratchet ties the claim to the guard, in both directions: a role the matrix shows as
        able to `release` MUST hold write authority, and a role it shows as read-only must not.
        Whichever side someone edits next, the other has to move with it.
        """
        from tessera.api.operator import MUTATION_ROLES
        from tessera.observability.rbac import ROLE_CAPS

        displayed_writers = set()
        for role, spec in ROLE_CAPS.items():
            caps = spec["caps"]
            assert isinstance(caps, list)
            if "release" in caps:
                displayed_writers.add(role)

        assert displayed_writers == MUTATION_ROLES, (
            "the roles-and-access page and the mutation guard disagree about who may act: "
            f"the page shows {sorted(displayed_writers)} as able to release, "
            f"the guard admits {sorted(MUTATION_ROLES)}"
        )
