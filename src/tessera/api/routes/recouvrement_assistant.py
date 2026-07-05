"""Structured backend endpoint for the Recouvrement assistant workflow v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.recouvrement import DEFAULT_SURFACE, run_recouvrement_graph_v1

router = APIRouter(tags=["recouvrement-assistant"])


class RecouvrementAssistantRequest(BaseModel):
    """Input contract for the minimal Recouvrement assistant workflow."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default="RC-2048", min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2_000)
    assistant_state: dict[str, Any] | None = None
    conversation_id: str | None = Field(default=None, max_length=120)
    turn_id: str | None = Field(default=None, max_length=120)
    surface: str = Field(default=DEFAULT_SURFACE, max_length=80)


@router.post("/recouvrement-assistant/message")
@router.post("/api/recouvrement-assistant/message")
async def recouvrement_assistant_message(
    payload: RecouvrementAssistantRequest,
) -> dict[str, object]:
    """Run the first specialised Recouvrement graph and return drawer-ready cards."""
    return dict(
        run_recouvrement_graph_v1(
            case_id=payload.case_id,
            message=payload.message,
            assistant_state=payload.assistant_state,
            conversation_id=payload.conversation_id,
            turn_id=payload.turn_id,
            surface=payload.surface,
        )
    )
