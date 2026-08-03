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

**The subject is RESOLVED, never assumed.** These routes are addressed by conversation id, and
every one of them used to derive the storage key as ``str(conversation_id)``. That is only the
key when there is no authenticated subject: the turn seam writes long-term memory and consent
under ``session.subject_id`` and falls back to the conversation id otherwise (ADR 0007,
"Identity"). So for every authenticated customer the access request returned nothing, the
rectification found nothing, the consent flag was written where the reflector does not read it,
and the erasure deleted nothing while sealing a success. The key now comes from
:func:`~tessera.memory.governance.subject_keys_for`, which asks the transcript — the only table
carrying both ids on one row (ADR 0040).
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


async def _subject_keys(conversation_id: uuid.UUID) -> tuple[str, ...]:
    """Every storage key this conversation's personal data can live under.

    Always includes the conversation id (the anonymous fallback) plus whatever the transcript
    recorded. Resolution is the difference between a right that works and a 204 that lies.
    """
    return await governance.subject_keys_for(conversation_id)


def _primary_subject(keys: tuple[str, ...], conversation_id: uuid.UUID) -> str:
    """The key to *report* — a real subject when one exists, else the conversation id.

    A response that echoes the conversation id for an authenticated customer tells the reader
    the record is keyed by thread, which is exactly the belief that hid the erasure defect.
    """
    fallback = str(conversation_id)
    return next((key for key in keys if key != fallback), fallback)


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

    **The erasure now reaches an external engine too.** When the org runs one of the optional
    adapters (langmem / mem0 / zep), the facts live outside Postgres, and nothing in ``src/``
    ever called :meth:`MemoryBackend.forget` — so clearing the native tables (usually empty in
    that configuration) returned 204 while the processor's copy survived. The protocol call is
    made only for external backends: routing it through a first-party one would re-enter the
    canonical erasure and write a second audit entry for a single act. A failure is recorded
    as a refusal, never smoothed over — an erasure that could not reach a processor must read
    as incomplete, not as done.
    """
    keys = await _subject_keys(conversation_id)
    receipt = await governance.erase_subject(conversation_id, actor=actor_of(session))
    await _forget_on_external_backend(
        conversation_id, subject_id=_primary_subject(keys, conversation_id), session=session
    )
    from tessera.observability.erasure import purge_telemetry

    purge_telemetry(str(conversation_id))
    del receipt  # counted in the audit rationale; the HTTP contract stays 204 No Content
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _forget_on_external_backend(
    conversation_id: uuid.UUID, *, subject_id: str, session: SessionContext
) -> None:
    """Ask a non-first-party memory engine to forget the subject, and say so either way."""
    from tessera.memory import _FIRST_PARTY_TIERS, get_memory_backend, scope_for
    from tessera.settings import get_settings

    configured = get_settings().memory.backend
    if configured in _FIRST_PARTY_TIERS:
        return
    scope = scope_for(conversation_id, get_settings().default_language, subject_id=subject_id)
    try:
        await get_memory_backend().forget(scope=scope)
    except Exception as exc:  # a processor that refused must stay VISIBLE, never smoothed
        governance.audit_memory(
            action="memory.forget",
            subject_id=subject_id,
            decision="deny",
            rationale=f"external backend {configured!r} did not confirm erasure: {exc}",
            actor=actor_of(session),
        )
        return
    governance.audit_memory(
        action="memory.forget",
        subject_id=subject_id,
        decision="allow",
        rationale=f"external backend {configured!r} acknowledged erasure",
        actor=actor_of(session),
    )


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
    keys = await _subject_keys(conversation_id)
    subject_id = _primary_subject(keys, conversation_id)
    stored = [item for key in keys for item in await persistent.list_subject_memories(key)]
    governance.audit_memory(
        action="memory.read",
        subject_id=subject_id,
        decision="allow",
        rationale=f"subject access request: {len(stored)} item(s) over {len(keys)} key(s)",
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
    keys = await _subject_keys(conversation_id)
    subject_id = _primary_subject(keys, conversation_id)
    screened = governance.screen_memory(payload.text, actor=actor_of(session))
    if not screened.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="rejected")
    updated = False
    for key in keys:
        updated = await persistent.update_memory_text(memory_id, subject_id=key, text=screened.text)
        if updated:
            subject_id = key
            break
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
    keys = await _subject_keys(conversation_id)
    subject_id = _primary_subject(keys, conversation_id)
    deleted = False
    for key in keys:
        deleted = await persistent.delete_memory(memory_id, subject_id=key)
        if deleted:
            subject_id = key
            break
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

    Consent is written under **every** key this conversation resolves to, because it is the
    lawful basis for one person's data and the reflector checks it under the key it writes
    with. Setting it on the conversation id alone left the gate reading a row that was never
    written — a grant that granted nothing, and a revocation that revoked nothing.
    """
    keys = await _subject_keys(conversation_id)
    subject_id = _primary_subject(keys, conversation_id)
    for key in keys:
        await governance.set_consent(key, granted=payload.granted)
    governance.audit_memory(
        action="memory.write",
        subject_id=subject_id,
        decision="allow",
        rationale=(f"long-term retention consent set to {payload.granted} over {len(keys)} key(s)"),
        actor=actor_of(session),
    )
    return ConsentResponse(subject_id=subject_id, granted=payload.granted)
