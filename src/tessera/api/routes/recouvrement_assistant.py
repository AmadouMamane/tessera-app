"""Structured backend endpoint for the Recouvrement assistant workflow v1.

Audit 2026-07-12, **P0 F-1**: these two POSTs were mounted with no dependency at all —
the exact class closed on 2026-07-11 for the 26 cockpit mutations, missed here because
this router never went through the god-router split that put the guard on
``observability/mutations.py``. Both routes write: the message workflow emits ~30
business events per turn into the ledger, and the action route executes governed
artifact transitions. Worse, ``requested_by`` — the name the ledger records as having
acted — was a **body field with a default**, so the audit attribution was whatever the
caller typed (or "Julie Dubois" if they typed nothing).

Same remedy as the cockpit, same shape: the guard is declared HERE on the router, not at
the mount site, so a route added to this module inherits it by construction. The role
set is the business plane's (``COLLECTIONS_MUTATION_ROLES``): ``collections`` — the role
this console exists for — acts, the ``auditor`` reads and does not write, an anonymous
caller is refused before the body is parsed. ``requested_by`` now derives from the
verified operator assertion (the guard returns it), never from the body.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from tessera.agent.recouvrement import (
    DEFAULT_SURFACE,
    RecouvrementArtifact,
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)
from tessera.api.security import require_collections_operator
from tessera.api.session import (
    SessionContext,  # noqa: TCH001  — FastAPI resolves Annotated at runtime
)

#: Every route in this module writes (ledger events, governed transitions), so every
#: route requires a verified business-plane operator. Declared on the router, not
#: per-route — the ``observability/mutations.py`` model: a new route cannot forget it.
router = APIRouter(
    tags=["recouvrement-assistant"],
    dependencies=[Depends(require_collections_operator)],
)


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
    # NOTE ``requested_by`` is gone deliberately (audit 2026-07-12, P0 F-1): the ledger
    # attribution comes from the verified operator assertion, and ``extra="forbid"``
    # makes a body that still tries to assert an identity a 422 — the spoof is a
    # contract violation, not a silently ignored field.
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
    session: Annotated[SessionContext, Depends(require_collections_operator)],
) -> dict[str, object]:
    """Run a governed action cycle for a Recouvrement artifact.

    Synchronous and store-backed like the message workflow above — same reason, same
    offload. The audit named only the message path; this one blocks identically.

    ``session`` is the router guard's own return value (FastAPI caches the dependency
    per-request — the guard runs once). ``requested_by`` is the verified principal from
    the signed assertion: the ledger records who *proved* they asked, not who the body
    *claimed* asked. The ``or "operator"`` narrowing is the invoke-route idiom and is
    unreachable in practice — a verified assertion always carries a non-empty principal.
    """
    return dict(
        await run_in_threadpool(
            run_recouvrement_action_workflow_v1,
            case_id=payload.case_id,
            artifact=_artifact_from_request(payload.artifact),
            action_name=payload.action_name,
            requested_by=session.subject_id or "operator",
            conversation_id=payload.conversation_id,
            turn_id=payload.turn_id,
            surface=payload.surface,
        )
    )
