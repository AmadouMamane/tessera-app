"""Typed action targets for the Tessera agent.

Tools are typed, idempotent (where possible), and side-effect-bounded. They
are *not* LangGraph nodes — they expose a Pydantic-validated input schema
and a frozen Pydantic output type. Workers in
:mod:`tessera.agent.workers` wrap them with the firewall guard before
invoking.

They are also **not** exposed to the model. This package was documented for
two months as "LLM-callable function-call targets", and no such binding has
ever existed: a worker decides in Python that a tool is needed, builds its
arguments in Python, and calls it through ``guarded_invoke``. The model emits
no tool call and sees no tool schema. See ADR 0005 §Amendment 1 for why the
separation is kept anyway and what wiring the function-calling would cost.

The split between tools and workers is binding; see ADR 0005.
"""

from __future__ import annotations

from tessera.agent.tools import (
    account_balance,
    card_block,
    loan_simulate,
    ticket_escalate,
    transaction_search,
)

__all__ = [
    "account_balance",
    "card_block",
    "loan_simulate",
    "ticket_escalate",
    "transaction_search",
]
