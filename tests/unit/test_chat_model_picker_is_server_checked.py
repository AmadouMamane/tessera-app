"""The per-turn model picker is validated by the agent, not only by the browser's BFF.

Audit 2026-08-03. ``webapp/frontend/app/api/chat/route.ts`` refuses a gated model to anyone
but a superadmin and says so in a comment: *"This is the authoritative lock — the UI disabling
the card is only a courtesy."* ``POST /chat`` accepted ``request.model`` with no check.

That is the F-5 shape this repository has already named, in ``routes/settings.py``: *"A rule
enforced only in the browser's own BFF is not enforced."* The bearer the BFF attaches says the
call came from our frontend, never who is asking, and in dev/CI there is no bearer at all. So

    curl -X POST $AGENT/chat -d '{"message":"…","model":"gpt-5.5-pro"}'

routed to a paid frontier model — and ADR 0030's precedence puts the picker ABOVE the stored
governed override, so it also beat the superadmin's own choice.

``system_prompt_override`` and ``guard_overrides`` were already dropped outside the operator
sandbox. ``model`` is the third field of that family and was the one left unguarded.
"""

from __future__ import annotations

import pytest

from tessera.agent.registry import Surface
from tessera.api.routes.chat import _picked_model
from tessera.authz import AuthState
from tessera.llm.budget import model_is_paid

_OPERATOR_CONSOLE = (Surface.COCKPIT_EMBEDDED, AuthState.OPERATOR)
_CUSTOMER_WIDGET = (Surface.SHARED_CUSTOMER_WIDGET, AuthState.CUSTOMER)
_ANONYMOUS = (Surface.SHARED_CUSTOMER_WIDGET, AuthState.ANONYMOUS)


def _paid_model() -> str:
    """A servable model the price table says costs money — the class under test."""
    from tessera.api.config_overrides import allowed_chat_models

    paid = sorted(m for m in allowed_chat_models() if model_is_paid(m))
    if not paid:
        pytest.skip("no paid model in the catalogue on this configuration")
    return paid[0]


def _free_model() -> str:
    from tessera.api.config_overrides import allowed_chat_models

    free = sorted(m for m in allowed_chat_models() if not model_is_paid(m))
    if not free:
        pytest.skip("no zero-cost model in the catalogue on this configuration")
    return free[0]


def test_the_catalogue_distinguishes_paid_from_free() -> None:
    """Anti-vacuity: if nothing is paid, every assertion below is trivially satisfied."""
    assert _paid_model() != _free_model()


def test_no_picker_leaves_the_governed_override_in_charge() -> None:
    assert _picked_model(None, *_CUSTOMER_WIDGET) is None
    assert _picked_model("", *_CUSTOMER_WIDGET) is None


def test_a_model_outside_the_catalogue_is_dropped() -> None:
    """Writing one is already refused; accepting one here broke every turn at execution."""
    assert _picked_model("gemini-9.9-imaginary", *_OPERATOR_CONSOLE) is None


def test_a_customer_turn_cannot_pick_a_paid_model() -> None:
    """THE regression: this is the curl that reached gpt-5.5-pro through the widget plane."""
    assert _picked_model(_paid_model(), *_CUSTOMER_WIDGET) is None


def test_an_anonymous_turn_cannot_pick_a_paid_model() -> None:
    assert _picked_model(_paid_model(), *_ANONYMOUS) is None


def test_the_operator_console_may_pick_a_paid_model() -> None:
    """The privilege still exists — it is now derived server-side rather than asserted."""
    paid = _paid_model()
    assert _picked_model(paid, *_OPERATOR_CONSOLE) == paid


def test_a_zero_cost_model_stays_pickable_everywhere() -> None:
    """The picker is a product feature; only the paid tier is a privilege."""
    free = _free_model()
    assert _picked_model(free, *_CUSTOMER_WIDGET) == free
