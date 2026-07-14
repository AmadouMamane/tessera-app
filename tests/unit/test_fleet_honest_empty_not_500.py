"""Observing nothing is not a failure to observe — and it must never be a 500.

`/observability/fleet` answered **500 on a virgin install**: no eval run, no manifest, and the
component whose entire job is to observe could not observe its own absence of data.

The cause is subtle, and it is the reason this file exists rather than a one-line patch.
`compute_fleet` did **not raise** — so the handler's ``except`` never saw it. It returned, quite
correctly, ``release=None`` (no eval has ever run) and ``level=None`` (no AgentSpec manifest):
the honest-empty the module documents in so many words. But the ``response_model`` had been
**generated from 31 live samples** in which every agent happened to have both, so those fields
were declared required and non-null. FastAPI validated the RESPONSE, matched neither arm of the
union — not ``FleetPayload`` (nulls where non-null was promised), not ``FleetUnavailable``
(``available`` is True) — and served a 500.

    *A ``try``/``except`` catches an exception. A partial-but-successful return walks past it.*
    *And a sample shows what WAS there; it can never show what is ALLOWED to be absent.*

The tests below are written through the **real router with a TestClient**, never by calling
`compute_fleet` in isolation: the bug lives in FastAPI's RESPONSE validation, which a direct
function call does not traverse. A unit test on the function would have been green all along —
that is precisely how this survived.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING, get_args, get_type_hints

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tessera.api.routes.observability import fleet as fleet_routes, router as observability_router
from tessera.api.routes.observability.schemas_fleet import (
    FleetAgentsItem,
    FleetAgentsItemNorthStarEvidence,
    FleetPayload,
)
from tessera.observability.fleet import FleetAgent, FleetData

if TYPE_CHECKING:
    from pydantic import BaseModel

#: A fleet in its most honest state: the registry knows the agent, and NOTHING has happened to it.
#: No conversation, no eval, no manifest. Every field the contract promises is present; three of
#: them are null, and null is the truth. This is what `compute_fleet` really returns there.
VIRGIN_AGENT: FleetAgent = {
    "id": "support-client",
    "name": "Support Client",
    "owner": "ops",
    "audience": "customer",
    "description": "",
    "tags": [],
    "conversations": 0,
    "turns": 0,
    "messages": 0,
    "escalation_rate": 0.0,
    "latency_ms": None,
    "handoffs_in": 0,
    "handoffs_out": 0,
    "health": "grey",
    "release": None,  # no eval has ever run
    "level": None,  # no AgentSpec manifest
    "level_declared": None,
    "level_evidence": "dormant",
    "observable": False,
    "testable": False,
    "north_star": None,
    "pending_business_items": 0,
}

#: An agent that DOES declare a north-star metric, which no run has ever scored.
#:
#: This one exists because the fixture above was **less honest than reality**, and only a live
#: virgin install exposed it: with `north_star: None` the payload never reached
#: `north_star.evidence.last_checked_at` — declared `str`, returned `None` by a producer whose own
#: docstring says "A metric no run ever produced yields zeros and ``None`` — the genuine zero-data
#: case". The same disease, one level deeper, and a test fixture that stopped short of it.
NEVER_SCORED_AGENT: FleetAgent = {
    **VIRGIN_AGENT,
    "id": "recouvrement",
    "name": "Recouvrement",
    "north_star": {
        "agent_id": "recouvrement",
        "key": "contact_window_compliance",
        "north_star": True,
        "status": "no_data",
        "value": None,
        "evidence": {"observed_runs": 0, "checks": 0, "last_checked_at": None},
    },
}

VIRGIN_FLEET: FleetData = {
    "agents": [VIRGIN_AGENT, NEVER_SCORED_AGENT],
    "org": {"conversations": 0, "turns": 0},
    "naive_sum_conversations": 0,
    "shared_conversations": 0,
    "dedup_saved": 0,
    "handoff_events": 0,
    "handoff_conversations": 0,
    "handoff_conversations_seen_shared": 0,
}


def _client() -> TestClient:
    """The REAL router, so the response passes through FastAPI's response validation."""
    app = FastAPI()
    app.include_router(observability_router)
    return TestClient(app, raise_server_exceptions=False)


