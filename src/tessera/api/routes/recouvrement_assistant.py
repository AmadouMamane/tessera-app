"""Structured backend endpoint for the Recouvrement assistant workflow v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.recouvrement import (
    DEFAULT_SURFACE,
    RecouvrementArtifact,
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)

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


class RecouvrementAssistantActionRequest(BaseModel):
    """Input contract for governed Recouvrement artifact actions."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default="RC-2048", min_length=1, max_length=80)
    artifact: dict[str, Any]
    action_name: str = Field(min_length=1, max_length=120)
    requested_by: str = Field(default="Julie Dubois", min_length=1, max_length=120)
    conversation_id: str | None = Field(default=None, max_length=120)
    turn_id: str | None = Field(default=None, max_length=120)
    surface: str = Field(default=DEFAULT_SURFACE, max_length=80)


def _artifact_from_request(raw: dict[str, Any]) -> RecouvrementArtifact:
    """Coerce the frontend artifact payload into the backend typed shape."""
    content = raw.get("content")
    return {
        "id": str(raw.get("id") or "unknown-artifact"),
        "type": str(raw.get("type") or "unknown_artifact"),
        "task": str(raw.get("task") or "artifact_action"),
        "title": str(raw.get("title") or "Artefact Recouvrement"),
        "status": str(raw.get("status") or "draft"),
        "content": dict(content) if isinstance(content, dict) else {},
    }


@router.post("/recouvrement-assistant/message")
@router.post("/api/recouvrement-assistant/message")
async def recouvrement_assistant_message(
    payload: RecouvrementAssistantRequest,
) -> dict[str, object]:
    """Run the first specialised Recouvrement graph and return drawer-ready cards.

    The graph is a *synchronous* LangGraph ``.invoke()`` that performs store I/O and
    emits ~30 business events per turn. Called directly from this async route it would
    block the event loop for the whole turn — starving every other in-flight request,
    including the SSE streams. Offloaded to the threadpool instead.
    """
    return dict(
        await run_in_threadpool(
            run_recouvrement_graph_v1,
            case_id=payload.case_id,
            message=payload.message,
            assistant_state=payload.assistant_state,
            conversation_id=payload.conversation_id,
            turn_id=payload.turn_id,
            surface=payload.surface,
        )
    )


@router.post("/recouvrement-assistant/action")
@router.post("/api/recouvrement-assistant/action")
async def recouvrement_assistant_action(
    payload: RecouvrementAssistantActionRequest,
) -> dict[str, object]:
    """Run a governed action cycle for a Recouvrement artifact.

    Synchronous and store-backed like the message workflow above — same reason, same
    offload. The audit named only the message path; this one blocks identically.
    """
    return dict(
        await run_in_threadpool(
            run_recouvrement_action_workflow_v1,
            case_id=payload.case_id,
            artifact=_artifact_from_request(payload.artifact),
            action_name=payload.action_name,
            requested_by=payload.requested_by,
            conversation_id=payload.conversation_id,
            turn_id=payload.turn_id,
            surface=payload.surface,
        )
    )
