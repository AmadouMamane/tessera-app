"""Read-only audit-trail endpoint.

For the demo we expose the audit log via a thin filesystem-backed reader so
that the dashboard at ``webapp/frontend/app/audit/page.tsx`` has something
real to render. The production wiring queries Cloud Logging directly; the
schema returned by both readers is identical, defined here as
:class:`AuditEntry`.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TCH003  used at runtime in the file-backed reader
from threading import RLock
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tessera.guard.audit import verify_audit_chain

router = APIRouter(tags=["audit"])

type AuditOutcome = Literal["allowed", "denied", "error"]
type AuditEventType = Literal["guard", "tool", "memory", "other"]
type AuditActorRole = Literal["human", "service", "system", "model"]
type AuditMetricKey = Literal[
    "signed_events",
    "sensitive_actions",
    "guard_refusals",
    "proof_events",
    "chain_integrity",
    "unique_actors",
]


class AuditEntry(BaseModel):
    """One audit-trail entry, identical in shape across sinks."""

    model_config = ConfigDict(extra="ignore")

    occurred_at: str
    target: str
    outcome: AuditOutcome
    model: str | None = None
    arguments: dict[str, object] = Field(default_factory=dict)
    decisions: list[dict[str, object]] = Field(default_factory=list)
    error: str | None = None
    version: int | None = None
    data_residency: str | None = None
    prev_hash: str | None = None
    hash: str | None = None
    event_type: AuditEventType = "other"
    actor: str = "audit-log"
    actor_role: AuditActorRole = "system"
    scope: str = "global"
    object_label: str = "audit event"
    policy_rule: str | None = None
    proof_ref: str | None = None
    agent_id: str | None = None


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


class AuditCount(BaseModel):
    """A counted audit dimension used by the cockpit facets."""

    model_config = ConfigDict(extra="forbid")

    key: str
    count: int


class AuditMetric(BaseModel):
    """One summary metric for the audit cockpit."""

    model_config = ConfigDict(extra="forbid")

    key: AuditMetricKey
    value: int
    previous_value: int
    delta_pct: float | None = None


class AuditTimelineBucket(BaseModel):
    """One bucket in the audit chronology."""

    model_config = ConfigDict(extra="forbid")

    label: str
    start: str
    end: str
    total: int
    allowed: int
    denied: int
    error: int


class AuditProof(BaseModel):
    """Recent hash-chain proof material exposed to the dashboard."""

    model_config = ConfigDict(extra="forbid")

    occurred_at: str
    target: str
    outcome: AuditOutcome
    actor: str
    hash: str
    prev_hash: str | None = None


class AuditOverview(BaseModel):
    """Aggregated audit dashboard state, derived entirely from the audit endpoint data."""

    model_config = ConfigDict(extra="forbid")

    generated_at: str
    window_start: str
    window_end: str
    total_events: int
    chain_verified: bool
    chain_length: int
    chain_broken_at: int | None = None
    metrics: list[AuditMetric]
    timeline: list[AuditTimelineBucket]
    targets: list[AuditCount]
    outcomes: list[AuditCount]
    policies: list[AuditCount]
    actors: list[AuditCount]
    roles: list[AuditCount]
    scopes: list[AuditCount]
    event_types: list[AuditCount]
    recent_proofs: list[AuditProof]
    suggested_filters: list[AuditCount]


_PAGE_DEFAULT = 50
_PAGE_MAX = 500
_DEFAULT_WINDOW = timedelta(days=7)
_TIMELINE_BUCKETS = 8
_DAY_LABEL_THRESHOLD_SECONDS = 172_800
_RECENT_PROOF_LIMIT = 5
_METRIC_KEYS: tuple[AuditMetricKey, ...] = (
    "signed_events",
    "sensitive_actions",
    "guard_refusals",
    "proof_events",
    "chain_integrity",
    "unique_actors",
)


@dataclass(frozen=True, slots=True)
class _AuditFileState:
    path: str
    mtime_ns: int | None
    size: int | None


@dataclass(frozen=True, slots=True)
class _EntriesCache:
    state: _AuditFileState
    entries: list[AuditEntry]


@dataclass(frozen=True, slots=True)
class _IntegrityCache:
    state: _AuditFileState
    integrity: AuditIntegrity


_ENTRIES_CACHE_LOCK = RLock()
_INTEGRITY_CACHE_LOCK = RLock()
_ENTRIES_CACHE: _EntriesCache | None = None
_INTEGRITY_CACHE: _IntegrityCache | None = None


def _resolve_audit_path() -> Path:
    from tessera.settings import get_settings

    return get_settings().guard.audit_file


def _audit_file_state(path: Path) -> _AuditFileState:
    try:
        stat = path.stat()
    except OSError:
        return _AuditFileState(path=str(path), mtime_ns=None, size=None)
    return _AuditFileState(path=str(path), mtime_ns=stat.st_mtime_ns, size=stat.st_size)


def _first_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int | float | bool):
        return str(value)
    return None


def _decision_policy(decisions: list[dict[str, object]]) -> str | None:
    for decision in decisions:
        policy = _first_text(decision.get("policy_rule"))
        if policy:
            return policy
    return None


def _event_type(target: str) -> AuditEventType:
    if target == "user_input":
        return "guard"
    if target.startswith("memory."):
        return "memory"
    if target:
        return "tool"
    return "other"


def _actor_role(event_type: AuditEventType, outcome: AuditOutcome) -> AuditActorRole:
    if event_type == "guard" and outcome == "denied":
        return "human"
    if event_type in {"memory", "tool"}:
        return "service"
    return "system"


def _object_label(target: str, arguments: dict[str, object], policy_rule: str | None) -> str:
    for key in ("account_id", "ticket_id", "subject_id", "conversation_id", "trace_id"):
        text = _first_text(arguments.get(key))
        if text:
            return text
    if policy_rule:
        return policy_rule
    return target


def _entry_from_payload(payload: dict[str, object]) -> AuditEntry:
    target = _first_text(payload.get("target")) or "unknown"
    occurred_at = _first_text(payload.get("occurred_at")) or datetime.now(UTC).isoformat()
    raw_outcome = _first_text(payload.get("outcome"))
    if raw_outcome == "allowed":
        outcome: AuditOutcome = "allowed"
    elif raw_outcome == "denied":
        outcome = "denied"
    else:
        outcome = "error"
    decisions_raw = payload.get("decisions")
    decisions = decisions_raw if isinstance(decisions_raw, list) else []
    decision_maps = [cast(dict[str, object], d) for d in decisions if isinstance(d, dict)]
    arguments_raw = payload.get("arguments")
    arguments = cast(dict[str, object], arguments_raw) if isinstance(arguments_raw, dict) else {}
    event_type = _event_type(target)
    policy_rule = _decision_policy(decision_maps)
    model = _first_text(payload.get("model"))
    data_residency = _first_text(payload.get("data_residency"))
    hash_value = _first_text(payload.get("hash"))
    raw_version = payload.get("version")
    return AuditEntry(
        occurred_at=occurred_at,
        target=target,
        outcome=outcome,
        model=model,
        arguments=arguments,
        decisions=decision_maps,
        error=_first_text(payload.get("error")),
        version=raw_version if isinstance(raw_version, int) else None,
        data_residency=data_residency,
        prev_hash=_first_text(payload.get("prev_hash")),
        hash=hash_value,
        event_type=event_type,
        actor=model or target,
        actor_role=_actor_role(event_type, outcome),
        scope=data_residency or "local",
        object_label=_object_label(target, arguments, policy_rule),
        policy_rule=policy_rule,
        proof_ref=hash_value[:12] if hash_value else None,
        agent_id=_first_text(payload.get("agent_id")),
    )


def _read_entries_uncached(path: Path) -> list[AuditEntry]:
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
                out.append(_entry_from_payload(payload))
            except (ValidationError, TypeError):
                continue
    return out


def _read_entries(path: Path) -> list[AuditEntry]:
    global _ENTRIES_CACHE

    state = _audit_file_state(path)
    with _ENTRIES_CACHE_LOCK:
        if _ENTRIES_CACHE is not None and _ENTRIES_CACHE.state == state:
            return _ENTRIES_CACHE.entries
        entries = _read_entries_uncached(path)
        _ENTRIES_CACHE = _EntriesCache(state=state, entries=entries)
        return entries


def _audit_integrity(path: Path) -> AuditIntegrity:
    global _INTEGRITY_CACHE

    state = _audit_file_state(path)
    with _INTEGRITY_CACHE_LOCK:
        if _INTEGRITY_CACHE is not None and _INTEGRITY_CACHE.state == state:
            return _INTEGRITY_CACHE.integrity
        status = verify_audit_chain(path)
        integrity = AuditIntegrity(
            verified=status.verified,
            length=status.length,
            broken_at=status.broken_at,
        )
        _INTEGRITY_CACHE = _IntegrityCache(state=state, integrity=integrity)
        return integrity


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _entry_datetime(entry: AuditEntry) -> datetime | None:
    return _parse_datetime(entry.occurred_at)


def _within(entry: AuditEntry, since: datetime | None, until: datetime | None) -> bool:
    occurred = _entry_datetime(entry)
    if occurred is None:
        return False
    if since is not None and occurred < since:
        return False
    return not (until is not None and occurred > until)


def _matches_text(entry: AuditEntry, q: str) -> bool:
    needle = q.casefold()
    haystack = " ".join(
        [
            entry.occurred_at,
            entry.target,
            entry.outcome,
            entry.model or "",
            entry.actor,
            entry.actor_role,
            entry.scope,
            entry.object_label,
            entry.policy_rule or "",
            entry.proof_ref or "",
        ]
    ).casefold()
    return needle in haystack


def _filter_entries(
    entries: list[AuditEntry],
    *,
    target: str | None,
    outcome: AuditOutcome | None,
    event_type: AuditEventType | None,
    actor_role: AuditActorRole | None,
    scope: str | None,
    policy_rule: str | None,
    q: str | None,
    since: datetime | None,
    until: datetime | None,
    agent: str | None = None,
) -> list[AuditEntry]:
    filtered = [entry for entry in entries if _within(entry, since, until)]
    if agent and agent != "all":
        filtered = [entry for entry in filtered if entry.agent_id == agent]
    if target:
        filtered = [entry for entry in filtered if entry.target == target]
    if outcome:
        filtered = [entry for entry in filtered if entry.outcome == outcome]
    if event_type:
        filtered = [entry for entry in filtered if entry.event_type == event_type]
    if actor_role:
        filtered = [entry for entry in filtered if entry.actor_role == actor_role]
    if scope:
        filtered = [entry for entry in filtered if entry.scope == scope]
    if policy_rule:
        filtered = [entry for entry in filtered if entry.policy_rule == policy_rule]
    if q:
        filtered = [entry for entry in filtered if _matches_text(entry, q)]
    return filtered


def _newest_first(entries: list[AuditEntry]) -> list[AuditEntry]:
    return sorted(
        entries,
        key=lambda entry: _entry_datetime(entry) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def _count(items: list[str], limit: int = 10) -> list[AuditCount]:
    return [AuditCount(key=key, count=count) for key, count in Counter(items).most_common(limit)]


def _delta_pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _metric(key: AuditMetricKey, current: int, previous: int) -> AuditMetric:
    return AuditMetric(
        key=key,
        value=current,
        previous_value=previous,
        delta_pct=_delta_pct(current, previous),
    )


def _measure(entries: list[AuditEntry], integrity: AuditIntegrity) -> dict[AuditMetricKey, int]:
    signed = sum(1 for entry in entries if entry.hash)
    sensitive = sum(1 for entry in entries if entry.event_type in {"memory", "tool"})
    refusals = sum(1 for entry in entries if entry.outcome == "denied")
    actors = {entry.actor for entry in entries if entry.actor}
    return {
        "signed_events": len(entries),
        "sensitive_actions": sensitive,
        "guard_refusals": refusals,
        "proof_events": signed,
        "chain_integrity": int(integrity.verified),
        "unique_actors": len(actors),
    }


def _comparison_counts(
    current: list[AuditEntry],
    previous: list[AuditEntry],
    integrity: AuditIntegrity,
    start: datetime,
    end: datetime,
) -> tuple[dict[AuditMetricKey, int], dict[AuditMetricKey, int]]:
    if previous:
        return _measure(current, integrity), _measure(previous, integrity)

    midpoint = start + ((end - start) / 2)
    early = [
        entry
        for entry in current
        if (occurred := _entry_datetime(entry)) is not None and occurred < midpoint
    ]
    late = [
        entry
        for entry in current
        if (occurred := _entry_datetime(entry)) is not None and occurred >= midpoint
    ]
    return _measure(late, integrity), _measure(early, integrity)


def _window_bounds(
    entries: list[AuditEntry],
    since: datetime | None,
    until: datetime | None,
) -> tuple[datetime, datetime]:
    observed: list[datetime] = []
    for entry in entries:
        occurred = _entry_datetime(entry)
        if occurred is not None:
            observed.append(occurred)
    end = until if until is not None else (max(observed) if observed else datetime.now(UTC))
    start = since if since is not None else (end - _DEFAULT_WINDOW)
    if start >= end:
        start = end - _DEFAULT_WINDOW
    return start, end


def _timeline(
    entries: list[AuditEntry],
    start: datetime,
    end: datetime,
) -> list[AuditTimelineBucket]:
    span = max((end - start).total_seconds(), float(_TIMELINE_BUCKETS))
    bucket_seconds = span / _TIMELINE_BUCKETS
    totals = [0] * _TIMELINE_BUCKETS
    outcomes_by_bucket: list[Counter[AuditOutcome]] = [Counter() for _ in range(_TIMELINE_BUCKETS)]

    for entry in entries:
        occurred = _entry_datetime(entry)
        if occurred is None or occurred < start or occurred >= end:
            continue
        index = min(
            _TIMELINE_BUCKETS - 1,
            int((occurred - start).total_seconds() / bucket_seconds),
        )
        totals[index] += 1
        outcomes_by_bucket[index][entry.outcome] += 1

    buckets: list[AuditTimelineBucket] = []
    for index in range(_TIMELINE_BUCKETS):
        bucket_start = start + timedelta(seconds=bucket_seconds * index)
        bucket_end = start + timedelta(seconds=bucket_seconds * (index + 1))
        outcomes = outcomes_by_bucket[index]
        buckets.append(
            AuditTimelineBucket(
                label=bucket_start.strftime(
                    "%d/%m" if span > _DAY_LABEL_THRESHOLD_SECONDS else "%H:%M"
                ),
                start=bucket_start.isoformat(),
                end=bucket_end.isoformat(),
                total=totals[index],
                allowed=outcomes["allowed"],
                denied=outcomes["denied"],
                error=outcomes["error"],
            )
        )
    return buckets


def _recent_proofs(entries: list[AuditEntry]) -> list[AuditProof]:
    proofs: list[AuditProof] = []
    for entry in _newest_first(entries):
        if entry.hash is None:
            continue
        proofs.append(
            AuditProof(
                occurred_at=entry.occurred_at,
                target=entry.target,
                outcome=entry.outcome,
                actor=entry.actor,
                hash=entry.hash,
                prev_hash=entry.prev_hash,
            )
        )
        if len(proofs) == _RECENT_PROOF_LIMIT:
            break
    return proofs


def _build_overview(
    entries: list[AuditEntry],
    integrity: AuditIntegrity,
    *,
    since: datetime | None,
    until: datetime | None,
    target: str | None = None,
    outcome: AuditOutcome | None = None,
    event_type: AuditEventType | None = None,
    actor_role: AuditActorRole | None = None,
    scope: str | None = None,
    policy_rule: str | None = None,
    q: str | None = None,
    agent: str | None = None,
) -> AuditOverview:
    start, end = _window_bounds(entries, since, until)
    current = _filter_entries(
        entries,
        target=target,
        outcome=outcome,
        event_type=event_type,
        actor_role=actor_role,
        scope=scope,
        policy_rule=policy_rule,
        q=q,
        since=start,
        until=end,
        agent=agent,
    )
    duration = end - start
    previous = _filter_entries(
        entries,
        target=target,
        outcome=outcome,
        event_type=event_type,
        actor_role=actor_role,
        scope=scope,
        policy_rule=policy_rule,
        q=q,
        since=start - duration,
        until=start,
        agent=agent,
    )

    values = _measure(current, integrity)
    comparison_current, comparison_previous = _comparison_counts(
        current,
        previous,
        integrity,
        start,
        end,
    )

    metrics = [
        AuditMetric(
            key=key,
            value=values[key],
            previous_value=comparison_previous[key],
            delta_pct=_delta_pct(comparison_current[key], comparison_previous[key]),
        )
        for key in _METRIC_KEYS
    ]

    suggested = _count(
        [entry.target for entry in current]
        + [entry.policy_rule for entry in current if entry.policy_rule is not None],
        limit=5,
    )

    return AuditOverview(
        generated_at=datetime.now(UTC).isoformat(),
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        total_events=len(current),
        chain_verified=integrity.verified,
        chain_length=integrity.length,
        chain_broken_at=integrity.broken_at,
        metrics=metrics,
        timeline=_timeline(current, start, end),
        targets=_count([entry.target for entry in current]),
        outcomes=_count([entry.outcome for entry in current], limit=3),
        policies=_count([entry.policy_rule or "unknown" for entry in current]),
        actors=_count([entry.actor for entry in current]),
        roles=_count([entry.actor_role for entry in current], limit=4),
        scopes=_count([entry.scope for entry in current]),
        event_types=_count([entry.event_type for entry in current], limit=4),
        recent_proofs=_recent_proofs(current),
        suggested_filters=suggested,
    )


@router.get("/audit", response_model=AuditPage)
async def audit_list(
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_PAGE_MAX)] = _PAGE_DEFAULT,
    target: Annotated[str | None, Query()] = None,
    outcome: Annotated[AuditOutcome | None, Query()] = None,
    event_type: Annotated[AuditEventType | None, Query()] = None,
    actor_role: Annotated[AuditActorRole | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    policy_rule: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    since: Annotated[str | None, Query()] = None,
    until: Annotated[str | None, Query()] = None,
    agent: Annotated[str | None, Query()] = None,
) -> AuditPage:
    """Return a paged slice of the audit log."""
    path = _resolve_audit_path()
    entries = _filter_entries(
        _read_entries(path),
        target=target,
        outcome=outcome,
        event_type=event_type,
        actor_role=actor_role,
        scope=scope,
        policy_rule=policy_rule,
        q=q,
        since=_parse_datetime(since),
        until=_parse_datetime(until),
        agent=agent,
    )
    entries = _newest_first(entries)  # most recent activity at the top
    slice_ = entries[cursor : cursor + limit]
    return AuditPage(
        entries=slice_,
        cursor=cursor + len(slice_),
        has_more=(cursor + len(slice_)) < len(entries),
    )


@router.get("/audit/overview", response_model=AuditOverview)
async def audit_overview(
    target: Annotated[str | None, Query()] = None,
    outcome: Annotated[AuditOutcome | None, Query()] = None,
    event_type: Annotated[AuditEventType | None, Query()] = None,
    actor_role: Annotated[AuditActorRole | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    policy_rule: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    since: Annotated[str | None, Query()] = None,
    until: Annotated[str | None, Query()] = None,
    agent: Annotated[str | None, Query()] = None,
) -> AuditOverview:
    """Return aggregate audit cockpit data for the selected window."""
    path = _resolve_audit_path()
    integrity = _audit_integrity(path)
    return _build_overview(
        _read_entries(path),
        integrity,
        since=_parse_datetime(since),
        until=_parse_datetime(until),
        target=target,
        outcome=outcome,
        event_type=event_type,
        actor_role=actor_role,
        scope=scope,
        policy_rule=policy_rule,
        q=q,
        agent=agent,
    )


@router.get("/audit/integrity", response_model=AuditIntegrity)
async def audit_integrity() -> AuditIntegrity:
    """Verify the audit log's tamper-evident hash chain."""
    return _audit_integrity(_resolve_audit_path())
