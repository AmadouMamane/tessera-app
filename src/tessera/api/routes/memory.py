"""Memory governance endpoints — GDPR erasure and consent (ADR 0007).

These expose the two regulator-facing capabilities of the memory layer:

* ``DELETE /memory/{conversation_id}`` — erase every trace of a subject across
  all memory layers (Art. 17). Total regardless of the configured backend.
* ``PUT /memory/{conversation_id}/consent`` — grant or revoke long-term
  retention consent for a subject.

The subject is identified by its conversation id while no authentication layer
exists (ADR 0007, "Identity").
"""

from __future__ import annotations

import uuid  # noqa: TCH003  — FastAPI resolves path-param annotations at runtime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette import status
from starlette.responses import Response

from tessera.memory import governance, persistent

router = APIRouter(tags=["memory"])


class ConsentRequest(BaseModel):
    """Body for a consent grant/revoke."""

    model_config = ConfigDict(extra="forbid")

    granted: bool


class MemoryItemView(BaseModel):
    """A stored memory surfaced for access/rectification (GDPR Art. 15/16)."""

    model_config = ConfigDict(extra="forbid")

    memory_id: int
    kind: str
    text: str
    created_at: str
    expires_at: str


class MemoryItemsResponse(BaseModel):
    """All memories held for a subject."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    items: list[MemoryItemView]


class RectifyRequest(BaseModel):
    """Body for rectifying a stored memory's text (GDPR Art. 16)."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2_000)


class ConsentResponse(BaseModel):
    """Current consent state for a subject."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    granted: bool


@router.delete("/memory/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def erase_memory(conversation_id: uuid.UUID) -> Response:
    """Erase all stored memory for a subject (GDPR Art. 17)."""
    await governance.erase_subject(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memory/{conversation_id}/items")
async def list_memory_items(conversation_id: uuid.UUID) -> MemoryItemsResponse:
    """List the memories held for a subject (GDPR Art. 15 access)."""
    subject_id = str(conversation_id)
    stored = await persistent.list_subject_memories(subject_id)
    governance.audit_memory(
        action="memory.read",
        subject_id=subject_id,
        decision="allow",
        rationale=f"subject access request: {len(stored)} item(s)",
    )
    return MemoryItemsResponse(
        subject_id=subject_id,
        items=[
            MemoryItemView(
                memory_id=item.memory_id,
                kind=item.kind,
                text=item.text,
                created_at=item.created_at.isoformat(),
                expires_at=item.expires_at.isoformat(),
            )
            for item in stored
        ],
    )


@router.patch("/memory/{conversation_id}/items/{memory_id}")
async def rectify_memory_item(
    conversation_id: uuid.UUID,
    memory_id: int,
    payload: Annotated[RectifyRequest, Body(...)],
) -> Response:
    """Rectify a stored memory's text (GDPR Art. 16). Re-screened and re-embedded."""
    subject_id = str(conversation_id)
    screened = governance.screen_memory(payload.text)
    if not screened.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="rejected")
    updated = await persistent.update_memory_text(
        memory_id, subject_id=subject_id, text=screened.text
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    governance.audit_memory(
        action="memory.write",
        subject_id=subject_id,
        decision="transform",
        rationale=f"subject rectification of memory {memory_id}",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/memory/{conversation_id}/items/{memory_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_memory_item(conversation_id: uuid.UUID, memory_id: int) -> Response:
    """Delete a single stored memory of a subject (GDPR Art. 17, granular)."""
    subject_id = str(conversation_id)
    deleted = await persistent.delete_memory(memory_id, subject_id=subject_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    governance.audit_memory(
        action="memory.forget",
        subject_id=subject_id,
        decision="allow",
        rationale=f"subject deleted memory {memory_id}",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/memory/{conversation_id}/consent")
async def set_memory_consent(
    conversation_id: uuid.UUID,
    payload: Annotated[ConsentRequest, Body(...)],
) -> ConsentResponse:
    """Grant or revoke long-term retention consent for a subject."""
    subject_id = str(conversation_id)
    await governance.set_consent(subject_id, granted=payload.granted)
    return ConsentResponse(subject_id=subject_id, granted=payload.granted)
