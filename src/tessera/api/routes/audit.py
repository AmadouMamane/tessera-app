"""Read-only audit-trail endpoint.

For the demo we expose the audit log via a thin filesystem-backed reader so
that the dashboard at ``webapp/frontend/app/audit/page.tsx`` has something
real to render. The production wiring queries Cloud Logging directly; the
schema returned by both readers is identical, defined here as
:class:`AuditEntry`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TCH003  used at runtime in the file-backed reader
from threading import RLock
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tessera.authz import SYSTEM_ROLE
from tessera.guard.ledger_store import (
    active_ledger_tree_status,
    ledger_head_seq,
    ledger_source,
    read_ledger_entries,
)
from tessera.observability.read_snapshot import (
    SNAPSHOT_TTL_S,
    audit_overview_snapshot_key,
    audit_page_snapshot_key,
    read_snapshot,
)

router = APIRouter(tags=["audit"])

type AuditOutcome = Literal["allowed", "denied", "error"]
type AuditEventType = Literal["guard", "tool", "memory", "governance", "other"]
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
    # No default, on either. This is a RESPONSE model — naming the author is the whole point of
    # the ledger view — and ``actor: str = "audit-log"`` meant that an entry which reached this
    # model without an author was rendered as having been performed by a thing called
    # "audit-log". That is the same species of bug as ``"Julie Dubois"``: a plausible constant
    # standing where a person should be, invisible precisely because nothing ever hit it. The
    # resolver below always supplies a value — ``_UNRECORDED_ACTOR`` when the entry genuinely has
    # none — so the default was pure latent lie, and a latent lie is one refactor from a live one.
    actor: str
    actor_role: AuditActorRole
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
    """Tamper-evident hash-chain status of the audit log (ADR 0010, #3).

    TESS-LEDGER-001 — tree-aware: ``verified``/``content_integrity`` is the tamper-evidence
    guarantee (every row hashes correctly, no edit/deletion). ``linear`` is the separate
    total-order property; historical forks degrade ``linear`` WITHOUT touching content
    integrity (a fork is a tree, not a forgery). ``attested`` is True once an appended
    attestation entry has ratified the forks (point 4).
    """

    model_config = ConfigDict(extra="forbid")

    verified: bool  # back-compat alias of content_integrity (tamper-evidence)
    length: int
    broken_at: int | None = None
    content_integrity: bool = True
    linear: bool = True
    fork_count: int = 0
    orphan_count: int = 0
    attested: bool = False
    # Verification provenance — the badge must say SINCE WHEN, never just "verified". Content
    # integrity is now checked incrementally against a checkpoint (the ledger is append-only, so a
    # verified prefix stays verified); these three fields are what stop that from being an
    # assumption dressed as a proof. ``full_verified_at`` is when the WHOLE chain was last walked;
    # ``entries_since_full`` is how many entries were verified incrementally since. Null in file
    # mode, where every read walks the whole journal anyway.
    full_verified_at: str | None = None
    entries_since_full: int = 0
    checkpoint_used: bool = False
    # Hica external seal facet (ADR 0015 §Amendment 3 pt3 / §Correction 3c pt4). ``badge`` is the
    # register §9 opposability verdict, computed live from tree + seal — never stored (design note).
    seal_state: Literal["absent", "verified", "stale", "unverifiable", "divergent"] = "absent"
    seal_provider: str | None = None
    seal_qualified: bool = False
    sealed_at: str | None = None
    sealed_head: str | None = None
    badge: Literal[
        "non_scelle", "scelle_opposable", "scelle_non_qualifie", "integrite_partielle"
    ] = "integrite_partielle"


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

# Postgres mode has no file mtime/size to key on, so the promoted table was RE-READ and every
# payload RE-VALIDATED into an AuditEntry on every request — ~2 s of Pydantic over ~126 k rows that
# both the overview (polled every 15 s) and the default log page paid each call. The append-only
# chain's head (`max(seq)`) is a complete cache key: an unchanged head proves every row is
# byte-identical, so the whole validated list is safe to reuse until the head moves.
_PG_ENTRIES_CACHE_LOCK = RLock()
_PG_ENTRIES_CACHE: tuple[int, list[AuditEntry]] | None = None  # (head_seq, validated entries)

_OVERVIEW_CACHE_LOCK = RLock()
# (head_seq, {filter-key: AuditOverview}) — the ~1 s aggregation memoised per chain head.
_OVERVIEW_CACHE: tuple[int, dict[tuple[object, ...], AuditOverview]] | None = None


def reset_audit_entries_cache() -> None:
    """Drop the postgres validated-entries + overview memos (test isolation; no-op in file mode)."""
    global _PG_ENTRIES_CACHE, _OVERVIEW_CACHE
    with _PG_ENTRIES_CACHE_LOCK:
        _PG_ENTRIES_CACHE = None
    with _OVERVIEW_CACHE_LOCK:
        _OVERVIEW_CACHE = None


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


#: What the Journal shows when the entry never recorded an author (audit entry v2 and earlier).
#: The column used to fall back to ``model or target`` — so the cockpit displayed **the LLM's
#: model name** as the person who erased a customer's record. That is not an empty column, it is
#: a wrong one, and it is the shape of mistake that survives review precisely because it looks
#: populated. An act whose author was never written down says so, and the ``version`` beside it
#: says why.
_UNRECORDED_ACTOR = "auteur non enregistré"


def _actor_of_payload(
    payload: dict[str, object],
    *,
    is_governance: bool,
    event_type: AuditEventType,
    outcome: AuditOutcome,
) -> tuple[str, AuditActorRole]:
    """WHO performed the act, read from where the writer puts it: the entry's TOP level.

    Every S1 event — guard audit (v3+), hand-off, routing, lifecycle, invocation, seal — stamps
    ``actor`` at the top level. Keying the read on the *event type* (``tessera.agent.*``) rather
    than on the presence of the field is what made the Journal misread the GDPR erasure: the
    erasure's type is ``tessera.guard.audit``, so it took the ``else`` branch and rendered
    ``model or target`` — the LLM's model name, in the column headed "who did this". The name
    was in the entry all along; nobody looked at it.

    ``actor_role`` separates a person from a machine, which is the distinction a reader of an
    audit trail actually needs: ``system:`` principals (the guard, the retention purge, the
    reflector) acted on policy and cannot be asked what they were thinking; everything else is
    somebody who can. The old heuristic survives for entries that predate the field, and only
    for them — it *infers* a role from the event's shape, and inference is exactly what a
    recorded actor replaces.
    """
    recorded = _first_text(payload.get("actor"))
    if recorded:
        role = _first_text(payload.get("actor_role"))
        is_machine = role == SYSTEM_ROLE or recorded.startswith(f"{SYSTEM_ROLE}:")
        return recorded, "system" if is_machine else "human"
    if is_governance:
        # Governance events (routing/hand-off) have always carried "system" here; keep their
        # existing label untouched, so this change adds honesty where there was a lie and
        # changes nothing where there was not.
        return "système", "human"
    return _UNRECORDED_ACTOR, _actor_role(event_type, outcome)


def _object_label(target: str, arguments: dict[str, object], policy_rule: str | None) -> str:
    for key in ("account_id", "ticket_id", "subject_id", "conversation_id", "trace_id"):
        text = _first_text(arguments.get(key))
        if text:
            return text
    if policy_rule:
        return policy_rule
    return target


def _governance_label(kind: str, payload: dict[str, object]) -> str:
    """Readable object for a governance event — the agent acted on, not 'unknown'.

    A hand-off reads ``from → to``; every other governed action (routing, proposal,
    release, block, lineage deploy) reads the agent it concerns.
    """
    agent = _first_text(payload.get("agent_id")) or "?"
    if kind == "tessera.agent.handoff":
        src = _first_text(payload.get("from_agent")) or "?"
        dst = _first_text(payload.get("to_agent")) or agent
        return f"{src} → {dst}"
    return agent


def _entry_from_payload(payload: dict[str, object]) -> AuditEntry:
    # Governance events (agent routing / hand-offs / lifecycle) are S1 journal
    # entries with a `type` of "tessera.agent.*" and NO `target`. Without this they
    # fell through to target="unknown" → event_type="tool", so a governed routing
    # decision showed up in the Journal as an anonymous tool call. Detect them and
    # give them their own category + a real object label.
    event_kind = _first_text(payload.get("type")) or ""
    is_governance = event_kind.startswith("tessera.agent.")
    raw_target = _first_text(payload.get("target"))
    target = raw_target or (event_kind.removeprefix("tessera.") if is_governance else "unknown")
    occurred_at = _first_text(payload.get("occurred_at")) or datetime.now(UTC).isoformat()
    raw_outcome = _first_text(payload.get("outcome"))
    if raw_outcome == "allowed":
        outcome: AuditOutcome = "allowed"
    elif raw_outcome == "denied":
        outcome = "denied"
    elif is_governance and raw_outcome is None:
        # A governed action is a recorded decision, not an error: a block is a
        # denial, every other governance event an allowed/effected action.
        outcome = "denied" if event_kind.endswith(("release_blocked", "blocked")) else "allowed"
    else:
        outcome = "error"
    decisions_raw = payload.get("decisions")
    decisions = decisions_raw if isinstance(decisions_raw, list) else []
    decision_maps = [cast(dict[str, object], d) for d in decisions if isinstance(d, dict)]
    arguments_raw = payload.get("arguments")
    arguments = cast(dict[str, object], arguments_raw) if isinstance(arguments_raw, dict) else {}
    event_type: AuditEventType = (
        "governance" if is_governance else _event_type(raw_target or "unknown")
    )
    policy_rule = _decision_policy(decision_maps)
    model = _first_text(payload.get("model"))
    data_residency = _first_text(payload.get("data_residency"))
    hash_value = _first_text(payload.get("hash"))
    raw_version = payload.get("version")
    actor, actor_role = _actor_of_payload(
        payload, is_governance=is_governance, event_type=event_type, outcome=outcome
    )
    object_label = (
        _governance_label(event_kind, payload)
        if is_governance
        else _object_label(target, arguments, policy_rule)
    )
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
        actor=actor,
        actor_role=actor_role,
        scope=data_residency or "local",
        object_label=object_label,
        policy_rule=policy_rule,
        proof_ref=hash_value[:12] if hash_value else None,
        agent_id=_first_text(payload.get("agent_id")),
    )


def _read_entries_uncached(
    path: Path, *, since: datetime | None = None, until: datetime | None = None
) -> list[AuditEntry]:
    out: list[AuditEntry] = []
    for payload in read_ledger_entries(path, since=since, until=until):
        try:
            out.append(_entry_from_payload(payload))
        except (ValidationError, TypeError):
            # skip a payload that will not shape into an AuditEntry from the rendered VIEW;
            # tamper-detection is computed separately (the chain walk), so this cannot hide a
            # forged entry — best-effort display (0015)
            continue
    return out


def _read_entries(
    path: Path, *, since: datetime | None = None, until: datetime | None = None
) -> list[AuditEntry]:
    """Entries from the active source, optionally bounded to a time window.

    Both the full read and a windowed read are served from the head-cached, fully-validated chain
    (postgres): the ~2 s Pydantic validation of ~126 k payloads happens once per append, and a
    window is then a cheap Python filter over that cached list. ``AuditEntry.occurred_at`` derives
    from the same payload field the SQL ``occurred_at`` column does, so the filter reproduces the
    SQL window exactly — no per-request re-read.
    """
    global _ENTRIES_CACHE

    # Postgres has no file mtime/size to key on. The audit-log page sends a rolling 7-day window
    # (until=now) that changes every load, so an SQL-bounded windowed read here NEVER hit a cache
    # and paid the full ~2 s validation on every request (seconds more under the leader snapshot
    # cycle's DB contention). Filtering the head-cached full chain instead is fast and correct.
    if ledger_source() == "postgres":
        entries = _read_entries_full_cached()
        if since is None and until is None:
            return entries
        return [entry for entry in entries if _within(entry, since, until)]
    state = _audit_file_state(path)
    with _ENTRIES_CACHE_LOCK:
        if _ENTRIES_CACHE is not None and _ENTRIES_CACHE.state == state:
            return _ENTRIES_CACHE.entries
        entries = _read_entries_uncached(path)
        _ENTRIES_CACHE = _EntriesCache(state=state, entries=entries)
        return entries


def _read_entries_full_cached() -> list[AuditEntry]:
    """The whole validated chain (postgres), memoised on the append-only head ``max(seq)``.

    The underlying payload read is already head-cached; what this adds is caching the VALIDATION —
    mapping ~126 k payloads into ``AuditEntry`` — the ~2 s cost the overview and log page paid on
    every request. The head is read first as the key; if a row lands mid-read the
    freshly validated (newer) list is simply cached under the older key and re-validated once on the
    next request — never a stale entry served.
    """
    global _PG_ENTRIES_CACHE
    head = ledger_head_seq()
    with _PG_ENTRIES_CACHE_LOCK:
        cached = _PG_ENTRIES_CACHE
        if cached is not None and cached[0] == head:
            return cached[1]
        entries = _read_entries_uncached(_resolve_audit_path())
        _PG_ENTRIES_CACHE = (head, entries)
        return entries


def _safe_seal_status(path: Path) -> object:
    """The active seal facet, or an honest ``absent`` if the ledger read fails (never green)."""
    from tessera.guard.seal import SealStatus, active_ledger_seal_status

    try:
        return active_ledger_seal_status(path)
    except Exception:  # a read failure degrades to absent — it never fabricates a seal
        return SealStatus("absent", None, False, None, None, "seal status unavailable")


def _integrity_from_tree(
    status: object,
    seal: object | None = None,
    freshness: object | None = None,
) -> AuditIntegrity:
    """Lift the tree verdict + seal facet into the API model.

    ``verified`` = content integrity (tamper-evidence). ``badge`` is the register §9 opposability
    verdict, composed live from ``{content_integrity, linear, attested}`` and the seal — the single
    source of the badge (design note §6), never a stored string.

    ``freshness`` (a ``LedgerVerdict``) carries WHEN the whole chain was last walked. It is
    optional only because file mode has no checkpoint — there, every read walks the journal, so
    "since when" is "now" and the fields stay null rather than claiming a checkpoint that does
    not exist.
    """
    from tessera.guard.ledger_checkpoint import LedgerVerdict
    from tessera.guard.ledger_store import LedgerTreeStatus
    from tessera.guard.seal import SealStatus, seal_badge

    assert isinstance(status, LedgerTreeStatus)
    seal_status = (
        seal if isinstance(seal, SealStatus) else SealStatus("absent", None, False, None, None)
    )
    verdict = freshness if isinstance(freshness, LedgerVerdict) else None
    return AuditIntegrity(
        verified=status.content_integrity,
        length=status.length,
        broken_at=status.broken_at,
        content_integrity=status.content_integrity,
        linear=status.linear,
        fork_count=status.fork_count,
        orphan_count=status.orphan_count,
        attested=status.attested,
        full_verified_at=(
            verdict.full_verified_at.isoformat()
            if verdict is not None and verdict.full_verified_at is not None
            else None
        ),
        entries_since_full=verdict.entries_since_full if verdict is not None else 0,
        checkpoint_used=verdict.checkpoint_used if verdict is not None else False,
        seal_state=seal_status.state,
        seal_provider=seal_status.provider,
        seal_qualified=seal_status.qualified,
        sealed_at=seal_status.sealed_at,
        sealed_head=seal_status.sealed_head,
        badge=seal_badge(status, seal_status),
    )


def _audit_integrity(path: Path) -> AuditIntegrity:
    """The badge's verdict.

    Postgres mode verifies INCREMENTALLY: content integrity is checked only for rows above a
    persisted checkpoint (the append-only trigger makes a verified prefix permanently verified),
    while forks/orphans/length are recomputed exactly in SQL every time. Re-walking 25 634 rows
    per request cost 1.1 s and grew forever.
    """
    global _INTEGRITY_CACHE

    if ledger_source() == "postgres":
        from tessera.guard.ledger_checkpoint import verify_ledger_incremental

        verdict = verify_ledger_incremental()
        return _integrity_from_tree(verdict.tree, _safe_seal_status(path), verdict)
    state = _audit_file_state(path)
    with _INTEGRITY_CACHE_LOCK:
        if _INTEGRITY_CACHE is not None and _INTEGRITY_CACHE.state == state:
            return _INTEGRITY_CACHE.integrity
        integrity = _integrity_from_tree(active_ledger_tree_status(path), _safe_seal_status(path))
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
        # `and length` matters: an absent or empty journal has no break in it either, and
        # this field used to report integrity 1 over a chain that was never written. (Not
        # `integrity.attested` — on THIS model that name already means "an attestation entry
        # has ratified the forks", which is a different claim entirely.)
        "chain_integrity": int(integrity.verified and integrity.length > 0),
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


def _overview_cached(
    path: Path,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    target: str | None = None,
    outcome: AuditOutcome | None = None,
    event_type: AuditEventType | None = None,
    actor_role: AuditActorRole | None = None,
    scope: str | None = None,
    policy_rule: str | None = None,
    q: str | None = None,
    agent: str | None = None,
) -> AuditOverview:
    """The overview, memoised on the append-only chain head (postgres only).

    ``_build_overview`` aggregates the whole chain (~1 s over ~160 k entries — the 7-day window the
    audit-log page sends captures essentially all of it) and it was recomputed on every 15 s poll
    AND on every leader snapshot cycle. The head is a complete key (an unchanged ``max(seq)`` proves
    every row is byte-identical), so the aggregation now runs once per (head, window, filters). File
    mode has no head to key on, so it builds directly (the entries memo already covers dev/test).
    """

    def build() -> AuditOverview:
        return _build_overview(
            _read_entries(path),
            _audit_integrity(path),
            since=since,
            until=until,
            target=target,
            outcome=outcome,
            event_type=event_type,
            actor_role=actor_role,
            scope=scope,
            policy_rule=policy_rule,
            q=q,
            agent=agent,
        )

    if ledger_source() != "postgres":
        return build()

    global _OVERVIEW_CACHE
    head = ledger_head_seq()
    key: tuple[object, ...] = (
        since.isoformat() if since is not None else None,
        until.isoformat() if until is not None else None,
        target,
        outcome,
        event_type,
        actor_role,
        scope,
        policy_rule,
        q,
        agent,
    )
    with _OVERVIEW_CACHE_LOCK:
        cached = _OVERVIEW_CACHE
        if cached is not None and cached[0] == head and key in cached[1]:
            return cached[1][key]
    # Built OUTSIDE the lock: the ~1 s aggregation must not serialise every overview request behind
    # one build. A rare concurrent double-build at the same head is harmless (same result, cached).
    overview = build()
    with _OVERVIEW_CACHE_LOCK:
        cached = _OVERVIEW_CACHE
        if cached is None or cached[0] != head:
            _OVERVIEW_CACHE = (head, {key: overview})
        else:
            cached[1][key] = overview
    return overview


def compute_default_overview() -> dict[str, object]:
    """The unfiltered, full-window audit overview — the org-wide default the snapshot precomputes.

    Locale-independent (the overview carries no free text), so one snapshot entry serves every
    operator. Shared by the leader's snapshot writer and by the route's own miss fallback.
    """
    overview = _overview_cached(_resolve_audit_path())
    return overview.model_dump(mode="json")


def compute_default_page() -> dict[str, object]:
    """The newest default page of the audit log (no filters, cursor 0) — the snapshot's list."""
    entries = _newest_first(_read_entries(_resolve_audit_path()))
    slice_ = entries[:_PAGE_DEFAULT]
    page = AuditPage(entries=slice_, cursor=len(slice_), has_more=len(slice_) < len(entries))
    return page.model_dump(mode="json")


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
    # The default landing view (newest page, no filters) is the same for every operator and walks
    # the whole chain, so it is served from the leader's shared snapshot when fresh; any filter,
    # window or deeper page falls through to a live read.
    _filters = (target, outcome, event_type, actor_role, scope, policy_rule, q, since, until, agent)
    if cursor == 0 and limit == _PAGE_DEFAULT and all(f is None for f in _filters):
        snap = read_snapshot(audit_page_snapshot_key(), SNAPSHOT_TTL_S)
        if snap is not None:
            return AuditPage.model_validate(snap)
    path = _resolve_audit_path()
    since_at, until_at = _parse_datetime(since), _parse_datetime(until)
    entries = _filter_entries(
        # The window is applied in SQL (occurred_at index); the payload-shape filters below
        # still run in Python, over the bounded set rather than over the whole table.
        _read_entries(path, since=since_at, until=until_at),
        target=target,
        outcome=outcome,
        event_type=event_type,
        actor_role=actor_role,
        scope=scope,
        policy_rule=policy_rule,
        q=q,
        since=since_at,
        until=until_at,
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
    # The unfiltered org-wide overview is polled every 15 s and walks the whole chain; serve it from
    # the leader's shared snapshot when fresh, so it is computed once, not once per worker per poll.
    _filters = (target, outcome, event_type, actor_role, scope, policy_rule, q, since, until, agent)
    if all(f is None for f in _filters):
        snap = read_snapshot(audit_overview_snapshot_key(), SNAPSHOT_TTL_S)
        if snap is not None:
            return AuditOverview.model_validate(snap)
    # A windowed/filtered overview (the audit-log page's rolling 7-day view, polled every 15 s) is
    # memoised on the chain head, so the ~1 s aggregation runs once per (head, window, filters) —
    # not on every poll — and cannot pile up under the leader snapshot cycle's contention.
    return _overview_cached(
        _resolve_audit_path(),
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
async def audit_integrity(at: str | None = None) -> AuditIntegrity:
    """Verify the audit log's tamper-evident hash chain.

    The chain *verification* is a structural property of the whole log, so it always
    reflects the current state (you cannot meaningfully tamper-check "the log as it
    was at T"). The chain *length*, however, honours an as-of instant ``at`` when
    given: the append-only log's count at T is well-defined (entries recorded up to
    and including T), so the cockpit's audit-count signal reads "à T" like every
    other point-in-time signal instead of being pinned to the live total.
    """
    path = _resolve_audit_path()
    integrity = _audit_integrity(path)
    until = _parse_datetime(at)
    if until is None:
        return integrity
    if ledger_source() == "postgres":
        # Counted in SQL on the occurred_at index. This branch used to load every payload and
        # Pydantic-validate every row into an AuditEntry just to count them — and the overview
        # dashboard polls this endpoint WITH `at` every 15 seconds.
        from tessera.guard.ledger_store import ledger_length_as_of

        return integrity.model_copy(update={"length": ledger_length_as_of(until)})
    length = sum(1 for entry in _read_entries(path) if _within(entry, None, until))
    return integrity.model_copy(update={"length": length})
