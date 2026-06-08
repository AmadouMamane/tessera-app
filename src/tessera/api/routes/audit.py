"""Read-only audit-trail endpoint.

For the demo we expose the audit log via a thin filesystem-backed reader so
that the dashboard at ``webapp/frontend/app/audit/page.tsx`` has something
real to render. The production wiring queries Cloud Logging directly; the
schema returned by both readers is identical, defined here as
:class:`AuditEntry`.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TCH003  used at runtime in the file-backed reader
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tessera.guard.audit import verify_audit_chain

router = APIRouter(tags=["audit"])


class AuditEntry(BaseModel):
    """One audit-trail entry, identical in shape across sinks."""

    model_config = ConfigDict(extra="ignore")

    occurred_at: str
    target: str
    outcome: Literal["allowed", "denied", "error"]
    model: str | None = None
    arguments: dict[str, object] = Field(default_factory=dict)
    decisions: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None


class AuditPage(BaseModel):
    """Paged audit response."""

    model_config = ConfigDict(extra="forbid")

    entries: list[AuditEntry]
    cursor: int
    has_more: bool


class AuditIntegrity(BaseModel):
    """Tamper-evident hash-chain status of the audit log (ADR 0010, #3)."""

    model_config = ConfigDict(extra="forbid")

    verified: bool
    length: int
    broken_at: int | None = None


_PAGE_DEFAULT = 50
_PAGE_MAX = 500


def _resolve_audit_path() -> Path:
    from tessera.settings import get_settings

    return get_settings().guard.audit_file


def _read_entries(path: Path) -> list[AuditEntry]:
    if not path.exists():
        return []
    out: list[AuditEntry] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            try:
                out.append(AuditEntry(**payload))
            except (ValidationError, TypeError):
                continue
    return out


@router.get("/audit", response_model=AuditPage)
async def audit_list(
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_PAGE_MAX)] = _PAGE_DEFAULT,
    target: Annotated[str | None, Query()] = None,
    outcome: Annotated[Literal["allowed", "denied", "error"] | None, Query()] = None,
) -> AuditPage:
    """Return a paged slice of the audit log."""
    path = _resolve_audit_path()
    entries = _read_entries(path)
    entries.reverse()  # newest first — most recent activity at the top
    if target:
        entries = [e for e in entries if e.target == target]
    if outcome:
        entries = [e for e in entries if e.outcome == outcome]
    slice_ = entries[cursor : cursor + limit]
    return AuditPage(
        entries=slice_,
        cursor=cursor + len(slice_),
        has_more=(cursor + len(slice_)) < len(entries),
    )


@router.get("/audit/integrity", response_model=AuditIntegrity)
async def audit_integrity() -> AuditIntegrity:
    """Verify the audit log's tamper-evident hash chain."""
    status = verify_audit_chain(_resolve_audit_path())
    return AuditIntegrity(
        verified=status.verified, length=status.length, broken_at=status.broken_at
    )
