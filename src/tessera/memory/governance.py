"""Memory governance — the EU-banking differentiator (ADR 0007).

Long-term memory in a banking agent is not a neutral cache; it is regulated
personal data and a latent attack surface. This module is the single place that
enforces, on every long-term write and read:

* **Consent** — Tier 2 writes require an explicit per-subject consent flag.
* **Data minimisation** — raw secrets (card numbers, full IBANs) are never
  stored; they are masked before persistence.
* **Anti-poisoning** — a memory candidate is screened with the same injection
  guard as live user input, because a fact extracted from a malicious turn is a
  stored prompt-injection (OWASP LLM03). Memory is untrusted data on both write
  and read.
* **Audit** — every accepted or rejected memory action emits a record into the
  existing guard audit trail.
* **Retention** — a per-kind TTL bounds how long memory lives.

Erasure (GDPR Art. 17) is implemented by the persistent backend's ``forget``,
which deletes everything keyed to a subject; consent rows are cleared here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final, Literal

from psycopg import sql
from psycopg.rows import dict_row

from tessera.agent.state import GuardDecisionRecord
from tessera.guard.adapter import check_user_input
from tessera.guard.audit import emit_audit
from tessera.retrieval.store import get_pool
from tessera.settings import get_settings

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "ScreenResult",
    "audit_memory",
    "consent_allows",
    "delete_consent",
    "ensure_consent_schema",
    "erase_subject",
    "purge_posture",
    "screen_memory",
    "set_consent",
    "ttl_for",
]

_CONSENT_TABLE: Final[sql.Identifier] = sql.Identifier("memory_consent")

# Retention per memory kind (ADR 0007). Semantic facts about a customer outlive
# episodic incident summaries.
_TTL: Final[dict[str, timedelta]] = {
    "semantic": timedelta(days=365),
    "episodic": timedelta(days=90),
}

# Card-number-like runs (13-19 digits, optionally space/dash grouped).
_CARD_RE: Final = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Full IBAN — masked to country + last 4 on storage.
_IBAN_RE: Final = re.compile(r"\b([A-Z]{2}\d{2})(?:[ ]?[A-Z0-9]{2,4}){2,}([A-Z0-9]{4})\b")


def ttl_for(kind: str) -> timedelta:
    """Return the retention period for a memory ``kind``."""
    return _TTL.get(kind, timedelta(days=90))


def purge_posture() -> dict[str, object]:
    """Whether expired memories are physically purged, and how often.

    The single source of the purge decision, so the boot log line and the scheduler can
    never disagree — the same discipline as ``seal_posture`` and ``canary_posture``.

    Until this shipped, :func:`tessera.memory.persistent.purge_expired` had *no caller*:
    ``ttl_for`` bounded retention at read time while the rows themselves lived on in
    Postgres indefinitely. Retention was enforced in the view, not in the store — which is
    not retention at all under GDPR Art. 5(1)(e).

    Returns:
        ``purging`` (bool), ``interval_s`` (int) and the active memory ``backend``.
    """
    from tessera.settings import get_settings

    memory = get_settings().memory
    return {
        "purging": memory.purge_interval_s > 0,
        "interval_s": memory.purge_interval_s,
        "backend": memory.backend,
    }


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """Outcome of screening a memory candidate before it is written or shown."""

    allowed: bool
    text: str
    rationale: str


def _mask_secrets(text: str) -> tuple[str, bool]:
    """Mask card numbers and full IBANs; return ``(masked_text, did_mask)``."""
    masked = False

    def _mask_card(match: re.Match[str]) -> str:
        nonlocal masked
        masked = True
        digits = re.sub(r"\D", "", match.group(0))
        return f"[card ••••{digits[-4:]}]"

    def _mask_iban(match: re.Match[str]) -> str:
        nonlocal masked
        masked = True
        return f"[IBAN {match.group(1)}••••{match.group(2)}]"

    out = _CARD_RE.sub(_mask_card, text)
    out = _IBAN_RE.sub(_mask_iban, out)
    return out, masked


def screen_memory(text: str) -> ScreenResult:
    """Screen a memory candidate for injection content, then minimise PII.

    Rejects outright when the text matches an injection deny pattern (a poisoned
    memory must never be stored or shown). Otherwise masks card numbers and full
    IBANs and returns the minimised text.
    """
    check = check_user_input(text)
    if not check.allowed:
        return ScreenResult(allowed=False, text="", rationale="matched injection deny pattern")
    minimised, masked = _mask_secrets(check.sanitised_text)
    rationale = "ok (secrets masked)" if masked else "ok"
    return ScreenResult(allowed=True, text=minimised, rationale=rationale)


def audit_memory(
    *,
    action: Literal["memory.write", "memory.read", "memory.forget"],
    subject_id: str,
    decision: Literal["allow", "deny", "transform"],
    rationale: str,
) -> None:
    """Emit a memory action into the guard audit trail."""
    record = GuardDecisionRecord(
        target=action,
        decision=decision,
        policy_rule=f"{action}.governance",
        rationale=rationale,
    )
    emit_audit(
        target=action,
        arguments={"subject_id": subject_id},
        decisions=[record],
        sink=get_settings().guard.audit_sink,
        outcome="allowed" if decision != "deny" else "denied",
    )


# ---------------------------------------------------------------------------
# Consent (per subject)
# ---------------------------------------------------------------------------


async def ensure_consent_schema() -> None:
    """Create the consent table idempotently."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            subject_id text        PRIMARY KEY,
            granted    boolean     NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_CONSENT_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create)
        await conn.commit()


