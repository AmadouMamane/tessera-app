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

from datetime import datetime  # noqa: TCH003  — pydantic resolves field annotations at runtime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from tessera.api.config_overrides import (
    BUDGET_OVERRUN_BEHAVIOURS,
    BUDGET_OVERRUN_KEY,
    DAILY_BUDGET_KEY,
    KnobError,
    Override,
    OverrideNotStoredError,
    agent_of_key,
    allowed_chat_models,
    base_chat_model,
    delete_override,
    knob_keys,
    list_overrides,
    set_override,
)
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


# ── operable knobs (ADR 0030) ────────────────────────────────────────────────


class OverrideOut(BaseModel):
    """One stored override, with the attribution the write recorded."""

    value: str
    author: str
    reason: str
    updated_at: datetime


class KnobOut(BaseModel):
    """One registry knob: its frozen base and its override, if any.

    ``kind`` names the knob family so the UI binds the right control (a model
    select, a numeric EUR input, a closed behaviour select — never free text);
    ``options`` is the closed value list for enum knobs (ADR 0034).
    """

    key: str
    agent_id: str | None
    base: str
    kind: Literal["model", "budget_eur", "overrun"] = "model"
    options: list[str] | None = None
    override: OverrideOut | None


class OverridesPanel(BaseModel):
    """The whole closed registry, ready for the cockpit to render."""

    allowed_chat_models: list[str]
    knobs: list[KnobOut]


class OverrideBody(BaseModel):
    """The write body. ``extra="forbid"``: an author-naming field is a loud 422 (ADR 0024)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str
    reason: str


class RevertBody(BaseModel):
    """The revert body — a revert is a governed act too, so it carries its reason."""

    model_config = ConfigDict(extra="forbid")

    key: str
    reason: str


def _base_of(key: str) -> str:
    """The knob's frozen base, per family (ADR 0034) — the value a revert restores.

    Locale-neutral tokens for the budget knobs: "—" = no ceiling (the
    historical truth), "block" = the default overrun behaviour.
    """
    if key == DAILY_BUDGET_KEY:
        return "—"
    if key == BUDGET_OVERRUN_KEY:
        return "block"
    return base_chat_model()


def _knob_out(key: str, override: Override | None) -> KnobOut:
    # ADR 0034 — each knob family carries its own kind, base and value space.
    kind: Literal["model", "budget_eur", "overrun"] = "model"
    base = _base_of(key)
    options: list[str] | None = None
    if key == DAILY_BUDGET_KEY:
        kind = "budget_eur"
    elif key == BUDGET_OVERRUN_KEY:
        kind, options = "overrun", list(BUDGET_OVERRUN_BEHAVIOURS)
    return KnobOut(
        key=key,
        agent_id=agent_of_key(key),
        base=base,
        kind=kind,
        options=options,
        override=(
            OverrideOut(
                value=override.value,
                author=override.author,
                reason=override.reason,
                updated_at=override.updated_at,
            )
            if override is not None
            else None
        ),
    )


@router.get("/overrides", response_model=OverridesPanel)
async def read_overrides() -> OverridesPanel:
    """Return every operable knob with its base, override and allowed values.

    Read stays on the bearer floor: model ids and operator principals, no
    subject data. The registry is enumerated server-side so the UI can never
    invent a key.
    """
    stored = {o.key: o for o in await list_overrides()}
    return OverridesPanel(
        allowed_chat_models=sorted(allowed_chat_models()),
        knobs=[_knob_out(key, stored.get(key)) for key in knob_keys()],
    )


@router.put("/overrides", response_model=KnobOut)
async def write_override(
    body: OverrideBody,
    session: Annotated[SessionContext, Depends(require_superadmin)],
) -> KnobOut:
    """Set one governed override (superadmin action, ADR 0030).

    The key travels in the body, like the rule-state toggles — a fixed path, so
    the governance ratchet can drive it verbatim. The store validates against
    the closed registry (unknown knob / uncatalogued model → 422, never stored).
    The author is the verified assertion principal; the mandatory reason is
    recorded on the row *and* in the governance journal.
    """
    actor = actor_of(session)
    try:
        override = await set_override(
            body.key, body.value, author=actor.principal, reason=body.reason
        )
    except KnobError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    emit_governance_mutation(
        target=f"config_overrides.{body.key}",
        detail={"value": body.value, "base": _base_of(body.key), "reason": override.reason},
        actor=actor,
    )
    return _knob_out(body.key, override)


@router.post("/overrides/revert", response_model=KnobOut)
async def revert_override(
    body: RevertBody,
    session: Annotated[SessionContext, Depends(require_superadmin)],
) -> KnobOut:
    """Remove one override so the frozen base serves again (superadmin action).

    A revert is a governed act: it changes what the fleet serves, so it carries
    its reason and lands in the journal like the write did. Reverting a knob
    that holds no override is a 404 — "nothing changed" must never read as
    "change recorded".
    """
    if body.key not in knob_keys():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown knob {body.key!r} — the registry is closed (ADR 0030)",
        )
    if not body.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="a governed revert carries its reason (ADR 0024) — blank refused",
        )
    try:
        await delete_override(body.key)
    except OverrideNotStoredError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no override stored for {body.key!r}"
        ) from exc
    emit_governance_mutation(
        target=f"config_overrides.{body.key}",
        detail={"reverted": True, "base": _base_of(body.key), "reason": body.reason.strip()},
        actor=actor_of(session),
    )
    return _knob_out(body.key, None)
