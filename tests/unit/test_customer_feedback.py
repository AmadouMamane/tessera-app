"""Unit tests for the customer CSAT capture (ADR 0041).

The route handler is exercised directly with its dependencies monkeypatched — the resume
capability, the transcript turn-resolver and the durable write — so no Postgres is needed;
the real round-trip is the integration suite's job. What is pinned here is the CONTRACT: a
vote requires the signed capability, only a real turn can be rated, and the vote inherits
the rated turn's agent and test-marker.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from tessera.api.routes.observability import feedback as fb
from tessera.observability.customer_feedback import RATINGS, record_customer_feedback


class _Headers:
    def __init__(self, d: dict[str, str]) -> None:
        self._d = d

    def get(self, key: str) -> str | None:
        return self._d.get(key)


class _Req:
    """Minimal stand-in for ``fastapi.Request`` — the handler only reads a header."""

    def __init__(self, token: str | None = None) -> None:
        self.headers = _Headers({fb.RESUME_TOKEN_HEADER: token} if token else {})


def _payload(rating: str = "up") -> fb.CustomerFeedbackRequest:
    return fb.CustomerFeedbackRequest(
        conversation_id=uuid.uuid4(), turn_id=uuid.uuid4(), rating=rating
    )


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    recorded: list[dict[str, object]] = []

    async def fake_record(conv: object, turn: object, **kw: object) -> None:
        recorded.append({"conv": conv, "turn": turn, **kw})

    async def fake_attr(_turn_id: object) -> tuple[str, bool]:
        return ("support-client", False)

    monkeypatch.setattr(fb, "record_customer_feedback", fake_record)
    monkeypatch.setattr(fb, "turn_agent_and_synthetic", fake_attr)
    monkeypatch.setattr(
        fb,
        "verify_resume_token",
        lambda token, _cid: token == "good-token",  # noqa: S105  test fixture, not a secret
    )
    return recorded


@pytest.mark.asyncio
async def test_records_with_the_rated_turns_agent_and_realness(
    wired: list[dict[str, object]],
) -> None:
    resp = await fb.customer_feedback(_payload("up"), _Req("good-token"))  # type: ignore[arg-type]
    assert resp == {"ok": True, "rating": "up"}
    assert wired[0]["agent_id"] == "support-client"
    assert wired[0]["synthetic"] is False
    assert wired[0]["rating"] == "up"


@pytest.mark.asyncio
async def test_a_vote_on_a_test_turn_is_itself_excluded(
    wired: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def test_turn(_turn_id: object) -> tuple[str, bool]:
        return ("recouvrement", True)

    monkeypatch.setattr(fb, "turn_agent_and_synthetic", test_turn)
    await fb.customer_feedback(_payload("down"), _Req("good-token"))  # type: ignore[arg-type]
    assert wired[0]["synthetic"] is True
    assert wired[0]["agent_id"] == "recouvrement"


@pytest.mark.asyncio
async def test_a_missing_or_invalid_capability_is_refused(
    wired: list[dict[str, object]],
) -> None:
    for req in (_Req(None), _Req("wrong-token")):
        with pytest.raises(HTTPException) as exc:
            await fb.customer_feedback(_payload("up"), req)  # type: ignore[arg-type]
        assert exc.value.status_code == 403
    assert wired == []  # nothing recorded without the capability


@pytest.mark.asyncio
async def test_an_unknown_turn_cannot_be_rated(
    wired: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_turn(_turn_id: object) -> None:
        return None

    monkeypatch.setattr(fb, "turn_agent_and_synthetic", no_turn)
    with pytest.raises(HTTPException) as exc:
        await fb.customer_feedback(_payload("up"), _Req("good-token"))  # type: ignore[arg-type]
    assert exc.value.status_code == 404
    assert wired == []


@pytest.mark.asyncio
async def test_an_unknown_rating_is_rejected(wired: list[dict[str, object]]) -> None:
    with pytest.raises(HTTPException) as exc:
        await fb.customer_feedback(_payload("sideways"), _Req("good-token"))  # type: ignore[arg-type]
    assert exc.value.status_code == 422
    assert wired == []


@pytest.mark.asyncio
async def test_record_rejects_an_unknown_rating_defence_in_depth() -> None:
    # The store validates too — the raise happens before any DB access.
    with pytest.raises(ValueError, match="unknown rating"):
        await record_customer_feedback(
            uuid.uuid4(), uuid.uuid4(), agent_id="x", rating="meh", synthetic=False
        )


def test_the_only_ratings_are_up_and_down() -> None:
    assert frozenset({"up", "down"}) == RATINGS
