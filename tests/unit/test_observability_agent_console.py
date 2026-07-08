"""ADR 0019 §I2 — the Console is generated from the declared ``invocation.binding``.

The console's *shape* is a function of the agent's declaration, not a per-agent
assumption: an ``in_process_chat`` agent gets the full interactive payload (parity with
the shipped console — context strip, tools / guardrails / eval panels), a publish-only
``none`` agent gets a slim honest-empty descriptor with NO fabricated config panels.
These tests pin that gate so the console can never silently regress to "every agent is
chattable" (the O(agents) drift ADR 0019 exists to remove).
"""

from __future__ import annotations

import pytest

from tessera.observability.agent_console import compute_agent_console

# The three native Q&A / collections agents declare ``in_process_chat``; hello-agent is
# the publish-only ``none`` proof (ADR 0017 §F / ADR 0019 §1).
_INTERACTIVE_AGENTS = ("support-client", "onboarding", "recouvrement")


@pytest.mark.parametrize("agent_id", _INTERACTIVE_AGENTS)
def test_in_process_chat_agent_gets_the_interactive_payload(agent_id: str) -> None:
    payload = compute_agent_console("fr", agent_id)
    invocation = payload["invocation"]
    assert isinstance(invocation, dict)
    assert invocation["binding"] == "in_process_chat"
    assert invocation["invocable"] is True
    # Parity with the shipped console: the interactive config panels are present.
    for panel in ("context", "tools", "guardrails", "evaluation", "tabs", "actions"):
        assert panel in payload, f"{agent_id}: interactive payload missing {panel!r}"
    # An interactive console is not the honest-empty state.
    assert "empty" not in payload


def test_http_agent_gets_a_request_response_test_bench() -> None:
    # ADR 0019 §I3 — turn-agent declares binding: http, so the console is invocable via the
    # request/response invoker, NOT honest-empty and NOT the in-process SSE console.
    payload = compute_agent_console("fr", "turn-agent")
    invocation = payload["invocation"]
    assert isinstance(invocation, dict)
    assert invocation["binding"] == "http"
    assert invocation["invocable"] is True
    assert invocation["mode"] == "request_response"
    assert invocation["endpoint"]  # the declared endpoint the cockpit consumes
    assert isinstance(payload["http_console"], dict)
    # A foreign runtime owns its own guard/telemetry — no in-process panels are fabricated.
    for panel in ("tools", "guardrails", "evaluation", "context"):
        assert panel not in payload
    assert "empty" not in payload  # it IS invocable, so it is not the honest-empty state


def test_publish_only_agent_gets_honest_empty_not_a_broken_chat() -> None:
    payload = compute_agent_console("fr", "hello-agent")
    invocation = payload["invocation"]
    assert isinstance(invocation, dict)
    assert invocation["binding"] == "none"
    assert invocation["invocable"] is False
    # The honest-empty descriptor is present with real copy…
    empty = payload["empty"]
    assert isinstance(empty, dict)
    assert empty["title"] and empty["detail"]
    # …and NONE of the config panels are fabricated for an agent that runs no tessera
    # guard (the honesty invariant: no guardrails/tools/eval it does not own).
    for panel in ("context", "tools", "guardrails", "evaluation", "actions"):
        assert panel not in payload, f"honest-empty payload must not fabricate {panel!r}"


def test_honest_empty_copy_is_localized() -> None:
    details = {
        lang: compute_agent_console(lang, "hello-agent")["empty"]["detail"]  # type: ignore[index]
        for lang in ("fr", "de", "en")
    }
    # Three distinct localizations — never one string echoed across locales.
    assert len({details["fr"], details["de"], details["en"]}) == 3
    assert "évaluations" in details["fr"]
    assert "evaluations" in details["en"]


def test_unknown_agent_raises_so_the_route_degrades() -> None:
    # The route wraps this in try/except → ``available: false``; an unknown agent must
    # not silently return a default agent's console (that would mislabel the surface).
    with pytest.raises(KeyError):
        compute_agent_console("fr", "no-such-agent")
