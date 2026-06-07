"""Correlation context shared by traces, audit entries, and evidence bundles."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.observability.privacy import hash_identifier

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "TurnContextTokens",
    "current_conversation_hash",
    "current_request_id",
    "current_turn_id",
    "reset_request_context",
    "reset_turn_context",
    "set_request_context",
    "set_turn_context",
]


current_request_id: ContextVar[str | None] = ContextVar(
    "tessera_request_id",
    default=None,
)
current_conversation_hash: ContextVar[str | None] = ContextVar(
    "tessera_conversation_id_hash",
    default=None,
)
current_turn_id: ContextVar[str | None] = ContextVar("tessera_turn_id", default=None)


@dataclass(frozen=True, slots=True)
class TurnContextTokens:
    """ContextVar tokens returned when binding a turn context."""

    conversation_hash: Token[str | None]
    turn_id: Token[str | None]


def set_request_context(request_id: str) -> Token[str | None]:
    """Bind the active HTTP request id to the current context."""
    return current_request_id.set(request_id)


def reset_request_context(token: Token[str | None]) -> None:
    """Reset the active HTTP request id context."""
    current_request_id.reset(token)


def set_turn_context(conversation_id: UUID | str, turn_id: UUID | str) -> TurnContextTokens:
    """Bind hashed conversation and turn identifiers to the current context."""
    return TurnContextTokens(
        conversation_hash=current_conversation_hash.set(hash_identifier(conversation_id)),
        turn_id=current_turn_id.set(str(turn_id)),
    )


def reset_turn_context(tokens: TurnContextTokens) -> None:
    """Reset the active turn context."""
    current_conversation_hash.reset(tokens.conversation_hash)
    current_turn_id.reset(tokens.turn_id)
