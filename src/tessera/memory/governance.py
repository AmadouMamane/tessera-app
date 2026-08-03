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

    from tessera.authz import Actor

__all__ = [
    "ErasureReceipt",
    "ScreenResult",
    "audit_memory",
    "consent_allows",
    "delete_consent",
    "ensure_consent_schema",
    "erase_subject",
    "purge_posture",
    "screen_memory",
    "set_consent",
    "subject_keys_for",
    "ttl_for",
]

_CONSENT_TABLE: Final[sql.Identifier] = sql.Identifier("memory_consent")


def _memory_table(table: sql.Identifier) -> sql.Composed:
    """Schema-qualify a memory table (ADR 0014), so no statement can fall through to `public`.

    The connection carries ``search_path = <schema>, public``, so a bare table name resolves to
    this environment's table *when it exists* and to ``public`` when it does not — silently, in
    both directions:

    * a **read** that falls through returns ANOTHER environment's rows, and in the deployed
      stack ``public`` IS production;
    * a **delete** that falls through erases them.

    One ``CREATE TABLE`` skipped in a migration is all it takes, and nothing raises.

    Naming the schema also makes the converse legible, which is the finding that produced this
    function: erasure reaches exactly this environment's rows and NO others. On 2026-08-01
    ``public`` held 1 357 memory rows over **138 distinct subjects**, last written 2026-06-24,
    outside every erasure path — while `DELETE /memory` returned success and the ledger recorded
    a total erasure. :mod:`tessera.memory.erasure_reach` measures that gap;
    ``scripts/purge_orphan_schema.py`` closes it as an operator act, because purging another
    environment's schema from inside this one is exactly what ADR 0014 forbids.
    """
    from tessera.settings import get_settings

    return sql.SQL("{schema}.{table}").format(
        schema=sql.Identifier(get_settings().pg_schema), table=table
    )


# Retention per memory kind (ADR 0007). Semantic facts about a customer outlive
# episodic incident summaries.
_TTL: Final[dict[str, timedelta]] = {
    "semantic": timedelta(days=365),
    "episodic": timedelta(days=90),
}

# Card-number-like runs (13-19 digits, optionally space/dash grouped).
_CARD_RE: Final = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Full IBAN — masked to country + last 4 on storage. Country code, check digits, then 11 to
# 30 more alphanumerics (Norway's 15 to Malta's 34), each optionally preceded by a space so
# the grouped form "FR76 3000 4000 0300 0012 3456 789" is one match rather than several.
#
# The previous pattern ended in a mandatory group of exactly four, which the grouped form
# does not have — it ends in three. It therefore stopped short, and worse, `_CARD_RE` ran
# FIRST and ate sixteen of the digits in the middle as a card number. An IBAN written the way
# every French bank statement writes it came out as "FR76 [card ••••0012] 3456 789": the
# customer's account number, unmasked at both ends, inside a string the audit trail recorded
# as PII-screened.
_IBAN_RE: Final = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")


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
        compact = match.group(0).replace(" ", "")
        return f"[IBAN {compact[:4]}••••{compact[-4:]}]"

    # IBAN first. The card pattern is the greedier of the two and does not know it is
    # standing in the middle of an account number; run it second and it only ever sees text
    # an IBAN has already declined.
    out = _IBAN_RE.sub(_mask_iban, text)
    out = _CARD_RE.sub(_mask_card, out)
    return out, masked


def screen_memory(text: str, *, actor: Actor) -> ScreenResult:
    """Screen a memory candidate for injection content, then minimise PII.

    Rejects outright when the text matches an injection deny pattern (a poisoned
    memory must never be stored or shown). Otherwise masks card numbers and full
    IBANs and returns the minimised text.
    """
    check = check_user_input(text, actor=actor)
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
    actor: Actor,
) -> None:
    """Emit a memory action into the guard audit trail — naming both people involved.

    ``subject_id`` says **whose** data was touched. ``actor`` says **who touched it**. Until
    2026-07-12 this function had only the first, so the trail could record that a subject's
    entire record had been erased and never record who ordered it — on the one operation where
    the GDPR itself demands the controller be able to demonstrate exactly that (Art. 5(2)
    accountability, Art. 30 records of processing). For a product whose thesis is the opposable
    audit trail, that is the most expensive sentence a DPO could read.

    Args:
        action: The memory action taken.
        subject_id: WHOSE data it touched — the data subject.
        decision: The guard's verdict.
        rationale: Why.
        actor: WHO touched it. **Required, no default** — see :class:`~tessera.authz.Actor`.
            Derive it from a verified session (:func:`tessera.api.security.actor_of`) or name
            the system task out loud (:meth:`~tessera.authz.Actor.system`). Never from a
            request body: a caller who can pick the name in the ledger can pin an erasure on
            someone else, which is not a record but a forgery with a hash.
    """
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
        actor=actor,
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
    ).format(table=_memory_table(_CONSENT_TABLE))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create)
        await conn.commit()


async def consent_allows(subject_id: str) -> bool:
    """Return whether long-term retention is permitted for ``subject_id``.

    An explicit row wins; absent one, the configured default applies
    (conservative ``False`` by default — no retention without consent).
    """
    query = sql.SQL("SELECT granted FROM {table} WHERE subject_id = %s;").format(
        table=_memory_table(_CONSENT_TABLE)
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
    ).format(table=_memory_table(_CONSENT_TABLE))
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (subject_id, granted))
        await conn.commit()


