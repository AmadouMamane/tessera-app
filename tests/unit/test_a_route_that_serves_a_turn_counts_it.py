"""Ratchet — a route that serves an agent turn counts it. No third bucket.

The class, not the finding. ``tessera_agent_turns_total`` was incremented in ``/chat`` and
nowhere else, so the cockpit's L1 evidence read — whose whole job is to ask a store whether an
agent has been observed emitting — could not see ``recouvrement``, which serves its turns over
``/recouvrement-assistant/message``. It sat at L0 while writing 1281 business events: the only
agent producing evidence was the one refused for want of it.

Fixing that one route would leave the trap armed for the next agent served outside ``/chat``.
This file disarms it: a module that invokes an agent turn must either count the turn, or be
named in :data:`COUNTS_ELSEWHERE` with the reason it does not. Both sets are asserted with
``==``, so neither can grow silently — adding one means editing this file, in review.

It is the same shape as ``test_mutation_routes_carry_auth.py``, and for the same reason:
``recouvrement_assistant.py`` has now been found outside a ``/chat`` seam three times — the
input guard (2026-07-21), the durable transcript (ADR 0040), and this counter. Three instances
of one class is not three bugs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pytest

from tessera.api.routes import recouvrement_assistant as ra
from tessera.observability.metrics import registry

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROUTES_DIR: Final = Path(__file__).resolve().parents[2] / "src" / "tessera" / "api" / "routes"

#: The counter every turn-serving route must reach. Named once so a rename breaks this file
#: loudly instead of turning the ratchet into a test of a string that no longer exists.
_COUNTER = "AGENT_TURNS_TOTAL"

#: What "invoking an agent turn" looks like in source. ``ainvoke`` is the LangGraph entry point
#: ``/chat`` uses; ``run_<something>_graph_v<n>`` / ``run_<something>_workflow_v<n>`` is the
#: convention the specialised agents follow (``run_recouvrement_graph_v1``).
_TURN_INVOCATION = re.compile(r"^(ainvoke|run_.+_(graph|workflow)_v\d+)$")

#: Route modules that invoke a turn and legitimately do NOT count it here — each with why.
#: Asserted with ``==``: this set may not grow without a reviewed reason.
COUNTS_ELSEWHERE: Final[frozenset[str]] = frozenset(
    {
        # `/agents/{id}/invoke` drives an http-binding agent through `HttpTurnInvoker`, i.e. it
        # sends a real HTTP turn to the agent's OWN turn route — which counts it there. Counting
        # again here would double every invoked turn.
        "invoke.py",
    }
)


def _module_sources() -> Iterator[tuple[str, str]]:
    """Every route module's (name, source), including the nested ``observability`` package."""
    for path in sorted(_ROUTES_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        yield path.name, path.read_text(encoding="utf-8")


def _invokes_a_turn(source: str) -> bool:
    """Whether this module calls something that runs an agent turn."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else ""
        )
        if _TURN_INVOCATION.match(name):
            return True
        # `run_in_threadpool(run_x_graph_v1, ...)` — the callable is an ARGUMENT, not the
        # callee. Missing this is exactly how the recouvrement route stayed invisible.
        for arg in node.args:
            if isinstance(arg, ast.Name) and _TURN_INVOCATION.match(arg.id):
                return True
    return False


def _turn_serving_modules() -> dict[str, str]:
    return {name: src for name, src in _module_sources() if _invokes_a_turn(src)}


# ── the detector, tested before it is trusted ────────────────────────────────────────────────


def test_the_detector_sees_the_two_modules_we_know_serve_turns() -> None:
    """ "No findings" and "the pattern stopped matching" are otherwise the same sentence.

    Both known turn paths must be found. If this fails, the ratchet below is green over a hole
    and proves nothing — ADR 0026's rule that a witness which cannot see may never report "ok".
    """
    found = set(_turn_serving_modules())
    assert {"chat.py", "recouvrement_assistant.py"} <= found, found


def test_the_detector_does_not_match_an_ordinary_read_route() -> None:
    assert _invokes_a_turn("def read(): return store.list()") is False


def test_the_detector_sees_a_callable_passed_to_the_threadpool() -> None:
    """The precise shape that hid the defect: the graph is an argument, never the callee."""
    assert _invokes_a_turn("await run_in_threadpool(run_widget_graph_v1, x=1)") is True


# ── the ratchet ──────────────────────────────────────────────────────────────────────────────


def test_every_route_that_serves_a_turn_counts_it() -> None:
    uncounted = {
        name
        for name, src in _turn_serving_modules().items()
        if _COUNTER not in src and name not in COUNTS_ELSEWHERE
    }
    assert uncounted == set(), (
        f"these route modules run an agent turn without incrementing {_COUNTER}: "
        f"{sorted(uncounted)}. A turn nobody counts is an agent the cockpit reads as dormant, "
        f"and the L1 evidence read will pin it at L0 however much it emits. Either increment "
        f"the counter where the turn is served, or add the module to COUNTS_ELSEWHERE with "
        f"the reason its turns are counted somewhere else."
    )


def test_the_delegating_set_is_frozen() -> None:
    """Asserted with ``==`` so a new exemption cannot slip in unreviewed."""
    assert frozenset({"invoke.py"}) == COUNTS_ELSEWHERE


def test_every_delegating_module_still_exists() -> None:
    """An exemption for a module that is gone is a rule policing nothing."""
    present = {name for name, _ in _module_sources()}
    assert present >= COUNTS_ELSEWHERE, COUNTS_ELSEWHERE - present


# ── the thing itself: does the route actually move the counter? ──────────────────────────────


def _turns(agent_id: str, language: str, outcome: str) -> float:
    value = registry.get_sample_value(
        "tessera_agent_turns_total",
        {"agent_id": agent_id, "language": language, "outcome": outcome},
    )
    return float(value or 0.0)


@pytest.mark.asyncio
async def test_the_recouvrement_route_increments_the_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The witness that interrogates the thing, not its source text.

    The ratchet above reads source; this drives the handler. Both are needed — a module can
    mention the counter and never reach it.
    """
    monkeypatch.setattr(ra, "run_recouvrement_graph_v1", lambda **_k: {"visibleReply": "ok"})
    monkeypatch.setattr(ra, "_persist_recouvrement_turn", _noop)
    before = _turns("recouvrement", "fr", "complete")

    await ra.recouvrement_assistant_message(
        ra.RecouvrementAssistantRequest(message="Bonjour", language="fr"),
        _session(),
    )

    assert _turns("recouvrement", "fr", "complete") == before + 1


@pytest.mark.asyncio
async def test_a_failed_turn_is_still_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/chat` counts its failures. An agent being asked and failing must not read as dormant."""

    def _boom(**_k: object) -> dict[str, object]:
        raise RuntimeError("graph exploded")

    monkeypatch.setattr(ra, "run_recouvrement_graph_v1", _boom)
    before = _turns("recouvrement", "fr", "error")

    with pytest.raises(RuntimeError):
        await ra.recouvrement_assistant_message(
            ra.RecouvrementAssistantRequest(message="Bonjour", language="fr"),
            _session(),
        )

    assert _turns("recouvrement", "fr", "error") == before + 1


async def _noop(*_a: object, **_k: object) -> None:
    """Stand in for the transcript write — Postgres is not this test's subject."""


def _session() -> Any:
    """The verified collections operator the router's guard would have resolved."""
    from tessera.api.session import SessionContext
    from tessera.authz import AuthState

    return SessionContext(
        auth_state=AuthState.OPERATOR,
        subject_id="op-1",
        authenticated=True,
        label="Opérateur recouvrement",
        demo=False,
        role="collections",
    )