def _returns_a_raw_available_dict(route: str) -> bool:
    """Does this handler ``return`` a bare dict stamped ``{"available": True, ...}``?

    That is the shape with the hole: an unvalidated dict handed to FastAPI, whose only contract
    is a `response_model` generated from samples. Whether it splats a compute or lists its keys
    by hand is beside the point — what matters is that **nothing checked it before it was served**.

    Asked of the SYNTAX TREE, never of the source text. The first version of this witness read the
    raw file and went red on the very docstring that explains the bug, because the prose quotes the
    pattern it forbids. Then, told to forbid the ``**`` splat, it went red on the FIX — whose
    `model_validate({"available": True, **data})` splats too, but *into a validator*. A witness
    that cannot tell code from prose, or a served value from a checked one, is not looking at the
    thing. It asks the precise question now: what does this handler RETURN?
    """
    tree = ast.parse(Path(fleet_routes.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if not any(
            isinstance(dec, ast.Call)
            and dec.args
            and isinstance(dec.args[0], ast.Constant)
            and dec.args[0].value == f"/observability/{route}"
            for dec in node.decorator_list
        ):
            continue
        return any(
            isinstance(stmt, ast.Return) and _is_available_true_dict(stmt.value)
            for stmt in ast.walk(node)
        )
    msg = f"no handler found for /observability/{route} — the witness cannot see its target"
    raise AssertionError(msg)


def _is_available_true_dict(value: ast.expr | None) -> bool:
    """A dict literal carrying ``"available": True`` — served as-is, checked by nobody."""
    if not isinstance(value, ast.Dict):
        return False
    return any(
        isinstance(key, ast.Constant)
        and key.value == "available"
        and isinstance(val, ast.Constant)
        and val.value is True
        for key, val in zip(value.keys, value.values, strict=True)
        if key is not None
    )


class TestAnEmptyLedgerIsAFactNotAnOutage:
    def test_a_virgin_install_answers_200_and_not_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The bug, reproduced by the path that has it. This was a 500."""

        async def _virgin(*_a: object, **_k: object) -> FleetData:
            return VIRGIN_FLEET

        monkeypatch.setattr(fleet_routes.fleet_mod, "compute_fleet", _virgin)

        response = _client().get("/observability/fleet")

        assert response.status_code == 200, (
            f"a fleet with no eval and no manifest answered {response.status_code}. "
            "Observing nothing is not a failure to observe."
        )

    def test_it_still_hands_over_the_fleet_rather_than_hiding_behind_available_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`available: false` here would be a LIE OF OMISSION, and a regression.

        An agent that has done nothing is a fact worth rendering: the operator of a fresh
        install must still see their fleet, with an honest "Éval non exécutée" in the release
        column. Degrading the whole payload to `available: false` would blank the page and
        destroy information we HAVE — the very failure this route's honest-empty exists to avoid.
        """

        async def _virgin(*_a: object, **_k: object) -> FleetData:
            return VIRGIN_FLEET

        monkeypatch.setattr(fleet_routes.fleet_mod, "compute_fleet", _virgin)

        body = _client().get("/observability/fleet").json()

        assert body["available"] is True
        assert [a["id"] for a in body["agents"]] == ["support-client", "recouvrement"]
        # The nulls survive the wire — they are the honest-empty, not a field to be dropped.
        assert body["agents"][0]["release"] is None
        assert body["agents"][0]["level"] is None
        assert body["agents"][0]["level_declared"] is None


class TestTheThreeStatesAreThreeDifferentAnswers:
    """ "No data" and "I could not read" both show an empty page — they must not read alike."""

    def test_a_read_that_failed_degrades_and_says_so(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        async def _boom(*_a: object, **_k: object) -> FleetData:
            msg = "postgres unreachable"
            raise RuntimeError(msg)

        monkeypatch.setattr(fleet_routes.fleet_mod, "compute_fleet", _boom)

        response = _client().get("/observability/fleet")

        assert response.status_code == 200
        assert response.json() == {"available": False}
        assert "failed: postgres unreachable" in capsys.readouterr().err

    def test_a_payload_that_breaks_its_contract_degrades_but_is_named_a_contract_break(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The third state, and the one that must never be drowned in the second.

        A payload that does not honour the contract is a bug in US, not an absence of data. It
        may not take the page down (a 500 at the worst possible moment), and it may not read like
        an ordinary empty either — or it hides forever behind "nothing to show". So: degrade,
        AND say which of the two happened.
        """
        broken = {k: v for k, v in VIRGIN_FLEET.items() if k != "org"}  # a promised key, missing

        async def _broken(*_a: object, **_k: object) -> FleetData:
            return broken  # type: ignore[return-value]  # deliberately off-contract

        monkeypatch.setattr(fleet_routes.fleet_mod, "compute_fleet", _broken)

        response = _client().get("/observability/fleet")

        assert response.status_code == 200, "a broken contract must not become a 500"
        assert response.json() == {"available": False}
        assert "CONTRACT BREAK" in capsys.readouterr().err


class TestTheContractIsTrueByConstruction:
    """`available: True` GUARANTEES the payload — so the two declarations may never drift.

    `compute_fleet` is typed (`FleetData`), which makes a missing or mistyped field a **mypy
    error at build** rather than a 500 at runtime. That only holds while the TypedDict and the
    response model agree, and nothing in the language ties them together. This is that tie.
    """

    def test_the_typed_payload_and_the_response_model_declare_the_same_fields(self) -> None:
        assert set(get_type_hints(FleetData)) == set(FleetPayload.model_fields) - {"available"}

    def test_the_agent_card_declares_the_same_fields_in_both(self) -> None:
        assert set(get_type_hints(FleetAgent)) == set(FleetAgentsItem.model_fields)

    @pytest.mark.parametrize("field", ["release", "level", "level_declared", "latency_ms"])
    def test_a_field_the_computer_may_return_none_for_is_nullable_in_the_model(
        self, field: str
    ) -> None:
        """The exact axis the generated model got wrong.

        These four are `| None` in the code and always have been. Three of them were declared
        non-null by a model derived from samples that happened to have them — and that is the
        500. A sample cannot show you what is allowed to be absent.
        """
        annotation = FleetAgentsItem.model_fields[field].annotation

        assert type(None) in get_args(annotation), (
            f"FleetAgentsItem.{field} forbids None, but compute_fleet returns None for it — "
            "this is the exact shape that answered 500 on a virgin install"
        )

    def test_the_field_only_a_live_virgin_install_found_is_nullable_too(self) -> None:
        """`north_star.evidence.last_checked_at` — the same bug, one level deeper.

        The TestClient fixture above did not have a north-star, so it never reached this field.
        A real virgin install did, and the route logged a CONTRACT BREAK naming it. Its producer
        always knew: "A metric no run ever produced yields zeros and ``None`` — the genuine
        zero-data case." The generated model forbade exactly that.
        """
        annotation = FleetAgentsItemNorthStarEvidence.model_fields["last_checked_at"].annotation

        assert type(None) in get_args(annotation), (
            "north_star.evidence.last_checked_at forbids None, but a metric no run ever scored "
            "returns None for it — a virgin install then degrades on a CONTRACT BREAK"
        )

    @pytest.mark.parametrize("field", ["release", "level", "level_declared"])
    def test_the_nullable_field_is_still_required_present(self, field: str) -> None:
        """`| None` yes; `= None` never.

        A default would let the key go MISSING and still validate — and `available: True`
        promising a complete payload is the entire point of this union. Nullable is not optional.
        """
        assert FleetAgentsItem.model_fields[field].is_required(), (
            f"FleetAgentsItem.{field} has a default, so the key may vanish silently — "
            "`available: True` would then promise a field the payload does not carry"
        )


class TestTheSameHoleElsewhere:
    """The pattern is not one route's mistake. Do not claim the class is closed on one fix.

    64 observability handlers stamp `{"available": True, **compute(...)}`. Only the SIX carrying a
    `response_model` can 500 on a shape mismatch — the other 58 have no contract at all, which is a
    quieter disease (they serve whatever the compute produced, and the cockpit silently misses
    fields). Of those six, `fleet` is now typed by construction; the remaining five still splat an
    untyped dict, and each can 500 exactly as `fleet` did the moment its compute returns a legit
    `None` the sample never showed.

    They are FROZEN here, by name. The count may only go DOWN.
    """

    #: The piloted routes still stamping an untyped dict. Each is a `fleet` waiting to happen.
    OWED_UNTYPED_PAYLOADS = frozenset(
        {"rbac-matrix", "chrome", "access", "agent-evaluations", "sandbox-config"}
    )
    OWED_COUNT = 5

    def test_the_debt_is_named_and_only_shrinks(self) -> None:
        assert len(self.OWED_UNTYPED_PAYLOADS) == self.OWED_COUNT, (
            "a route was typed (good) or added (not good) — update OWED_COUNT deliberately, "
            "and never upward"
        )

    def test_fleet_is_no_longer_among_them(self) -> None:
        assert "fleet" not in self.OWED_UNTYPED_PAYLOADS

    def test_every_owed_route_really_does_still_serve_an_unchecked_dict(self) -> None:
        """The freeze must describe the code, not a memory of it (ADR 0026: ask the THING).

        If someone types one of these and forgets this list, this goes red and the debt shrinks
        deliberately — rather than the list quietly describing a world that no longer exists.
        """
        for route in sorted(self.OWED_UNTYPED_PAYLOADS):
            assert _returns_a_raw_available_dict(route), (
                f"{route} no longer serves an unchecked dict — remove it from "
                "OWED_UNTYPED_PAYLOADS and drop OWED_COUNT by one"
            )

    def test_fleet_itself_no_longer_serves_an_unchecked_dict(self) -> None:
        assert not _returns_a_raw_available_dict("fleet"), (
            "the fleet route serves a raw dict again — the payload must be VALIDATED, so a shape "
            "that does not honour the contract is caught instead of served"
        )


def test_the_captured_live_responses_still_validate() -> None:
    """The 31 real samples must still pass — the nullability widened, nothing else moved."""
    fixture = Path(__file__).parent / "fixtures" / "fleet_real_responses.json"
    real: dict[str, list[dict[str, object]]] = json.loads(fixture.read_text(encoding="utf-8"))

    for sample in real["fleet"]:
        model: BaseModel = FleetPayload.model_validate(sample)
        assert model.model_dump(mode="json") == sample
