"""Closure test for the blocked FastAPI event loop.

Audit 2026-07-10, P1 `async-blocking`: ``recouvrement.py:2655/2680`` —
``run_recouvrement_graph_v1`` is a *synchronous* ``def`` performing a LangGraph
``.invoke()`` (store I/O, ~30 business-event emissions per turn), called directly from
the ``async`` route in ``recouvrement_assistant.py:67`` with no ``run_in_threadpool``.
For the whole duration of a turn the event loop could not advance: every other in-flight
request — including open SSE streams — was starved.

The test does not inspect the implementation; it measures the symptom. A ticker task runs
concurrently and we count how far it got *while the route was awaiting*. Against the
pre-fix route the loop is pinned and the ticker cannot advance at all (0 ticks); with the
work offloaded it ticks freely.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import SecretStr
from starlette.requests import Request

from tessera.api.operator import OPERATOR_ASSERTION_HEADER, issue_operator_assertion
from tessera.api.routes import recouvrement_assistant as module
from tessera.api.routes.recouvrement_assistant import (
    RecouvrementAssistantActionRequest,
    RecouvrementAssistantRequest,
    recouvrement_assistant_action,
    recouvrement_assistant_message,
)
from tessera.api.security import require_collections_operator
from tessera.authz import Surface
from tessera.settings import get_settings

if TYPE_CHECKING:
    from tessera.api.session import SessionContext

# Long enough to dwarf scheduler jitter, short enough to keep the gate fast.
_BLOCKING_S = 0.30
_TICK_S = 0.005


async def _ticks_during(coro: Any) -> int:
    """Run ``coro`` and count how many times a concurrent task got scheduled meanwhile."""
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(_TICK_S)
            ticks += 1

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)  # let the ticker reach its first await
    await coro
    observed = ticks
    task.cancel()
    return observed


def _blocking(**_: object) -> dict[str, object]:
    """Stand in for the real graph: synchronous, and slow because it does I/O."""
    time.sleep(_BLOCKING_S)
    return {"visibleReply": "ok"}


def _verified_session(monkeypatch: pytest.MonkeyPatch) -> SessionContext:
    """A ``SessionContext`` produced by the REAL verification chain, never hand-assembled.

    The action handler takes the verified operator identity as a required argument (audit
    2026-07-12, P0 F-1) — so a test that calls it directly must supply one, the same way
    FastAPI's injection does: mint a genuinely signed assertion, put it on a request, and
    let ``require_collections_operator`` verify it. Building a ``SessionContext(...)``
    literal here would quietly re-teach the codebase that identities can be asserted
    rather than proven — the exact habit F-1 grew from.
    """
    settings = get_settings()
    monkeypatch.setattr(settings.api, "operator_assertion_signing_key", SecretStr("test-key"))
    token = issue_operator_assertion(
        principal="collections", role="collections", surface=Surface.DEDICATED_UI
    )
    request = Request(
        {"type": "http", "headers": [(OPERATOR_ASSERTION_HEADER.encode(), token.encode())]}
    )
    return require_collections_operator(request)


async def test_message_route_does_not_pin_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow Recouvrement turn must not starve every other request on the worker."""
    monkeypatch.setattr(module, "run_recouvrement_graph_v1", _blocking)

    ticks = await _ticks_during(
        recouvrement_assistant_message(
            RecouvrementAssistantRequest(message="bonjour"),
            session=_verified_session(monkeypatch),
        )
    )

    # Pre-fix this is 0: the loop is pinned for the whole turn. Post-fix the ticker gets
    # ~60 slices; assert a fraction of that so the test is not timing-fragile.
    assert ticks >= 10


async def test_action_route_does_not_pin_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The governed-action workflow blocks identically — the audit named only the other."""
    monkeypatch.setattr(module, "run_recouvrement_action_workflow_v1", _blocking)

    ticks = await _ticks_during(
        recouvrement_assistant_action(
            RecouvrementAssistantActionRequest(
                artifact={"id": "a", "type": "t", "task": "x", "title": "T", "status": "draft"},
                action_name="approve",
            ),
            session=_verified_session(monkeypatch),
        )
    )

    assert ticks >= 10


def test_action_route_refuses_to_run_without_a_verified_identity() -> None:
    """The seam this file now supplies is load-bearing — assert it both ways.

    Calling the handler without a session must refuse at the signature (``TypeError`` —
    the code cannot even bind, let alone write to the ledger), and the ``session``
    parameter must have NO default: a default identity on this argument would be the F-1
    vulnerability reintroduced for test convenience — "Julie Dubois" one level up. The
    handler never invents an identity; its callers prove one.
    """
    payload = RecouvrementAssistantActionRequest(
        artifact={"id": "a", "type": "t", "task": "x", "title": "T", "status": "draft"},
        action_name="approve",
    )

    with pytest.raises(TypeError):
        recouvrement_assistant_action(payload)  # type: ignore[call-arg]

    session_param = inspect.signature(recouvrement_assistant_action).parameters["session"]
    assert session_param.default is inspect.Parameter.empty