async def consent_allows(subject_id: str) -> bool:
    """Return whether long-term retention is permitted for ``subject_id``.

    An explicit row wins; absent one, the configured default applies
    (conservative ``False`` by default — no retention without consent).
    """
    query = sql.SQL("SELECT granted FROM {table} WHERE subject_id = %s;").format(
        table=_CONSENT_TABLE
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (subject_id,))
        row = await cur.fetchone()
    if row is None:
        return get_settings().memory.consent_default
    return bool(row["granted"])


async def set_consent(subject_id: str, *, granted: bool) -> None:
    """Grant or revoke long-term retention consent for ``subject_id``."""
    query = sql.SQL(
        """
        INSERT INTO {table} (subject_id, granted, updated_at)
        VALUES (%s, %s, now())
        ON CONFLICT (subject_id)
        DO UPDATE SET granted = EXCLUDED.granted, updated_at = now();
        """
    ).format(table=_CONSENT_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (subject_id, granted))
        await conn.commit()


async def delete_consent(subject_id: str) -> None:
    """Delete the consent row for ``subject_id`` (part of GDPR erasure)."""
    query = sql.SQL("DELETE FROM {table} WHERE subject_id = %s;").format(table=_CONSENT_TABLE)
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (subject_id,))
        await conn.commit()


async def erase_subject(conversation_id: UUID) -> None:
    """Erase every trace of a subject across all memory layers (GDPR Art. 17).

    This is the canonical erasure used by both the persistent backend's
    ``forget`` and the ``DELETE /memory`` endpoint, so a deletion is total
    regardless of which backend is configured. Imports are deferred to avoid an
    import cycle with the layers it deletes from.
    """
    from tessera.memory.persistent import delete_subject
    from tessera.memory.summary import delete_summary
    from tessera.memory.transcript import delete_transcript

    subject_id = str(conversation_id)
    await delete_subject(subject_id)
    await delete_summary(conversation_id)
    await delete_transcript(conversation_id)
    await delete_consent(subject_id)
    audit_memory(
        action="memory.forget",
        subject_id=subject_id,
        decision="allow",
        rationale="subject erasure (GDPR Art. 17)",
    )