async def delete_consent(subject_id: str) -> int:
    """Delete the consent row for ``subject_id`` (part of GDPR erasure); return the row count."""
    query = sql.SQL("DELETE FROM {table} WHERE subject_id = %s;").format(
        table=_memory_table(_CONSENT_TABLE)
    )
    pool = get_pool()
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, (subject_id,))
        deleted = cur.rowcount or 0
        await conn.commit()
    return deleted


@dataclass(frozen=True, slots=True)
class ErasureReceipt:
    """What an erasure actually removed, per layer — the proof a 204 cannot carry.

    A deletion that touched nothing and a deletion that cleared a person's whole record are
    indistinguishable to an HTTP caller, and were indistinguishable in the audit trail too:
    both sealed ``memory.forget / allow``. The counts are what let a DPO replay the claim, and
    what let a regression be seen — an erasure silently reaching zero rows is the failure mode
    this receipt exists to expose.
    """

    #: The subject keys the erasure ran under — resolved, never assumed.
    subject_keys: tuple[str, ...]
    long_term: int = 0
    consent: int = 0
    summary: int = 0
    transcript: int = 0

    @property
    def total(self) -> int:
        """Rows removed across every layer."""
        return self.long_term + self.consent + self.summary + self.transcript

    def describe(self) -> str:
        """A one-line, stable rendering for the audit rationale."""
        keys = ",".join(self.subject_keys) or "<none>"
        return (
            f"subject erasure (GDPR Art. 17): keys={keys} "
            f"long_term={self.long_term} consent={self.consent} "
            f"summary={self.summary} transcript={self.transcript}"
        )


async def subject_keys_for(conversation_id: UUID) -> tuple[str, ...]:
    """Resolve every subject key a conversation's data could be stored under.

    The conversation id itself is always included: it is the key ``scope_for`` falls back to
    when there is no authenticated subject, so anonymous threads genuinely live under it. The
    keys recorded on the transcript are added because an authenticated turn is written under
    ``session.subject_id``, and *that* is the key long-term memory and consent actually use.

    Erasing under the union is the only complete answer, and it is safe: a key that owns no
    rows deletes none.
    """
    from tessera.memory.transcript import subject_ids_for

    keys = {str(conversation_id)}
    try:
        keys.update(await subject_ids_for(conversation_id))
    except Exception as exc:  # resolution must never silently NARROW the erasure
        import sys

        sys.stderr.write(
            f"tessera.memory.governance: could not resolve subject keys for "
            f"{conversation_id} ({exc}); erasing under the conversation id only\n"
        )
    return tuple(sorted(keys))


async def erase_subject(
    conversation_id: UUID, *, actor: Actor, subject_id: str | None = None
) -> ErasureReceipt:
    """Erase every trace of a subject across all memory layers (GDPR Art. 17).

    This is the canonical erasure used by both the persistent backend's ``forget`` and the
    ``DELETE /memory`` endpoint, so a deletion is total regardless of which backend is
    configured. Imports are deferred to avoid an import cycle with the layers it deletes from.

    **The key is resolved, not assumed, and that is the whole repair.** This function used to
    take ``str(conversation_id)`` as the subject key. The turn seam writes long-term memory
    under ``session.subject_id`` and only falls back to the conversation id when there is no
    subject — so for every authenticated customer the DELETE matched zero rows, returned 204,
    and sealed ``memory.forget / allow`` into an append-only chain over data that was still
    there. The same class of defect as the schema-scoped one closed on 2026-08-01, moved onto
    the identity axis. It is resolved from the transcript, which is the only table carrying
    both ids on one row (ADR 0040) — and it is read BEFORE the transcript is deleted, because
    the delete destroys the witness.

    Args:
        conversation_id: The conversation whose subject is to be erased.
        actor: WHO ordered it. **Required, no default.** The audit event is emitted **here**,
            at the canonical erasure — the one function every path goes through — so the actor
            is *threaded in* rather than stamped by a second call at the route. One act, one
            entry: a regulator reading two entries for one deletion would have to guess which
            is authoritative, and a caller-stamped second entry could disagree with the first.
        subject_id: A key the caller already holds (the backend protocol path has it on the
            scope). Added to the resolved set rather than replacing it — a caller that knows
            one key does not thereby know there are no others.

    Returns:
        An :class:`ErasureReceipt` naming the keys used and counting what each layer removed.
    """
    from tessera.memory.persistent import delete_subject
    from tessera.memory.summary import delete_summary
    from tessera.memory.transcript import delete_transcript

    keys = await subject_keys_for(conversation_id)
    if subject_id and subject_id not in keys:
        keys = tuple(sorted({*keys, subject_id}))

    long_term = 0
    consent = 0
    for key in keys:
        long_term += await delete_subject(key)
        consent += await delete_consent(key)
    summary = await delete_summary(conversation_id)
    transcript = await delete_transcript(conversation_id)

    receipt = ErasureReceipt(
        subject_keys=keys,
        long_term=long_term,
        consent=consent,
        summary=summary,
        transcript=transcript,
    )
    audit_memory(
        action="memory.forget",
        subject_id=str(conversation_id),
        decision="allow",
        rationale=receipt.describe(),
        actor=actor,
    )
    return receipt
