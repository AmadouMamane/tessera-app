"""Memory governance endpoints — GDPR erasure, access, rectification and consent (ADR 0007).

These expose the regulator-facing capabilities of the memory layer:

* ``DELETE /memory/{conversation_id}`` — erase every trace of a subject across
  all memory layers (Art. 17). Total regardless of the configured backend.
* ``GET /memory/{conversation_id}/items`` — the memories held for a subject (Art. 15).
* ``PATCH /memory/{conversation_id}/items/{memory_id}`` — rectify one (Art. 16).
* ``PUT /memory/{conversation_id}/consent`` — grant or revoke long-term
  retention consent for a subject.

**Two planes, two guards** (audit 2026-07-12, F-4 + F-5). Until then the whole module was
mounted behind ``dependencies=[Depends(require_bearer)]`` and nothing else, which is a
service credential the BFF attaches on any caller's behalf: it says *"this came from our
frontend"*, never *"who is asking"*. Erasing, rectifying or reading the personal data of an
arbitrary subject demands the second answer.

* the **writes** carry :func:`~tessera.api.security.require_operator` — the cockpit control
  plane's role set, so the ``auditor`` is refused (it reads and does not write, on every
  plane) and no anonymous caller can erase or rewrite a subject's record;
* the **read** carries :func:`~tessera.api.security.require_subject_reader` — every operator
  role, auditor included, because reading is what an auditor is FOR.

Both are declared on their router rather than at the mount site, so a route added to this
module cannot forget its guard (the ``mutations.py`` model, and F-1's structural lesson).

The subject is still identified by its conversation id (ADR 0007, "Identity") — the caller,
now, is identified by a signed operator assertion.
"""

from __future__ import annotations

import uuid  # noqa: TCH003  — FastAPI resolves path-param annotations at runtime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette import status
from starlette.responses import Response

from tessera.api.security import actor_of, require_operator, require_subject_reader
from tessera.api.session import (  # noqa: TCH001  FastAPI resolves Depends annotations at runtime
    SessionContext,
)
from tessera.memory import governance, persistent

#: The GDPR write plane: erase, rectify, consent. A verified operator with write authority.
router = APIRouter(tags=["memory"], dependencies=[Depends(require_operator)])

#: The GDPR read plane (Art. 15 access). Subject-scoped personal data, so every operator
#: role may read it — the auditor above all. Kept a separate router precisely so the read
#: is not silently swept into the writers' role set, nor the writes into the readers'.
read_router = APIRouter(tags=["memory"], dependencies=[Depends(require_subject_reader)])


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
async def erase_memory(
    conversation_id: uuid.UUID,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> Response:
    """Erase all stored memory *and telemetry* for a subject (GDPR Art. 17).

    Beyond the memory layers, this also purges the subject's captured replay
    bundles and online-eval scores, so the deletion reaches telemetry and not
    only the system of record (ADR 0010, #180).

    **The act names its author.** This is the most legally consequential operation in the
    system — an irreversible deletion of a person's record — and until this change the trail
    could not say who ordered it: the erasure event carried a subject and no actor, and the
    surface in front of it could not have supplied one anyway (``require_bearer`` names the
    frontend *service*, and a service is not a person). A right to erasure you cannot attribute
    is not a control; it is a deletion nobody answers for.

    The name is the principal of the server-verified operator assertion, read off the session
    the guard already resolved, and threaded into the canonical erasure rather than stamped by
    a second audit call here — one act, one entry. It cannot be supplied by the caller: no
    request model on this router has an actor field, and all of them are ``extra="forbid"``.
    """
    await governance.erase_subject(conversation_id, actor=actor_of(session))
    from tessera.observability.erasure import purge_telemetry

    purge_telemetry(str(conversation_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@read_router.get("/memory/{conversation_id}/items")
async def list_memory_items(
    conversation_id: uuid.UUID,
    session: Annotated[SessionContext, Depends(require_subject_reader)],
) -> MemoryItemsResponse:
    """List the memories held for a subject (GDPR Art. 15 access).

    A *read* of personal data is a governed act too, and it was the last one here without an
    author: the trail recorded whose record had been read and never who read it. Under Art. 15
    the subject may ask what is held about them; under Art. 5(2) they may also ask **who has
    been looking**. Reading is what the auditor role is FOR — which is exactly why the reader
    must be named, not exempted.
    """
    subject_id = str(conversation_id)
    stored = await persistent.list_subject_memories(subject_id)
    governance.audit_memory(
        action="memory.read",
        subject_id=subject_id,
        decision="allow",
        rationale=f"subject access request: {len(stored)} item(s)",
        actor=actor_of(session),
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
    session: Annotated[SessionContext, Depends(require_operator)],
) -> Response:
    """Rectify a stored memory's text (GDPR Art. 16). Re-screened and re-embedded."""
    subject_id = str(conversation_id)
    screened = governance.screen_memory(payload.text, actor=actor_of(session))
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
        rationale=f"rectification of memory {memory_id} (GDPR Art. 16)",
        actor=actor_of(session),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/memory/{conversation_id}/items/{memory_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_memory_item(
    conversation_id: uuid.UUID,
    memory_id: int,
    session: Annotated[SessionContext, Depends(require_operator)],
) -> Response:
    """Delete a single stored memory of a subject (GDPR Art. 17, granular)."""
    subject_id = str(conversation_id)
    deleted = await persistent.delete_memory(memory_id, subject_id=subject_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    governance.audit_memory(
        action="memory.forget",
        subject_id=subject_id,
        decision="allow",
        rationale=f"deletion of memory {memory_id} (GDPR Art. 17, granular)",
        actor=actor_of(session),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/memory/{conversation_id}/consent")
async def set_memory_consent(
    conversation_id: uuid.UUID,
    payload: Annotated[ConsentRequest, Body(...)],
    session: Annotated[SessionContext, Depends(require_operator)],
) -> ConsentResponse:
    """Grant or revoke long-term retention consent for a subject.

    Consent is the *lawful basis* for retaining this person's data, so flipping it is a
    governed act of the first order — and it wrote **no audit event at all**. The record simply
    changed, with no trace of who changed it or when. Revoking consent and then deleting on
    that basis, with neither step attributable, is the shape of an incident nobody can
    reconstruct afterwards.
    """
    subject_id = str(conversation_id)
    await governance.set_consent(subject_id, granted=payload.granted)
    governance.audit_memory(
        action="memory.write",
        subject_id=subject_id,
        decision="allow",
        rationale=f"long-term retention consent set to {payload.granted}",
        actor=actor_of(session),
    )
    return ConsentResponse(subject_id=subject_id, granted=payload.granted)
