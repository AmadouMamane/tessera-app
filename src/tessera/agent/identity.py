"""Agent identity primitives for the multi-agent foundation (Phase 0).

Tessera runs a single agent today; the supervisor (Phase 2) will set the
acting agent per turn. Until then every audit event, metric and transcript
message is stamped with :data:`DEFAULT_AGENT_ID` so the data is already
partitioned by agent and the cockpit can scope by it. The id is the same slug
used by the AGENT routes (``/agents/<agent_id>/...``), so data and URLs agree.

The acting agent is carried as a context variable rather than threaded through
every call site: each API request runs in its own asyncio task, so there is no
cross-request leak, and the guard/transcript layers read it without changing
their signatures. The chat route sets it at the turn boundary.
"""

from __future__ import annotations

from contextvars import ContextVar

__all__ = [
    "DEFAULT_AGENT_ID",
    "current_agent_id",
    "current_conversation_id",
    "current_turn_id",
    "resolve_agent_id",
]

#: Default agent slug used until the multi-agent registry (Phase 1) lands.
DEFAULT_AGENT_ID = "support-client"

#: Agent acting on the current turn. Set at the turn boundary (chat route) and
#: read by audit/metric/transcript emitters. Defaults to the single agent.
current_agent_id: ContextVar[str] = ContextVar("tessera_current_agent_id", default=DEFAULT_AGENT_ID)

#: Correlation carried by the current chat turn. Audit emitters use these fields to distinguish
#: a governed product/test turn from a direct policy probe that has no business-turn identity.
current_conversation_id: ContextVar[str | None] = ContextVar(
    "tessera_current_conversation_id", default=None
)
current_turn_id: ContextVar[str | None] = ContextVar("tessera_current_turn_id", default=None)


def resolve_agent_id(agent_id: str | None = None) -> str:
    """Return the explicit ``agent_id`` if given, else the context default."""
    return agent_id if agent_id is not None else current_agent_id.get()
