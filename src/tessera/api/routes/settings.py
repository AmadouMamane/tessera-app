"""Runtime application-settings endpoints (read + write superadmin grants).

The write **carries its own role check** (audit 2026-07-12, **P1 F-5**). It did not, and
this docstring used to explain why not: *"These endpoints carry no role check of their own —
the service is reached only through the trusted front (BFF), which holds the bearer token
and enforces who may write."* That is the finding, written down as a design.

Two things were wrong with it. The bearer authenticates the frontend **service**, not the
human behind the call — the BFF attaches it on any caller's behalf (``security.py``,
``require_operator``). And "reached only through the trusted front" is an assumption about
the network, not a property the agent enforces: nothing stopped a direct call. So the rule
"only the superadmin may flip this" existed solely in ``app/api/settings/synthesis-access/
route.ts`` — in the browser's own BFF, which is where friendly refusals live, never
authority.

The grant is now gated on the signed operator assertion, by
:func:`~tessera.api.security.require_superadmin` — and on the superadmin specifically, not
merely on a writer: the flag decides whether an ``admin`` may see the synthesis, so an
``admin`` must not be able to grant it to itself. See ADR 0009 (roles) and ADR 0010
(assertion).

The read stays on the bearer floor: it returns one boolean, no subject data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from tessera.api.security import actor_of, require_superadmin
from tessera.api.session import (  # noqa: TCH001  — FastAPI resolves Depends annotations at runtime
    SessionContext,
)
from tessera.api.settings_store import get_synthesis_admin, set_synthesis_admin
from tessera.guard.audit import emit_governance_mutation

router = APIRouter(prefix="/settings", tags=["settings"])


class SynthesisAdminFlag(BaseModel):
    """Whether the ``admin`` role may view the failure synthesis.

    ``extra="forbid"``, and the reason is not hygiene. This model is bound to the **request
    body** of the grant below, so any field it tolerates is a field a caller can send. A body
    that tries to name an author now gets a loud 422 instead of a silently ignored forgery —
    the same closure as ``_CurationDecisionBody`` (ADR 0024).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool


@router.get("/synthesis-admin", response_model=SynthesisAdminFlag)
async def read_synthesis_admin() -> SynthesisAdminFlag:
    """Return the current admin-visibility grant for the synthesis."""
    return SynthesisAdminFlag(enabled=await get_synthesis_admin())


@router.put("/synthesis-admin", response_model=SynthesisAdminFlag)
async def write_synthesis_admin(
    flag: SynthesisAdminFlag,
    session: Annotated[SessionContext, Depends(require_superadmin)],
) -> SynthesisAdminFlag:
    """Grant or revoke admin visibility of the synthesis (superadmin action).

    **This is a privilege grant, and it left no trace** (ADR 0024 §Owed). It decides whether the
    ``admin`` role may read the failure synthesis — which is why only a superadmin may flip it,
    so an admin cannot grant it to itself. The authority check was in place; the *record* was
    not. Nothing in the chain said the grant had ever been made, and nothing said by whom, so
    the one control standing between ``admin`` and that data could be opened and closed with no
    residue. A privilege that can be granted invisibly is a privilege nobody can audit.

    The guard moved from ``dependencies=[...]`` into the signature on purpose: as a *dependency*
    it proved a superadmin was there and handed back **nothing**, so the handler had no way to
    say who. As a *parameter* it returns the verified ``SessionContext``, and ``actor_of`` turns
    it into the one name the caller could not have chosen. FastAPI caches it per-request — the
    guard still runs exactly once.
    """
    emit_governance_mutation(
        target="settings.synthesis_admin",
        detail={"enabled": flag.enabled},
        actor=actor_of(session),
    )
    return SynthesisAdminFlag(enabled=await set_synthesis_admin(enabled=flag.enabled))
