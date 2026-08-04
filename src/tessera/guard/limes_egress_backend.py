"""The limes egress backend behind the guard's output leg (ADR 0049).

The outbound mirror of :mod:`tessera.guard.limes_backend` (which owns the inbound
injection leg). It carries the two outbound capabilities Tessera's regex guard did
not have, each a distinct limes detector under a distinct disposition:

* **secret block** (:func:`check_egress`, ``secrets-egress``). A credential — an
  AWS/Stripe/GitHub/Google/Slack key, a PEM private key, a JWT — in the answer never
  leaves. Tessera had *nothing* for this; the null control was the state of the art.
* **PII recall** (:func:`check_pii_egress`, ``pii-egress``, ADR 0049 §Amendment 1). A
  *second* pass, run on the answer the first-party regex guard has **already masked**,
  to catch a checksummed datum the regex missed — a Corsica NIR (whose ``2A``/``2B``
  letters break the regex's digit-only shapes), a PAN or IBAN whose grouping the regex
  pattern does not match. It masks the leftover; it does not own the display.

Detection is delegated to limes; Tessera keeps no second copy of the rules (ADR 0029).

Why each runs where it does:

* **The secret check runs on the RAW answer, before the regex guard.** The regex PII
  guard's broad IBAN shape can graze a substring *inside* a secret (``…ONLY0000…``
  reads as an ``LY`` IBAN) and mangle it, after which the secret rule no longer
  matches. So the secret check must see the answer before the regex touches it.
* **The PII recall runs on the MASKED answer, after the regex guard.** This is what
  makes it safe to add ``pii-egress`` (deferred in ADR 0049's first cut): the regex
  keeps ownership of the PCI last-four display and the harness cases (02/45) — those
  are masked *before* recall sees them, so recall never re-fires on ``XXXX XXXX XXXX
  6467`` (four digits, no PAN), ``FRXX XXXX 0123`` (no ``dd`` head), ``XXXX@XXXX`` (no
  TLD) or ``XXXX 78`` (two digits). Recall only ever masks what the regex *left
  behind*, to a shape-free ``[REDACTED:pii]``.

Disposition. A secret ``Deny`` blocks; a PII ``Deny`` redacts (the region is masked,
the answer stands). ``CannotSay`` (a detector that could not look) blocks on both legs
— fail-closed, exactly as the inbound leg. There is no redact leg for a secret: a
credential is never masked-around, it is withheld whole.

The dependency runs one way only: Tessera imports limes, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from limes.detectors.pii_egress import PiiEgressDetector
from limes.detectors.secrets_egress import SecretsEgressDetector
from limes.transports.in_process import Egress, Guard
from limes.transports.redaction import Action, EgressPolicy, OnEgressFinding
from limes.verdict import CannotSay

__all__ = [
    "EgressOutcome",
    "PiiEgressOutcome",
    "check_egress",
    "check_pii_egress",
    "contains_secret",
    "egress_witness",
    "pii_egress_witness",
]

#: Fail-closed secret disposition, shared by every secrets-egress guard here.
_SECRET_EGRESS_POLICY: Final = EgressPolicy(
    default=OnEgressFinding.BLOCK,
    by_kind={"secret": OnEgressFinding.BLOCK},
)


# ---------------------------------------------------------------------------
# secrets-egress — a credential in the answer is withheld whole (block)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EgressOutcome:
    """The guard-facing result of one limes secret-egress check.

    Attributes:
        blocked: ``True`` when a secret fired or the detector could not look
            (``CannotSay``); the answer must be withheld, never sent.
        rule: The ``policy_rule`` recorded on the guard decision / audit entry.
        rationale: Human-readable reason, carrying limes' own text.
        policy_hash: SHA-256 of the limes egress policy the detector ran under.
    """

    blocked: bool
    rule: str
    rationale: str
    policy_hash: str


@lru_cache(maxsize=1)
def _secret_detector() -> SecretsEgressDetector:
    """The process-wide secrets-egress detector (its policy is loaded once)."""
    return SecretsEgressDetector()


@lru_cache(maxsize=1)
def _policy_hash() -> str:
    """SHA-256 of the packaged limes egress policy the secret detector runs under."""
    return _secret_detector().policy_hash


@lru_cache(maxsize=1)
def _guard() -> Guard:
    """Return the process-wide limes secret-egress guard (detector + block once)."""
    det = _secret_detector()
    return Guard([det], policy_hash=det.policy_hash, egress=_SECRET_EGRESS_POLICY)


def egress_witness() -> tuple[str, str]:
    """Return ``(id, version)`` of the live secret-egress detector.

    Proves that limes — not a fallback — produced an egress decision.
    """
    det = _secret_detector()
    return det.id, det.version


def contains_secret(text: str, *, observed_at: str, actor: str | None = None) -> bool:
    """True when limes' secrets-egress finds a credential in ``text`` (detection only).

    The lightweight check :class:`~tessera.guard.redaction.StreamingRedactor` runs
    before emitting a segment, so a secret is caught token-by-token and its characters
    never reach the wire (ADR 0049 §Amendment 1, the SSE pre-emption). It uses a
    **fresh ledger per call**: the streaming leg is not the leg of record — the post-hoc
    :func:`check_egress` is — so a per-token check must not append to a shared chain.

    Only a genuine secret ``Deny`` returns ``True``; a ``CannotSay`` does not. A single
    streamed segment is tiny (never over limes' budget), so the blind spot the
    fail-closed disposition guards against can only be raised meaningfully by the
    whole-answer post-hoc check, not by freezing the stream on a fragment.

    Args:
        text: The candidate segment about to be emitted.
        observed_at: ISO-8601 timestamp, recorded into limes' evidence.
        actor: The session's asserted identity (``None`` when anonymous).

    Returns:
        ``True`` when a credential is present; the caller withholds the segment.
    """
    from limes.record import Ledger

    det = _secret_detector()
    guard = Guard([det], policy_hash=det.policy_hash, ledger=Ledger(), egress=_SECRET_EGRESS_POLICY)
    egress = guard.check_egress(text, actor=actor, observed_at=observed_at)
    return egress.action is Action.BLOCK and not isinstance(egress.verdict, CannotSay)


def _outcome(egress: Egress, policy_hash: str) -> EgressOutcome:
    """Map a limes :class:`Egress` to the guard-facing :class:`EgressOutcome`."""
    if egress.action is not Action.BLOCK:
        return EgressOutcome(
            blocked=False,
            rule="egress.limes.allow",
            rationale="limes secret-egress ran and found no credential to block",
            policy_hash=policy_hash,
        )
    if isinstance(egress.verdict, CannotSay):
        return EgressOutcome(
            blocked=True,
            rule="egress.limes.cannot_say",
            rationale=(
                f"limes secret-egress could not see: {egress.reason} "
                "(fail-closed — a blind spot is refused, never passed)"
            ),
            policy_hash=policy_hash,
        )
    return EgressOutcome(
        blocked=True,
        rule="egress.limes.secret.block",
        rationale=f"limes secret-egress blocked the response: {egress.reason}",
        policy_hash=policy_hash,
    )


def check_egress(
    text: str,
    *,
    observed_at: str,
    actor: str | None = None,
    locale: str | None = None,
) -> EgressOutcome:
    """Run the limes secret-egress detector over ``text`` and map the disposition.

    Args:
        text: The outbound content about to reach the user (the RAW final answer,
            before the first-party regex guard, ADR 0049).
        observed_at: ISO-8601 timestamp supplied by the caller (Tessera), never
            ``now()`` inside limes — the decision chain must re-derive on replay.
        actor: The session's asserted identity (``None`` when anonymous); limes
            records it in context.
        locale: Optional locale hint for the content.

    Returns:
        An :class:`EgressOutcome`. ``blocked`` maps a secret ``Deny`` and a
        ``CannotSay`` (fail-closed); the caller withholds the answer on a block.
    """
    egress = _guard().check_egress(text, actor=actor, observed_at=observed_at, locale=locale)
    return _outcome(egress, _policy_hash())


# ---------------------------------------------------------------------------
# pii-egress — a recall pass on the already-masked answer (redact, ADR 0049 §Am.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PiiEgressOutcome:
    """The guard-facing result of one limes pii-egress *recall* check.

    Attributes:
        action: ``"forward"`` (no PII the regex missed), ``"redact"`` (leftover PII
            masked to ``[REDACTED:pii]``) or ``"block"`` (the detector could not
            look — fail-closed).
        content: The masked text for ``redact``; the input text unchanged for
            ``forward``; ``None`` for ``block``.
        redactions: One shape-free label per masked region (``"pii=[REDACTED:pii]"``),
            never the masked value.
        rule: The ``policy_rule`` recorded on the guard decision / audit entry.
        rationale: Human-readable reason, carrying limes' own text.
        policy_hash: SHA-256 of the limes egress policy the detector ran under.
    """

    action: str
    content: str | None
    redactions: tuple[str, ...]
    rule: str
    rationale: str
    policy_hash: str

    @property
    def redacted(self) -> bool:
        """Whether leftover PII was masked."""
        return self.action == "redact"

    @property
    def blocked(self) -> bool:
        """Whether the recall detector could not look (fail-closed)."""
        return self.action == "block"


@lru_cache(maxsize=1)
def _pii_policy_hash() -> str:
    """SHA-256 of the packaged limes egress policy the pii detector runs under."""
    return PiiEgressDetector().policy_hash


@lru_cache(maxsize=1)
def _pii_guard() -> Guard:
    """Return the process-wide limes pii-egress recall guard (detect + redact)."""
    pii = PiiEgressDetector()
    return Guard(
        [pii],
        policy_hash=pii.policy_hash,
        egress=EgressPolicy(
            default=OnEgressFinding.REDACT,
            by_kind={"pii": OnEgressFinding.REDACT},
        ),
    )


def pii_egress_witness() -> tuple[str, str]:
    """Return ``(id, version)`` of the live pii-egress detector.

    Proves that limes — not a fallback — produced the recall decision.
    """
    pii = PiiEgressDetector()
    return pii.id, pii.version


def _pii_outcome(egress: Egress, policy_hash: str) -> PiiEgressOutcome:
    """Map a limes pii-egress :class:`Egress` to :class:`PiiEgressOutcome`."""
    if egress.action is Action.FORWARD:
        return PiiEgressOutcome(
            action="forward",
            content=egress.content,
            redactions=(),
            rule="egress.limes.pii.allow",
            rationale="limes pii-egress recall ran and found no PII the regex missed",
            policy_hash=policy_hash,
        )
    if egress.action is Action.REDACT:
        plan = egress.redaction
        redactions = (
            tuple(f"pii={masking.token}" for masking in plan.maskings) if plan is not None else ()
        )
        return PiiEgressOutcome(
            action="redact",
            content=egress.content,
            redactions=redactions,
            rule="egress.limes.pii.redact",
            rationale=f"limes pii-egress recall masked PII the regex missed: {egress.reason}",
            policy_hash=policy_hash,
        )
    # BLOCK — a recall over already-masked text only blocks when the detector could
    # not look (``CannotSay``: content over the 200k budget, or non-UTF-8). Fail-closed:
    # a blind spot is refused, never passed. The regex guard already masked what it saw.
    return PiiEgressOutcome(
        action="block",
        content=None,
        redactions=(),
        rule="egress.limes.pii.cannot_say",
        rationale=(
            f"limes pii-egress recall could not see: {egress.reason} "
            "(fail-closed — a blind spot is refused, never passed)"
        ),
        policy_hash=policy_hash,
    )


def check_pii_egress(
    text: str,
    *,
    observed_at: str,
    actor: str | None = None,
    locale: str | None = None,
) -> PiiEgressOutcome:
    """Run limes' ``pii-egress`` over the ALREADY-masked answer (ADR 0049 §Amendment 1).

    A recall pass: the first-party regex guard has already masked what it recognises,
    keeping the PCI last-four display; this catches the tail it missed (a checksummed
    NIR/PAN/IBAN whose shape the regex's patterns do not match) and masks it to a
    shape-free ``[REDACTED:pii]``. It never re-fires on the regex's own masks.

    Args:
        text: The answer *after* the first-party regex guard (``apply_output_guard``
            / ``StreamingRedactor``), never before — that ordering is what keeps the
            display and the harness intact.
        observed_at: ISO-8601 timestamp supplied by the caller, never ``now()`` inside
            limes — the decision chain must re-derive on replay.
        actor: The session's asserted identity (``None`` when anonymous).
        locale: Optional locale hint.

    Returns:
        A :class:`PiiEgressOutcome`: ``redact`` with the further-masked content, or
        ``forward`` unchanged, or ``block`` (fail-closed) when the detector was blind.
    """
    egress = _pii_guard().check_egress(text, actor=actor, observed_at=observed_at, locale=locale)
    return _pii_outcome(egress, _pii_policy_hash())
