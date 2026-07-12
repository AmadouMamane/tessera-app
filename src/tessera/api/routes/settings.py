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

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tessera.api.security import require_superadmin
from tessera.api.settings_store import get_synthesis_admin, set_synthesis_admin

router = APIRouter(prefix="/settings", tags=["settings"])


class SynthesisAdminFlag(BaseModel):
    """Whether the ``admin`` role may view the failure synthesis."""

    enabled: bool


@router.get("/synthesis-admin", response_model=SynthesisAdminFlag)
async def read_synthesis_admin() -> SynthesisAdminFlag:
    """Return the current admin-visibility grant for the synthesis."""
    return SynthesisAdminFlag(enabled=await get_synthesis_admin())


@router.put(
    "/synthesis-admin",
    response_model=SynthesisAdminFlag,
    dependencies=[Depends(require_superadmin)],
)
async def write_synthesis_admin(flag: SynthesisAdminFlag) -> SynthesisAdminFlag:
    """Grant or revoke admin visibility of the synthesis (superadmin action)."""
    return SynthesisAdminFlag(enabled=await set_synthesis_admin(enabled=flag.enabled))
